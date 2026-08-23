from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.notifications.models import PatientNotification
from apps.notifications.realtime import broadcast_patient_notification
from common.exceptions import ConflictError, ValidationError

from ._crypto import encrypt_sensitive_value
from ._shared import (
    clean_optional_text,
    get_appointment,
    get_notification,
    get_patient,
    get_queue_entry,
    get_user,
    resolve_scheduled_for,
    safe_failure_reason,
    validate_notification_source,
    validate_patient_is_active,
    validate_recipient_user,
)


EXTERNAL_CHANNELS = {
    PatientNotification.Channel.SMS,
    PatientNotification.Channel.EMAIL,
    PatientNotification.Channel.PUSH,
}


@transaction.atomic
def create_patient_notification(
    *,
    patient_id,
    notification_type: str,
    channel: str,
    body: str,
    destination: str | None = None,
    subject: str | None = None,
    recipient_user_id=None,
    appointment_id=None,
    queue_entry_id=None,
    scheduled_for=None,
    idempotency_key: str | None = None,
    created_by_id=None,
) -> PatientNotification:
    patient = get_patient(patient_id)
    validate_patient_is_active(patient)

    if notification_type not in PatientNotification.NotificationType.values:
        raise ValidationError("Invalid notification type.")
    if channel not in PatientNotification.Channel.values:
        raise ValidationError("Invalid notification channel.")

    appointment = get_appointment(appointment_id) if appointment_id else None
    queue_entry = get_queue_entry(queue_entry_id) if queue_entry_id else None
    validate_notification_source(patient=patient, appointment=appointment, queue_entry=queue_entry)

    recipient_user = get_user(recipient_user_id) if recipient_user_id else None
    if channel in {PatientNotification.Channel.PUSH, PatientNotification.Channel.IN_APP} and recipient_user is None:
        raise ValidationError("Recipient user is required for push and in-app notifications.")
    validate_recipient_user(patient, recipient_user)

    destination_value = clean_optional_text(destination)
    if channel in EXTERNAL_CHANNELS and destination_value is None:
        raise ValidationError("Destination is required for SMS, email, and push notifications.")

    subject_value = clean_optional_text(subject)
    body_value = clean_optional_text(body)
    if body_value is None:
        raise ValidationError("Notification body is required.")

    created_by = get_user(created_by_id) if created_by_id else None
    key = clean_optional_text(idempotency_key)

    try:
        notification = PatientNotification.objects.create(
            patient=patient,
            appointment=appointment,
            queue_entry=queue_entry,
            notification_type=notification_type,
            channel=channel,
            recipient_user=recipient_user,
            destination_encrypted=encrypt_sensitive_value(destination_value) if destination_value else None,
            subject_encrypted=encrypt_sensitive_value(subject_value) if subject_value else None,
            body_encrypted=encrypt_sensitive_value(body_value),
            scheduled_for=resolve_scheduled_for(scheduled_for),
            idempotency_key=key,
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Notification conflicts with an existing record.") from exc
    broadcast_patient_notification(notification_id=notification.id, event="created")
    return notification


@transaction.atomic
def cancel_notification(*, notification_id, cancelled_by_id=None, reason: str | None = None) -> PatientNotification:
    notification = get_notification(notification_id, lock=True)
    if notification.status == PatientNotification.Status.CANCELLED:
        return notification
    if notification.status == PatientNotification.Status.DELIVERED:
        raise ValidationError("Delivered notification cannot be cancelled.")

    notification.status = PatientNotification.Status.CANCELLED
    notification.failure_reason = safe_failure_reason(reason) if reason else notification.failure_reason
    notification.save(update_fields=["status", "failure_reason", "updated_at"])
    broadcast_patient_notification(notification_id=notification.id, event="cancelled")
    return notification


@transaction.atomic
def mark_notification_processing(*, notification_id) -> PatientNotification:
    notification = get_notification(notification_id, lock=True)
    if notification.status != PatientNotification.Status.PENDING:
        raise ValidationError("Only pending notifications can be marked processing.")
    notification.status = PatientNotification.Status.PROCESSING
    notification.save(update_fields=["status", "updated_at"])
    broadcast_patient_notification(notification_id=notification.id, event="processing")
    return notification


@transaction.atomic
def mark_notification_sent(*, notification_id, provider_message_id: str | None = None, sent_at=None) -> PatientNotification:
    notification = get_notification(notification_id, lock=True)
    if notification.status == PatientNotification.Status.CANCELLED:
        raise ValidationError("Cancelled notification cannot be sent.")
    if notification.status == PatientNotification.Status.DELIVERED:
        return notification
    if notification.attempt_count <= 0 or notification.last_attempt_at is None:
        notification.attempt_count += 1
        notification.last_attempt_at = timezone.now()

    notification.status = PatientNotification.Status.SENT
    notification.sent_at = sent_at or timezone.now()
    notification.provider_message_id = clean_optional_text(provider_message_id)
    notification.failed_at = None
    notification.failure_reason = None
    notification.save(
        update_fields=[
            "status",
            "attempt_count",
            "last_attempt_at",
            "sent_at",
            "provider_message_id",
            "failed_at",
            "failure_reason",
            "updated_at",
        ]
    )
    broadcast_patient_notification(notification_id=notification.id, event="sent")
    return notification


@transaction.atomic
def mark_notification_delivered(*, notification_id, delivered_at=None) -> PatientNotification:
    notification = get_notification(notification_id, lock=True)
    if notification.status == PatientNotification.Status.FAILED:
        raise ValidationError("Failed notification cannot be marked delivered.")
    if notification.status == PatientNotification.Status.CANCELLED:
        raise ValidationError("Cancelled notification cannot be delivered.")
    if notification.sent_at is None:
        notification.sent_at = timezone.now()
    notification.status = PatientNotification.Status.DELIVERED
    notification.delivered_at = delivered_at or timezone.now()
    notification.failed_at = None
    notification.failure_reason = None
    notification.save(update_fields=["status", "sent_at", "delivered_at", "failed_at", "failure_reason", "updated_at"])
    broadcast_patient_notification(notification_id=notification.id, event="delivered")
    return notification


@transaction.atomic
def mark_notification_failed(*, notification_id, failure_reason: str, failed_at=None) -> PatientNotification:
    notification = get_notification(notification_id, lock=True)
    if notification.status == PatientNotification.Status.DELIVERED:
        raise ValidationError("Delivered notification cannot be marked failed.")
    if notification.status == PatientNotification.Status.CANCELLED:
        raise ValidationError("Cancelled notification cannot be marked failed.")
    if notification.attempt_count <= 0 or notification.last_attempt_at is None:
        notification.attempt_count += 1
        notification.last_attempt_at = timezone.now()
    notification.status = PatientNotification.Status.FAILED
    notification.failed_at = failed_at or timezone.now()
    notification.failure_reason = safe_failure_reason(failure_reason)
    notification.save(update_fields=["status", "attempt_count", "last_attempt_at", "failed_at", "failure_reason", "updated_at"])
    broadcast_patient_notification(notification_id=notification.id, event="failed")
    return notification


@transaction.atomic
def mark_notification_read(*, notification_id, read_at=None) -> PatientNotification:
    notification = get_notification(notification_id, lock=True)
    if notification.channel != PatientNotification.Channel.IN_APP:
        raise ValidationError("Only in-app notifications can be marked read.")
    if notification.status != PatientNotification.Status.DELIVERED:
        raise ValidationError("Only delivered in-app notifications can be marked read.")

    read_time = read_at or timezone.now()
    if notification.delivered_at and read_time < notification.delivered_at:
        raise ValidationError("Read time cannot be before delivered time.")

    notification.read_at = read_time
    notification.save(update_fields=["read_at", "updated_at"])
    broadcast_patient_notification(notification_id=notification.id, event="read")
    return notification
