from __future__ import annotations

from apps.notifications.models import PatientNotification
from common.exceptions import ValidationError

from ._shared import clean_optional_text, get_appointment, get_queue_entry
from .notification_service import create_patient_notification


def _patient_destination(patient, channel: str) -> str | None:
    if channel == PatientNotification.Channel.SMS:
        return patient.phone_number
    if channel == PatientNotification.Channel.EMAIL:
        return patient.email
    if channel == PatientNotification.Channel.PUSH:
        return f"user:{patient.user_id}" if patient.user_id else None
    return None


def _recipient_user_id(patient, channel: str):
    if channel in {PatientNotification.Channel.PUSH, PatientNotification.Channel.IN_APP}:
        return patient.user_id
    return None


def _create_from_appointment(
    *,
    appointment_id,
    notification_type: str,
    body: str,
    channel: str = PatientNotification.Channel.IN_APP,
    idempotency_key: str | None = None,
    scheduled_for=None,
    created_by_id=None,
) -> PatientNotification:
    appointment = get_appointment(appointment_id)
    patient = appointment.patient
    if channel in {PatientNotification.Channel.PUSH, PatientNotification.Channel.IN_APP} and patient.user_id is None:
        raise ValidationError("Patient must be linked to a user for push or in-app notifications.")

    key = clean_optional_text(idempotency_key) or f"{notification_type}:{appointment.id}:{channel}"
    return create_patient_notification(
        patient_id=patient.id,
        appointment_id=appointment.id,
        notification_type=notification_type,
        channel=channel,
        destination=_patient_destination(patient, channel),
        recipient_user_id=_recipient_user_id(patient, channel),
        subject="Appointment notification",
        body=body,
        scheduled_for=scheduled_for,
        idempotency_key=key,
        created_by_id=created_by_id,
    )


def _create_from_queue_entry(
    *,
    queue_entry_id,
    notification_type: str,
    body: str,
    channel: str = PatientNotification.Channel.IN_APP,
    idempotency_key: str | None = None,
    scheduled_for=None,
    created_by_id=None,
) -> PatientNotification:
    queue_entry = get_queue_entry(queue_entry_id)
    patient = queue_entry.patient_checkin.patient
    if channel in {PatientNotification.Channel.PUSH, PatientNotification.Channel.IN_APP} and patient.user_id is None:
        raise ValidationError("Patient must be linked to a user for push or in-app notifications.")

    key = clean_optional_text(idempotency_key) or f"{notification_type}:{queue_entry.id}:{channel}"
    return create_patient_notification(
        patient_id=patient.id,
        queue_entry_id=queue_entry.id,
        notification_type=notification_type,
        channel=channel,
        destination=_patient_destination(patient, channel),
        recipient_user_id=_recipient_user_id(patient, channel),
        subject="Queue notification",
        body=body,
        scheduled_for=scheduled_for,
        idempotency_key=key,
        created_by_id=created_by_id,
    )


def create_appointment_confirmation_notification(**kwargs) -> PatientNotification:
    return _create_from_appointment(
        notification_type=PatientNotification.NotificationType.APPOINTMENT_CONFIRMATION,
        body="Your appointment has been confirmed.",
        **kwargs,
    )


def create_appointment_reminder_notification(**kwargs) -> PatientNotification:
    return _create_from_appointment(
        notification_type=PatientNotification.NotificationType.APPOINTMENT_REMINDER,
        body="You have an upcoming appointment.",
        **kwargs,
    )


def create_appointment_rescheduled_notification(**kwargs) -> PatientNotification:
    return _create_from_appointment(
        notification_type=PatientNotification.NotificationType.APPOINTMENT_RESCHEDULED,
        body="Your appointment has been rescheduled.",
        **kwargs,
    )


def create_appointment_cancelled_notification(**kwargs) -> PatientNotification:
    return _create_from_appointment(
        notification_type=PatientNotification.NotificationType.APPOINTMENT_CANCELLED,
        body="Your appointment has been cancelled.",
        **kwargs,
    )


def create_queue_joined_notification(**kwargs) -> PatientNotification:
    return _create_from_queue_entry(
        notification_type=PatientNotification.NotificationType.QUEUE_JOINED,
        body="You have joined the queue.",
        **kwargs,
    )


def create_queue_updated_notification(**kwargs) -> PatientNotification:
    return _create_from_queue_entry(
        notification_type=PatientNotification.NotificationType.QUEUE_UPDATED,
        body="Your queue status has been updated.",
        **kwargs,
    )


def create_queue_called_notification(**kwargs) -> PatientNotification:
    return _create_from_queue_entry(
        notification_type=PatientNotification.NotificationType.QUEUE_CALLED,
        body="Please proceed for service.",
        **kwargs,
    )
