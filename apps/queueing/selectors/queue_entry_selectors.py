from __future__ import annotations

from django.db.models import Q

from apps.queueing.models import QueueEntry
from apps.queueing.services._shared import ACTIVE_QUEUE_ENTRY_STATUSES


def base_queue_entry_queryset():
    return QueueEntry.objects.select_related(
        "queue",
        "queue__service_point",
        "queue__service_point__facility",
        "queue__facility_specialty",
        "queue__facility_specialty__specialty",
        "patient_checkin",
        "patient_checkin__patient",
        "patient_checkin__appointment",
        "practitioner_shift",
        "created_by",
        "cancelled_by",
    )


def queue_entry_ordering():
    return ["-priority_level", "joined_at", "sequence_number"]


def list_queue_entries(
    *,
    queue_id=None,
    facility_id=None,
    patient_id=None,
    patient_checkin_id=None,
    status=None,
    active_only: bool | None = None,
):
    queryset = base_queue_entry_queryset()
    if queue_id:
        queryset = queryset.filter(queue_id=queue_id)
    if facility_id:
        queryset = queryset.filter(queue__service_point__facility_id=facility_id)
    if patient_id:
        queryset = queryset.filter(patient_checkin__patient_id=patient_id)
    if patient_checkin_id:
        queryset = queryset.filter(patient_checkin_id=patient_checkin_id)
    if status:
        queryset = queryset.filter(status=status)
    if active_only is True:
        queryset = queryset.filter(status__in=ACTIVE_QUEUE_ENTRY_STATUSES)
    elif active_only is False:
        queryset = queryset.exclude(status__in=ACTIVE_QUEUE_ENTRY_STATUSES)
    return queryset.order_by(*queue_entry_ordering())


def list_active_entries_in_queue(*, queue_id):
    return list_queue_entries(queue_id=queue_id, active_only=True)


def get_queue_entry_by_id(entry_id):
    return base_queue_entry_queryset().filter(pk=entry_id).first()


def calculate_queue_position(*, entry: QueueEntry) -> int | None:
    if entry.status not in ACTIVE_QUEUE_ENTRY_STATUSES:
        return None
    ahead = QueueEntry.objects.filter(
        queue_id=entry.queue_id,
        status__in=ACTIVE_QUEUE_ENTRY_STATUSES,
    ).filter(
        Q(priority_level__gt=entry.priority_level)
        | Q(priority_level=entry.priority_level, joined_at__lt=entry.joined_at)
        | Q(priority_level=entry.priority_level, joined_at=entry.joined_at, sequence_number__lte=entry.sequence_number)
    )
    return ahead.count()


def get_next_callable_entry(*, queue_id):
    return list_queue_entries(queue_id=queue_id).filter(status=QueueEntry.Status.WAITING).first()


def list_entries_by_checkin(*, patient_checkin_id):
    return list_queue_entries(patient_checkin_id=patient_checkin_id)
