from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.notifications.realtime import patient_notifications_group_name
from apps.patients.models import Patient


@database_sync_to_async
def _has_patient_profile(user) -> bool:
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    return Patient.objects.filter(user=user, is_active=True).exists()


class PatientNotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        if not await _has_patient_profile(self.scope["user"]):
            await self.close(code=4403)
            return
        self.group_name = patient_notifications_group_name(self.scope["user"].id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "scope": "patient_notifications"})

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def patient_notification_update(self, event):
        await self.send_json(event["payload"])
