from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.scheduling.models import Appointment, AppointmentSlot, AppointmentStatusHistory, PractitionerShift
from common.exceptions import ConflictError, ValidationError

from ._crypto import encrypt_sensitive_value
from ._shared import (
    ACTIVE_APPOINTMENT_STATUSES,
    TERMINAL_APPOINTMENT_STATUSES,
    active_appointment_overlap_queryset,
    availability_covers_time,
    enforce_booking_cutoffs,
    enforce_cancellation_cutoff,
    enforce_reschedule_cutoff,
    ensure_appointment_within_facility_schedule,
    ensure_not_on_approved_leave,
    get_appointment,
    get_appointment_slot,
    get_facility,
    get_facility_flow_settings,
    get_facility_specialty,
    get_patient,
    get_practitioner_facility_assignment,
    get_practitioner_specialty_assignment,
    get_shift,
    get_user,
    normalize_optional_text,
    practitioner_has_specialty_assignment,
    sync_slot_status,
    validate_datetime_range,
)
from .appointment_number_service import generate_appointment_number
from .appointment_status_service import create_initial_appointment_status_history, mark_cancelled, mark_rescheduled


def _active_practitioner_overlap_exists(*, practitioner_facility_assignment, scheduled_start, scheduled_end, exclude_id=None) -> bool:
    queryset = active_appointment_overlap_queryset(exclude_id=exclude_id).filter(
        practitioner_facility_assignment__practitioner_id=practitioner_facility_assignment.practitioner_id,
    )
    return queryset.filter(scheduled_start__lt=scheduled_end, scheduled_end__gt=scheduled_start).exists()


def _active_patient_overlap_exists(*, patient, scheduled_start, scheduled_end, exclude_id=None) -> bool:
    queryset = active_appointment_overlap_queryset(exclude_id=exclude_id).filter(patient=patient)
    return queryset.filter(scheduled_start__lt=scheduled_end, scheduled_end__gt=scheduled_start).exists()


