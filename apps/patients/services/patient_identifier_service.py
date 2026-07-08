from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.patients.models import PatientIdentifier
from common.exceptions import ConflictError, NotFoundError, ValidationError

from ._crypto import build_value_hash, derive_last_four, encrypt_sensitive_value
from ._shared import (
    get_patient,
    get_patient_identifier_type,
    get_user,
    normalize_country_code,
    normalize_optional_text,
)


def _get_identifier_for_update(identifier_id) -> PatientIdentifier:
    try:
        return PatientIdentifier.objects.select_for_update().select_related(
            "patient",
            "patient__organization",
            "identifier_type",
        ).get(pk=identifier_id)
    except PatientIdentifier.DoesNotExist as exc:
        raise NotFoundError("Patient identifier not found.") from exc


def _validate_identifier_scope(*, patient, identifier_type) -> None:
    if identifier_type.organization_id is not None and identifier_type.organization_id != patient.organization_id:
        raise ValidationError("Patient identifier type is outside the patient organization.")


def _ensure_primary_identifier_available(*, identifier, patient, identifier_type) -> None:
    PatientIdentifier.objects.select_for_update().filter(
        patient=patient,
        identifier_type=identifier_type,
        is_active=True,
        is_primary=True,
    ).exclude(pk=getattr(identifier, "pk", None)).update(
        is_primary=False,
        updated_at=timezone.now(),
    )


@transaction.atomic
def add_patient_identifier(
    *,
    patient_id,
    identifier_type_id,
    value: str,
    issuing_country_code: str | None = None,
    issuing_authority: str | None = None,
    issued_on=None,
    expires_on=None,
    is_primary: bool = False,
    created_by_id=None,
) -> PatientIdentifier:
    patient = get_patient(patient_id, active_only=True, for_update=True)
    identifier_type = get_patient_identifier_type(identifier_type_id, active_only=True, for_update=True)
    created_by = get_user(created_by_id, field_label="Creator user") if created_by_id is not None else None

    _validate_identifier_scope(patient=patient, identifier_type=identifier_type)

    normalized_value = normalize_optional_text(value)
    if normalized_value is None:
        raise ValidationError("Patient identifier value is required.")
    if expires_on is not None and issued_on is not None and expires_on < issued_on:
        raise ValidationError("Patient identifier expires_on must be greater than or equal to issued_on.")

    value_hash = build_value_hash(normalized_value)
    if PatientIdentifier.objects.select_for_update().filter(
        identifier_type=identifier_type,
        value_hash=value_hash,
    ).exists():
        raise ConflictError("This patient identifier already exists for the selected identifier type.")

    if is_primary:
        _ensure_primary_identifier_available(
            identifier=None,
            patient=patient,
            identifier_type=identifier_type,
        )

    try:
        return PatientIdentifier.objects.create(
            patient=patient,
            identifier_type=identifier_type,
            value_encrypted=encrypt_sensitive_value(normalized_value),
            value_hash=value_hash,
            last_four=derive_last_four(normalized_value),
            issuing_country_code=normalize_country_code(issuing_country_code),
            issuing_authority=normalize_optional_text(issuing_authority),
            issued_on=issued_on,
            expires_on=expires_on,
            is_primary=bool(is_primary),
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Patient identifier could not be created because a unique value already exists.") from exc


@transaction.atomic
def verify_patient_identifier(
    *,
    identifier_id,
    verified_by_id,
    verified_at=None,
) -> PatientIdentifier:
    identifier = _get_identifier_for_update(identifier_id)
    if not identifier.is_active:
        raise ValidationError("Patient identifier must be active.")
    if not identifier.patient.is_active:
        raise ValidationError("Patient must be active.")
    if not identifier.identifier_type.is_active:
        raise ValidationError("Patient identifier type must be active.")

    if identifier.verified_at is not None and identifier.verified_by_id is not None:
        return identifier

    identifier.verified_by = get_user(verified_by_id, field_label="Verifying user")
    identifier.verified_at = verified_at or timezone.now()
    identifier.save(update_fields=["verified_at", "verified_by", "updated_at"])
    return identifier


@transaction.atomic
def deactivate_patient_identifier(*, identifier_id) -> PatientIdentifier:
    identifier = _get_identifier_for_update(identifier_id)
    if not identifier.is_active:
        return identifier
    if not identifier.patient.is_active:
        raise ValidationError("Patient must be active.")

    identifier.is_active = False
    identifier.is_primary = False
    identifier.save(update_fields=["is_active", "is_primary", "updated_at"])
    return identifier


@transaction.atomic
def set_primary_patient_identifier(*, identifier_id) -> PatientIdentifier:
    identifier = _get_identifier_for_update(identifier_id)
    if not identifier.is_active:
        raise ValidationError("Primary patient identifier must be active.")
    if not identifier.patient.is_active:
        raise ValidationError("Patient must be active.")
    if not identifier.identifier_type.is_active:
        raise ValidationError("Patient identifier type must be active.")

    _ensure_primary_identifier_available(
        identifier=identifier,
        patient=identifier.patient,
        identifier_type=identifier.identifier_type,
    )
    if identifier.is_primary:
        return identifier

    identifier.is_primary = True
    identifier.save(update_fields=["is_primary", "updated_at"])
    return identifier
