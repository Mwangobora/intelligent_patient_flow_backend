from __future__ import annotations

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.queueing.models import QueueEntry
from apps.queueing.services import call_queue_entry, start_service
from config.asgi import application


def _cookie_headers(user: User):
    refresh = RefreshToken.for_user(user)
    return [(b"cookie", f"access_token={refresh.access_token}".encode())]


@pytest.mark.django_db(transaction=True)
def test_patient_queue_socket_rejects_unauthenticated_user():
    async def run():
        communicator = WebsocketCommunicator(application, "/ws/patient/queue/")
        connected, _ = await communicator.connect()
        await communicator.disconnect()
        return connected

    import asyncio

    assert asyncio.run(run()) is False


@pytest.mark.django_db(transaction=True)
def test_staff_can_connect_to_facility_queue_socket_with_permission(user_factory, grant_system_permission, organization, facility):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="queueing_entry.view",
        scope="facility",
        organization=organization,
        facility=facility,
    )
    headers = _cookie_headers(user)

    async def run():
        communicator = WebsocketCommunicator(
            application,
            f"/ws/queueing/facilities/{facility.id}/",
            headers=headers,
        )
        connected, _ = await communicator.connect()
        message = await communicator.receive_json_from()
        await communicator.disconnect()
        return connected, message

    import asyncio

    connected, message = asyncio.run(run())
    assert connected is True
    assert message["type"] == "connected"
    assert message["scope"] == "facility_queue"
    assert message["facility_id"] == str(facility.id)


@pytest.mark.django_db(transaction=True)
def test_staff_queue_socket_rejects_user_without_permission(user_factory, open_queue):
    user = user_factory()
    headers = _cookie_headers(user)

    async def run():
        communicator = WebsocketCommunicator(
            application,
            f"/ws/queueing/queues/{open_queue.id}/",
            headers=headers,
        )
        connected, _ = await communicator.connect()
        await communicator.disconnect()
        return connected

    import asyncio

    assert asyncio.run(run()) is False


@pytest.mark.django_db(transaction=True)
def test_patient_queue_socket_returns_own_queue_snapshot(patient, user_factory, open_queue, patient_checkin):
    user = user_factory(email="patient-queue-socket@example.com")
    patient.user = user
    patient.save(update_fields=["user", "updated_at"])
    entry = QueueEntry.objects.create(
        queue=open_queue,
        patient_checkin=patient_checkin,
        sequence_number=1,
        status=QueueEntry.Status.WAITING,
    )
    headers = _cookie_headers(user)

    async def run():
        communicator = WebsocketCommunicator(
            application,
            "/ws/patient/queue/",
            headers=headers,
        )
        connected, _ = await communicator.connect()
        message = await communicator.receive_json_from()
        await communicator.disconnect()
        return connected, message

    import asyncio

    connected, message = asyncio.run(run())
    assert connected is True
    assert message["type"] == "patient_queue_snapshot"
    assert message["queue_entry"]["queue_entry_id"] == str(entry.id)
    assert message["queue_entry"]["queue_number"] == "FD-001"
    assert "patient_name" not in message["queue_entry"]


@pytest.mark.django_db(transaction=True)
def test_patient_queue_socket_updates_people_ahead_when_queue_moves(
    patient,
    user_factory,
    patient_factory,
    checkin_factory,
    open_queue,
    patient_checkin,
):
    second_user = user_factory(email="patient-behind-socket@example.com")
    second_patient = patient_factory(user=second_user)
    second_checkin = checkin_factory(patient=second_patient)
    first_entry = QueueEntry.objects.create(
        queue=open_queue,
        patient_checkin=patient_checkin,
        sequence_number=1,
        status=QueueEntry.Status.WAITING,
        joined_at=timezone.now(),
    )
    QueueEntry.objects.create(
        queue=open_queue,
        patient_checkin=second_checkin,
        sequence_number=2,
        status=QueueEntry.Status.WAITING,
        joined_at=timezone.now(),
    )
    headers = _cookie_headers(second_user)

    async def run():
        communicator = WebsocketCommunicator(
            application,
            "/ws/patient/queue/",
            headers=headers,
        )
        connected, _ = await communicator.connect()
        snapshot = await communicator.receive_json_from()
        await database_sync_to_async(call_queue_entry)(queue_entry_id=first_entry.id)
        call_update = await communicator.receive_json_from()
        await database_sync_to_async(start_service)(queue_entry_id=first_entry.id)
        service_update = await communicator.receive_json_from()
        await communicator.disconnect()
        return connected, snapshot, call_update, service_update

    import asyncio

    connected, snapshot, call_update, service_update = asyncio.run(run())
    assert connected is True
    assert snapshot["queue_entry"]["people_ahead"] == 1
    assert call_update["type"] == "patient_queue_update"
    assert call_update["event"] == "position_updated"
    assert call_update["queue_entry"]["people_ahead"] == 1
    assert service_update["type"] == "patient_queue_update"
    assert service_update["event"] == "position_updated"
    assert service_update["queue_entry"]["people_ahead"] == 0
