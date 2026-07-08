from __future__ import annotations

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q, F
from django.utils import timezone

from apps.patients.models import Patient
from common.db import ActiveModel, TimeStampedModel

hash_validator = RegexValidator(regex=r"^[0-9A-Fa-f]{64}$", message="Hash values must be 64 hexadecimal characters.")


class PatientNotification(TimeStampedModel):
    class NotificationType(models.TextChoices):
        APPOINTMENT_CONFIRMATION = "appointment_confirmation", "Appointment Confirmation"
        APPOINTMENT_REMINDER = "appointment_reminder", "Appointment Reminder"
        APPOINTMENT_RESCHEDULED = "appointment_rescheduled", "Appointment Rescheduled"
        APPOINTMENT_CANCELLED = "appointment_cancelled", "Appointment Cancelled"
        QUEUE_JOINED = "queue_joined", "Queue Joined"
        QUEUE_UPDATED = "queue_updated", "Queue Updated"
        QUEUE_CALLED = "queue_called", "Queue Called"
        GENERAL = "general", "General"

    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"
        PUSH = "push", "Push"
        IN_APP = "in_app", "In App"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="notifications")
    appointment = models.ForeignKey("scheduling.Appointment", on_delete=models.PROTECT, related_name="notifications", blank=True, null=True)
    queue_entry = models.ForeignKey("queueing.QueueEntry", on_delete=models.PROTECT, related_name="notifications", blank=True, null=True)
    notification_type = models.CharField(max_length=40, choices=NotificationType.choices)
    channel = models.CharField(max_length=20, choices=Channel.choices)
    recipient_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="patient_notifications", blank=True, null=True)
    destination_encrypted = models.TextField(blank=True, null=True)
    subject_encrypted = models.TextField(blank=True, null=True)
    body_encrypted = models.TextField()
    scheduled_for = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.SmallIntegerField(default=0)
    last_attempt_at = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    failed_at = models.DateTimeField(blank=True, null=True)
    failure_reason = models.CharField(max_length=250, blank=True, null=True)
    provider_message_id = models.CharField(max_length=150, blank=True, null=True)
    idempotency_key = models.CharField(max_length=100, blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_patient_notifications", blank=True, null=True)

    class Meta:
        db_table = "patient_notifications"
        constraints = [
            models.UniqueConstraint(fields=["idempotency_key"], condition=Q(idempotency_key__isnull=False), name="uq_patient_notifications_idempotency"),
            models.CheckConstraint(condition=Q(notification_type__in=["appointment_confirmation", "appointment_reminder", "appointment_rescheduled", "appointment_cancelled", "queue_joined", "queue_updated", "queue_called", "general"]), name="ck_patient_notifications_type"),
            models.CheckConstraint(condition=Q(channel__in=["sms", "email", "push", "in_app"]), name="ck_patient_notifications_channel"),
            models.CheckConstraint(condition=Q(status__in=["pending", "processing", "sent", "delivered", "failed", "cancelled"]), name="ck_patient_notifications_status"),
            models.CheckConstraint(condition=Q(attempt_count__gte=0), name="ck_patient_notifications_attempts"),
            models.CheckConstraint(condition=Q(channel="in_app") | Q(destination_encrypted__isnull=False), name="ck_patient_notifications_destination"),
            models.CheckConstraint(condition=~Q(channel__in=["push", "in_app"]) | Q(recipient_user__isnull=False), name="ck_patient_notifications_recipient"),
            models.CheckConstraint(condition=~(Q(appointment__isnull=False) & Q(queue_entry__isnull=False)), name="ck_patient_notifications_single_source"),
            models.CheckConstraint(condition=~(Q(delivered_at__isnull=False) & Q(failed_at__isnull=False)), name="ck_patient_notifications_outcome"),
        ]
        indexes = [
            models.Index(fields=["status", "scheduled_for"], name="idx_pat_notif_dispatch", condition=Q(status__in=["pending", "processing"])),
            models.Index(fields=["patient", "-created_at"], name="idx_pat_notif_pat_time"),
            models.Index(fields=["appointment"], name="idx_pat_notif_appt"),
            models.Index(fields=["queue_entry"], name="idx_pat_notif_queue"),
            models.Index(fields=["recipient_user"], name="idx_pat_notif_recip"),
        ]

    # TODO: enforce patient notification timeline/state validation trigger from the SQL file in a custom migration.


class UserPushDevice(TimeStampedModel, ActiveModel):
    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="push_devices")
    platform = models.CharField(max_length=15, choices=Platform.choices)
    token_encrypted = models.TextField()
    token_hash = models.CharField(max_length=64, validators=[hash_validator])
    device_name = models.CharField(max_length=100, blank=True, null=True)
    app_version = models.CharField(max_length=30, blank=True, null=True)
    last_seen_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "user_push_devices"
        constraints = [
            models.UniqueConstraint(fields=["token_hash"], name="uq_user_push_devices_hash"),
            models.CheckConstraint(condition=Q(platform__in=["android", "ios", "web"]), name="ck_user_push_devices_platform"),
            models.CheckConstraint(condition=Q(token_hash__regex=r"^[0-9A-Fa-f]{64}$"), name="ck_user_push_devices_hash"),
            models.CheckConstraint(condition=Q(revoked_at__isnull=True) | Q(is_active=False), name="ck_user_push_devices_revocation"),
        ]
        indexes = [models.Index(fields=["user", "is_active"], name="idx_push_dev_user_act")]
