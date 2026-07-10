from __future__ import annotations

from django.db import transaction

from apps.queueing.models import Queue
from common.exceptions import ValidationError

from ._shared import get_queue


@transaction.atomic
def issue_next_sequence_number(*, queue_id) -> int:
    queue = get_queue(queue_id, for_update=True)
    if queue.status != Queue.Status.OPEN:
        raise ValidationError("Queue must be open to issue a sequence number.")

    sequence_number = queue.next_sequence_number
    queue.next_sequence_number += 1
    queue.save(update_fields=["next_sequence_number", "updated_at"])
    return sequence_number
