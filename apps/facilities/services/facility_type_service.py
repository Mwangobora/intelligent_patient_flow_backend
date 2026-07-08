from __future__ import annotations

from django.db import transaction

from apps.facilities.models import FacilityType
from common.exceptions import ConflictError, NotFoundError, ValidationError

from .code_generation import generate_unique_code, normalize_code_value


def _get_facility_type_for_update(facility_type_id) -> FacilityType:
    try:
        return FacilityType.objects.select_for_update().get(pk=facility_type_id)
    except FacilityType.DoesNotExist as exc:
        raise NotFoundError("Facility type not found.") from exc


@transaction.atomic
def create_facility_type(
    *,
    name: str,
    description: str | None = None,
    code: str | None = None,
) -> FacilityType:
    if not name or not name.strip():
        raise ValidationError("Facility type name is required.")

    normalized_code = normalize_code_value(code) if code else generate_unique_code(
        model=FacilityType,
        source_value=name,
    )
    if FacilityType.objects.select_for_update().filter(code=normalized_code).exists():
        raise ConflictError("Facility type code already exists.")

    return FacilityType.objects.create(
        name=name.strip(),
        description=description.strip() if description else None,
        code=normalized_code,
    )


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
        facility_type.name = updates["name"].strip()

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

    facility_type.save()
    return facility_type


@transaction.atomic
def deactivate_facility_type(*, facility_type_id) -> FacilityType:
    facility_type = _get_facility_type_for_update(facility_type_id)
    if not facility_type.is_active:
        return facility_type

    facility_type.is_active = False
    facility_type.save(update_fields=["is_active", "updated_at"])
    return facility_type
