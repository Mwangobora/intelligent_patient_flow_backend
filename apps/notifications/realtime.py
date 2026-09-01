from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from rest_framework.renderers import JSONRenderer

logger = logging.getLogger(__name__)


def patient_notifications_group_name(user_id) -> str:
    return f"patient_notifications_user_{user_id}"


def _make_json_safe(data: Any) -> Any:
    import json

    return json.loads(JSONRenderer().render(data))


def broadcast_patient_notification(*, notification_id, event: str) -> None:
    def _broadcast() -> None:
        from apps.notifications.models import PatientNotification
        from apps.notifications.serializers import PatientNotificationPatientOutputSerializer

        notification = (
            PatientNotification.objects.select_related("patient", "recipient_user")
            .filter(pk=notification_id)
            .first()
        )
        if notification is None:
            return
        user_id = notification.recipient_user_id or notification.patient.user_id
        if not user_id:
            return

        payload = {
            "type": "patient_notification_update",
            "event": event,
            "notification": _make_json_safe(PatientNotificationPatientOutputSerializer(notification).data),
        }
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        try:
            async_to_sync(channel_layer.group_send)(
                patient_notifications_group_name(user_id),
                {"type": "patient_notification_update", "payload": payload},
            )
        except Exception:
            logger.exception("Notification realtime broadcast failed for user %s", user_id)

    transaction.on_commit(_broadcast)
