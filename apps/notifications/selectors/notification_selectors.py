from __future__ import annotations

from django.utils import timezone

from apps.notifications.models import PatientNotification


def notification_queryset():
    return PatientNotification.objects.select_related("patient", "recipient_user", "appointment", "queue_entry").order_by("-created_at")


def list_notifications(
    *,
    patient_id=None,
    appointment_id=None,
    queue_entry_id=None,
    status=None,
    channel=None,
    notification_type=None,
    scheduled_pending: bool | None = None,
):
    queryset = notification_queryset()
    if patient_id:
        queryset = queryset.filter(patient_id=patient_id)
    if appointment_id:
        queryset = queryset.filter(appointment_id=appointment_id)
    if queue_entry_id:
        queryset = queryset.filter(queue_entry_id=queue_entry_id)
    if status:
        queryset = queryset.filter(status=status)
    if channel:
        queryset = queryset.filter(channel=channel)
    if notification_type:
        queryset = queryset.filter(notification_type=notification_type)
    if scheduled_pending is True:
        queryset = queryset.filter(status=PatientNotification.Status.PENDING, scheduled_for__lte=timezone.now())
    return queryset


def get_notification_by_id(notification_id):
    return notification_queryset().filter(pk=notification_id).first()


def list_notifications_by_patient(*, patient_id):
    return notification_queryset().filter(patient_id=patient_id)


def list_notifications_by_appointment(*, appointment_id):
    return notification_queryset().filter(appointment_id=appointment_id)


def list_notifications_by_queue_entry(*, queue_entry_id):
    return notification_queryset().filter(queue_entry_id=queue_entry_id)


def list_scheduled_pending_notifications():
    return notification_queryset().filter(status=PatientNotification.Status.PENDING, scheduled_for__lte=timezone.now())
