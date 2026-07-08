from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.patients.models import PatientAddress
from common.exceptions import ConflictError, NotFoundError, ValidationError

from ._crypto import encrypt_sensitive_value
from ._shared import (
    get_patient,
    get_user,
    normalize_country_code,
    normalize_optional_text,
    validate_coordinates,
)


def _get_address_for_update(address_id) -> PatientAddress:
    try:
        return PatientAddress.objects.select_for_update().select_related("patient").get(pk=address_id)
    except PatientAddress.DoesNotExist as exc:
        raise NotFoundError("Patient address not found.") from exc


def _validate_meaningful_address(
    *,
    address_line1_encrypted,
    address_line2_encrypted,
    region,
    district,
    ward,
    postal_code,
    latitude,
) -> None:
    if any(
        value is not None
        for value in (
            address_line1_encrypted,
            address_line2_encrypted,
            region,
            district,
            ward,
            postal_code,
            latitude,
        )
    ):
        return
    raise ValidationError("At least one meaningful address field is required.")


def _clear_other_primary_addresses(*, patient, exclude_id=None) -> None:
    queryset = PatientAddress.objects.select_for_update().filter(
        patient=patient,
        is_active=True,
        is_primary=True,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    queryset.update(is_primary=False, updated_at=timezone.now())


@transaction.atomic
def add_patient_address(
    *,
    patient_id,
    label: str | None = None,
    address_line1: str | None = None,
    address_line2: str | None = None,
    country_code: str | None = None,
    region: str | None = None,
    district: str | None = None,
    ward: str | None = None,
    postal_code: str | None = None,
    latitude=None,
    longitude=None,
    is_primary: bool = False,
    created_by_id=None,
) -> PatientAddress:
    patient = get_patient(patient_id, active_only=True, for_update=True)
    created_by = get_user(created_by_id, field_label="Creator user") if created_by_id is not None else None

    normalized_address_line1 = normalize_optional_text(address_line1)
    normalized_address_line2 = normalize_optional_text(address_line2)
    normalized_region = normalize_optional_text(region)
    normalized_district = normalize_optional_text(district)
    normalized_ward = normalize_optional_text(ward)
    normalized_postal_code = normalize_optional_text(postal_code)

    validate_coordinates(latitude, longitude)

    encrypted_address_line1 = (
        encrypt_sensitive_value(normalized_address_line1)
        if normalized_address_line1 is not None
        else None
    )
    encrypted_address_line2 = (
        encrypt_sensitive_value(normalized_address_line2)
        if normalized_address_line2 is not None
        else None
    )
    _validate_meaningful_address(
        address_line1_encrypted=encrypted_address_line1,
        address_line2_encrypted=encrypted_address_line2,
        region=normalized_region,
        district=normalized_district,
        ward=normalized_ward,
        postal_code=normalized_postal_code,
        latitude=latitude,
    )

    if is_primary:
        _clear_other_primary_addresses(patient=patient)

    try:
        return PatientAddress.objects.create(
            patient=patient,
            label=normalize_optional_text(label),
            address_line1_encrypted=encrypted_address_line1,
            address_line2_encrypted=encrypted_address_line2,
            country_code=normalize_country_code(country_code),
            region=normalized_region,
            district=normalized_district,
            ward=normalized_ward,
            postal_code=normalized_postal_code,
            latitude=latitude,
            longitude=longitude,
            is_primary=bool(is_primary),
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Patient address could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_patient_address(
    *,
    address_id,
    **updates,
) -> PatientAddress:
    address = _get_address_for_update(address_id)
    if not address.is_active:
        raise ValidationError("Patient address must be active.")
    if not address.patient.is_active:
        raise ValidationError("Patient must be active.")

    allowed_fields = {
        "label",
        "address_line1",
        "address_line2",
        "country_code",
        "region",
        "district",
        "ward",
        "postal_code",
        "latitude",
        "longitude",
        "is_primary",
    }
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported patient address update fields: {unexpected}.")

    if "label" in updates:
        address.label = normalize_optional_text(updates["label"])

    if "address_line1" in updates:
        normalized_address_line1 = normalize_optional_text(updates["address_line1"])
        address.address_line1_encrypted = (
            encrypt_sensitive_value(normalized_address_line1)
            if normalized_address_line1 is not None
            else None
        )

    if "address_line2" in updates:
        normalized_address_line2 = normalize_optional_text(updates["address_line2"])
        address.address_line2_encrypted = (
            encrypt_sensitive_value(normalized_address_line2)
            if normalized_address_line2 is not None
            else None
        )

    if "country_code" in updates:
        address.country_code = normalize_country_code(updates["country_code"])

    for field_name in ("region", "district", "ward", "postal_code"):
        if field_name in updates:
            setattr(address, field_name, normalize_optional_text(updates[field_name]))

    next_latitude = updates.get("latitude", address.latitude)
    next_longitude = updates.get("longitude", address.longitude)
    validate_coordinates(next_latitude, next_longitude)
    if "latitude" in updates:
        address.latitude = updates["latitude"]
    if "longitude" in updates:
        address.longitude = updates["longitude"]

    _validate_meaningful_address(
        address_line1_encrypted=address.address_line1_encrypted,
        address_line2_encrypted=address.address_line2_encrypted,
        region=address.region,
        district=address.district,
        ward=address.ward,
        postal_code=address.postal_code,
        latitude=address.latitude,
    )

    if "is_primary" in updates:
        requested_primary = bool(updates["is_primary"])
        if requested_primary:
            _clear_other_primary_addresses(patient=address.patient, exclude_id=address.pk)
        address.is_primary = requested_primary

    try:
        address.save()
    except IntegrityError as exc:
        raise ConflictError("Patient address could not be updated because a unique value already exists.") from exc
    return address


@transaction.atomic
def deactivate_patient_address(*, address_id) -> PatientAddress:
    address = _get_address_for_update(address_id)
    if not address.is_active:
        return address
    if not address.patient.is_active:
        raise ValidationError("Patient must be active.")

    address.is_active = False
    address.is_primary = False
    address.save(update_fields=["is_active", "is_primary", "updated_at"])
    return address


@transaction.atomic
def set_primary_patient_address(*, address_id) -> PatientAddress:
    address = _get_address_for_update(address_id)
    if not address.is_active:
        raise ValidationError("Primary patient address must be active.")
    if not address.patient.is_active:
        raise ValidationError("Patient must be active.")

    _clear_other_primary_addresses(patient=address.patient, exclude_id=address.pk)
    if address.is_primary:
        return address

    address.is_primary = True
    address.save(update_fields=["is_primary", "updated_at"])
    return address
