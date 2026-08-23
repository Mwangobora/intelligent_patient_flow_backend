from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.queueing.models import Queue, QueueEntry, QueueEntryEvent
from common.exceptions import ConflictError, ValidationError

from ..realtime import broadcast_queue_entry_update
from ._shared import (
    ACTIVE_QUEUE_ENTRY_STATUSES,
    TERMINAL_QUEUE_ENTRY_STATUSES,
    ensure_entry_can_transition,
    get_patient_checkin,
    get_practitioner_shift,
    get_queue,
    get_queue_entry,
    get_user,
    normalize_optional_text,
    validate_checkin_for_queue,
    validate_practitioner_shift_for_queue,
    validate_priority,
)
from .queue_entry_event_service import record_queue_event
from .queue_number_service import issue_next_sequence_number

logger = logging.getLogger(__name__)


def _mark_appointment_queued(*, entry: QueueEntry, changed_by_id=None) -> None:
    if entry.patient_checkin.appointment_id is None:
        return
    from apps.scheduling.services import mark_queued

    mark_queued(appointment_id=entry.patient_checkin.appointment_id, changed_by_id=changed_by_id)


def _mark_appointment_in_service(*, entry: QueueEntry, changed_by_id=None) -> None:
    if entry.patient_checkin.appointment_id is None:
        return
    from apps.scheduling.services import mark_in_service

    mark_in_service(appointment_id=entry.patient_checkin.appointment_id, changed_by_id=changed_by_id)


def _mark_appointment_completed(*, entry: QueueEntry, changed_by_id=None) -> None:
    if entry.patient_checkin.appointment_id is None:
        return
    from apps.scheduling.services import mark_completed

    mark_completed(appointment_id=entry.patient_checkin.appointment_id, changed_by_id=changed_by_id)


def _notify_patient_queue_event(*, entry: QueueEntry, event: str, event_id, created_by_id=None) -> None:
    if not entry.patient_checkin.patient.user_id:
        return
    try:
        from apps.notifications.services import send_notification
        from apps.notifications.services.notification_factory_service import (
            create_queue_called_notification,
            create_queue_joined_notification,
            create_queue_updated_notification,
        )

        factory = {
            "joined": create_queue_joined_notification,
            "called": create_queue_called_notification,
        }.get(event, create_queue_updated_notification)
        notification = factory(
            queue_entry_id=entry.id,
            idempotency_key=f"queue:{entry.id}:{event}:{event_id}",
            created_by_id=created_by_id,
        )
        send_notification(notification_id=notification.id)
    except Exception:
        logger.info("Patient queue notification skipped for entry %s event %s", entry.id, event, exc_info=True)


