from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.practitioners.models import PractitionerDepartmentAssignment, PractitionerFacilityAssignment, PractitionerSpecialtyAssignment
from common.exceptions import ConflictError, NotFoundError, ValidationError

from ._shared import (
    get_facility,
    get_practitioner,
    get_practitioner_facility_assignment,
    get_user,
    validate_starts_ends,
)


def _get_assignment_for_update(assignment_id) -> PractitionerFacilityAssignment:
    try:
        return PractitionerFacilityAssignment.objects.select_for_update().select_related(
            "practitioner",
            "practitioner__organization",
            "facility",
            "facility__organization",
        ).get(pk=assignment_id)
    except PractitionerFacilityAssignment.DoesNotExist as exc:
        raise NotFoundError("Practitioner facility assignment not found.") from exc


def _validate_assignment_scope(*, practitioner, facility) -> None:
    if not practitioner.is_active:
        raise ValidationError("Practitioner must be active.")
    if not practitioner.organization.is_active:
        raise ValidationError("Practitioner organization must be active.")
    if not facility.is_active:
        raise ValidationError("Facility must be active.")
    if facility.organization_id != practitioner.organization_id:
        raise ValidationError("Facility must belong to the same organization as the practitioner.")


def _ensure_unique_assignment(*, practitioner, facility, exclude_id=None) -> None:
    queryset = PractitionerFacilityAssignment.objects.select_for_update().filter(
        practitioner=practitioner,
        facility=facility,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.exists():
        raise ConflictError("This practitioner is already assigned to the selected facility.")


def _clear_other_primary_assignments(*, practitioner, exclude_id=None) -> None:
    queryset = PractitionerFacilityAssignment.objects.select_for_update().filter(
        practitioner=practitioner,
        is_active=True,
        is_primary=True,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    queryset.update(is_primary=False, updated_at=timezone.now())


def _ensure_no_active_children(assignment: PractitionerFacilityAssignment) -> None:
    if PractitionerDepartmentAssignment.objects.select_for_update().filter(
        practitioner_facility_assignment=assignment,
        is_active=True,
    ).exists():
        raise ValidationError("Deactivate practitioner department assignments before deactivating the facility assignment.")
    if PractitionerSpecialtyAssignment.objects.select_for_update().filter(
        practitioner_facility_assignment=assignment,
        is_active=True,
    ).exists():
        raise ValidationError("Deactivate practitioner specialty assignments before deactivating the facility assignment.")


def _ensure_child_ranges_fit(*, assignment: PractitionerFacilityAssignment, starts_on, ends_on) -> None:
    dept_conflict = PractitionerDepartmentAssignment.objects.select_for_update().filter(
        practitioner_facility_assignment=assignment,
        is_active=True,
        starts_on__lt=starts_on,
    ).exists() or (
        ends_on is not None
        and PractitionerDepartmentAssignment.objects.select_for_update().filter(
            practitioner_facility_assignment=assignment,
            is_active=True,
        ).filter(ends_on__isnull=True).exists()
    ) or (
        ends_on is not None
        and PractitionerDepartmentAssignment.objects.select_for_update().filter(
            practitioner_facility_assignment=assignment,
            is_active=True,
            ends_on__gt=ends_on,
        ).exists()
    )
    if dept_conflict:
        raise ValidationError("Existing department assignments must remain within facility assignment dates.")

    specialty_conflict = PractitionerSpecialtyAssignment.objects.select_for_update().filter(
        practitioner_facility_assignment=assignment,
        is_active=True,
        starts_on__lt=starts_on,
    ).exists() or (
        ends_on is not None
        and PractitionerSpecialtyAssignment.objects.select_for_update().filter(
            practitioner_facility_assignment=assignment,
            is_active=True,
        ).filter(ends_on__isnull=True).exists()
    ) or (
        ends_on is not None
        and PractitionerSpecialtyAssignment.objects.select_for_update().filter(
            practitioner_facility_assignment=assignment,
            is_active=True,
            ends_on__gt=ends_on,
        ).exists()
    )
    if specialty_conflict:
        raise ValidationError("Existing specialty assignments must remain within facility assignment dates.")


@transaction.atomic
def assign_practitioner_to_facility(
    *,
    practitioner_id,
    facility_id,
    starts_on,
    ends_on=None,
    is_primary: bool = False,
    assigned_by_id=None,
) -> PractitionerFacilityAssignment:
    practitioner = get_practitioner(practitioner_id, active_only=True, for_update=True)
    facility = get_facility(facility_id, active_only=True, for_update=True)
    assigned_by = get_user(assigned_by_id, field_label="Assigning user", active_only=True) if assigned_by_id is not None else None

    validate_starts_ends(starts_on=starts_on, ends_on=ends_on, label="Practitioner facility assignment")
    _validate_assignment_scope(practitioner=practitioner, facility=facility)
    _ensure_unique_assignment(practitioner=practitioner, facility=facility)

    if is_primary:
        _clear_other_primary_assignments(practitioner=practitioner)

    try:
        return PractitionerFacilityAssignment.objects.create(
            practitioner=practitioner,
            facility=facility,
            starts_on=starts_on,
            ends_on=ends_on,
            is_primary=bool(is_primary),
            assigned_by=assigned_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Practitioner facility assignment could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_facility_assignment(*, assignment_id, **updates) -> PractitionerFacilityAssignment:
    assignment = _get_assignment_for_update(assignment_id)
    allowed_fields = {"facility_id", "starts_on", "ends_on", "is_primary"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported facility assignment update fields: {unexpected}.")
    if not assignment.is_active:
        raise ValidationError("Practitioner facility assignment must be active.")

    next_facility = assignment.facility
    if "facility_id" in updates:
        next_facility = get_facility(updates["facility_id"], active_only=True, for_update=True)

    next_starts_on = updates.get("starts_on", assignment.starts_on)
    next_ends_on = updates.get("ends_on", assignment.ends_on)
    validate_starts_ends(starts_on=next_starts_on, ends_on=next_ends_on, label="Practitioner facility assignment")
    _validate_assignment_scope(practitioner=assignment.practitioner, facility=next_facility)
    _ensure_unique_assignment(
        practitioner=assignment.practitioner,
        facility=next_facility,
        exclude_id=assignment.pk,
    )
    _ensure_child_ranges_fit(assignment=assignment, starts_on=next_starts_on, ends_on=next_ends_on)

    assignment.facility = next_facility
    assignment.starts_on = next_starts_on
    assignment.ends_on = next_ends_on

    if "is_primary" in updates:
        requested_primary = bool(updates["is_primary"])
        if requested_primary:
            _clear_other_primary_assignments(practitioner=assignment.practitioner, exclude_id=assignment.pk)
        assignment.is_primary = requested_primary

    try:
        assignment.save()
    except IntegrityError as exc:
        raise ConflictError("Practitioner facility assignment could not be updated because a unique value already exists.") from exc
    return assignment


@transaction.atomic
def deactivate_facility_assignment(*, assignment_id) -> PractitionerFacilityAssignment:
    assignment = _get_assignment_for_update(assignment_id)
    if not assignment.is_active:
        return assignment
    if not assignment.practitioner.is_active:
        raise ValidationError("Practitioner must be active.")
    _ensure_no_active_children(assignment)
    assignment.is_active = False
    assignment.is_primary = False
    assignment.save(update_fields=["is_active", "is_primary", "updated_at"])
    return assignment


@transaction.atomic
def set_primary_facility_assignment(*, assignment_id) -> PractitionerFacilityAssignment:
    assignment = _get_assignment_for_update(assignment_id)
    if not assignment.is_active:
        raise ValidationError("Primary practitioner facility assignment must be active.")
    if not assignment.practitioner.is_active:
        raise ValidationError("Practitioner must be active.")
    _clear_other_primary_assignments(practitioner=assignment.practitioner, exclude_id=assignment.pk)
    if assignment.is_primary:
        return assignment
    assignment.is_primary = True
    assignment.save(update_fields=["is_primary", "updated_at"])
    return assignment
