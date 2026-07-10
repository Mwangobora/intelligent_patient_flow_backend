from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.checkins.models import CheckinToken, PatientCheckin
from common.exceptions import ConflictError, NotFoundError, ValidationError

from ._crypto import build_token_hash, generate_raw_token
from ._shared import (
    get_appointment,
    get_token,
    get_user,
    normalize_optional_text,
    validate_appointment_eligible_for_checkin,
)
from .checkin_service import create_appointment_checkin

DEFAULT_TOKEN_LIFETIME = timedelta(minutes=30)


@dataclass(frozen=True)
class IssuedCheckinToken:
    token: CheckinToken
    raw_token: str


def _validate_expires_at(*, created_at, expires_at) -> None:
    if expires_at <= created_at:
        raise ValidationError("expires_at must be greater than created_at.")


def _validate_token_usable(token: CheckinToken, *, now) -> None:
    if token.revoked_at is not None:
        raise ValidationError("Check-in token has been revoked.")
    if token.used_at is not None:
        raise ValidationError("Check-in token has already been used.")
    if now >= token.expires_at:
        raise ValidationError("Check-in token has expired.")


def _active_tokens_for_appointment(*, appointment):
    return CheckinToken.objects.select_for_update().filter(
        appointment=appointment,
        used_at__isnull=True,
        revoked_at__isnull=True,
    )


@transaction.atomic
def issue_checkin_token(*, appointment_id, expires_at=None, created_by_id=None) -> IssuedCheckinToken:
    appointment = get_appointment(appointment_id, for_update=True)
    created_by = get_user(created_by_id, field_label="Created by user", active_only=True) if created_by_id is not None else None
    validate_appointment_eligible_for_checkin(
        appointment=appointment,
        patient=appointment.patient,
        facility=appointment.facility,
    )

    now = timezone.now()
    token_expires_at = expires_at or (now + DEFAULT_TOKEN_LIFETIME)
    _validate_expires_at(created_at=now, expires_at=token_expires_at)

    for active_token in _active_tokens_for_appointment(appointment=appointment):
        if created_by is None:
            raise ValidationError("created_by is required when reissuing a token.")
        active_token.revoked_at = now
        active_token.revoked_by = created_by
        active_token.revocation_reason = "Reissued check-in token."
        active_token.save(update_fields=["revoked_at", "revoked_by", "revocation_reason"])

    raw_token = generate_raw_token()
    token_hash = build_token_hash(raw_token)
    try:
        token = CheckinToken.objects.create(
            appointment=appointment,
            token_hash=token_hash,
            expires_at=token_expires_at,
            created_by=created_by,
            created_at=now,
        )
    except IntegrityError as exc:
        raise ConflictError("Check-in token could not be issued because a conflicting token already exists.") from exc

    return IssuedCheckinToken(token=token, raw_token=raw_token)


@transaction.atomic
def revoke_checkin_token(*, token_id, revoked_by_id, revocation_reason: str, revoked_at=None) -> CheckinToken:
    token = get_token(token_id, for_update=True)
    revoked_by = get_user(revoked_by_id, field_label="Revoked by user", active_only=True)
    normalized_reason = normalize_optional_text(revocation_reason)
    if normalized_reason is None:
        raise ValidationError("revocation_reason is required.")
    if token.used_at is not None:
        raise ConflictError("Used check-in token cannot be revoked.")
    if token.revoked_at is not None:
        raise ConflictError("Check-in token is already revoked.")

    revoke_time = revoked_at or timezone.now()
    if revoke_time < token.created_at:
        raise ValidationError("revoked_at must be greater than or equal to created_at.")

    token.revoked_at = revoke_time
    token.revoked_by = revoked_by
    token.revocation_reason = normalized_reason
    try:
        token.save(update_fields=["revoked_at", "revoked_by", "revocation_reason"])
    except IntegrityError as exc:
        raise ConflictError("Check-in token could not be revoked because of a conflicting state.") from exc
    return token


@transaction.atomic
def consume_checkin_token(
    *,
    raw_token: str,
    checked_in_at=None,
    checked_in_by_id=None,
    notes: str | None = None,
) -> PatientCheckin:
    token_hash = build_token_hash(raw_token)
    token = CheckinToken.objects.select_for_update().filter(token_hash=token_hash).first()
    if token is None:
        raise NotFoundError("Valid check-in token not found.")

    now = timezone.now()
    _validate_token_usable(token, now=now)
    appointment = get_appointment(token.appointment_id, for_update=True)
    validate_appointment_eligible_for_checkin(
        appointment=appointment,
        patient=appointment.patient,
        facility=appointment.facility,
    )

    checkin = create_appointment_checkin(
        facility_id=appointment.facility_id,
        patient_id=appointment.patient_id,
        appointment_id=appointment.id,
        facility_specialty_id=appointment.facility_specialty_id,
        checkin_method=PatientCheckin.CheckinMethod.QR_CODE,
        checked_in_at=checked_in_at or now,
        checked_in_by_id=checked_in_by_id,
        notes=notes,
    )

    token.used_at = now
    token.patient_checkin = checkin
    try:
        token.save(update_fields=["used_at", "patient_checkin"])
    except IntegrityError as exc:
        raise ConflictError("Check-in token could not be consumed because of a conflicting state.") from exc
    return checkin
