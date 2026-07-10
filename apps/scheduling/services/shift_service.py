from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.scheduling.models import PractitionerShift
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    ensure_not_on_approved_leave,
    ensure_within_assignment_dates,
    get_consultation_room,
    get_practitioner_department_assignment,
    get_practitioner_facility_assignment,
    get_service_point,
    get_shift,
    get_user,
    normalize_optional_text,
    to_local_date,
    validate_datetime_range,
)


def _validate_shift_scope(
    *,
    practitioner_facility_assignment,
    practitioner_department_assignment,
    service_point,
    consultation_room,
    starts_at,
    ends_at,
) -> None:
    if not practitioner_facility_assignment.is_active:
        raise ValidationError("Practitioner facility assignment must be active.")
    validate_datetime_range(starts_at=starts_at, ends_at=ends_at, label="Practitioner shift")
    ensure_within_assignment_dates(
        facility=practitioner_facility_assignment.facility,
        starts_at=starts_at,
        ends_at=ends_at,
        assignment=practitioner_facility_assignment,
        label="Shift",
    )
    department = None
    if practitioner_department_assignment is not None:
        if not practitioner_department_assignment.is_active:
            raise ValidationError("Practitioner department assignment must be active.")
        if practitioner_department_assignment.practitioner_facility_assignment_id != practitioner_facility_assignment.id:
            raise ValidationError("Department assignment must belong to the same practitioner facility assignment.")
        department = practitioner_department_assignment.department

    if service_point is not None:
        if not service_point.is_active:
            raise ValidationError("Service point must be active.")
        if service_point.facility_id != practitioner_facility_assignment.facility_id:
            raise ValidationError("Service point must belong to the same facility.")
        if department is not None and service_point.department_id is not None and service_point.department_id != department.id:
            raise ValidationError("Service point department must match practitioner department assignment.")

    if consultation_room is not None:
        if not consultation_room.is_active:
            raise ValidationError("Consultation room must be active.")
        if consultation_room.facility_id != practitioner_facility_assignment.facility_id:
            raise ValidationError("Consultation room must belong to the same facility.")
        if department is not None and consultation_room.department_id is not None and consultation_room.department_id != department.id:
            raise ValidationError("Consultation room department must match practitioner department assignment.")


def _validate_department_assignment_dates(*, practitioner_facility_assignment, practitioner_department_assignment, starts_at, ends_at) -> None:
    if practitioner_department_assignment is None:
        return
    facility = practitioner_facility_assignment.facility
    local_start_date = to_local_date(facility=facility, value=starts_at)
    local_end_date = to_local_date(facility=facility, value=ends_at)
    if practitioner_department_assignment.starts_on > local_start_date:
        raise ValidationError("Department assignment must cover the full shift period.")
    if practitioner_department_assignment.ends_on is not None and practitioner_department_assignment.ends_on < local_end_date:
        raise ValidationError("Department assignment must cover the full shift period.")


def _ensure_no_shift_overlap(*, practitioner_facility_assignment, starts_at, ends_at, exclude_id=None) -> None:
    practitioner_id = practitioner_facility_assignment.practitioner_id
    queryset = PractitionerShift.objects.select_for_update().filter(
        practitioner_facility_assignment__practitioner_id=practitioner_id,
    ).exclude(status=PractitionerShift.Status.CANCELLED)
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.filter(starts_at__lt=ends_at, ends_at__gt=starts_at).exists():
        raise ConflictError("Practitioner cannot have overlapping shifts across facilities.")


def _ensure_no_room_overlap(*, consultation_room, starts_at, ends_at, exclude_id=None) -> None:
    if consultation_room is None:
        return
    queryset = PractitionerShift.objects.select_for_update().filter(
        consultation_room=consultation_room,
    ).exclude(status=PractitionerShift.Status.CANCELLED)
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.filter(starts_at__lt=ends_at, ends_at__gt=starts_at).exists():
        raise ConflictError("Consultation room is already allocated for an overlapping shift.")


