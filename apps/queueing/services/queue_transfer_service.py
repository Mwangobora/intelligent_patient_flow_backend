from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.queueing.models import Queue, QueueEntry, QueueEntryEvent, QueueTransfer
from common.exceptions import ConflictError, ValidationError

from ..realtime import broadcast_queue_entry_update
from ._shared import get_queue, get_queue_entry, get_user, normalize_optional_text, validate_checkin_for_queue
from .queue_entry_event_service import record_queue_event
from .queue_entry_service import create_queue_entry

logger = logging.getLogger(__name__)

TRANSFERABLE_QUEUE_ENTRY_STATUSES = {
    QueueEntry.Status.WAITING,
    QueueEntry.Status.CALLED,
    QueueEntry.Status.SKIPPED,
    QueueEntry.Status.IN_SERVICE,
}


def _notify_patient_transfer(*, source_entry: QueueEntry, destination_entry: QueueEntry, event_id, created_by_id=None) -> None:
    if not source_entry.patient_checkin.patient.user_id:
        return
    try:
        from apps.notifications.services import send_notification
        from apps.notifications.services.notification_factory_service import create_queue_updated_notification

        source_notification = create_queue_updated_notification(
            queue_entry_id=source_entry.id,
            idempotency_key=f"queue:{source_entry.id}:transferred:{event_id}",
            created_by_id=created_by_id,
        )
        destination_notification = create_queue_updated_notification(
            queue_entry_id=destination_entry.id,
            idempotency_key=f"queue:{destination_entry.id}:transfer_joined:{event_id}",
            created_by_id=created_by_id,
        )
        send_notification(notification_id=source_notification.id)
        send_notification(notification_id=destination_notification.id)
    except Exception:
        logger.info("Patient queue transfer notification skipped for entry %s", source_entry.id, exc_info=True)


@transaction.atomic
def transfer_queue_entry(
    *,
    source_queue_entry_id,
    destination_queue_id,
    transfer_reason: str,
    transferred_by_id=None,
    transferred_at=None,
) -> QueueTransfer:
    source_entry = get_queue_entry(source_queue_entry_id, for_update=True)
    destination_queue = get_queue(destination_queue_id, for_update=True)
    transferred_by = get_user(transferred_by_id, field_label="Transferred by user", active_only=True) if transferred_by_id is not None else None
    reason = normalize_optional_text(transfer_reason)
    if reason is None:
        raise ValidationError("transfer_reason is required.")
    if source_entry.status not in TRANSFERABLE_QUEUE_ENTRY_STATUSES:
        raise ValidationError("Only waiting, called, skipped, or in-service entries can be transferred.")
    if destination_queue.status != Queue.Status.OPEN:
        raise ValidationError("Destination queue must be open.")
    if source_entry.queue_id == destination_queue.id:
        raise ValidationError("Destination queue must be different from source queue.")
    if source_entry.queue.service_point.facility_id != destination_queue.service_point.facility_id:
        raise ValidationError("Queue transfer must stay within the same facility.")
    validate_checkin_for_queue(checkin=source_entry.patient_checkin, queue=destination_queue)

    transfer_time = transferred_at or timezone.now()
    if transfer_time < source_entry.joined_at:
        raise ValidationError("transferred_at must be greater than or equal to source joined_at.")

    previous_status = source_entry.status
    source_entry.status = QueueEntry.Status.TRANSFERRED
    source_entry.save(update_fields=["status", "updated_at"])
    event = record_queue_event(
        queue_entry=source_entry,
        event_type=QueueEntryEvent.EventType.TRANSFERRED,
        from_status=previous_status,
        to_status=QueueEntry.Status.TRANSFERRED,
        performed_by_id=transferred_by_id,
        reason=reason,
        occurred_at=transfer_time,
    )

    destination_entry = create_queue_entry(
        queue_id=destination_queue.id,
        patient_checkin_id=source_entry.patient_checkin_id,
        practitioner_shift_id=None,
        priority_level=source_entry.priority_level,
        priority_reason=source_entry.priority_reason,
        joined_at=transfer_time,
        created_by_id=transferred_by_id,
        mark_appointment_status=False,
    )

    try:
        transfer = QueueTransfer.objects.create(
            source_queue_entry=source_entry,
            destination_queue_entry=destination_entry,
            transferred_by=transferred_by,
            transfer_reason=reason,
            transferred_at=transfer_time,
        )
        _notify_patient_transfer(
            source_entry=source_entry,
            destination_entry=destination_entry,
            event_id=event.id,
            created_by_id=transferred_by_id,
        )
        broadcast_queue_entry_update(queue_entry_id=source_entry.id, event="transferred")
        return transfer
    except IntegrityError as exc:
        raise ConflictError("Queue transfer could not be created because a conflicting transfer already exists.") from exc
