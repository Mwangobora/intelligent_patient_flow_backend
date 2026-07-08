from __future__ import annotations

import re

from django.db import IntegrityError, transaction

from apps.facilities.models import Facility, FacilityType, Organization
from common.exceptions import ConflictError, NotFoundError, ValidationError

from .code_generation import generate_unique_code, normalize_code_value

PHONE_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")


def _normalize_email(email: str | None) -> str | None:
    if email is None:
        return None

    normalized_email = email.strip().lower()
    return normalized_email or None


def _validate_phone_number(phone_number: str | None) -> str | None:
    if phone_number is None:
        return None

    normalized_phone = phone_number.strip()
    if not normalized_phone:
        return None
    if not PHONE_RE.fullmatch(normalized_phone):
        raise ValidationError("Phone number must be in E.164 format.")
    return normalized_phone


def _validate_coordinates(latitude, longitude) -> None:
    if (latitude is None) != (longitude is None):
        raise ValidationError("Latitude and longitude must be provided together.")
    if latitude is not None and not (-90 <= latitude <= 90):
        raise ValidationError("Latitude must be between -90 and 90.")
    if longitude is not None and not (-180 <= longitude <= 180):
        raise ValidationError("Longitude must be between -180 and 180.")


def _get_active_organization_for_update(organization_id) -> Organization:
    try:
        organization = Organization.objects.select_for_update().get(pk=organization_id)
    except Organization.DoesNotExist as exc:
        raise NotFoundError("Organization not found.") from exc

    if not organization.is_active:
        raise ValidationError("Organization must be active.")
    return organization


def _get_active_facility_type_for_update(facility_type_id) -> FacilityType:
    try:
        facility_type = FacilityType.objects.select_for_update().get(pk=facility_type_id)
    except FacilityType.DoesNotExist as exc:
        raise NotFoundError("Facility type not found.") from exc

    if not facility_type.is_active:
        raise ValidationError("Facility type must be active.")
    return facility_type


def _ensure_primary_facility_available(*, organization: Organization, exclude_id=None) -> None:
    existing_primary = (
        Facility.objects.select_for_update()
        .filter(organization=organization, is_primary=True, is_active=True)
        .exclude(pk=exclude_id)
        .exists()
    )
    if existing_primary:
        raise ConflictError("Organization already has an active primary facility.")


def _get_facility_for_update(facility_id) -> Facility:
    try:
        return Facility.objects.select_for_update().select_related("organization", "facility_type").get(pk=facility_id)
    except Facility.DoesNotExist as exc:
        raise NotFoundError("Facility not found.") from exc


@transaction.atomic
def create_facility(
    *,
    organization_id,
    facility_type_id,
    name: str,
    code: str | None = None,
    license_number: str | None = None,
    email: str | None = None,
    phone_number: str | None = None,
    address_line1: str | None = None,
    address_line2: str | None = None,
    country_code: str | None = None,
    region: str | None = None,
    district: str | None = None,
    ward: str | None = None,
    postal_code: str | None = None,
    latitude=None,
    longitude=None,
    timezone_name: str = "Africa/Dar_es_Salaam",
    is_primary: bool = False,
) -> Facility:
    if not name or not name.strip():
        raise ValidationError("Facility name is required.")
    if not timezone_name or not timezone_name.strip():
        raise ValidationError("Facility timezone is required.")

    organization = _get_active_organization_for_update(organization_id)
    facility_type = _get_active_facility_type_for_update(facility_type_id)
    _validate_coordinates(latitude, longitude)

    scoped_queryset = Facility.objects.filter(organization=organization)
    if code is not None:
        normalized_code = normalize_code_value(code)
        if not normalized_code:
            raise ValidationError("Facility code cannot be empty.")
    else:
        normalized_code = generate_unique_code(
            model=Facility,
            source_value=name,
            queryset=scoped_queryset,
        )
    if scoped_queryset.select_for_update().filter(code=normalized_code).exists():
        raise ConflictError("Facility code already exists in this organization.")

    if is_primary:
        _ensure_primary_facility_available(organization=organization)

    try:
        facility = Facility.objects.create(
            organization=organization,
            facility_type=facility_type,
            name=name.strip(),
            code=normalized_code,
            license_number=license_number.strip() if license_number else None,
            email=_normalize_email(email),
            phone_number=_validate_phone_number(phone_number),
            address_line1=address_line1.strip() if address_line1 else None,
            address_line2=address_line2.strip() if address_line2 else None,
            country_code=country_code.strip().upper() if country_code else None,
            region=region.strip() if region else None,
            district=district.strip() if district else None,
            ward=ward.strip() if ward else None,
            postal_code=postal_code.strip() if postal_code else None,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone_name.strip(),
            is_primary=is_primary,
        )
    except IntegrityError as exc:
        raise ConflictError("Facility could not be created because a unique value already exists.") from exc
    return facility