@transaction.atomic
def create_practitioner_shift(
    *,
    practitioner_facility_assignment_id,
    starts_at,
    ends_at,
    practitioner_department_assignment_id=None,
    service_point_id=None,
    consultation_room_id=None,
    accepts_appointments: bool = True,
    notes: str | None = None,
    created_by_id=None,
) -> PractitionerShift:
    practitioner_facility_assignment = get_practitioner_facility_assignment(
        practitioner_facility_assignment_id,
        active_only=True,
        for_update=True,
    )
    practitioner_department_assignment = (
        get_practitioner_department_assignment(
            practitioner_department_assignment_id,
            active_only=True,
            for_update=True,
        )
        if practitioner_department_assignment_id is not None
        else None
    )
    service_point = get_service_point(service_point_id, active_only=True, for_update=True) if service_point_id is not None else None
    consultation_room = (
        get_consultation_room(consultation_room_id, active_only=True, for_update=True)
        if consultation_room_id is not None
        else None
    )
    created_by = get_user(created_by_id, field_label="Creator user", active_only=True) if created_by_id is not None else None

    _validate_shift_scope(
        practitioner_facility_assignment=practitioner_facility_assignment,
        practitioner_department_assignment=practitioner_department_assignment,
        service_point=service_point,
        consultation_room=consultation_room,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    _validate_department_assignment_dates(
        practitioner_facility_assignment=practitioner_facility_assignment,
        practitioner_department_assignment=practitioner_department_assignment,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    ensure_not_on_approved_leave(
        practitioner_facility_assignment=practitioner_facility_assignment,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    _ensure_no_shift_overlap(
        practitioner_facility_assignment=practitioner_facility_assignment,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    _ensure_no_room_overlap(
        consultation_room=consultation_room,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    try:
        return PractitionerShift.objects.create(
            practitioner_facility_assignment=practitioner_facility_assignment,
            practitioner_department_assignment=practitioner_department_assignment,
            service_point=service_point,
            consultation_room=consultation_room,
            starts_at=starts_at,
            ends_at=ends_at,
            accepts_appointments=bool(accepts_appointments),
            notes=normalize_optional_text(notes),
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Practitioner shift could not be created because a conflicting record already exists.") from exc


@transaction.atomic
def update_practitioner_shift(*, shift_id, **updates) -> PractitionerShift:
    shift = get_shift(shift_id, for_update=True)
    if shift.status != PractitionerShift.Status.SCHEDULED:
        raise ValidationError("Only scheduled shifts can be updated.")
    allowed_fields = {
        "starts_at",
        "ends_at",
        "practitioner_department_assignment_id",
        "service_point_id",
        "consultation_room_id",
        "accepts_appointments",
        "notes",
    }
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        raise ValidationError(f"Unsupported shift update fields: {', '.join(sorted(unexpected_fields))}.")

    practitioner_department_assignment = (
        get_practitioner_department_assignment(
            updates["practitioner_department_assignment_id"],
            active_only=True,
            for_update=True,
        )
        if "practitioner_department_assignment_id" in updates and updates["practitioner_department_assignment_id"] is not None
        else shift.practitioner_department_assignment
    )
    if "practitioner_department_assignment_id" in updates and updates["practitioner_department_assignment_id"] is None:
        practitioner_department_assignment = None

    service_point = get_service_point(updates["service_point_id"], active_only=True, for_update=True) if "service_point_id" in updates and updates["service_point_id"] is not None else shift.service_point
    if "service_point_id" in updates and updates["service_point_id"] is None:
        service_point = None

    consultation_room = (
        get_consultation_room(updates["consultation_room_id"], active_only=True, for_update=True)
        if "consultation_room_id" in updates and updates["consultation_room_id"] is not None
        else shift.consultation_room
    )
    if "consultation_room_id" in updates and updates["consultation_room_id"] is None:
        consultation_room = None

    next_starts_at = updates.get("starts_at", shift.starts_at)
    next_ends_at = updates.get("ends_at", shift.ends_at)
    _validate_shift_scope(
        practitioner_facility_assignment=shift.practitioner_facility_assignment,
        practitioner_department_assignment=practitioner_department_assignment,
        service_point=service_point,
        consultation_room=consultation_room,
        starts_at=next_starts_at,
        ends_at=next_ends_at,
    )
    _validate_department_assignment_dates(
        practitioner_facility_assignment=shift.practitioner_facility_assignment,
        practitioner_department_assignment=practitioner_department_assignment,
        starts_at=next_starts_at,
        ends_at=next_ends_at,
    )
    ensure_not_on_approved_leave(
        practitioner_facility_assignment=shift.practitioner_facility_assignment,
        starts_at=next_starts_at,
        ends_at=next_ends_at,
    )
    _ensure_no_shift_overlap(
        practitioner_facility_assignment=shift.practitioner_facility_assignment,
        starts_at=next_starts_at,
        ends_at=next_ends_at,
        exclude_id=shift.pk,
    )
    _ensure_no_room_overlap(
        consultation_room=consultation_room,
        starts_at=next_starts_at,
        ends_at=next_ends_at,
        exclude_id=shift.pk,
    )

    shift.practitioner_department_assignment = practitioner_department_assignment
    shift.service_point = service_point
    shift.consultation_room = consultation_room
    shift.starts_at = next_starts_at
    shift.ends_at = next_ends_at
    if "accepts_appointments" in updates:
        shift.accepts_appointments = bool(updates["accepts_appointments"])
    if "notes" in updates:
        shift.notes = normalize_optional_text(updates["notes"])
    try:
        shift.save()
    except IntegrityError as exc:
        raise ConflictError("Practitioner shift could not be updated because a conflicting record already exists.") from exc
    return shift


@transaction.atomic
def cancel_practitioner_shift(*, shift_id, cancelled_by_id, cancellation_reason: str, cancelled_at=None) -> PractitionerShift:
    shift = get_shift(shift_id, for_update=True)
    if shift.status == PractitionerShift.Status.CANCELLED:
        return shift
    if shift.status == PractitionerShift.Status.COMPLETED:
        raise ValidationError("Completed shifts cannot be cancelled normally.")
    reason = normalize_optional_text(cancellation_reason)
    if reason is None:
        raise ValidationError("cancellation_reason is required.")
    shift.status = PractitionerShift.Status.CANCELLED
    shift.cancelled_by = get_user(cancelled_by_id, field_label="Cancelling user", active_only=True)
    shift.cancelled_at = cancelled_at or timezone.now()
    shift.cancellation_reason = reason
    shift.save()
    return shift


@transaction.atomic
def start_practitioner_shift(*, shift_id, actual_started_at=None) -> PractitionerShift:
    shift = get_shift(shift_id, for_update=True)
    if shift.status != PractitionerShift.Status.SCHEDULED:
        raise ValidationError("Only scheduled shifts can be started.")
    shift.status = PractitionerShift.Status.IN_PROGRESS
    shift.actual_started_at = actual_started_at or timezone.now()
    shift.actual_ended_at = None
    shift.save()
    return shift


@transaction.atomic
def complete_practitioner_shift(*, shift_id, actual_ended_at=None) -> PractitionerShift:
    shift = get_shift(shift_id, for_update=True)
    if shift.status != PractitionerShift.Status.IN_PROGRESS:
        raise ValidationError("Only in-progress shifts can be completed.")
    ended_at = actual_ended_at or timezone.now()
    if ended_at <= shift.actual_started_at:
        raise ValidationError("actual_ended_at must be after actual_started_at.")
    shift.status = PractitionerShift.Status.COMPLETED
    shift.actual_ended_at = ended_at
    shift.save()
    return shift
