from __future__ import annotations

from django.db.models import Prefetch

from apps.queueing.models import Queue

from .queue_entry_selectors import list_active_entries_in_queue


def list_queues(
    *,
    facility_id=None,
    service_point_id=None,
    facility_specialty_id=None,
    queue_date=None,
    status=None,
):
    queryset = Queue.objects.select_related(
        "service_point",
        "service_point__facility",
        "service_point__department",
        "facility_specialty",
        "facility_specialty__specialty",
        "facility_specialty__department",
        "opened_by",
        "closed_by",
        "created_by",
    )
    if facility_id:
        queryset = queryset.filter(service_point__facility_id=facility_id)
    if service_point_id:
        queryset = queryset.filter(service_point_id=service_point_id)
    if facility_specialty_id:
        queryset = queryset.filter(facility_specialty_id=facility_specialty_id)
    if queue_date:
        queryset = queryset.filter(queue_date=queue_date)
    if status:
        queryset = queryset.filter(status=status)
    return queryset.order_by("-queue_date", "service_point__display_order", "service_point__code")


def get_queue_by_id(queue_id):
    return list_queues().prefetch_related(
        Prefetch("entries", queryset=list_active_entries_in_queue(queue_id=queue_id))
    ).filter(pk=queue_id).first()
