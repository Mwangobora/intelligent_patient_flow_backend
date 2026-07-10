from __future__ import annotations

from datetime import timedelta

from django.db import IntegrityError, transaction

from apps.scheduling.models import Appointment, AppointmentSlot, PractitionerShift
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    ACTIVE_APPOINTMENT_STATUSES,
    get_appointment_slot,
    get_facility_specialty,
    get_shift,
    practitioner_has_specialty_assignment,
    sync_slot_status,
    validate_datetime_range,
)


def _validate_slot_scope(*, practitioner_shift, facility_specialty, starts_at, ends_at, capacity) -> None:
    if practitioner_shift.status == PractitionerShift.Status.CANCELLED:
        raise ValidationError("Practitioner shift must not be cancelled.")
    if not practitioner_shift.accepts_appointments:
        raise ValidationError("Practitioner shift must accept appointments.")
    if not facility_specialty.is_active:
        raise ValidationError("Facility specialty must be active.")
    if facility_specialty.facility_id != practitioner_shift.practitioner_facility_assignment.facility_id:
        raise ValidationError("Facility specialty must belong to the same facility as the shift.")
    validate_datetime_range(starts_at=starts_at, ends_at=ends_at, label="Appointment slot")
    if starts_at < practitioner_shift.starts_at or ends_at > practitioner_shift.ends_at:
        raise ValidationError("Appointment slot must fit within the practitioner shift.")
    if capacity <= 0:
        raise ValidationError("capacity must be greater than 0.")
    if practitioner_has_specialty_assignment(
        practitioner_facility_assignment=practitioner_shift.practitioner_facility_assignment,
        facility_specialty=facility_specialty,
        scheduled_start=starts_at,
        scheduled_end=ends_at,
    ) is None:
        raise ValidationError("Practitioner must have an active specialty assignment for this slot.")


def _ensure_unique_slot(*, practitioner_shift, facility_specialty, starts_at, ends_at, exclude_id=None) -> None:
    queryset = AppointmentSlot.objects.select_for_update().filter(
        practitioner_shift=practitioner_shift,
        facility_specialty=facility_specialty,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.exists():
        raise ConflictError("A matching appointment slot already exists.")


def _ensure_slot_not_bound_to_active_appointments(slot: AppointmentSlot) -> None:
    if Appointment.objects.select_for_update().filter(
        appointment_slot=slot,
        status__in=ACTIVE_APPOINTMENT_STATUSES,
    ).exists():
        raise ValidationError("Slot has active appointments and cannot be changed in this way.")


@transaction.atomic
def create_appointment_slot(
    *,
    practitioner_shift_id,
    facility_specialty_id,
    starts_at,
    ends_at,
    capacity: int = 1,
    is_online_bookable: bool = True,
) -> AppointmentSlot:
    practitioner_shift = get_shift(practitioner_shift_id, for_update=True)
    facility_specialty = get_facility_specialty(facility_specialty_id, active_only=True, for_update=True)
    _validate_slot_scope(
        practitioner_shift=practitioner_shift,
        facility_specialty=facility_specialty,
        starts_at=starts_at,
        ends_at=ends_at,
        capacity=capacity,
    )
    _ensure_unique_slot(
        practitioner_shift=practitioner_shift,
        facility_specialty=facility_specialty,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    try:
        slot = AppointmentSlot.objects.create(
            practitioner_shift=practitioner_shift,
            facility_specialty=facility_specialty,
            starts_at=starts_at,
            ends_at=ends_at,
            capacity=capacity,
            booked_count=0,
            is_online_bookable=bool(is_online_bookable),
        )
    except IntegrityError as exc:
        raise ConflictError("Appointment slot could not be created because a conflicting record already exists.") from exc
    return slot


@transaction.atomic
def generate_slots_for_shift(
    *,
    practitioner_shift_id,
    facility_specialty_id,
    capacity: int = 1,
    is_online_bookable: bool = True,
):
    practitioner_shift = get_shift(practitioner_shift_id, for_update=True)
    facility_specialty = get_facility_specialty(facility_specialty_id, active_only=True, for_update=True)
    duration_minutes = facility_specialty.appointment_duration_minutes
    if duration_minutes <= 0:
        raise ValidationError("Facility specialty appointment duration must be greater than 0.")

    generated_slots: list[AppointmentSlot] = []
    cursor = practitioner_shift.starts_at
    while cursor + timedelta(minutes=duration_minutes) <= practitioner_shift.ends_at:
        generated_slots.append(
            create_appointment_slot(
                practitioner_shift_id=practitioner_shift.id,
                facility_specialty_id=facility_specialty.id,
                starts_at=cursor,
                ends_at=cursor + timedelta(minutes=duration_minutes),
                capacity=capacity,
                is_online_bookable=is_online_bookable,
            )
        )
        cursor += timedelta(minutes=duration_minutes)
    return generated_slots


@transaction.atomic
def block_appointment_slot(*, slot_id) -> AppointmentSlot:
    slot = get_appointment_slot(slot_id, for_update=True)
    if slot.status == AppointmentSlot.Status.BLOCKED:
        return slot
    _ensure_slot_not_bound_to_active_appointments(slot)
    slot.status = AppointmentSlot.Status.BLOCKED
    slot.save(update_fields=["status", "updated_at"])
    return slot


@transaction.atomic
def unblock_appointment_slot(*, slot_id) -> AppointmentSlot:
    slot = get_appointment_slot(slot_id, for_update=True)
    if slot.status != AppointmentSlot.Status.BLOCKED:
        return sync_slot_status(slot)
    sync_slot_status(slot)
    slot.save(update_fields=["status", "updated_at"])
    return slot


@transaction.atomic
def cancel_appointment_slot(*, slot_id) -> AppointmentSlot:
    slot = get_appointment_slot(slot_id, for_update=True)
    if slot.status == AppointmentSlot.Status.CANCELLED:
        return slot
    _ensure_slot_not_bound_to_active_appointments(slot)
    slot.status = AppointmentSlot.Status.CANCELLED
    slot.save(update_fields=["status", "updated_at"])
    return slot
