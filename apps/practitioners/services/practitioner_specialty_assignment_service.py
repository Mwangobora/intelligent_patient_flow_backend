from __future__ import annotations

from django.db import models
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.practitioners.models import PractitionerDepartmentAssignment, PractitionerSpecialtyAssignment
from common.exceptions import ConflictError, NotFoundError, ValidationError

from ._shared import (
    get_facility_specialty,
    get_practitioner_facility_assignment,
    get_user,
    validate_starts_ends,
    validate_within_parent_range,
)


def _get_assignment_for_update(assignment_id) -> PractitionerSpecialtyAssignment:
    try:
        return PractitionerSpecialtyAssignment.objects.select_for_update().select_related(
            "practitioner_facility_assignment",
            "practitioner_facility_assignment__practitioner",
            "practitioner_facility_assignment__facility",
            "facility_specialty",
            "facility_specialty__facility",
            "facility_specialty__department",
            "facility_specialty__specialty",
        ).get(pk=assignment_id)
    except PractitionerSpecialtyAssignment.DoesNotExist as exc:
        raise NotFoundError("Practitioner specialty assignment not found.") from exc


def _has_department_coverage(*, practitioner_facility_assignment, facility_specialty, starts_on, ends_on) -> bool:
    if facility_specialty.department_id is None:
        return True
    queryset = PractitionerDepartmentAssignment.objects.select_for_update().filter(
        practitioner_facility_assignment=practitioner_facility_assignment,
        department_id=facility_specialty.department_id,
        is_active=True,
        starts_on__lte=starts_on,
    )
    if ends_on is None:
        queryset = queryset.filter(ends_on__isnull=True)
    else:
        queryset = queryset.filter(models.Q(ends_on__isnull=True) | models.Q(ends_on__gte=ends_on))
    return queryset.exists()


def _validate_scope(*, practitioner_facility_assignment, facility_specialty, starts_on, ends_on) -> None:
    if not practitioner_facility_assignment.is_active:
        raise ValidationError("Practitioner facility assignment must be active.")
    if not practitioner_facility_assignment.practitioner.is_active:
        raise ValidationError("Practitioner must be active.")
    if not facility_specialty.is_active:
        raise ValidationError("Facility specialty must be active.")
    if facility_specialty.facility_id != practitioner_facility_assignment.facility_id:
        raise ValidationError("Facility specialty must belong to the same facility as the practitioner facility assignment.")
    validate_starts_ends(starts_on=starts_on, ends_on=ends_on, label="Practitioner specialty assignment")
    validate_within_parent_range(
        child_start=starts_on,
        child_end=ends_on,
        parent_start=practitioner_facility_assignment.starts_on,
        parent_end=practitioner_facility_assignment.ends_on,
        label="Practitioner specialty assignment",
    )
    if facility_specialty.department_id is not None and not _has_department_coverage(
        practitioner_facility_assignment=practitioner_facility_assignment,
        facility_specialty=facility_specialty,
        starts_on=starts_on,
        ends_on=ends_on,
    ):
        raise ValidationError("Department assignment must cover the full specialty-assignment period.")


def _ensure_unique_assignment(*, practitioner_facility_assignment, facility_specialty, exclude_id=None) -> None:
    queryset = PractitionerSpecialtyAssignment.objects.select_for_update().filter(
        practitioner_facility_assignment=practitioner_facility_assignment,
        facility_specialty=facility_specialty,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.exists():
        raise ConflictError("This practitioner is already assigned to the selected facility specialty for the facility assignment.")


def _clear_other_primary_assignments(*, practitioner_facility_assignment, exclude_id=None) -> None:
    queryset = PractitionerSpecialtyAssignment.objects.select_for_update().filter(
        practitioner_facility_assignment=practitioner_facility_assignment,
        is_active=True,
        is_primary=True,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    queryset.update(is_primary=False, updated_at=timezone.now())


@transaction.atomic
def assign_practitioner_to_specialty(
    *,
    practitioner_facility_assignment_id,
    facility_specialty_id,
    starts_on,
    ends_on=None,
    is_primary: bool = False,
    assigned_by_id=None,
) -> PractitionerSpecialtyAssignment:
    practitioner_facility_assignment = get_practitioner_facility_assignment(
        practitioner_facility_assignment_id,
        active_only=True,
        for_update=True,
    )
    facility_specialty = get_facility_specialty(facility_specialty_id, active_only=True, for_update=True)
    assigned_by = get_user(assigned_by_id, field_label="Assigning user", active_only=True) if assigned_by_id is not None else None

    _validate_scope(
        practitioner_facility_assignment=practitioner_facility_assignment,
        facility_specialty=facility_specialty,
        starts_on=starts_on,
        ends_on=ends_on,
    )
    _ensure_unique_assignment(
        practitioner_facility_assignment=practitioner_facility_assignment,
        facility_specialty=facility_specialty,
    )

    if is_primary:
        _clear_other_primary_assignments(practitioner_facility_assignment=practitioner_facility_assignment)

    try:
        return PractitionerSpecialtyAssignment.objects.create(
            practitioner_facility_assignment=practitioner_facility_assignment,
            facility_specialty=facility_specialty,
            starts_on=starts_on,
            ends_on=ends_on,
            is_primary=bool(is_primary),
            assigned_by=assigned_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Practitioner specialty assignment could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_specialty_assignment(*, assignment_id, **updates) -> PractitionerSpecialtyAssignment:
    assignment = _get_assignment_for_update(assignment_id)
    allowed_fields = {"facility_specialty_id", "starts_on", "ends_on", "is_primary"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported specialty assignment update fields: {unexpected}.")
    if not assignment.is_active:
        raise ValidationError("Practitioner specialty assignment must be active.")

    next_facility_specialty = assignment.facility_specialty
    if "facility_specialty_id" in updates:
        next_facility_specialty = get_facility_specialty(updates["facility_specialty_id"], active_only=True, for_update=True)

    next_starts_on = updates.get("starts_on", assignment.starts_on)
    next_ends_on = updates.get("ends_on", assignment.ends_on)
    _validate_scope(
        practitioner_facility_assignment=assignment.practitioner_facility_assignment,
        facility_specialty=next_facility_specialty,
        starts_on=next_starts_on,
        ends_on=next_ends_on,
    )
    _ensure_unique_assignment(
        practitioner_facility_assignment=assignment.practitioner_facility_assignment,
        facility_specialty=next_facility_specialty,
        exclude_id=assignment.pk,
    )

    assignment.facility_specialty = next_facility_specialty
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
        raise ConflictError("Practitioner specialty assignment could not be updated because a unique value already exists.") from exc
    return assignment


@transaction.atomic
def deactivate_specialty_assignment(*, assignment_id) -> PractitionerSpecialtyAssignment:
    assignment = _get_assignment_for_update(assignment_id)
    if not assignment.is_active:
        return assignment
    if not assignment.practitioner_facility_assignment.is_active:
        raise ValidationError("Practitioner facility assignment must be active.")
    assignment.is_active = False
    assignment.is_primary = False
    assignment.save(update_fields=["is_active", "is_primary", "updated_at"])
    return assignment


@transaction.atomic
def set_primary_specialty_assignment(*, assignment_id) -> PractitionerSpecialtyAssignment:
    assignment = _get_assignment_for_update(assignment_id)
    if not assignment.is_active:
        raise ValidationError("Primary practitioner specialty assignment must be active.")
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
