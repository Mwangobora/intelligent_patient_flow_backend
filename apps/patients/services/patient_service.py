from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.patients.models import Patient
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    get_facility,
    get_organization,
    get_patient,
    get_user,
    normalize_email,
    normalize_optional_text,
    validate_phone_number,
)
from .patient_number_service import generate_patient_number


def _validate_sex_code(sex_code: str | None) -> str | None:
    normalized_sex_code = normalize_optional_text(sex_code)
    if normalized_sex_code is None:
        return None
    if normalized_sex_code not in Patient.SexCode.values:
        raise ValidationError("Invalid sex_code.")
    return normalized_sex_code


def _validate_date_of_birth(date_of_birth) -> None:
    if date_of_birth is not None and date_of_birth > timezone.localdate():
        raise ValidationError("Date of birth cannot be in the future.")


def _ensure_registered_facility_scope(*, organization, registered_facility) -> None:
    if registered_facility is None:
        return
    if registered_facility.organization_id != organization.id:
        raise ValidationError("Registered facility must belong to the same organization as the patient.")


def _ensure_unique_patient_user(*, organization, user, exclude_id=None) -> None:
    if user is None:
        return

    queryset = Patient.objects.select_for_update().filter(
        organization=organization,
        user=user,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    if queryset.exists():
        raise ConflictError("This user already has a patient profile in the selected organization.")


def _ensure_unique_patient_number(*, organization, patient_number: str, exclude_id=None) -> None:
    queryset = Patient.objects.select_for_update().filter(
        organization=organization,
        patient_number=patient_number,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    if queryset.exists():
        raise ConflictError("Patient number already exists in the selected organization.")


@transaction.atomic
def create_patient(
    *,
    organization_id,
    first_name: str,
    last_name: str,
    patient_number: str | None = None,
    middle_name: str | None = None,
    registered_facility_id=None,
    user_id=None,
    date_of_birth=None,
    date_of_birth_is_estimated: bool = False,
    sex_code: str | None = None,
    email: str | None = None,
    phone_number: str | None = None,
    created_by_id=None,
) -> Patient:
    if not first_name or not first_name.strip():
        raise ValidationError("Patient first_name is required.")
    if not last_name or not last_name.strip():
        raise ValidationError("Patient last_name is required.")

    organization = get_organization(organization_id, active_only=True, for_update=True)
    registered_facility = (
        get_facility(registered_facility_id, field_label="Registered facility", active_only=True, for_update=True)
        if registered_facility_id is not None
        else None
    )
    user = (
        get_user(user_id, field_label="Patient user", active_only=True, for_update=True)
        if user_id is not None
        else None
    )
    created_by = get_user(created_by_id, field_label="Creator user") if created_by_id is not None else None

    _ensure_registered_facility_scope(organization=organization, registered_facility=registered_facility)
    _ensure_unique_patient_user(organization=organization, user=user)
    _validate_date_of_birth(date_of_birth)

    normalized_patient_number = normalize_optional_text(patient_number)
    if normalized_patient_number is None:
        normalized_patient_number = generate_patient_number(organization=organization)
    else:
        _ensure_unique_patient_number(organization=organization, patient_number=normalized_patient_number)

    try:
        return Patient.objects.create(
            organization=organization,
            user=user,
            registered_facility=registered_facility,
            patient_number=normalized_patient_number,
            first_name=first_name.strip(),
            middle_name=normalize_optional_text(middle_name),
            last_name=last_name.strip(),
            date_of_birth=date_of_birth,
            date_of_birth_is_estimated=bool(date_of_birth_is_estimated),
            sex_code=_validate_sex_code(sex_code),
            email=normalize_email(email),
            phone_number=validate_phone_number(phone_number),
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Patient could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_patient(
    *,
    patient_id,
    **updates,
) -> Patient:
    patient = get_patient(patient_id, for_update=True)

    allowed_fields = {
        "patient_number",
        "first_name",
        "middle_name",
        "last_name",
        "registered_facility_id",
        "user_id",
        "date_of_birth",
        "date_of_birth_is_estimated",
        "sex_code",
        "email",
        "phone_number",
    }
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported patient update fields: {unexpected}.")

    organization = patient.organization
    if not organization.is_active:
        raise ValidationError("Organization must be active.")

    if "first_name" in updates:
        if not updates["first_name"] or not updates["first_name"].strip():
            raise ValidationError("Patient first_name is required.")
        patient.first_name = updates["first_name"].strip()

    if "middle_name" in updates:
        patient.middle_name = normalize_optional_text(updates["middle_name"])

    if "last_name" in updates:
        if not updates["last_name"] or not updates["last_name"].strip():
            raise ValidationError("Patient last_name is required.")
        patient.last_name = updates["last_name"].strip()

    if "user_id" in updates:
        patient.user = (
            get_user(updates["user_id"], field_label="Patient user", active_only=True, for_update=True)
            if updates["user_id"] is not None
            else None
        )
    elif patient.user_id is not None and not patient.user.is_active:
        raise ValidationError("Patient user must be active.")

    _ensure_unique_patient_user(organization=organization, user=patient.user, exclude_id=patient.pk)

    if "registered_facility_id" in updates:
        patient.registered_facility = (
            get_facility(
                updates["registered_facility_id"],
                field_label="Registered facility",
                active_only=True,
                for_update=True,
            )
            if updates["registered_facility_id"] is not None
            else None
        )

    if patient.registered_facility_id is not None:
        if not patient.registered_facility.is_active:
            raise ValidationError("Registered facility must be active.")
        _ensure_registered_facility_scope(organization=organization, registered_facility=patient.registered_facility)

    if "patient_number" in updates:
        normalized_patient_number = normalize_optional_text(updates["patient_number"])
        if normalized_patient_number is None:
            raise ValidationError("Patient number cannot be empty.")
        _ensure_unique_patient_number(
            organization=organization,
            patient_number=normalized_patient_number,
            exclude_id=patient.pk,
        )
        patient.patient_number = normalized_patient_number

    if "date_of_birth" in updates:
        _validate_date_of_birth(updates["date_of_birth"])
        patient.date_of_birth = updates["date_of_birth"]

    if "date_of_birth_is_estimated" in updates:
        patient.date_of_birth_is_estimated = bool(updates["date_of_birth_is_estimated"])

    if "sex_code" in updates:
        patient.sex_code = _validate_sex_code(updates["sex_code"])

    if "email" in updates:
        patient.email = normalize_email(updates["email"])

    if "phone_number" in updates:
        patient.phone_number = validate_phone_number(updates["phone_number"])

    try:
        patient.save()
    except IntegrityError as exc:
        raise ConflictError("Patient could not be updated because a unique value already exists.") from exc
    return patient


@transaction.atomic
def deactivate_patient(*, patient_id) -> Patient:
    patient = get_patient(patient_id, for_update=True)
    if not patient.is_active:
        return patient

    patient.is_active = False
    patient.save(update_fields=["is_active", "updated_at"])
    return patient


@transaction.atomic
def reactivate_patient(*, patient_id) -> Patient:
    patient = get_patient(patient_id, for_update=True)
    if patient.is_active:
        return patient

    if not patient.organization.is_active:
        raise ValidationError("Organization must be active.")
    if patient.user_id is not None and not patient.user.is_active:
        raise ValidationError("Patient user must be active.")
    if patient.registered_facility_id is not None:
        if not patient.registered_facility.is_active:
            raise ValidationError("Registered facility must be active.")
        _ensure_registered_facility_scope(
            organization=patient.organization,
            registered_facility=patient.registered_facility,
        )

    patient.is_active = True
    patient.save(update_fields=["is_active", "updated_at"])
    return patient
