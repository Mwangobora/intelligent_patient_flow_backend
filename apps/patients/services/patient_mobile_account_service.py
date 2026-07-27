from __future__ import annotations

import secrets

from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.accounts.services.user_service import create_user
from apps.facilities.models import Facility, Organization
from apps.patients.models import Patient
from apps.patients.services.patient_service import create_patient
from common.exceptions import ConflictError, NotFoundError, ValidationError

from ._shared import normalize_email, normalize_optional_text, validate_phone_number


def normalize_mobile_phone(phone_number: str | None) -> str | None:
    normalized_phone = normalize_optional_text(phone_number)
    if normalized_phone is None:
        return None

    compact_phone = normalized_phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if compact_phone.startswith("0"):
        compact_phone = f"+255{compact_phone[1:]}"
    elif compact_phone.startswith("255"):
        compact_phone = f"+{compact_phone}"
    return validate_phone_number(compact_phone)


def _select_default_registration_scope():
    facility = (
        Facility.objects.select_for_update()
        .select_related("organization")
        .filter(is_active=True, organization__is_active=True, is_primary=True)
        .order_by("created_at")
        .first()
    )
    if facility is None:
        facility = (
            Facility.objects.select_for_update()
            .select_related("organization")
            .filter(is_active=True, organization__is_active=True)
            .order_by("created_at")
            .first()
        )
    if facility is not None:
        return facility.organization, facility

    organization = Organization.objects.select_for_update().filter(is_active=True).order_by("created_at").first()
    if organization is None:
        raise ValidationError("No active organization is configured for patient registration.")
    return organization, None


def _ensure_contact_available(*, email: str | None, phone_number: str | None) -> None:
    if not email and not phone_number:
        raise ValidationError("Email or phone number is required.")
    if email and User.objects.select_for_update().filter(email__iexact=email).exists():
        raise ConflictError("An account with this email already exists.")
    if phone_number and User.objects.select_for_update().filter(phone_number=phone_number).exists():
        raise ConflictError("An account with this phone number already exists.")


def _password_or_generated(temporary_password: str | None = None) -> tuple[str, bool]:
    if temporary_password:
        return temporary_password, False
    return f"{secrets.token_urlsafe(12)}A1!", True


def _validate_password(password: str) -> None:
    try:
        validate_password(password)
    except DjangoValidationError as exc:
        raise ValidationError(" ".join(exc.messages)) from exc


def _safe_patient_summary(patient: Patient) -> dict:
    return {
        "id": patient.id,
        "patient_number": patient.patient_number,
        "first_name": patient.first_name,
        "middle_name": patient.middle_name,
        "last_name": patient.last_name,
        "date_of_birth": patient.date_of_birth,
        "date_of_birth_is_estimated": patient.date_of_birth_is_estimated,
        "sex_code": patient.sex_code,
        "email": patient.email,
        "phone_number": patient.phone_number,
        "organization": patient.organization_id,
        "organization_name": patient.organization.name,
        "registered_facility": patient.registered_facility_id,
        "registered_facility_name": patient.registered_facility.name if patient.registered_facility else None,
        "is_active": patient.is_active,
    }


@transaction.atomic
def register_mobile_patient(
    *,
    first_name: str,
    last_name: str,
    password: str,
    password_confirm: str,
    middle_name: str | None = None,
    date_of_birth=None,
    date_of_birth_is_estimated: bool = False,
    sex_code: str | None = None,
    email: str | None = None,
    phone_number: str | None = None,
) -> tuple[User, Patient]:
    if password != password_confirm:
        raise ValidationError("Passwords do not match.")
    _validate_password(password)

    normalized_email = normalize_email(email)
    normalized_phone = normalize_mobile_phone(phone_number)
    _ensure_contact_available(email=normalized_email, phone_number=normalized_phone)

    organization, registered_facility = _select_default_registration_scope()
    try:
        user = create_user(
            email=normalized_email,
            phone_number=normalized_phone,
            password=password,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
        )
        patient = create_patient(
            organization_id=organization.id,
            registered_facility_id=registered_facility.id if registered_facility else None,
            user_id=user.id,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            date_of_birth_is_estimated=date_of_birth_is_estimated,
            sex_code=sex_code,
            email=normalized_email,
            phone_number=normalized_phone,
        )
    except IntegrityError as exc:
        raise ConflictError("Patient mobile account could not be created because a unique value already exists.") from exc

    return user, patient


def get_patient_for_user(user: User, *, for_update: bool = False) -> Patient:
    queryset = Patient.objects.select_related("organization", "registered_facility", "user")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))

    try:
        return queryset.get(user=user, is_active=True)
    except Patient.DoesNotExist as exc:
        raise NotFoundError("Patient profile was not found for this account.") from exc
    except Patient.MultipleObjectsReturned as exc:
        raise ConflictError("Multiple patient profiles are linked to this account. Please contact support.") from exc


