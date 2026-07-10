from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.queueing.models import Queue
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    facility_local_date,
    get_facility_specialty,
    get_queue,
    get_service_point,
    get_user,
    validate_service_point_specialty_scope,
)


@transaction.atomic
def create_queue(*, service_point_id, queue_date=None, facility_specialty_id=None, created_by_id=None) -> Queue:
    service_point = get_service_point(service_point_id, active_only=True, for_update=True)
    facility_specialty = (
        get_facility_specialty(facility_specialty_id, active_only=True, for_update=True)
        if facility_specialty_id is not None
        else None
    )
    created_by = get_user(created_by_id, field_label="Created by user", active_only=True) if created_by_id is not None else None
    validate_service_point_specialty_scope(service_point=service_point, facility_specialty=facility_specialty)

    try:
        return Queue.objects.create(
            service_point=service_point,
            facility_specialty=facility_specialty,
            queue_date=queue_date or facility_local_date(service_point.facility),
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Queue already exists for this service point, specialty, and date.") from exc


@transaction.atomic
def open_queue(*, queue_id, opened_by_id=None, opened_at=None) -> Queue:
    queue = get_queue(queue_id, for_update=True)
    opened_by = get_user(opened_by_id, field_label="Opened by user", active_only=True) if opened_by_id is not None else None
    if queue.status == Queue.Status.CLOSED:
        raise ValidationError("Closed queue cannot be reopened.")
    if queue.status == Queue.Status.CANCELLED:
        raise ValidationError("Cancelled queue cannot be opened.")
    if queue.status == Queue.Status.OPEN:
        return queue

    queue.status = Queue.Status.OPEN
    queue.opened_at = queue.opened_at or opened_at or timezone.now()
    queue.opened_by = queue.opened_by or opened_by
    queue.paused_at = None
    queue.closed_at = None
    queue.closed_by = None
    queue.save(update_fields=["status", "opened_at", "opened_by", "paused_at", "closed_at", "closed_by", "updated_at"])
    return queue


@transaction.atomic
def pause_queue(*, queue_id, paused_at=None) -> Queue:
    queue = get_queue(queue_id, for_update=True)
    if queue.status != Queue.Status.OPEN:
        raise ValidationError("Only an open queue can be paused.")
    queue.status = Queue.Status.PAUSED
    queue.paused_at = paused_at or timezone.now()
    queue.save(update_fields=["status", "paused_at", "updated_at"])
    return queue


@transaction.atomic
def resume_queue(*, queue_id) -> Queue:
    queue = get_queue(queue_id, for_update=True)
    if queue.status != Queue.Status.PAUSED:
        raise ValidationError("Only a paused queue can be resumed.")
    queue.status = Queue.Status.OPEN
    queue.paused_at = None
    queue.save(update_fields=["status", "paused_at", "updated_at"])
    return queue


@transaction.atomic
def close_queue(*, queue_id, closed_by_id, closed_at=None) -> Queue:
    queue = get_queue(queue_id, for_update=True)
    closed_by = get_user(closed_by_id, field_label="Closed by user", active_only=True)
    if queue.status == Queue.Status.CLOSED:
        return queue
    if queue.status == Queue.Status.CANCELLED:
        raise ValidationError("Cancelled queue cannot be closed.")
    if queue.status == Queue.Status.DRAFT:
        raise ValidationError("Draft queue cannot be closed before it is opened.")

    queue.status = Queue.Status.CLOSED
    queue.closed_at = closed_at or timezone.now()
    queue.closed_by = closed_by
    queue.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
    return queue


@transaction.atomic
def cancel_queue(*, queue_id) -> Queue:
    queue = get_queue(queue_id, for_update=True)
    if queue.status == Queue.Status.CLOSED:
        raise ValidationError("Closed queue cannot be cancelled.")
    if queue.status == Queue.Status.CANCELLED:
        return queue
    queue.status = Queue.Status.CANCELLED
    queue.save(update_fields=["status", "updated_at"])
    return queue