@transaction.atomic
def create_queue_entry(
    *,
    queue_id,
    patient_checkin_id,
    practitioner_shift_id=None,
    priority_level: int = 0,
    priority_reason: str | None = None,
    joined_at=None,
    created_by_id=None,
    mark_appointment_status: bool = True,
) -> QueueEntry:
    queue = get_queue(queue_id, for_update=True)
    if queue.status != Queue.Status.OPEN:
        raise ValidationError("Queue must be open to create entries.")

    checkin = get_patient_checkin(patient_checkin_id, for_update=True)
    validate_checkin_for_queue(checkin=checkin, queue=queue)
    validate_priority(priority_level=priority_level, priority_reason=priority_reason)

    practitioner_shift = None
    if practitioner_shift_id is not None:
        practitioner_shift = get_practitioner_shift(practitioner_shift_id, for_update=True)
        validate_practitioner_shift_for_queue(practitioner_shift=practitioner_shift, queue=queue)

    if QueueEntry.objects.select_for_update().filter(queue=queue, patient_checkin=checkin).exists():
        raise ConflictError("Check-in already exists in this queue.")

    sequence_number = issue_next_sequence_number(queue_id=queue.id)
    created_by = get_user(created_by_id, field_label="Created by user", active_only=True) if created_by_id is not None else None
    join_time = joined_at or timezone.now()

    try:
        entry = QueueEntry.objects.create(
            queue=queue,
            patient_checkin=checkin,
            practitioner_shift=practitioner_shift,
            sequence_number=sequence_number,
            priority_level=priority_level,
            priority_reason=normalize_optional_text(priority_reason),
            joined_at=join_time,
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Queue entry could not be created because a conflicting record already exists.") from exc

    event = record_queue_event(
        queue_entry=entry,
        event_type=QueueEntryEvent.EventType.JOINED,
        from_status=None,
        to_status=QueueEntry.Status.WAITING,
        performed_by_id=created_by_id,
        occurred_at=join_time,
    )
    if mark_appointment_status:
        _mark_appointment_queued(entry=entry, changed_by_id=created_by_id)
    entry.refresh_from_db()
    _notify_patient_queue_event(entry=entry, event="joined", event_id=event.id, created_by_id=created_by_id)
    broadcast_queue_entry_update(queue_entry_id=entry.id, event="joined")
    return entry


@transaction.atomic
def call_queue_entry(*, queue_entry_id, performed_by_id=None, called_at=None) -> QueueEntry:
    entry = get_queue_entry(queue_entry_id, for_update=True)
    ensure_entry_can_transition(entry=entry, allowed_statuses={QueueEntry.Status.WAITING, QueueEntry.Status.CALLED}, action="called")
    previous_status = entry.status
    event_time = called_at or timezone.now()
    if event_time < entry.joined_at:
        raise ValidationError("called_at must be greater than or equal to joined_at.")

    if entry.called_at is None:
        entry.called_at = event_time
    entry.status = QueueEntry.Status.CALLED
    entry.save(update_fields=["status", "called_at", "updated_at"])
    event = record_queue_event(
        queue_entry=entry,
        event_type=QueueEntryEvent.EventType.CALLED,
        from_status=previous_status,
        to_status=QueueEntry.Status.CALLED,
        performed_by_id=performed_by_id,
        occurred_at=event_time,
    )
    _notify_patient_queue_event(entry=entry, event="called", event_id=event.id, created_by_id=performed_by_id)
    broadcast_queue_entry_update(queue_entry_id=entry.id, event="called")
    return entry


@transaction.atomic
def recall_queue_entry(*, queue_entry_id, performed_by_id=None, recalled_at=None) -> QueueEntry:
    entry = get_queue_entry(queue_entry_id, for_update=True)
    ensure_entry_can_transition(entry=entry, allowed_statuses={QueueEntry.Status.SKIPPED}, action="recalled")
    event_time = recalled_at or timezone.now()
    previous_status = entry.status
    entry.status = QueueEntry.Status.CALLED
    entry.save(update_fields=["status", "updated_at"])
    event = record_queue_event(
        queue_entry=entry,
        event_type=QueueEntryEvent.EventType.RECALLED,
        from_status=previous_status,
        to_status=QueueEntry.Status.CALLED,
        performed_by_id=performed_by_id,
        occurred_at=event_time,
    )
    _notify_patient_queue_event(entry=entry, event="recalled", event_id=event.id, created_by_id=performed_by_id)
    broadcast_queue_entry_update(queue_entry_id=entry.id, event="recalled")
    return entry


@transaction.atomic
def skip_queue_entry(*, queue_entry_id, performed_by_id=None, reason: str | None = None, skipped_at=None) -> QueueEntry:
    entry = get_queue_entry(queue_entry_id, for_update=True)
    ensure_entry_can_transition(entry=entry, allowed_statuses={QueueEntry.Status.CALLED}, action="skipped")
    event_time = skipped_at or timezone.now()
    previous_status = entry.status
    entry.status = QueueEntry.Status.SKIPPED
    entry.save(update_fields=["status", "updated_at"])
    event = record_queue_event(
        queue_entry=entry,
        event_type=QueueEntryEvent.EventType.SKIPPED,
        from_status=previous_status,
        to_status=QueueEntry.Status.SKIPPED,
        performed_by_id=performed_by_id,
        reason=reason,
        occurred_at=event_time,
    )
    _notify_patient_queue_event(entry=entry, event="skipped", event_id=event.id, created_by_id=performed_by_id)
    broadcast_queue_entry_update(queue_entry_id=entry.id, event="skipped")
    return entry


@transaction.atomic
def start_service(*, queue_entry_id, performed_by_id=None, started_at=None, allow_skipped: bool = False) -> QueueEntry:
    entry = get_queue_entry(queue_entry_id, for_update=True)
    allowed_statuses = {QueueEntry.Status.CALLED}
    if allow_skipped:
        allowed_statuses.add(QueueEntry.Status.SKIPPED)
    ensure_entry_can_transition(entry=entry, allowed_statuses=allowed_statuses, action="started")
    event_time = started_at or timezone.now()
    if entry.called_at is None or event_time < entry.called_at:
        raise ValidationError("service_started_at must be greater than or equal to called_at.")

    previous_status = entry.status
    entry.status = QueueEntry.Status.IN_SERVICE
    entry.service_started_at = event_time
    entry.save(update_fields=["status", "service_started_at", "updated_at"])
    event = record_queue_event(
        queue_entry=entry,
        event_type=QueueEntryEvent.EventType.SERVICE_STARTED,
        from_status=previous_status,
        to_status=QueueEntry.Status.IN_SERVICE,
        performed_by_id=performed_by_id,
        occurred_at=event_time,
    )
    _mark_appointment_in_service(entry=entry, changed_by_id=performed_by_id)
    _notify_patient_queue_event(entry=entry, event="service_started", event_id=event.id, created_by_id=performed_by_id)
    broadcast_queue_entry_update(queue_entry_id=entry.id, event="service_started")
    return entry


@transaction.atomic
def complete_service(*, queue_entry_id, performed_by_id=None, completed_at=None) -> QueueEntry:
    entry = get_queue_entry(queue_entry_id, for_update=True)
    ensure_entry_can_transition(entry=entry, allowed_statuses={QueueEntry.Status.IN_SERVICE}, action="completed")
    event_time = completed_at or timezone.now()
    if entry.service_started_at is None or event_time < entry.service_started_at:
        raise ValidationError("service_completed_at must be greater than or equal to service_started_at.")

    previous_status = entry.status
    entry.status = QueueEntry.Status.COMPLETED
    entry.service_completed_at = event_time
    entry.save(update_fields=["status", "service_completed_at", "updated_at"])
    event = record_queue_event(
        queue_entry=entry,
        event_type=QueueEntryEvent.EventType.SERVICE_COMPLETED,
        from_status=previous_status,
        to_status=QueueEntry.Status.COMPLETED,
        performed_by_id=performed_by_id,
        occurred_at=event_time,
    )
    _mark_appointment_completed(entry=entry, changed_by_id=performed_by_id)
    _notify_patient_queue_event(entry=entry, event="service_completed", event_id=event.id, created_by_id=performed_by_id)
    broadcast_queue_entry_update(queue_entry_id=entry.id, event="service_completed")
    return entry


@transaction.atomic
def cancel_queue_entry(*, queue_entry_id, cancelled_by_id, cancellation_reason: str, cancelled_at=None) -> QueueEntry:
    entry = get_queue_entry(queue_entry_id, for_update=True)
    ensure_entry_can_transition(entry=entry, allowed_statuses=ACTIVE_QUEUE_ENTRY_STATUSES, action="cancelled")
    cancelled_by = get_user(cancelled_by_id, field_label="Cancelled by user", active_only=True)
    reason = normalize_optional_text(cancellation_reason)
    if reason is None:
        raise ValidationError("cancellation_reason is required.")
    event_time = cancelled_at or timezone.now()
    if event_time < entry.joined_at:
        raise ValidationError("cancelled_at must be greater than or equal to joined_at.")

    previous_status = entry.status
    entry.status = QueueEntry.Status.CANCELLED
    entry.cancelled_at = event_time
    entry.cancelled_by = cancelled_by
    entry.cancellation_reason = reason
    entry.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancellation_reason", "updated_at"])
    event = record_queue_event(
        queue_entry=entry,
        event_type=QueueEntryEvent.EventType.CANCELLED,
        from_status=previous_status,
        to_status=QueueEntry.Status.CANCELLED,
        performed_by_id=cancelled_by_id,
        reason=reason,
        occurred_at=event_time,
    )
    _notify_patient_queue_event(entry=entry, event="cancelled", event_id=event.id, created_by_id=cancelled_by_id)
    broadcast_queue_entry_update(queue_entry_id=entry.id, event="cancelled")
    return entry


@transaction.atomic
def change_priority(*, queue_entry_id, priority_level: int, priority_reason: str, performed_by_id=None) -> QueueEntry:
    entry = get_queue_entry(queue_entry_id, for_update=True)
    if entry.status in TERMINAL_QUEUE_ENTRY_STATUSES:
        raise ValidationError("Terminal queue entry priority cannot be changed.")
    validate_priority(priority_level=priority_level, priority_reason=priority_reason)
    reason = normalize_optional_text(priority_reason)

    entry.priority_level = priority_level
    entry.priority_reason = reason
    entry.save(update_fields=["priority_level", "priority_reason", "updated_at"])
    event = record_queue_event(
        queue_entry=entry,
        event_type=QueueEntryEvent.EventType.PRIORITY_CHANGED,
        from_status=entry.status,
        to_status=entry.status,
        performed_by_id=performed_by_id,
        reason=reason,
    )
    _notify_patient_queue_event(entry=entry, event="priority_changed", event_id=event.id, created_by_id=performed_by_id)
    broadcast_queue_entry_update(queue_entry_id=entry.id, event="priority_changed")
    return entry
