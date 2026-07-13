from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.notifications.models import PatientNotification
from common.exceptions import ValidationError

from ._shared import get_notification, safe_failure_reason


def get_pending_notifications_for_delivery(*, limit: int = 50, now=None):
    due_at = now or timezone.now()
    return (
        PatientNotification.objects.select_related("patient", "recipient_user", "appointment", "queue_entry")
        .filter(status=PatientNotification.Status.PENDING, scheduled_for__lte=due_at)
        .order_by("scheduled_for", "created_at")[:limit]
    )


@transaction.atomic
def claim_notification_for_processing(*, notification_id) -> PatientNotification:
    notification = get_notification(notification_id, lock=True)
    if notification.status != PatientNotification.Status.PENDING:
        raise ValidationError("Only pending notifications can be claimed for processing.")
    notification.status = PatientNotification.Status.PROCESSING
    notification.save(update_fields=["status", "updated_at"])
    return notification


def send_notification(*, notification_id) -> PatientNotification:
    with transaction.atomic():
        notification = get_notification(notification_id, lock=True)
        if notification.status == PatientNotification.Status.CANCELLED:
            raise ValidationError("Cancelled notification cannot be sent.")
        if notification.status == PatientNotification.Status.DELIVERED:
            return notification
        if notification.status not in {PatientNotification.Status.PENDING, PatientNotification.Status.PROCESSING, PatientNotification.Status.FAILED}:
            raise ValidationError("Notification cannot be sent from its current status.")

        attempt_time = timezone.now()
        notification.status = PatientNotification.Status.PROCESSING
        notification.attempt_count += 1
        notification.last_attempt_at = attempt_time

        if notification.channel == PatientNotification.Channel.IN_APP:
            return send_in_app_notification(notification=notification, sent_at=attempt_time)

        try:
            if notification.channel == PatientNotification.Channel.SMS:
                send_sms_notification_placeholder(notification=notification)
            elif notification.channel == PatientNotification.Channel.EMAIL:
                send_email_notification_placeholder(notification=notification)
            elif notification.channel == PatientNotification.Channel.PUSH:
                send_push_notification_placeholder(notification=notification)
        except ValidationError as exc:
            notification.status = PatientNotification.Status.FAILED
            notification.failed_at = attempt_time
            notification.failure_reason = safe_failure_reason(str(exc))
            notification.save(update_fields=["status", "attempt_count", "last_attempt_at", "failed_at", "failure_reason", "updated_at"])
        else:
            notification.status = PatientNotification.Status.SENT
            notification.sent_at = attempt_time
            notification.save(update_fields=["status", "attempt_count", "last_attempt_at", "sent_at", "updated_at"])

    return notification


def send_sms_notification_placeholder(*, notification: PatientNotification) -> None:
    raise ValidationError("Notification provider is not configured.")


def send_email_notification_placeholder(*, notification: PatientNotification) -> None:
    raise ValidationError("Notification provider is not configured.")


def send_push_notification_placeholder(*, notification: PatientNotification) -> None:
    raise ValidationError("Notification provider is not configured.")


def send_in_app_notification(*, notification: PatientNotification, sent_at=None) -> PatientNotification:
    delivery_time = sent_at or timezone.now()
    notification.status = PatientNotification.Status.DELIVERED
    notification.sent_at = delivery_time
    notification.delivered_at = delivery_time
    notification.failed_at = None
    notification.failure_reason = None
    notification.save(
        update_fields=[
            "status",
            "attempt_count",
            "last_attempt_at",
            "sent_at",
            "delivered_at",
            "failed_at",
            "failure_reason",
            "updated_at",
        ]
    )
    return notification