def _derive_practitioner_context(
    *,
    facility,
    facility_specialty,
    scheduled_start,
    scheduled_end,
    practitioner_facility_assignment_id=None,
    practitioner_specialty_assignment_id=None,
    practitioner_shift_id=None,
    appointment_slot_id=None,
):
    practitioner_facility_assignment = None
    practitioner_specialty_assignment = None
    practitioner_shift = None
    appointment_slot = None

    if appointment_slot_id is not None:
        appointment_slot = get_appointment_slot(appointment_slot_id, for_update=True)
        practitioner_shift = get_shift(appointment_slot.practitioner_shift_id, for_update=True)
        practitioner_facility_assignment = get_practitioner_facility_assignment(
            practitioner_shift.practitioner_facility_assignment_id,
            active_only=True,
            for_update=True,
        )
        practitioner_specialty_assignment = practitioner_has_specialty_assignment(
            practitioner_facility_assignment=practitioner_facility_assignment,
            facility_specialty=facility_specialty,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
        )
    elif practitioner_shift_id is not None:
        practitioner_shift = get_shift(practitioner_shift_id, for_update=True)
        practitioner_facility_assignment = get_practitioner_facility_assignment(
            practitioner_shift.practitioner_facility_assignment_id,
            active_only=True,
            for_update=True,
        )

    if practitioner_facility_assignment_id is not None:
        practitioner_facility_assignment = get_practitioner_facility_assignment(
            practitioner_facility_assignment_id,
            active_only=True,
            for_update=True,
        )
    if practitioner_specialty_assignment_id is not None:
        practitioner_specialty_assignment = get_practitioner_specialty_assignment(
            practitioner_specialty_assignment_id,
            active_only=True,
            for_update=True,
        )

    if practitioner_facility_assignment is None and practitioner_specialty_assignment is not None:
        practitioner_facility_assignment = get_practitioner_facility_assignment(
            practitioner_specialty_assignment.practitioner_facility_assignment_id,
            active_only=True,
            for_update=True,
        )

    if practitioner_facility_assignment is None:
        return None, None, practitioner_shift, appointment_slot

    if practitioner_facility_assignment.facility_id != facility.id:
        raise ValidationError("Practitioner facility assignment must belong to the selected facility.")
    if not practitioner_facility_assignment.practitioner.is_active:
        raise ValidationError("Practitioner must be active.")
    ensure_not_on_approved_leave(
        practitioner_facility_assignment=practitioner_facility_assignment,
        starts_at=scheduled_start,
        ends_at=scheduled_end,
    )

    if practitioner_specialty_assignment is None:
        practitioner_specialty_assignment = practitioner_has_specialty_assignment(
            practitioner_facility_assignment=practitioner_facility_assignment,
            facility_specialty=facility_specialty,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
        )
    if practitioner_specialty_assignment is None:
        raise ValidationError("Practitioner specialty assignment does not match appointment.")
    if practitioner_specialty_assignment.practitioner_facility_assignment_id != practitioner_facility_assignment.id:
        raise ValidationError("Practitioner specialty assignment must belong to the same practitioner assignment.")
    if practitioner_specialty_assignment.facility_specialty_id != facility_specialty.id:
        raise ValidationError("Practitioner specialty assignment must match the selected facility specialty.")

    if practitioner_shift is not None:
        if practitioner_shift.practitioner_facility_assignment_id != practitioner_facility_assignment.id:
            raise ValidationError("Shift must belong to the selected practitioner facility assignment.")
        if practitioner_shift.status == PractitionerShift.Status.CANCELLED or not practitioner_shift.accepts_appointments:
            raise ValidationError("Shift must be active and accept appointments.")
        if scheduled_start < practitioner_shift.starts_at or scheduled_end > practitioner_shift.ends_at:
            raise ValidationError("Appointment time must fit completely inside the assigned shift.")
    elif not availability_covers_time(
        practitioner_facility_assignment=practitioner_facility_assignment,
        starts_at=scheduled_start,
        ends_at=scheduled_end,
    ):
        raise ValidationError("Practitioner is not available for the requested appointment time.")

    if appointment_slot is not None:
        if appointment_slot.facility_specialty_id != facility_specialty.id:
            raise ValidationError("Appointment slot must match the selected facility specialty.")
        if practitioner_shift is None or appointment_slot.practitioner_shift_id != practitioner_shift.id:
            raise ValidationError("Appointment slot must match the selected shift.")
        if scheduled_start != appointment_slot.starts_at or scheduled_end != appointment_slot.ends_at:
            raise ValidationError("Appointment time must match the selected slot.")
        if appointment_slot.status in {
            AppointmentSlot.Status.BLOCKED,
            AppointmentSlot.Status.CANCELLED,
            AppointmentSlot.Status.FULL,
        }:
            raise ValidationError("Selected slot is not bookable.")
        if appointment_slot.booked_count >= appointment_slot.capacity:
            raise ValidationError("Selected slot is full.")

    if _active_practitioner_overlap_exists(
        practitioner_facility_assignment=practitioner_facility_assignment,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
    ):
        raise ConflictError("Practitioner cannot have overlapping appointments across facilities.")

    return practitioner_facility_assignment, practitioner_specialty_assignment, practitioner_shift, appointment_slot


def _set_reason_for_visit(*, reason_for_visit: str | None):
    normalized_reason = normalize_optional_text(reason_for_visit)
    if normalized_reason is None:
        return None
    return encrypt_sensitive_value(normalized_reason)


def _increment_slot_booking(slot: AppointmentSlot) -> AppointmentSlot:
    if slot.booked_count >= slot.capacity:
        raise ValidationError("Selected slot is full.")
    slot.booked_count += 1
    sync_slot_status(slot)
    slot.save(update_fields=["booked_count", "status", "updated_at"])
    return slot


