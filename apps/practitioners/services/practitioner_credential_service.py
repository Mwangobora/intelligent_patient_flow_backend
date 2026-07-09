from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.practitioners.models import PractitionerCredential
from common.exceptions import ConflictError, NotFoundError, ValidationError

from ._crypto import build_value_hash, derive_last_four, encrypt_sensitive_value, normalize_credential_number_for_lookup
from ._shared import (
    get_practitioner,
    get_practitioner_credential,
    get_practitioner_credential_type,
    get_user,
    normalize_country_code,
    normalize_optional_text,
)


def _get_credential_for_update(credential_id) -> PractitionerCredential:
    try:
        return PractitionerCredential.objects.select_for_update().select_related(
            "practitioner",
            "practitioner__organization",
            "credential_type",
            "verified_by",
        ).get(pk=credential_id)
    except PractitionerCredential.DoesNotExist as exc:
        raise NotFoundError("Practitioner credential not found.") from exc


def _validate_credential_scope(*, practitioner, credential_type) -> None:
    if not practitioner.is_active:
        raise ValidationError("Practitioner must be active.")
    if not practitioner.organization.is_active:
        raise ValidationError("Practitioner organization must be active.")
    if not credential_type.is_active:
        raise ValidationError("Practitioner credential type must be active.")
    if credential_type.organization_id is not None and credential_type.organization_id != practitioner.organization_id:
        raise ValidationError("Credential type is outside practitioner organization.")


def _validate_credential_dates(*, credential_type, issued_on, expires_on) -> None:
    if credential_type.requires_expiry_date and expires_on is None:
        raise ValidationError("Credential type requires an expiry date.")
    if expires_on is not None and issued_on is not None and expires_on < issued_on:
        raise ValidationError("Practitioner credential expires_on must be greater than or equal to issued_on.")


