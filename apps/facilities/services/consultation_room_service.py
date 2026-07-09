from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.facilities.models import ConsultationRoom
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    clean_optional_text,
    ensure_department_in_facility,
    get_consultation_room_for_update,
    get_department_for_update,
    get_facility_for_update,
    require_non_empty_name,
    require_positive_smallint,
)
from .code_generation import generate_unique_code, normalize_code_value


@transaction.atomic
def create_consultation_room(
    *,
    facility_id,
    name: str,
    code: str | None = None,
    department_id=None,
    location_description: str | None = None,
    floor: str | None = None,
    capacity: int = 1,
) -> ConsultationRoom:
    facility = get_facility_for_update(facility_id, require_active=True)
    department = get_department_for_update(department_id, require_active=True) if department_id else None
    ensure_department_in_facility(
        department=department,
        facility=facility,
        message="Consultation room department must belong to the same facility.",
    )
    cleaned_name = require_non_empty_name(value=name, label="Consultation room name")
    normalized_capacity = require_positive_smallint(value=capacity, label="Capacity")

    queryset = ConsultationRoom.objects.filter(facility=facility)
    if code is not None:
        normalized_code = normalize_code_value(code)
        if not normalized_code:
            raise ValidationError("Consultation room code cannot be empty.")
    else:
        normalized_code = generate_unique_code(model=ConsultationRoom, source_value=cleaned_name, queryset=queryset)

    if queryset.select_for_update().filter(code=normalized_code).exists():
        raise ConflictError("Consultation room code already exists in this facility.")

    try:
        return ConsultationRoom.objects.create(
            facility=facility,
            department=department,
            name=cleaned_name,
            code=normalized_code,
            location_description=clean_optional_text(location_description),
            floor=clean_optional_text(floor),
            capacity=normalized_capacity,
        )
    except IntegrityError as exc:
        raise ConflictError("Consultation room could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_consultation_room(
    *,
    consultation_room_id,
    regenerate_code: bool = False,
    **updates,
) -> ConsultationRoom:
    consultation_room = get_consultation_room_for_update(consultation_room_id)
    allowed_fields = {"facility_id", "department_id", "name", "code", "location_description", "floor", "capacity"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        raise ValidationError(f"Unsupported consultation room update fields: {', '.join(sorted(unexpected_fields))}.")

    facility = (
        get_facility_for_update(updates["facility_id"], require_active=True)
        if "facility_id" in updates
        else get_facility_for_update(consultation_room.facility_id, require_active=True)
    )
    department = (
        get_department_for_update(updates["department_id"], require_active=True)
        if "department_id" in updates and updates["department_id"] is not None
        else None if "department_id" in updates else consultation_room.department
    )
    ensure_department_in_facility(
        department=department,
        facility=facility,
        message="Consultation room department must belong to the same facility.",
    )

    next_name = consultation_room.name
    if "name" in updates:
        next_name = require_non_empty_name(value=updates["name"], label="Consultation room name")

    queryset = ConsultationRoom.objects.filter(facility=facility).exclude(pk=consultation_room.pk)
    if regenerate_code:
        next_code = generate_unique_code(model=ConsultationRoom, source_value=next_name, queryset=queryset)
    elif "code" in updates and updates["code"] is not None:
        next_code = normalize_code_value(updates["code"])
        if not next_code:
            raise ValidationError("Consultation room code cannot be empty.")
    else:
        next_code = consultation_room.code

    if queryset.select_for_update().filter(code=next_code).exists():
        raise ConflictError("Consultation room code already exists in this facility.")

    consultation_room.facility = facility
    consultation_room.department = department
    consultation_room.name = next_name
    consultation_room.code = next_code
    if "location_description" in updates:
        consultation_room.location_description = clean_optional_text(updates["location_description"])
    if "floor" in updates:
        consultation_room.floor = clean_optional_text(updates["floor"])
    if "capacity" in updates:
        consultation_room.capacity = require_positive_smallint(value=updates["capacity"], label="Capacity")

    try:
        consultation_room.save()
    except IntegrityError as exc:
        raise ConflictError("Consultation room could not be updated because a unique value already exists.") from exc
    return consultation_room


@transaction.atomic
def deactivate_consultation_room(*, consultation_room_id) -> ConsultationRoom:
    consultation_room = get_consultation_room_for_update(consultation_room_id)
    if not consultation_room.is_active:
        return consultation_room

    consultation_room.is_active = False
    consultation_room.save(update_fields=["is_active", "updated_at"])
    return consultation_room