def _release_slot_booking(*, appointment: Appointment) -> None:
    if appointment.appointment_slot_id is None:
        return
    if appointment.status not in ACTIVE_APPOINTMENT_STATUSES:
        return
    slot = get_appointment_slot(appointment.appointment_slot_id, for_update=True)
    if slot.booked_count > 0:
        slot.booked_count -= 1
        sync_slot_status(slot)
        slot.save(update_fields=["booked_count", "status", "updated_at"])


@transaction.atomic
def create_appointment(
    *,
    facility_id,
    patient_id,
    facility_specialty_id,
    scheduled_start,
    scheduled_end,
    booking_channel,
    practitioner_facility_assignment_id=None,
    practitioner_specialty_assignment_id=None,
    practitioner_shift_id=None,
    appointment_slot_id=None,
    appointment_number: str | None = None,
    reason_for_visit: str | None = None,
    rescheduled_from_id=None,
    created_by_id=None,
) -> Appointment:
    facility = get_facility(facility_id, active_only=True, for_update=True)
    patient = get_patient(patient_id, active_only=True, for_update=True)
    facility_specialty = get_facility_specialty(facility_specialty_id, active_only=True, for_update=True)
    created_by = get_user(created_by_id, field_label="Creator user", active_only=True) if created_by_id is not None else None
    rescheduled_from = get_appointment(rescheduled_from_id, for_update=True) if rescheduled_from_id is not None else None

    validate_datetime_range(starts_at=scheduled_start, ends_at=scheduled_end, label="Appointment")
    if patient.organization_id != facility.organization_id:
        raise ValidationError("Appointment patient must belong to the facility organization.")
    if facility_specialty.facility_id != facility.id:
        raise ValidationError("Appointment specialty must belong to the selected facility.")
    flow_settings = get_facility_flow_settings(facility=facility, for_update=True)
    enforce_booking_cutoffs(facility=facility, scheduled_start=scheduled_start, flow_settings=flow_settings)
    ensure_appointment_within_facility_schedule(
        facility=facility,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
    )
    if _active_patient_overlap_exists(
        patient=patient,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
    ):
        raise ConflictError("Patient cannot have overlapping active appointments.")

    practitioner_facility_assignment, practitioner_specialty_assignment, practitioner_shift, appointment_slot = _derive_practitioner_context(
        facility=facility,
        facility_specialty=facility_specialty,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        practitioner_facility_assignment_id=practitioner_facility_assignment_id,
        practitioner_specialty_assignment_id=practitioner_specialty_assignment_id,
        practitioner_shift_id=practitioner_shift_id,
        appointment_slot_id=appointment_slot_id,
    )

    generated_number = appointment_number or generate_appointment_number(facility=facility, scheduled_start=scheduled_start)
    if appointment_slot is not None:
        _increment_slot_booking(appointment_slot)

    try:
        appointment = Appointment.objects.create(
            facility=facility,
            patient=patient,
            facility_specialty=facility_specialty,
            practitioner_facility_assignment=practitioner_facility_assignment,
            practitioner_specialty_assignment=practitioner_specialty_assignment,
            practitioner_shift=practitioner_shift,
            appointment_slot=appointment_slot,
            appointment_number=generated_number,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            booking_channel=booking_channel,
            reason_for_visit_encrypted=_set_reason_for_visit(reason_for_visit=reason_for_visit),
            rescheduled_from=rescheduled_from,
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Appointment could not be created because a conflicting record already exists.") from exc

    create_initial_appointment_status_history(
        appointment=appointment,
        change_source=AppointmentStatusHistory.ChangeSource.API,
        changed_by_id=created_by_id,
    )
    return appointment


@transaction.atomic
def update_appointment(*, appointment_id, **updates) -> Appointment:
    appointment = get_appointment(appointment_id, for_update=True)
    if appointment.status in TERMINAL_APPOINTMENT_STATUSES:
        raise ValidationError("Terminal appointments cannot be updated.")
    allowed_fields = {
        "scheduled_start",
        "scheduled_end",
        "facility_specialty_id",
        "booking_channel",
        "reason_for_visit",
    }
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        raise ValidationError(f"Unsupported appointment update fields: {', '.join(sorted(unexpected_fields))}.")

    next_scheduled_start = updates.get("scheduled_start", appointment.scheduled_start)
    next_scheduled_end = updates.get("scheduled_end", appointment.scheduled_end)
    next_facility_specialty = (
        get_facility_specialty(updates["facility_specialty_id"], active_only=True, for_update=True)
        if "facility_specialty_id" in updates
        else appointment.facility_specialty
    )
    validate_datetime_range(starts_at=next_scheduled_start, ends_at=next_scheduled_end, label="Appointment")
    flow_settings = get_facility_flow_settings(facility=appointment.facility, for_update=True)
    enforce_booking_cutoffs(
        facility=appointment.facility,
        scheduled_start=next_scheduled_start,
        flow_settings=flow_settings,
    )
    ensure_appointment_within_facility_schedule(
        facility=appointment.facility,
        scheduled_start=next_scheduled_start,
        scheduled_end=next_scheduled_end,
    )
    if _active_patient_overlap_exists(
        patient=appointment.patient,
        scheduled_start=next_scheduled_start,
        scheduled_end=next_scheduled_end,
        exclude_id=appointment.pk,
    ):
        raise ConflictError("Patient cannot have overlapping active appointments.")
    if appointment.practitioner_facility_assignment_id is not None and _active_practitioner_overlap_exists(
        practitioner_facility_assignment=appointment.practitioner_facility_assignment,
        scheduled_start=next_scheduled_start,
        scheduled_end=next_scheduled_end,
        exclude_id=appointment.pk,
    ):
        raise ConflictError("Practitioner cannot have overlapping appointments across facilities.")

    appointment.scheduled_start = next_scheduled_start
    appointment.scheduled_end = next_scheduled_end
    appointment.facility_specialty = next_facility_specialty
    if "booking_channel" in updates:
        appointment.booking_channel = updates["booking_channel"]
    if "reason_for_visit" in updates:
        appointment.reason_for_visit_encrypted = _set_reason_for_visit(reason_for_visit=updates["reason_for_visit"])
    try:
        appointment.save()
    except IntegrityError as exc:
        raise ConflictError("Appointment could not be updated because a conflicting record already exists.") from exc
    return appointment


@transaction.atomic
def assign_practitioner_to_appointment(
    *,
    appointment_id,
    practitioner_facility_assignment_id,
    practitioner_specialty_assignment_id,
    practitioner_shift_id=None,
    appointment_slot_id=None,
) -> Appointment:
    appointment = get_appointment(appointment_id, for_update=True)
    if appointment.status in TERMINAL_APPOINTMENT_STATUSES:
        raise ValidationError("Terminal appointments cannot be reassigned.")

    practitioner_facility_assignment, practitioner_specialty_assignment, practitioner_shift, appointment_slot = _derive_practitioner_context(
        facility=appointment.facility,
        facility_specialty=appointment.facility_specialty,
        scheduled_start=appointment.scheduled_start,
        scheduled_end=appointment.scheduled_end,
        practitioner_facility_assignment_id=practitioner_facility_assignment_id,
        practitioner_specialty_assignment_id=practitioner_specialty_assignment_id,
        practitioner_shift_id=practitioner_shift_id,
        appointment_slot_id=appointment_slot_id,
    )

    if appointment.appointment_slot_id is not None and appointment.appointment_slot_id != (appointment_slot.id if appointment_slot else None):
        _release_slot_booking(appointment=appointment)
    if appointment_slot is not None and appointment.appointment_slot_id != appointment_slot.id:
        _increment_slot_booking(appointment_slot)

    appointment.practitioner_facility_assignment = practitioner_facility_assignment
    appointment.practitioner_specialty_assignment = practitioner_specialty_assignment
    appointment.practitioner_shift = practitioner_shift
    appointment.appointment_slot = appointment_slot
    appointment.save()
    return appointment


@transaction.atomic
def book_slot_appointment(
    *,
    appointment_id=None,
    facility_id=None,
    patient_id=None,
    facility_specialty_id=None,
    scheduled_start=None,
    scheduled_end=None,
    booking_channel=None,
    appointment_slot_id,
    created_by_id=None,
    reason_for_visit: str | None = None,
) -> Appointment:
    if appointment_id is not None:
        appointment = get_appointment(appointment_id, for_update=True)
        return assign_practitioner_to_appointment(
            appointment_id=appointment.id,
            practitioner_facility_assignment_id=appointment.practitioner_facility_assignment_id,
            practitioner_specialty_assignment_id=appointment.practitioner_specialty_assignment_id,
            practitioner_shift_id=appointment.practitioner_shift_id,
            appointment_slot_id=appointment_slot_id,
        )
    return create_appointment(
        facility_id=facility_id,
        patient_id=patient_id,
        facility_specialty_id=facility_specialty_id,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        booking_channel=booking_channel,
        appointment_slot_id=appointment_slot_id,
        created_by_id=created_by_id,
        reason_for_visit=reason_for_visit,
    )


@transaction.atomic
def cancel_appointment(*, appointment_id, cancelled_by_id, cancellation_reason: str) -> Appointment:
    appointment = get_appointment(appointment_id, for_update=True)
    if appointment.status == Appointment.Status.COMPLETED:
        raise ValidationError("Completed appointments cannot be cancelled normally.")
    if appointment.status in TERMINAL_APPOINTMENT_STATUSES:
        raise ValidationError("This appointment can no longer be cancelled.")
    flow_settings = get_facility_flow_settings(facility=appointment.facility, for_update=True)
    enforce_cancellation_cutoff(
        facility=appointment.facility,
        scheduled_start=appointment.scheduled_start,
        flow_settings=flow_settings,
    )
    _release_slot_booking(appointment=appointment)
    return mark_cancelled(
        appointment_id=appointment.id,
        cancelled_by_id=cancelled_by_id,
        cancellation_reason=cancellation_reason,
    )


@transaction.atomic
def reschedule_appointment(
    *,
    appointment_id,
    scheduled_start,
    scheduled_end,
    booking_channel=None,
    practitioner_facility_assignment_id=None,
    practitioner_specialty_assignment_id=None,
    practitioner_shift_id=None,
    appointment_slot_id=None,
    reason_for_visit: str | None = None,
    created_by_id=None,
) -> Appointment:
    appointment = get_appointment(appointment_id, for_update=True)
    if appointment.status in TERMINAL_APPOINTMENT_STATUSES:
        raise ValidationError("Terminal appointments cannot be rescheduled.")
    flow_settings = get_facility_flow_settings(facility=appointment.facility, for_update=True)
    enforce_reschedule_cutoff(
        facility=appointment.facility,
        scheduled_start=appointment.scheduled_start,
        flow_settings=flow_settings,
    )
    _release_slot_booking(appointment=appointment)
    mark_rescheduled(
        appointment_id=appointment.id,
        changed_by_id=created_by_id,
        reason="Rescheduled",
    )
    return create_appointment(
        facility_id=appointment.facility_id,
        patient_id=appointment.patient_id,
        facility_specialty_id=appointment.facility_specialty_id,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        booking_channel=booking_channel or appointment.booking_channel,
        practitioner_facility_assignment_id=practitioner_facility_assignment_id or appointment.practitioner_facility_assignment_id,
        practitioner_specialty_assignment_id=practitioner_specialty_assignment_id or appointment.practitioner_specialty_assignment_id,
        practitioner_shift_id=practitioner_shift_id or appointment.practitioner_shift_id,
        appointment_slot_id=appointment_slot_id,
        reason_for_visit=reason_for_visit,
        rescheduled_from_id=appointment.id,
        created_by_id=created_by_id,
    )
