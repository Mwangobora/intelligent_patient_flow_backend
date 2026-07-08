from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.facilities.models import FacilityType
from common.exceptions import ConflictError, NotFoundError, ValidationError

from .code_generation import generate_unique_code, normalize_code_value


def _get_facility_type_for_update(facility_type_id) -> FacilityType:
    try:
        return FacilityType.objects.select_for_update().get(pk=facility_type_id)
    except FacilityType.DoesNotExist as exc:
        raise NotFoundError("Facility type not found.") from exc


def _ensure_unique_name(*, name: str, exclude_id=None) -> None:
    queryset = FacilityType.objects.select_for_update()
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    if queryset.filter(name__iexact=name).exists():
        raise ConflictError("Facility type name already exists.")


@transaction.atomic
def create_facility_type(
    *,
    name: str,
    description: str | None = None,
    code: str | None = None,
) -> FacilityType:
    if not name or not name.strip():
        raise ValidationError("Facility type name is required.")
    cleaned_name = name.strip()

    _ensure_unique_name(name=cleaned_name)

    if code is not None:
        normalized_code = normalize_code_value(code)
        if not normalized_code:
            raise ValidationError("Facility type code cannot be empty.")
    else:
        normalized_code = generate_unique_code(
            model=FacilityType,
            source_value=cleaned_name,
        )
    if FacilityType.objects.select_for_update().filter(code=normalized_code).exists():
        raise ConflictError("Facility type code already exists.")

    try:
        return FacilityType.objects.create(
            name=cleaned_name,
            description=description.strip() if description else None,
            code=normalized_code,
        )
    except IntegrityError as exc:
        raise ConflictError("Facility type could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_facility_type(
    *,
    facility_type_id,
    regenerate_code: bool = False,
    **updates,
) -> FacilityType:
    facility_type = _get_facility_type_for_update(facility_type_id)

    allowed_fields = {"name", "description", "code"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported facility type update fields: {unexpected}.")

    if "name" in updates:
        if not updates["name"] or not updates["name"].strip():
            raise ValidationError("Facility type name is required.")
        cleaned_name = updates["name"].strip()
        _ensure_unique_name(name=cleaned_name, exclude_id=facility_type.pk)
        facility_type.name = cleaned_name

    if "description" in updates:
        facility_type.description = updates["description"].strip() if updates["description"] else None

    if regenerate_code:
        facility_type.code = generate_unique_code(
            model=FacilityType,
            source_value=facility_type.name,
            queryset=FacilityType.objects.exclude(pk=facility_type.pk),
        )
    elif "code" in updates and updates["code"] is not None:
        normalized_code = normalize_code_value(updates["code"])
        if not normalized_code:
            raise ValidationError("Facility type code cannot be empty.")
        if FacilityType.objects.select_for_update().exclude(pk=facility_type.pk).filter(code=normalized_code).exists():
            raise ConflictError("Facility type code already exists.")
        facility_type.code = normalized_code

    try:
        facility_type.save()
    except IntegrityError as exc:
        raise ConflictError("Facility type could not be updated because a unique value already exists.") from exc
    return facility_type


@transaction.atomic
def deactivate_facility_type(*, facility_type_id) -> FacilityType:
    facility_type = _get_facility_type_for_update(facility_type_id)
    if not facility_type.is_active:
        return facility_type

    facility_type.is_active = False
    facility_type.save(update_fields=["is_active", "updated_at"])
    return facility_type
