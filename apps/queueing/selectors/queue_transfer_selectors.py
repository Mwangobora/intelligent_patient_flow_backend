from __future__ import annotations

from apps.queueing.models import QueueTransfer


def list_queue_transfers(
    *,
    source_queue_entry_id=None,
    destination_queue_entry_id=None,
    facility_id=None,
    transferred_from=None,
    transferred_to=None,
):
    queryset = QueueTransfer.objects.select_related(
        "source_queue_entry",
        "source_queue_entry__queue",
        "source_queue_entry__queue__service_point",
        "destination_queue_entry",
        "destination_queue_entry__queue",
        "destination_queue_entry__queue__service_point",
        "transferred_by",
    )
    if source_queue_entry_id:
        queryset = queryset.filter(source_queue_entry_id=source_queue_entry_id)
    if destination_queue_entry_id:
        queryset = queryset.filter(destination_queue_entry_id=destination_queue_entry_id)
    if facility_id:
        queryset = queryset.filter(source_queue_entry__queue__service_point__facility_id=facility_id)
    if transferred_from:
        queryset = queryset.filter(transferred_at__gte=transferred_from)
    if transferred_to:
        queryset = queryset.filter(transferred_at__lte=transferred_to)
    return queryset.order_by("-transferred_at")


def get_queue_transfer_by_id(transfer_id):
    return list_queue_transfers().filter(pk=transfer_id).first()
