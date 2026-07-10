from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.scheduling.models import Appointment, AppointmentStatusHistory
from common.exceptions import ValidationError

from ._shared import get_appointment, get_user, normalize_optional_text

ALLOWED_STATUS_TRANSITIONS = {
    Appointment.Status.PENDING: {
        Appointment.Status.CONFIRMED,
        Appointment.Status.CANCELLED,
        Appointment.Status.NO_SHOW,
        Appointment.Status.RESCHEDULED,
    },
    Appointment.Status.CONFIRMED: {
        Appointment.Status.CHECKED_IN,
        Appointment.Status.CANCELLED,
        Appointment.Status.NO_SHOW,
        Appointment.Status.RESCHEDULED,
    },
    Appointment.Status.CHECKED_IN: {
        Appointment.Status.QUEUED,
        Appointment.Status.IN_SERVICE,
        Appointment.Status.CANCELLED,
    },
    Appointment.Status.QUEUED: {
        Appointment.Status.IN_SERVICE,
        Appointment.Status.CANCELLED,
    },
    Appointment.Status.IN_SERVICE: {
        Appointment.Status.COMPLETED,
    },
    Appointment.Status.COMPLETED: set(),
    Appointment.Status.CANCELLED: set(),
    Appointment.Status.NO_SHOW: set(),
    Appointment.Status.RESCHEDULED: set(),
}


def create_initial_appointment_status_history(
    *,
    appointment: Appointment,
    change_source: str,
    changed_by_id=None,
    reason: str | None = None,
) -> AppointmentStatusHistory:
    changed_by = get_user(changed_by_id, field_label="Changed by user", active_only=True) if changed_by_id is not None else None
    return AppointmentStatusHistory.objects.create(
        appointment=appointment,
        from_status=None,
        to_status=appointment.status,
        change_source=change_source,
        changed_by=changed_by,
        reason=normalize_optional_text(reason),
    )


@transaction.atomic
def change_appointment_status(
    *,
    appointment_id,
    to_status: str,
    change_source: str,
    changed_by_id=None,
    reason: str | None = None,
    changed_at=None,
) -> Appointment:
    appointment = get_appointment(appointment_id, for_update=True)
    if appointment.status == to_status:
        return appointment
    allowed_transitions = ALLOWED_STATUS_TRANSITIONS.get(appointment.status, set())
    if to_status not in allowed_transitions:
        raise ValidationError(f"Cannot change appointment from {appointment.status} to {to_status}.")

    changed_by = get_user(changed_by_id, field_label="Changed by user", active_only=True) if changed_by_id is not None else None
    status_reason = normalize_optional_text(reason)
    if to_status == Appointment.Status.CANCELLED:
        if changed_by is None:
            raise ValidationError("cancelled_by is required.")
        if status_reason is None:
            raise ValidationError("cancellation_reason is required.")
        appointment.cancelled_by = changed_by
        appointment.cancelled_at = changed_at or timezone.now()
        appointment.cancellation_reason = status_reason
    elif appointment.status == Appointment.Status.CANCELLED:
        raise ValidationError("Cancelled appointments are terminal.")

    previous_status = appointment.status
    appointment.status = to_status
    appointment.save()
    AppointmentStatusHistory.objects.create(
        appointment=appointment,
        from_status=previous_status,
        to_status=to_status,
        change_source=change_source,
        changed_by=changed_by,
        reason=status_reason,
        changed_at=changed_at or timezone.now(),
    )
    return appointment


def mark_checked_in(*, appointment_id, changed_by_id=None, change_source=AppointmentStatusHistory.ChangeSource.API) -> Appointment:
    return change_appointment_status(
        appointment_id=appointment_id,
        to_status=Appointment.Status.CHECKED_IN,
        change_source=change_source,
        changed_by_id=changed_by_id,
    )


def mark_queued(*, appointment_id, changed_by_id=None, change_source=AppointmentStatusHistory.ChangeSource.API) -> Appointment:
    return change_appointment_status(
        appointment_id=appointment_id,
        to_status=Appointment.Status.QUEUED,
        change_source=change_source,
        changed_by_id=changed_by_id,
    )


def mark_in_service(*, appointment_id, changed_by_id=None, change_source=AppointmentStatusHistory.ChangeSource.API) -> Appointment:
    return change_appointment_status(
        appointment_id=appointment_id,
        to_status=Appointment.Status.IN_SERVICE,
        change_source=change_source,
        changed_by_id=changed_by_id,
    )


def mark_completed(*, appointment_id, changed_by_id=None, change_source=AppointmentStatusHistory.ChangeSource.API) -> Appointment:
    return change_appointment_status(
        appointment_id=appointment_id,
        to_status=Appointment.Status.COMPLETED,
        change_source=change_source,
        changed_by_id=changed_by_id,
    )


def mark_no_show(*, appointment_id, changed_by_id=None, change_source=AppointmentStatusHistory.ChangeSource.API, reason: str | None = None) -> Appointment:
    return change_appointment_status(
        appointment_id=appointment_id,
        to_status=Appointment.Status.NO_SHOW,
        change_source=change_source,
        changed_by_id=changed_by_id,
        reason=reason,
    )


def mark_cancelled(*, appointment_id, cancelled_by_id, cancellation_reason: str, change_source=AppointmentStatusHistory.ChangeSource.API) -> Appointment:
    return change_appointment_status(
        appointment_id=appointment_id,
        to_status=Appointment.Status.CANCELLED,
        change_source=change_source,
        changed_by_id=cancelled_by_id,
        reason=cancellation_reason,
    )


def mark_rescheduled(*, appointment_id, changed_by_id=None, reason: str | None = None, change_source=AppointmentStatusHistory.ChangeSource.API) -> Appointment:
    return change_appointment_status(
        appointment_id=appointment_id,
        to_status=Appointment.Status.RESCHEDULED,
        change_source=change_source,
        changed_by_id=changed_by_id,
        reason=reason,
    )
