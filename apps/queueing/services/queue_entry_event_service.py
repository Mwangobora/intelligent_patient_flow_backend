from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.queueing.models import QueueEntryEvent
from common.exceptions import ConflictError, ValidationError

from ._shared import get_queue_entry, get_user, normalize_optional_text


@transaction.atomic
def record_queue_event(
    *,
    queue_entry,
    event_type: str,
    from_status: str | None = None,
    to_status: str | None = None,
    performed_by_id=None,
    reason: str | None = None,
    occurred_at=None,
) -> QueueEntryEvent:
    if not hasattr(queue_entry, "joined_at"):
        queue_entry = get_queue_entry(queue_entry, for_update=True)
    if event_type not in QueueEntryEvent.EventType.values:
        raise ValidationError("Invalid queue event type.")

    event_reason = normalize_optional_text(reason)
    if event_type in {
        QueueEntryEvent.EventType.CANCELLED,
        QueueEntryEvent.EventType.TRANSFERRED,
        QueueEntryEvent.EventType.PRIORITY_CHANGED,
    } and event_reason is None:
        raise ValidationError("reason is required for this queue event.")

    event_time = occurred_at or timezone.now()
    if event_time < queue_entry.joined_at:
        raise ValidationError("Queue event cannot occur before queue entry joined_at.")

    performed_by = get_user(performed_by_id, field_label="Performed by user", active_only=True) if performed_by_id is not None else None

    try:
        return QueueEntryEvent.objects.create(
            queue_entry=queue_entry,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            performed_by=performed_by,
            reason=event_reason,
            occurred_at=event_time,
        )
    except IntegrityError as exc:
        raise ConflictError("Queue event could not be recorded because a conflicting event already exists.") from exc