@transaction.atomic
def update_current_patient_profile(*, user: User, email: str | None = None, phone_number: str | None = None) -> Patient:
    patient = get_patient_for_user(user, for_update=True)
    user = User.objects.select_for_update().get(pk=user.pk)

    next_email = user.email
    next_phone = user.phone_number
    if email is not None:
        next_email = normalize_email(email)
    if phone_number is not None:
        next_phone = normalize_mobile_phone(phone_number)

    _ensure_contact_available_for_update(email=next_email, phone_number=next_phone, user=user)

    user.email = next_email
    user.phone_number = next_phone
    patient.email = next_email
    patient.phone_number = next_phone

    try:
        user.save(update_fields=["email", "phone_number", "updated_at"])
        patient.save(update_fields=["email", "phone_number", "updated_at"])
    except IntegrityError as exc:
        raise ConflictError("Patient profile could not be updated because a unique value already exists.") from exc
    return patient


def _ensure_contact_available_for_update(*, email: str | None, phone_number: str | None, user: User) -> None:
    if not email and not phone_number:
        raise ValidationError("Email or phone number is required.")

    users = User.objects.select_for_update().exclude(pk=user.pk)
    if email and users.filter(email__iexact=email).exists():
        raise ConflictError("An account with this email already exists.")
    if phone_number and users.filter(phone_number=phone_number).exists():
        raise ConflictError("An account with this phone number already exists.")


@transaction.atomic
def create_mobile_account_for_existing_patient(
    *,
    patient_id,
    email: str | None = None,
    phone_number: str | None = None,
    temporary_password: str | None = None,
) -> tuple[User, Patient, str, bool]:
    try:
        patient = Patient.objects.select_for_update().select_related("organization").get(pk=patient_id)
    except Patient.DoesNotExist as exc:
        raise NotFoundError("Patient not found.") from exc

    if patient.user_id is not None:
        raise ConflictError("This patient already has a linked mobile account.")

    normalized_email = normalize_email(email) or patient.email
    normalized_phone = normalize_mobile_phone(phone_number) or patient.phone_number
    _ensure_contact_available(email=normalized_email, phone_number=normalized_phone)

    password, generated_password = _password_or_generated(temporary_password)
    _validate_password(password)
    user = create_user(
        email=normalized_email,
        phone_number=normalized_phone,
        password=password,
        first_name=patient.first_name,
        middle_name=patient.middle_name,
        last_name=patient.last_name,
    )
    patient.user = user
    patient.email = normalized_email
    patient.phone_number = normalized_phone
    patient.save(update_fields=["user", "email", "phone_number", "updated_at"])
    return user, patient, password, generated_password


@transaction.atomic
def claim_existing_patient_record(
    *,
    phone_number: str,
    date_of_birth,
    patient_number: str | None = None,
    password: str | None = None,
    password_confirm: str | None = None,
) -> dict:
    normalized_phone = normalize_mobile_phone(phone_number)
    queryset = Patient.objects.select_for_update().filter(
        phone_number=normalized_phone,
        date_of_birth=date_of_birth,
        is_active=True,
    )
    if patient_number:
        queryset = queryset.filter(patient_number=normalize_optional_text(patient_number))

    matches = list(queryset[:2])
    if len(matches) != 1:
        return {
            "status": "verification_required",
            "message": "Please visit reception to verify and activate your mobile account.",
        }

    patient = matches[0]
    if patient.user_id is not None:
        return {
            "status": "already_linked",
            "message": "This patient record already has a mobile account. Please log in or reset your password.",
        }

    if not password:
        return {
            "status": "verification_required",
            "message": "Record matched. Please complete hospital verification before account activation.",
        }
    if password != password_confirm:
        raise ValidationError("Passwords do not match.")
    _validate_password(password)

    _ensure_contact_available(email=patient.email, phone_number=patient.phone_number)
    user = create_user(
        email=patient.email,
        phone_number=patient.phone_number,
        password=password,
        first_name=patient.first_name,
        middle_name=patient.middle_name,
        last_name=patient.last_name,
    )
    patient.user = user
    patient.save(update_fields=["user", "updated_at"])
    return {
        "status": "linked",
        "message": "Your patient record is now linked to your mobile account.",
        "user": user,
        "patient": patient,
    }


__all__ = [
    "_safe_patient_summary",
    "claim_existing_patient_record",
    "create_mobile_account_for_existing_patient",
    "get_patient_for_user",
    "normalize_mobile_phone",
    "register_mobile_patient",
    "update_current_patient_profile",
]
