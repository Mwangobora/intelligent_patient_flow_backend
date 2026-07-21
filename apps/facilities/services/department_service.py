from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.facilities.models import Department
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    clean_optional_text,
    ensure_parent_department_valid,
    get_department_for_update,
    get_facility_for_update,
    require_non_empty_name,
)
from .code_generation import generate_unique_code


@transaction.atomic
def create_department(
    *,
    facility_id,
    name: str,
    code: str | None = None,
    description: str | None = None,
    parent_department_id=None,
) -> Department:
    facility = get_facility_for_update(facility_id, require_active=True)
    cleaned_name = require_non_empty_name(value=name, label="Department name")
    parent_department = get_department_for_update(parent_department_id) if parent_department_id else None
    ensure_parent_department_valid(parent_department=parent_department, facility=facility)

    queryset = Department.objects.filter(facility=facility)
    normalized_code = generate_unique_code(model=Department, source_value=cleaned_name, queryset=queryset)

    if queryset.select_for_update().filter(code=normalized_code).exists():
        raise ConflictError("Department code already exists in this facility.")

    try:
        return Department.objects.create(
            facility=facility,
            parent_department=parent_department,
            name=cleaned_name,
            code=normalized_code,
            description=clean_optional_text(description),
        )
    except IntegrityError as exc:
        raise ConflictError("Department could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_department(
    *,
    department_id,
    regenerate_code: bool = False,
    **updates,
) -> Department:
    department = get_department_for_update(department_id)
    allowed_fields = {"facility_id", "parent_department_id", "name", "description"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        raise ValidationError(f"Unsupported department update fields: {', '.join(sorted(unexpected_fields))}.")

    facility = (
        get_facility_for_update(updates["facility_id"], require_active=True)
        if "facility_id" in updates
        else get_facility_for_update(department.facility_id, require_active=True)
    )
    parent_department = (
        get_department_for_update(updates["parent_department_id"])
        if "parent_department_id" in updates and updates["parent_department_id"] is not None
        else None if "parent_department_id" in updates else department.parent_department
    )

    next_name = department.name
    if "name" in updates:
        next_name = require_non_empty_name(value=updates["name"], label="Department name")

    ensure_parent_department_valid(
        department_id=department.id,
        parent_department=parent_department,
        facility=facility,
    )

    queryset = Department.objects.filter(facility=facility).exclude(pk=department.pk)
    next_code = department.code

    if queryset.select_for_update().filter(code=next_code).exists():
        raise ConflictError("Department code already exists in this facility.")

    department.facility = facility
    department.parent_department = parent_department
    department.name = next_name
    department.code = next_code
    if "description" in updates:
        department.description = clean_optional_text(updates["description"])

    try:
        department.save()
    except IntegrityError as exc:
        raise ConflictError("Department could not be updated because a unique value already exists.") from exc
    return department


@transaction.atomic
def deactivate_department(*, department_id) -> Department:
    department = get_department_for_update(department_id)
    if not department.is_active:
        return department

    department.is_active = False
    department.save(update_fields=["is_active", "updated_at"])
    return department
