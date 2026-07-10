from __future__ import annotations

from apps.queueing.models import QueueEntryEvent


def list_queue_entry_events(*, queue_entry_id=None, event_type=None, occurred_from=None, occurred_to=None):
    queryset = QueueEntryEvent.objects.select_related(
        "queue_entry",
        "queue_entry__queue",
        "performed_by",
    )
    if queue_entry_id:
        queryset = queryset.filter(queue_entry_id=queue_entry_id)
    if event_type:
        queryset = queryset.filter(event_type=event_type)
    if occurred_from:
        queryset = queryset.filter(occurred_at__gte=occurred_from)
    if occurred_to:
        queryset = queryset.filter(occurred_at__lte=occurred_to)
    return queryset.order_by("occurred_at", "created_at")


def get_queue_entry_event_by_id(event_id):
    return list_queue_entry_events().filter(pk=event_id).first()
