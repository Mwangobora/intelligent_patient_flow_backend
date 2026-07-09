from __future__ import annotations

import re

from apps.accounts.models import User
from apps.facilities.models import Department, Facility, FacilitySpecialty, Organization
from apps.practitioners.models import (
    Practitioner,
    PractitionerCredential,
    PractitionerCredentialType,
    PractitionerDepartmentAssignment,
    PractitionerFacilityAssignment,
    PractitionerSpecialtyAssignment,
    PractitionerType,
)
from common.exceptions import NotFoundError, ValidationError

PHONE_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")
PHONE_SEPARATORS_RE = re.compile(r"[\s\-\(\)]+")


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
    normalized_phone = PHONE_SEPARATORS_RE.sub("", normalized_phone)
    if not PHONE_RE.fullmatch(normalized_phone):
        raise ValidationError("Phone number must be in E.164 format.")
    return normalized_phone


def normalize_country_code(country_code: str | None) -> str | None:
    normalized_country_code = normalize_optional_text(country_code)
    if normalized_country_code is None:
        return None
    return normalized_country_code.upper()


def validate_starts_ends(*, starts_on, ends_on, label: str) -> None:
    if starts_on is None:
        raise ValidationError(f"{label} starts_on is required.")
    if ends_on is not None and ends_on < starts_on:
        raise ValidationError(f"{label} ends_on must be greater than or equal to starts_on.")


def validate_within_parent_range(*, child_start, child_end, parent_start, parent_end, label: str) -> None:
    if child_start < parent_start:
        raise ValidationError(f"{label} must remain within facility assignment dates.")
    if parent_end is not None and (child_end is None or child_end > parent_end):
        raise ValidationError(f"{label} must remain within facility assignment dates.")


def get_user(user_id, *, field_label: str = "User", active_only: bool = False, for_update: bool = False) -> User:
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


def get_department(
    department_id,
    *,
    field_label: str = "Department",
    active_only: bool = False,
    for_update: bool = False,
) -> Department:
    queryset = Department.objects.select_related("facility")
    if for_update:
        queryset = queryset.select_for_update()
    try:
        department = queryset.get(pk=department_id)
    except Department.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not department.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return department


def get_facility_specialty(
    facility_specialty_id,
    *,
    field_label: str = "Facility specialty",
    active_only: bool = False,
    for_update: bool = False,
) -> FacilitySpecialty:
    queryset = FacilitySpecialty.objects.select_related("facility", "specialty")
    if for_update:
        queryset = queryset.select_for_update()
    else:
        queryset = queryset.select_related("department")
    try:
        facility_specialty = queryset.get(pk=facility_specialty_id)
    except FacilitySpecialty.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not facility_specialty.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return facility_specialty


def get_practitioner_type(
    practitioner_type_id,
    *,
    field_label: str = "Practitioner type",
    active_only: bool = False,
    for_update: bool = False,
) -> PractitionerType:
    queryset = PractitionerType.objects
    if for_update:
        queryset = queryset.select_for_update()
    try:
        practitioner_type = queryset.get(pk=practitioner_type_id)
    except PractitionerType.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not practitioner_type.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return practitioner_type


def get_practitioner(
    practitioner_id,
    *,
    field_label: str = "Practitioner",
    active_only: bool = False,
    for_update: bool = False,
) -> Practitioner:
    if for_update:
        queryset = Practitioner.objects.select_related("organization", "practitioner_type").select_for_update()
    else:
        queryset = Practitioner.objects.select_related("organization", "user", "practitioner_type")
    try:
        practitioner = queryset.get(pk=practitioner_id)
    except Practitioner.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not practitioner.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return practitioner


def get_practitioner_facility_assignment(
    assignment_id,
    *,
    field_label: str = "Practitioner facility assignment",
    active_only: bool = False,
    for_update: bool = False,
) -> PractitionerFacilityAssignment:
    queryset = PractitionerFacilityAssignment.objects.select_related("practitioner", "practitioner__organization", "facility")
    if for_update:
        queryset = queryset.select_for_update()
    try:
        assignment = queryset.get(pk=assignment_id)
    except PractitionerFacilityAssignment.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not assignment.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return assignment


def get_practitioner_department_assignment(
    assignment_id,
    *,
    field_label: str = "Practitioner department assignment",
    active_only: bool = False,
    for_update: bool = False,
) -> PractitionerDepartmentAssignment:
    queryset = PractitionerDepartmentAssignment.objects.select_related(
        "practitioner_facility_assignment",
        "practitioner_facility_assignment__practitioner",
        "practitioner_facility_assignment__facility",
        "department",
        "department__facility",
    )
    if for_update:
        queryset = queryset.select_for_update()
    try:
        assignment = queryset.get(pk=assignment_id)
    except PractitionerDepartmentAssignment.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not assignment.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return assignment


def get_practitioner_specialty_assignment(
    assignment_id,
    *,
    field_label: str = "Practitioner specialty assignment",
    active_only: bool = False,
    for_update: bool = False,
) -> PractitionerSpecialtyAssignment:
    queryset = PractitionerSpecialtyAssignment.objects.select_related(
        "practitioner_facility_assignment",
        "practitioner_facility_assignment__practitioner",
        "practitioner_facility_assignment__facility",
        "facility_specialty",
        "facility_specialty__facility",
        "facility_specialty__department",
        "facility_specialty__specialty",
    )
    if for_update:
        queryset = queryset.select_for_update()
    try:
        assignment = queryset.get(pk=assignment_id)
    except PractitionerSpecialtyAssignment.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not assignment.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return assignment


def get_practitioner_credential_type(
    credential_type_id,
    *,
    field_label: str = "Practitioner credential type",
    active_only: bool = False,
    for_update: bool = False,
) -> PractitionerCredentialType:
    if for_update:
        queryset = PractitionerCredentialType.objects.select_for_update()
    else:
        queryset = PractitionerCredentialType.objects.select_related("organization")
    try:
        credential_type = queryset.get(pk=credential_type_id)
    except PractitionerCredentialType.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not credential_type.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return credential_type


def get_practitioner_credential(
    credential_id,
    *,
    field_label: str = "Practitioner credential",
    active_only: bool = False,
    for_update: bool = False,
) -> PractitionerCredential:
    queryset = PractitionerCredential.objects.select_related(
        "practitioner",
        "practitioner__organization",
        "credential_type",
        "verified_by",
    )
    if for_update:
        queryset = queryset.select_for_update()
    try:
        credential = queryset.get(pk=credential_id)
    except PractitionerCredential.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not credential.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return credential
