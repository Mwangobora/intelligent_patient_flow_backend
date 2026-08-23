from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from rest_framework.renderers import JSONRenderer

logger = logging.getLogger(__name__)


def facility_group_name(facility_id) -> str:
    return f"queue_facility_{facility_id}"


def queue_group_name(queue_id) -> str:
    return f"queue_{queue_id}"


def patient_queue_group_name(user_id) -> str:
    return f"patient_queue_user_{user_id}"


def _json_safe(data: Any) -> Any:
    return JSONRenderer().render(data)


def _decode_json_safe(data: Any) -> Any:
    import json

    return json.loads(_json_safe(data))


def _send_group(group: str, event_type: str, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(group, {"type": event_type, "payload": payload})
    except Exception:
        logger.exception("Queue realtime broadcast failed for group %s", group)


def broadcast_queue_update(*, queue_id, event: str) -> None:
    def _broadcast() -> None:
        from apps.queueing.models import Queue
        from apps.queueing.serializers import QueueOutputSerializer

        queue = Queue.objects.select_related(
            "service_point",
            "service_point__facility",
            "facility_specialty",
            "facility_specialty__specialty",
        ).filter(pk=queue_id).first()
        if queue is None:
            return
        payload = {
            "type": "queue_update",
            "event": event,
            "queue": _decode_json_safe(QueueOutputSerializer(queue).data),
        }
        _send_group(facility_group_name(queue.service_point.facility_id), "queue_update", payload)
        _send_group(queue_group_name(queue.id), "queue_update", payload)

    transaction.on_commit(_broadcast)


def broadcast_queue_entry_update(*, queue_entry_id, event: str) -> None:
    def _broadcast() -> None:
        from apps.patients.models import Patient
        from apps.patients.selectors import build_patient_queue_payload, get_current_patient_queue_entry
        from apps.queueing.models import QueueEntry
        from apps.queueing.serializers import QueueEntryOutputSerializer

        entry = QueueEntry.objects.select_related(
            "queue",
            "queue__service_point",
            "queue__service_point__facility",
            "patient_checkin",
            "patient_checkin__patient",
            "patient_checkin__appointment",
            "practitioner_shift",
            "created_by",
            "cancelled_by",
        ).filter(pk=queue_entry_id).first()
        if entry is None:
            return

        queue_entry_payload = _decode_json_safe(QueueEntryOutputSerializer(entry).data)
        payload = {"type": "queue_entry_update", "event": event, "queue_entry": queue_entry_payload}
        facility_id = entry.queue.service_point.facility_id
        _send_group(facility_group_name(facility_id), "queue_update", payload)
        _send_group(queue_group_name(entry.queue_id), "queue_update", payload)

        patient = entry.patient_checkin.patient
        if patient.user_id:
            current_entry = get_current_patient_queue_entry(patient=patient)
            patient_payload = {
                "type": "patient_queue_update",
                "event": event,
                "queue_entry": _decode_json_safe(build_patient_queue_payload(current_entry)),
            }
            _send_group(patient_queue_group_name(patient.user_id), "patient_queue_update", patient_payload)

    transaction.on_commit(_broadcast)