@transaction.atomic
def update_facility(
    *,
    facility_id,
    regenerate_code: bool = False,
    **updates,
) -> Facility:
    facility = _get_facility_for_update(facility_id)

    allowed_fields = {
        "name",
        "code",
        "license_number",
        "email",
        "phone_number",
        "address_line1",
        "address_line2",
        "country_code",
        "region",
        "district",
        "ward",
        "postal_code",
        "latitude",
        "longitude",
        "timezone",
        "is_primary",
        "facility_type_id",
        "organization_id",
    }
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported facility update fields: {unexpected}.")

    if "organization_id" in updates and updates["organization_id"] != facility.organization_id:
        raise ValidationError("Changing a facility's organization is not supported in foundation services.")

    if "facility_type_id" in updates and updates["facility_type_id"] != facility.facility_type_id:
        facility.facility_type = _get_active_facility_type_for_update(updates["facility_type_id"])

    if "name" in updates:
        if not updates["name"] or not updates["name"].strip():
            raise ValidationError("Facility name is required.")
        facility.name = updates["name"].strip()

    if "license_number" in updates:
        facility.license_number = updates["license_number"].strip() if updates["license_number"] else None

    if "email" in updates:
        facility.email = _normalize_email(updates["email"])

    if "phone_number" in updates:
        facility.phone_number = _validate_phone_number(updates["phone_number"])

    for field_name in ("address_line1", "address_line2", "region", "district", "ward", "postal_code"):
        if field_name in updates:
            value = updates[field_name]
            setattr(facility, field_name, value.strip() if value else None)

    if "country_code" in updates:
        facility.country_code = updates["country_code"].strip().upper() if updates["country_code"] else None

    next_latitude = updates.get("latitude", facility.latitude)
    next_longitude = updates.get("longitude", facility.longitude)
    _validate_coordinates(next_latitude, next_longitude)
    if "latitude" in updates:
        facility.latitude = updates["latitude"]
    if "longitude" in updates:
        facility.longitude = updates["longitude"]

    if "timezone" in updates:
        if not updates["timezone"] or not updates["timezone"].strip():
            raise ValidationError("Facility timezone is required.")
        facility.timezone = updates["timezone"].strip()

    scoped_queryset = Facility.objects.filter(organization=facility.organization)
    if regenerate_code:
        facility.code = generate_unique_code(
            model=Facility,
            source_value=facility.name,
            queryset=scoped_queryset.exclude(pk=facility.pk),
        )
    elif "code" in updates and updates["code"] is not None:
        normalized_code = normalize_code_value(updates["code"])
        if not normalized_code:
            raise ValidationError("Facility code cannot be empty.")
        if scoped_queryset.select_for_update().exclude(pk=facility.pk).filter(code=normalized_code).exists():
            raise ConflictError("Facility code already exists in this organization.")
        facility.code = normalized_code

    if "is_primary" in updates:
        requested_primary = bool(updates["is_primary"])
        if requested_primary:
            _ensure_primary_facility_available(organization=facility.organization, exclude_id=facility.pk)
        facility.is_primary = requested_primary

    try:
        facility.save()
    except IntegrityError as exc:
        raise ConflictError("Facility could not be updated because a unique value already exists.") from exc
    return facility


@transaction.atomic
def deactivate_facility(*, facility_id) -> Facility:
    facility = _get_facility_for_update(facility_id)
    if not facility.is_active:
        return facility

    # Clear the primary flag on deactivation so a replacement primary facility
    # can be assigned without inheriting stale "primary but inactive" state.
    facility.is_active = False
    facility.is_primary = False
    facility.save(update_fields=["is_active", "is_primary", "updated_at"])
    return facility