def _ensure_unique_credential(*, credential_type, credential_number_hash: str, exclude_id=None) -> None:
    queryset = PractitionerCredential.objects.select_for_update().filter(
        credential_type=credential_type,
        credential_number_hash=credential_number_hash,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.exists():
        raise ConflictError("This practitioner credential already exists for the selected credential type.")


@transaction.atomic
def add_practitioner_credential(
    *,
    practitioner_id,
    credential_type_id,
    credential_number: str,
    issuing_authority: str | None = None,
    issuing_country_code: str | None = None,
    issued_on=None,
    expires_on=None,
    created_by_id=None,
) -> PractitionerCredential:
    practitioner = get_practitioner(practitioner_id, active_only=True, for_update=True)
    credential_type = get_practitioner_credential_type(credential_type_id, active_only=True, for_update=True)
    created_by = get_user(created_by_id, field_label="Creator user", active_only=True) if created_by_id is not None else None

    _validate_credential_scope(practitioner=practitioner, credential_type=credential_type)
    _validate_credential_dates(credential_type=credential_type, issued_on=issued_on, expires_on=expires_on)

    raw_credential_number = normalize_optional_text(credential_number)
    if raw_credential_number is None:
        raise ValidationError("Practitioner credential number is required.")
    normalized_lookup_value = normalize_credential_number_for_lookup(raw_credential_number)
    credential_number_hash = build_value_hash(normalized_lookup_value)
    _ensure_unique_credential(credential_type=credential_type, credential_number_hash=credential_number_hash)

    try:
        return PractitionerCredential.objects.create(
            practitioner=practitioner,
            credential_type=credential_type,
            credential_number_encrypted=encrypt_sensitive_value(raw_credential_number),
            credential_number_hash=credential_number_hash,
            last_four=derive_last_four(normalized_lookup_value),
            issuing_authority=normalize_optional_text(issuing_authority),
            issuing_country_code=normalize_country_code(issuing_country_code),
            issued_on=issued_on,
            expires_on=expires_on,
            verification_status=PractitionerCredential.VerificationStatus.UNVERIFIED,
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Practitioner credential could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_practitioner_credential(*, credential_id, **updates) -> PractitionerCredential:
    credential = _get_credential_for_update(credential_id)
    allowed_fields = {
        "credential_type_id",
        "credential_number",
        "issuing_authority",
        "issuing_country_code",
        "issued_on",
        "expires_on",
    }
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported practitioner credential update fields: {unexpected}.")
    if not credential.is_active:
        raise ValidationError("Practitioner credential must be active.")

    next_credential_type = credential.credential_type
    if "credential_type_id" in updates:
        next_credential_type = get_practitioner_credential_type(
            updates["credential_type_id"],
            active_only=True,
            for_update=True,
        )

    raw_credential_number = None
    normalized_lookup_value = None
    if "credential_number" in updates:
        raw_credential_number = normalize_optional_text(updates["credential_number"])
        if raw_credential_number is None:
            raise ValidationError("Practitioner credential number is required.")
        normalized_lookup_value = normalize_credential_number_for_lookup(raw_credential_number)
        next_hash = build_value_hash(normalized_lookup_value)
    else:
        next_hash = credential.credential_number_hash

    next_issued_on = updates.get("issued_on", credential.issued_on)
    next_expires_on = updates.get("expires_on", credential.expires_on)
    _validate_credential_scope(practitioner=credential.practitioner, credential_type=next_credential_type)
    _validate_credential_dates(
        credential_type=next_credential_type,
        issued_on=next_issued_on,
        expires_on=next_expires_on,
    )
    _ensure_unique_credential(
        credential_type=next_credential_type,
        credential_number_hash=next_hash,
        exclude_id=credential.pk,
    )

    credential.credential_type = next_credential_type
    if raw_credential_number is not None:
        credential.credential_number_encrypted = encrypt_sensitive_value(raw_credential_number)
        credential.credential_number_hash = next_hash
        credential.last_four = derive_last_four(normalized_lookup_value)
    if "issuing_authority" in updates:
        credential.issuing_authority = normalize_optional_text(updates["issuing_authority"])
    if "issuing_country_code" in updates:
        credential.issuing_country_code = normalize_country_code(updates["issuing_country_code"])
    if "issued_on" in updates:
        credential.issued_on = updates["issued_on"]
    if "expires_on" in updates:
        credential.expires_on = updates["expires_on"]

    try:
        credential.save()
    except IntegrityError as exc:
        raise ConflictError("Practitioner credential could not be updated because a unique value already exists.") from exc
    return credential


@transaction.atomic
def verify_practitioner_credential(*, credential_id, verified_by_id, verified_at=None) -> PractitionerCredential:
    credential = _get_credential_for_update(credential_id)
    if not credential.is_active:
        raise ValidationError("Practitioner credential must be active.")
    if not credential.practitioner.is_active:
        raise ValidationError("Practitioner must be active.")
    if not credential.credential_type.is_active:
        raise ValidationError("Practitioner credential type must be active.")

    credential.verified_by = get_user(verified_by_id, field_label="Verifying user", active_only=True)
    credential.verified_at = verified_at or timezone.now()
    credential.verification_status = PractitionerCredential.VerificationStatus.VERIFIED
    credential.save(update_fields=["verified_by", "verified_at", "verification_status", "updated_at"])
    return credential


@transaction.atomic
def reject_practitioner_credential(*, credential_id, verified_by_id, verified_at=None) -> PractitionerCredential:
    credential = _get_credential_for_update(credential_id)
    if not credential.is_active:
        raise ValidationError("Practitioner credential must be active.")
    if not credential.practitioner.is_active:
        raise ValidationError("Practitioner must be active.")
    if not credential.credential_type.is_active:
        raise ValidationError("Practitioner credential type must be active.")

    credential.verified_by = get_user(verified_by_id, field_label="Reviewing user", active_only=True)
    credential.verified_at = verified_at or timezone.now()
    credential.verification_status = PractitionerCredential.VerificationStatus.REJECTED
    credential.save(update_fields=["verified_by", "verified_at", "verification_status", "updated_at"])
    return credential


@transaction.atomic
def deactivate_practitioner_credential(*, credential_id) -> PractitionerCredential:
    credential = _get_credential_for_update(credential_id)
    if not credential.is_active:
        return credential
    if not credential.practitioner.is_active:
        raise ValidationError("Practitioner must be active.")
    credential.is_active = False
    credential.save(update_fields=["is_active", "updated_at"])
    return credential
