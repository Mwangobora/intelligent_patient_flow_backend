from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.accounts.permissions import user_has_permission
from apps.facilities.models import Facility
from apps.patients.models import Patient
from apps.patients.selectors import build_patient_queue_payload, get_current_patient_queue_entry
from apps.queueing.models import Queue
from apps.queueing.realtime import facility_group_name, make_json_safe, patient_queue_group_name, queue_group_name


@database_sync_to_async
def _can_view_facility_queue(user, facility_id) -> bool:
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    facility = Facility.objects.select_related("organization").filter(pk=facility_id).first()
    if facility is None:
        return False
    return user_has_permission(user, "queueing_entry.view", organization=facility.organization_id, facility=facility.id)


@database_sync_to_async
def _can_view_queue(user, queue_id) -> tuple[bool, str | None]:
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return False, None
    queue = Queue.objects.select_related("service_point__facility").filter(pk=queue_id).first()
    if queue is None:
        return False, None
    facility = queue.service_point.facility
    allowed = user_has_permission(user, "queueing_entry.view", organization=facility.organization_id, facility=facility.id)
    return allowed, str(queue.id)


@database_sync_to_async
def _patient_queue_payload(user) -> tuple[bool, dict]:
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return False, {}
    patient = Patient.objects.filter(user=user, is_active=True).order_by("-created_at").first()
    if patient is None:
        return False, {}
    entry = get_current_patient_queue_entry(patient=patient)
    return True, make_json_safe(build_patient_queue_payload(entry))


class QueueFacilityConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.facility_id = str(self.scope["url_route"]["kwargs"]["facility_id"])
        if not await _can_view_facility_queue(self.scope["user"], self.facility_id):
            await self.close(code=4403)
            return
        self.group_name = facility_group_name(self.facility_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "scope": "facility_queue", "facility_id": self.facility_id})

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def queue_update(self, event):
        await self.send_json(event["payload"])


class QueueConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        allowed, queue_id = await _can_view_queue(self.scope["user"], self.scope["url_route"]["kwargs"]["queue_id"])
        if not allowed or queue_id is None:
            await self.close(code=4403)
            return
        self.group_name = queue_group_name(queue_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "scope": "queue", "queue_id": queue_id})

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def queue_update(self, event):
        await self.send_json(event["payload"])


class PatientQueueConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        allowed, payload = await _patient_queue_payload(self.scope["user"])
        if not allowed:
            await self.close(code=4403)
            return
        self.group_name = patient_queue_group_name(self.scope["user"].id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "patient_queue_snapshot", "queue_entry": payload})

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def patient_queue_update(self, event):
        await self.send_json(event["payload"])
