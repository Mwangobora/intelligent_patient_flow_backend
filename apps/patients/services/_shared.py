from __future__ import annotations

import re

from apps.accounts.models import Role, User
from apps.facilities.models import Facility, Organization
from apps.patients.models import Patient, PatientIdentifierType, PatientRelatedPerson, RelationshipType
from common.exceptions import NotFoundError, ValidationError

PHONE_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned_value = value.strip()
    return cleaned_value or None


def normalize_email(email: str | None) -> str | None:
    normalized_email = normalize_optional_text(email)
    if normalized_email is None:
        return None
    return normalized_email.lower()


def validate_phone_number(phone_number: str | None) -> str | None:
    normalized_phone = normalize_optional_text(phone_number)
    if normalized_phone is None:
        return None
    if not PHONE_RE.fullmatch(normalized_phone):
        raise ValidationError("Phone number must be in E.164 format.")
    return normalized_phone


def normalize_country_code(country_code: str | None) -> str | None:
    normalized_country_code = normalize_optional_text(country_code)
    if normalized_country_code is None:
        return None
    return normalized_country_code.upper()


def validate_coordinates(latitude, longitude) -> None:
    if (latitude is None) != (longitude is None):
        raise ValidationError("Latitude and longitude must be provided together.")
    if latitude is not None and not (-90 <= latitude <= 90):
        raise ValidationError("Latitude must be between -90 and 90.")
    if longitude is not None and not (-180 <= longitude <= 180):
        raise ValidationError("Longitude must be between -180 and 180.")


def get_user(
    user_id,
    *,
    field_label: str = "User",
    active_only: bool = False,
    for_update: bool = False,
) -> User:
    queryset = User.objects
    if for_update:
        queryset = queryset.select_for_update()

    try:
        user = queryset.get(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc

    if active_only and not user.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return user


def get_organization(
    organization_id,
    *,
    field_label: str = "Organization",
    active_only: bool = False,
    for_update: bool = False,
) -> Organization:
    queryset = Organization.objects
    if for_update:
        queryset = queryset.select_for_update()

    try:
        organization = queryset.get(pk=organization_id)
    except Organization.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc

    if active_only and not organization.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return organization


def get_facility(
    facility_id,
    *,
    field_label: str = "Facility",
    active_only: bool = False,
    for_update: bool = False,
) -> Facility:
    queryset = Facility.objects.select_related("organization")
    if for_update:
        queryset = queryset.select_for_update()

    try:
        facility = queryset.get(pk=facility_id)
    except Facility.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc

    if active_only and not facility.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return facility


def get_patient(
    patient_id,
    *,
    field_label: str = "Patient",
    active_only: bool = False,
    for_update: bool = False,
) -> Patient:
    queryset = Patient.objects.select_related("organization", "registered_facility", "user")
    if for_update:
        queryset = queryset.select_for_update()

    try:
        patient = queryset.get(pk=patient_id)
    except Patient.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc

    if active_only and not patient.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return patient


def get_patient_identifier_type(
    identifier_type_id,
    *,
    field_label: str = "Patient identifier type",
    active_only: bool = False,
    for_update: bool = False,
) -> PatientIdentifierType:
    queryset = PatientIdentifierType.objects.select_related("organization")
    if for_update:
        queryset = queryset.select_for_update()

    try:
        identifier_type = queryset.get(pk=identifier_type_id)
    except PatientIdentifierType.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc

    if active_only and not identifier_type.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return identifier_type


def get_relationship_type(
    relationship_type_id,
    *,
    field_label: str = "Relationship type",
    active_only: bool = False,
    for_update: bool = False,
) -> RelationshipType:
    queryset = RelationshipType.objects
    if for_update:
        queryset = queryset.select_for_update()

    try:
        relationship_type = queryset.get(pk=relationship_type_id)
    except RelationshipType.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc

    if active_only and not relationship_type.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return relationship_type


def get_related_person(
    related_person_id,
    *,
    field_label: str = "Related person",
    active_only: bool = False,
    for_update: bool = False,
) -> PatientRelatedPerson:
    queryset = PatientRelatedPerson.objects.select_related(
        "patient",
        "patient__organization",
        "patient__user",
        "linked_user",
        "relationship_type",
    )
    if for_update:
        queryset = queryset.select_for_update()

    try:
        related_person = queryset.get(pk=related_person_id)
    except PatientRelatedPerson.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc

    if active_only and not related_person.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return related_person


def get_role(
    role_id,
    *,
    field_label: str = "Role",
    active_only: bool = False,
    for_update: bool = False,
) -> Role:
    queryset = Role.objects.select_related("organization", "facility")
    if for_update:
        queryset = queryset.select_for_update()

    try:
        role = queryset.get(pk=role_id)
    except Role.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc

    if active_only and not role.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return role
