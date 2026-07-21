from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.facilities.models import ServicePoint
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    clean_optional_text,
    ensure_department_in_facility,
    get_department_for_update,
    get_facility_for_update,
    get_service_point_for_update,
    get_service_point_type_for_update,
    require_non_empty_name,
    require_positive_smallint,
)
from .code_generation import generate_unique_code


@transaction.atomic
def create_service_point(
    *,
    facility_id,
    service_point_type_id,
    name: str,
    code: str | None = None,
    department_id=None,
    location_description: str | None = None,
    floor: str | None = None,
    display_order: int = 0,
) -> ServicePoint:
    facility = get_facility_for_update(facility_id, require_active=True)
    service_point_type = get_service_point_type_for_update(service_point_type_id, require_active=True)
    department = get_department_for_update(department_id, require_active=True) if department_id else None
    ensure_department_in_facility(
        department=department,
        facility=facility,
        message="Service point department must belong to the same facility.",
    )
    cleaned_name = require_non_empty_name(value=name, label="Service point name")
    normalized_display_order = require_positive_smallint(
        value=display_order,
        label="Display order",
        allow_zero=True,
    )

    queryset = ServicePoint.objects.filter(facility=facility)
    normalized_code = generate_unique_code(model=ServicePoint, source_value=cleaned_name, queryset=queryset)

    if queryset.select_for_update().filter(code=normalized_code).exists():
        raise ConflictError("Service point code already exists in this facility.")

    try:
        return ServicePoint.objects.create(
            facility=facility,
            department=department,
            service_point_type=service_point_type,
            name=cleaned_name,
            code=normalized_code,
            location_description=clean_optional_text(location_description),
            floor=clean_optional_text(floor),
            display_order=normalized_display_order,
        )
    except IntegrityError as exc:
        raise ConflictError("Service point could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_service_point(
    *,
    service_point_id,
    regenerate_code: bool = False,
    **updates,
) -> ServicePoint:
    service_point = get_service_point_for_update(service_point_id)
    allowed_fields = {
        "facility_id",
        "department_id",
        "service_point_type_id",
        "name",
        "location_description",
        "floor",
        "display_order",
    }
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        raise ValidationError(f"Unsupported service point update fields: {', '.join(sorted(unexpected_fields))}.")

    facility = (
        get_facility_for_update(updates["facility_id"], require_active=True)
        if "facility_id" in updates
        else get_facility_for_update(service_point.facility_id, require_active=True)
    )
    department = (
        get_department_for_update(updates["department_id"], require_active=True)
        if "department_id" in updates and updates["department_id"] is not None
        else None if "department_id" in updates else service_point.department
    )
    ensure_department_in_facility(
        department=department,
        facility=facility,
        message="Service point department must belong to the same facility.",
    )

    if "service_point_type_id" in updates:
        service_point.service_point_type = get_service_point_type_for_update(updates["service_point_type_id"], require_active=True)

    next_name = service_point.name
    if "name" in updates:
        next_name = require_non_empty_name(value=updates["name"], label="Service point name")

    queryset = ServicePoint.objects.filter(facility=facility).exclude(pk=service_point.pk)
    next_code = service_point.code

    if queryset.select_for_update().filter(code=next_code).exists():
        raise ConflictError("Service point code already exists in this facility.")

    service_point.facility = facility
    service_point.department = department
    service_point.name = next_name
    service_point.code = next_code
    if "location_description" in updates:
        service_point.location_description = clean_optional_text(updates["location_description"])
    if "floor" in updates:
        service_point.floor = clean_optional_text(updates["floor"])
    if "display_order" in updates:
        service_point.display_order = require_positive_smallint(
            value=updates["display_order"],
            label="Display order",
            allow_zero=True,
        )

    try:
        service_point.save()
    except IntegrityError as exc:
        raise ConflictError("Service point could not be updated because a unique value already exists.") from exc
    return service_point


@transaction.atomic
def deactivate_service_point(*, service_point_id) -> ServicePoint:
    service_point = get_service_point_for_update(service_point_id)
    if not service_point.is_active:
        return service_point

    service_point.is_active = False
    service_point.save(update_fields=["is_active", "updated_at"])
    return service_point
