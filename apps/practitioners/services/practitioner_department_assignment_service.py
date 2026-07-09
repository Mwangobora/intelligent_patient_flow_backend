from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.practitioners.models import PractitionerDepartmentAssignment, PractitionerSpecialtyAssignment
from common.exceptions import ConflictError, NotFoundError, ValidationError

from ._shared import (
    get_department,
    get_practitioner_department_assignment,
    get_practitioner_facility_assignment,
    get_user,
    validate_starts_ends,
    validate_within_parent_range,
)


def _get_assignment_for_update(assignment_id) -> PractitionerDepartmentAssignment:
    try:
        return PractitionerDepartmentAssignment.objects.select_for_update().select_related(
            "practitioner_facility_assignment",
            "practitioner_facility_assignment__practitioner",
            "practitioner_facility_assignment__facility",
            "department",
            "department__facility",
        ).get(pk=assignment_id)
    except PractitionerDepartmentAssignment.DoesNotExist as exc:
        raise NotFoundError("Practitioner department assignment not found.") from exc


def _validate_scope(*, practitioner_facility_assignment, department, starts_on, ends_on) -> None:
    if not practitioner_facility_assignment.is_active:
        raise ValidationError("Practitioner facility assignment must be active.")
    if not practitioner_facility_assignment.practitioner.is_active:
        raise ValidationError("Practitioner must be active.")
    if not department.is_active:
        raise ValidationError("Department must be active.")
    if department.facility_id != practitioner_facility_assignment.facility_id:
        raise ValidationError("Department must belong to the same facility as the practitioner facility assignment.")
    validate_starts_ends(starts_on=starts_on, ends_on=ends_on, label="Practitioner department assignment")
    validate_within_parent_range(
        child_start=starts_on,
        child_end=ends_on,
        parent_start=practitioner_facility_assignment.starts_on,
        parent_end=practitioner_facility_assignment.ends_on,
        label="Practitioner department assignment",
    )


