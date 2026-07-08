from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.checkins.models import PatientCheckin
from apps.facilities.models import FacilitySpecialty, ServicePoint
from apps.scheduling.models import PractitionerShift
from common.db import TimeStampedModel


class Queue(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        PAUSED = "paused", "Paused"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    service_point = models.ForeignKey(ServicePoint, on_delete=models.PROTECT, related_name="queues")
    facility_specialty = models.ForeignKey(FacilitySpecialty, on_delete=models.PROTECT, related_name="queues", blank=True, null=True)
    queue_date = models.DateField()
    next_sequence_number = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    opened_at = models.DateTimeField(blank=True, null=True)
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="opened_queues", blank=True, null=True)
    paused_at = models.DateTimeField(blank=True, null=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="closed_queues", blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_queues", blank=True, null=True)

    class Meta:
        db_table = "queues"
        constraints = [
            models.UniqueConstraint(fields=["service_point", "queue_date"], condition=Q(facility_specialty__isnull=True), name="uq_queues_general"),
            models.UniqueConstraint(fields=["service_point", "facility_specialty", "queue_date"], condition=Q(facility_specialty__isnull=False), name="uq_queues_specialty"),
            models.CheckConstraint(condition=Q(next_sequence_number__gt=0), name="ck_queues_sequence"),
            models.CheckConstraint(condition=Q(status__in=[c for c, _ in Status.choices]), name="ck_queues_status"),
        ]
        indexes = [
            models.Index(fields=["queue_date", "status"], name="idx_queues_date_status"),
            models.Index(fields=["service_point", "status"], name="idx_queues_service_point_status"),
        ]



class QueueEntry(TimeStampedModel):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        CALLED = "called", "Called"
        IN_SERVICE = "in_service", "In Service"
        COMPLETED = "completed", "Completed"
        SKIPPED = "skipped", "Skipped"
        CANCELLED = "cancelled", "Cancelled"
        TRANSFERRED = "transferred", "Transferred"

    queue = models.ForeignKey(Queue, on_delete=models.PROTECT, related_name="entries")
    patient_checkin = models.ForeignKey(PatientCheckin, on_delete=models.PROTECT, related_name="queue_entries")
    practitioner_shift = models.ForeignKey(PractitionerShift, on_delete=models.PROTECT, related_name="queue_entries", blank=True, null=True)
    sequence_number = models.IntegerField()
    priority_level = models.SmallIntegerField(default=0)
    priority_reason = models.CharField(max_length=250, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WAITING)
    joined_at = models.DateTimeField(default=timezone.now)
    called_at = models.DateTimeField(blank=True, null=True)
    service_started_at = models.DateTimeField(blank=True, null=True)
    service_completed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="cancelled_queue_entries", blank=True, null=True)
    cancellation_reason = models.CharField(max_length=250, blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_queue_entries", blank=True, null=True)

    class Meta:
        db_table = "queue_entries"
        constraints = [
            models.UniqueConstraint(fields=["queue", "sequence_number"], name="uq_queue_entries_sequence"),
            models.UniqueConstraint(fields=["queue", "patient_checkin"], name="uq_queue_entries_checkin"),
            models.CheckConstraint(condition=Q(sequence_number__gt=0), name="ck_queue_entries_sequence"),
            models.CheckConstraint(condition=Q(priority_level__gte=0, priority_level__lte=3), name="ck_queue_entries_priority"),
            models.CheckConstraint(condition=Q(priority_level=0) | Q(priority_reason__isnull=False), name="ck_queue_entries_priority_reason"),
            models.CheckConstraint(condition=Q(status__in=[c for c, _ in Status.choices]), name="ck_queue_entries_status"),
        ]
        indexes = [
            models.Index(fields=["queue", "status"], name="idx_queue_entries_queue_status"),
            models.Index(fields=["queue", "-priority_level", "joined_at", "sequence_number"], name="idx_queue_entries_order"),
            models.Index(fields=["patient_checkin"], name="idx_queue_entries_checkin"),
            models.Index(fields=["practitioner_shift"], name="idx_queue_entries_shift"),
        ]


class QueueTransfer(models.Model):
    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4, editable=False)
    source_queue_entry = models.OneToOneField(QueueEntry, on_delete=models.PROTECT, related_name="outgoing_transfer")
    destination_queue_entry = models.OneToOneField(QueueEntry, on_delete=models.PROTECT, related_name="incoming_transfer")
    transferred_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="queue_transfers", blank=True, null=True)
    transfer_reason = models.CharField(max_length=250)
    transferred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "queue_transfers"
        constraints = [models.CheckConstraint(condition=~Q(source_queue_entry=F("destination_queue_entry")), name="ck_queue_transfers_distinct")]
        indexes = [models.Index(fields=["transferred_at"], name="idx_queue_transfers_time")]


class QueueEntryEvent(models.Model):
    class EventType(models.TextChoices):
        JOINED = "joined", "Joined"
        CALLED = "called", "Called"
        RECALLED = "recalled", "Recalled"
        SKIPPED = "skipped", "Skipped"
        SERVICE_STARTED = "service_started", "Service Started"
        SERVICE_COMPLETED = "service_completed", "Service Completed"
        CANCELLED = "cancelled", "Cancelled"
        TRANSFERRED = "transferred", "Transferred"
        PRIORITY_CHANGED = "priority_changed", "Priority Changed"

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        CALLED = "called", "Called"
        IN_SERVICE = "in_service", "In Service"
        COMPLETED = "completed", "Completed"
        SKIPPED = "skipped", "Skipped"
        CANCELLED = "cancelled", "Cancelled"
        TRANSFERRED = "transferred", "Transferred"

    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4, editable=False)
    queue_entry = models.ForeignKey(QueueEntry, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    from_status = models.CharField(max_length=20, choices=Status.choices, blank=True, null=True)
    to_status = models.CharField(max_length=20, choices=Status.choices, blank=True, null=True)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="queue_entry_events", blank=True, null=True)
    reason = models.CharField(max_length=250, blank=True, null=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "queue_entry_events"
        constraints = [
            models.UniqueConstraint(fields=["queue_entry"], condition=Q(event_type="joined"), name="uq_queue_entry_events_one_joined"),
            models.CheckConstraint(condition=Q(event_type__in=[c for c, _ in EventType.choices]), name="ck_queue_entry_events_type"),
            models.CheckConstraint(condition=Q(from_status__isnull=True) | Q(from_status__in=[c for c, _ in Status.choices]), name="ck_queue_entry_events_from_status"),
            models.CheckConstraint(condition=Q(to_status__isnull=True) | Q(to_status__in=[c for c, _ in Status.choices]), name="ck_queue_entry_events_to_status"),
            models.CheckConstraint(condition=~Q(event_type__in=["cancelled", "transferred", "priority_changed"]) | Q(reason__isnull=False), name="ck_queue_entry_events_reason"),
        ]
        indexes = [
            models.Index(fields=["queue_entry", "occurred_at"], name="idx_queue_entry_events_entry_time"),
            models.Index(fields=["event_type", "occurred_at"], name="idx_queue_entry_events_type_time"),
        ]