def _ensure_unique_assignment(*, practitioner_facility_assignment, department, exclude_id=None) -> None:
    queryset = PractitionerDepartmentAssignment.objects.select_for_update().filter(
        practitioner_facility_assignment=practitioner_facility_assignment,
        department=department,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.exists():
        raise ConflictError("This practitioner is already assigned to the selected department for the facility assignment.")


def _clear_other_primary_assignments(*, practitioner_facility_assignment, exclude_id=None) -> None:
    queryset = PractitionerDepartmentAssignment.objects.select_for_update().filter(
        practitioner_facility_assignment=practitioner_facility_assignment,
        is_active=True,
        is_primary=True,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    queryset.update(is_primary=False, updated_at=timezone.now())


def _ensure_specialty_coverage_not_broken(*, assignment: PractitionerDepartmentAssignment, starts_on, ends_on) -> None:
    specialty_assignments = PractitionerSpecialtyAssignment.objects.select_for_update().select_related(
        "facility_specialty",
    ).filter(
        practitioner_facility_assignment=assignment.practitioner_facility_assignment,
        facility_specialty__department_id=assignment.department_id,
        is_active=True,
    )
    for specialty_assignment in specialty_assignments:
        if specialty_assignment.starts_on < starts_on:
            raise ValidationError("Department assignment must cover the full specialty-assignment period.")
        if ends_on is None:
            continue
        if specialty_assignment.ends_on is None or specialty_assignment.ends_on > ends_on:
            raise ValidationError("Department assignment must cover the full specialty-assignment period.")


@transaction.atomic
def assign_practitioner_to_department(
    *,
    practitioner_facility_assignment_id,
    department_id,
    starts_on,
    ends_on=None,
    is_primary: bool = False,
    assigned_by_id=None,
) -> PractitionerDepartmentAssignment:
    practitioner_facility_assignment = get_practitioner_facility_assignment(
        practitioner_facility_assignment_id,
        active_only=True,
        for_update=True,
    )
    department = get_department(department_id, active_only=True, for_update=True)
    assigned_by = get_user(assigned_by_id, field_label="Assigning user", active_only=True) if assigned_by_id is not None else None

    _validate_scope(
        practitioner_facility_assignment=practitioner_facility_assignment,
        department=department,
        starts_on=starts_on,
        ends_on=ends_on,
    )
    _ensure_unique_assignment(
        practitioner_facility_assignment=practitioner_facility_assignment,
        department=department,
    )

    if is_primary:
        _clear_other_primary_assignments(practitioner_facility_assignment=practitioner_facility_assignment)

    try:
        return PractitionerDepartmentAssignment.objects.create(
            practitioner_facility_assignment=practitioner_facility_assignment,
            department=department,
            starts_on=starts_on,
            ends_on=ends_on,
            is_primary=bool(is_primary),
            assigned_by=assigned_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Practitioner department assignment could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_department_assignment(*, assignment_id, **updates) -> PractitionerDepartmentAssignment:
    assignment = _get_assignment_for_update(assignment_id)
    allowed_fields = {"department_id", "starts_on", "ends_on", "is_primary"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported department assignment update fields: {unexpected}.")
    if not assignment.is_active:
        raise ValidationError("Practitioner department assignment must be active.")

    next_department = assignment.department
    if "department_id" in updates:
        next_department = get_department(updates["department_id"], active_only=True, for_update=True)

    next_starts_on = updates.get("starts_on", assignment.starts_on)
    next_ends_on = updates.get("ends_on", assignment.ends_on)
    _validate_scope(
        practitioner_facility_assignment=assignment.practitioner_facility_assignment,
        department=next_department,
        starts_on=next_starts_on,
        ends_on=next_ends_on,
    )
    _ensure_unique_assignment(
        practitioner_facility_assignment=assignment.practitioner_facility_assignment,
        department=next_department,
        exclude_id=assignment.pk,
    )
    _ensure_specialty_coverage_not_broken(assignment=assignment, starts_on=next_starts_on, ends_on=next_ends_on)

    assignment.department = next_department
    assignment.starts_on = next_starts_on
    assignment.ends_on = next_ends_on

    if "is_primary" in updates:
        requested_primary = bool(updates["is_primary"])
        if requested_primary:
            _clear_other_primary_assignments(
                practitioner_facility_assignment=assignment.practitioner_facility_assignment,
                exclude_id=assignment.pk,
            )
        assignment.is_primary = requested_primary

    try:
        assignment.save()
    except IntegrityError as exc:
        raise ConflictError("Practitioner department assignment could not be updated because a unique value already exists.") from exc
    return assignment


@transaction.atomic
def deactivate_department_assignment(*, assignment_id) -> PractitionerDepartmentAssignment:
    assignment = _get_assignment_for_update(assignment_id)
    if not assignment.is_active:
        return assignment
    if not assignment.practitioner_facility_assignment.is_active:
        raise ValidationError("Practitioner facility assignment must be active.")
    _ensure_specialty_coverage_not_broken(assignment=assignment, starts_on=assignment.starts_on, ends_on=assignment.ends_on)
    specialty_exists = PractitionerSpecialtyAssignment.objects.select_for_update().filter(
        practitioner_facility_assignment=assignment.practitioner_facility_assignment,
        facility_specialty__department_id=assignment.department_id,
        is_active=True,
    ).exists()
    if specialty_exists:
        raise ValidationError("Deactivate dependent specialty assignments before deactivating the department assignment.")
    assignment.is_active = False
    assignment.is_primary = False
    assignment.save(update_fields=["is_active", "is_primary", "updated_at"])
    return assignment


@transaction.atomic
def set_primary_department_assignment(*, assignment_id) -> PractitionerDepartmentAssignment:
    assignment = _get_assignment_for_update(assignment_id)
    if not assignment.is_active:
        raise ValidationError("Primary practitioner department assignment must be active.")
    if not assignment.practitioner_facility_assignment.is_active:
        raise ValidationError("Practitioner facility assignment must be active.")
    _clear_other_primary_assignments(
        practitioner_facility_assignment=assignment.practitioner_facility_assignment,
        exclude_id=assignment.pk,
    )
    if assignment.is_primary:
        return assignment
    assignment.is_primary = True
    assignment.save(update_fields=["is_primary", "updated_at"])
    return assignment
