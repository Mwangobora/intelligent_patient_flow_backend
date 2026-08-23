from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import DatabaseError
from django.urls import reverse
from django.utils import timezone

from apps.checkins.models import PatientCheckin
from apps.queueing.models import Queue, QueueEntry, QueueEntryEvent, QueueTransfer
from apps.scheduling.models import Appointment


def grant_queue_permissions(user, grant_system_permission, organization, *codes):
    for code in codes:
        grant_system_permission(user=user, permission_code=code, scope="organization", organization=organization)


def queue_payload(service_point, **overrides):
    payload = {
        "service_point_id": str(service_point.id),
        "queue_date": timezone.localdate().isoformat(),
    }
    payload.update(overrides)
    return payload


def entry_payload(queue, checkin, **overrides):
    payload = {
        "queue_id": str(queue.id),
        "patient_checkin_id": str(checkin.id),
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_unauthenticated_users_cannot_access_protected_endpoints(api_client):
    response = api_client.get(reverse("queueing-queues-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_unauthorized_users_cannot_create_open_or_close_queue(authenticated_client, queue, service_point, user_factory):
    user = user_factory()
    client = authenticated_client(user)

    create_response = client.post(reverse("queueing-queues-list"), queue_payload(service_point), format="json")
    open_response = client.post(reverse("queueing-queues-open", kwargs={"pk": queue.id}), format="json")
    close_response = client.post(reverse("queueing-queues-close", kwargs={"pk": queue.id}), format="json")

    assert create_response.status_code == 403
    assert open_response.status_code == 403
    assert close_response.status_code == 403


@pytest.mark.django_db
def test_authorized_user_can_create_queue(authenticated_client, grant_system_permission, organization, service_point, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_queue.manage")
    client = authenticated_client(user)

    response = client.post(reverse("queueing-queues-list"), queue_payload(service_point), format="json")

    assert response.status_code == 201
    assert response.data["status"] == Queue.Status.DRAFT


@pytest.mark.django_db
def test_duplicate_queue_same_service_point_date_specialty_fails(authenticated_client, grant_system_permission, organization, queue, service_point, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_queue.manage")
    client = authenticated_client(user)

    response = client.post(reverse("queueing-queues-list"), queue_payload(service_point), format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_queue_can_be_opened(authenticated_client, grant_system_permission, organization, queue, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_queue.manage")
    client = authenticated_client(user)

    response = client.post(reverse("queueing-queues-open", kwargs={"pk": queue.id}), format="json")

    assert response.status_code == 200
    assert response.data["status"] == Queue.Status.OPEN
    assert response.data["opened_at"] is not None


@pytest.mark.django_db
def test_queue_can_be_paused_and_resumed(authenticated_client, grant_system_permission, open_queue, organization, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_queue.manage")
    client = authenticated_client(user)

    pause_response = client.post(reverse("queueing-queues-pause", kwargs={"pk": open_queue.id}), format="json")
    resume_response = client.post(reverse("queueing-queues-resume", kwargs={"pk": open_queue.id}), format="json")

    assert pause_response.status_code == 200
    assert pause_response.data["status"] == Queue.Status.PAUSED
    assert resume_response.status_code == 200
    assert resume_response.data["status"] == Queue.Status.OPEN


@pytest.mark.django_db
def test_closed_queue_cannot_accept_new_entries(authenticated_client, grant_system_permission, open_queue, organization, patient_checkin, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_queue.manage", "queueing_entry.create")
    client = authenticated_client(user)
    client.post(reverse("queueing-queues-close", kwargs={"pk": open_queue.id}), format="json")

    response = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, patient_checkin), format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_cancelled_queue_cannot_accept_new_entries(authenticated_client, grant_system_permission, open_queue, organization, patient_checkin, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_queue.manage", "queueing_entry.create")
    client = authenticated_client(user)
    client.post(reverse("queueing-queues-cancel", kwargs={"pk": open_queue.id}), format="json")

    response = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, patient_checkin), format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_queue_entry_creation_issues_sequence_number_atomically(authenticated_client, checkin_factory, grant_system_permission, open_queue, organization, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create")
    client = authenticated_client(user)

    first = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")
    second = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")

    assert first.status_code == 201
    assert second.status_code == 201
    assert [first.data["sequence_number"], second.data["sequence_number"]] == [1, 2]


@pytest.mark.django_db
def test_displayed_queue_number_uses_service_point_code_and_sequence_number(authenticated_client, checkin_factory, flow_settings, grant_system_permission, open_queue, organization, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create")
    client = authenticated_client(user)

    response = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")

    assert response.status_code == 201
    assert response.data["display_queue_number"] == "FD-0001"


@pytest.mark.django_db
def test_same_checkin_cannot_enter_same_queue_twice(authenticated_client, grant_system_permission, open_queue, organization, patient_checkin, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create")
    client = authenticated_client(user)
    payload = entry_payload(open_queue, patient_checkin)

    first = client.post(reverse("queueing-entries-list"), payload, format="json")
    second = client.post(reverse("queueing-entries-list"), payload, format="json")

    assert first.status_code == 201
    assert second.status_code == 400


@pytest.mark.django_db
def test_checkin_facility_must_match_queue_facility(authenticated_client, grant_system_permission, other_service_point, organization, patient_checkin, user_factory):
    queue = Queue.objects.create(service_point=other_service_point, queue_date=timezone.localdate(), status=Queue.Status.OPEN, opened_at=timezone.now())
    user = user_factory()
    grant_system_permission(user=user, permission_code="queueing_entry.create")
    client = authenticated_client(user)

    response = client.post(reverse("queueing-entries-list"), entry_payload(queue, patient_checkin), format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_specialty_specific_queue_requires_matching_checkin_or_appointment_specialty(authenticated_client, grant_system_permission, open_queue, organization, other_facility_specialty, patient_checkin, service_point, user_factory):
    open_queue.facility_specialty = other_facility_specialty
    open_queue.save(update_fields=["facility_specialty", "updated_at"])
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create")
    client = authenticated_client(user)

    response = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, patient_checkin), format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_queue_ordering_respects_priority_joined_at_and_sequence(authenticated_client, checkin_factory, grant_system_permission, open_queue, organization, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create", "queueing_entry.view")
    client = authenticated_client(user)
    now = timezone.now()
    normal = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory(), joined_at=(now - timedelta(minutes=1)).isoformat()), format="json")
    urgent = client.post(
        reverse("queueing-entries-list"),
        entry_payload(open_queue, checkin_factory(), priority_level=2, priority_reason="Urgent", joined_at=now.isoformat()),
        format="json",
    )

    next_response = client.get(reverse("queueing-queues-next-entry", kwargs={"pk": open_queue.id}))

    assert normal.status_code == 201
    assert urgent.status_code == 201
    assert next_response.status_code == 200
    assert next_response.data["id"] == urgent.data["id"]
    assert urgent.data["queue_position"] == 1


@pytest.mark.django_db
def test_priority_above_zero_requires_reason(authenticated_client, checkin_factory, grant_system_permission, open_queue, organization, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create")
    client = authenticated_client(user)

    response = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory(), priority_level=1), format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_call_entry_sets_status_called_and_called_at(authenticated_client, checkin_factory, grant_system_permission, open_queue, organization, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create", "queueing_entry.call")
    client = authenticated_client(user)
    entry = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")

    response = client.post(reverse("queueing-entries-call", kwargs={"pk": entry.data["id"]}), format="json")

    assert response.status_code == 200
    assert response.data["status"] == QueueEntry.Status.CALLED
    assert response.data["called_at"] is not None


@pytest.mark.django_db
def test_recall_creates_event_but_does_not_overwrite_first_called_at(authenticated_client, checkin_factory, grant_system_permission, open_queue, organization, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create", "queueing_entry.call", "queueing_entry.skip", "queueing_entry.view")
    client = authenticated_client(user)
    entry = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")
    called = client.post(reverse("queueing-entries-call", kwargs={"pk": entry.data["id"]}), format="json")
    client.post(reverse("queueing-entries-skip", kwargs={"pk": entry.data["id"]}), format="json")
    recalled = client.post(reverse("queueing-entries-recall", kwargs={"pk": entry.data["id"]}), format="json")
    events = client.get(reverse("queueing-entries-events", kwargs={"pk": entry.data["id"]}))

    assert recalled.status_code == 200
    assert recalled.data["called_at"] == called.data["called_at"]
    assert QueueEntryEvent.EventType.RECALLED in [event["event_type"] for event in events.data]


@pytest.mark.django_db
def test_skip_start_complete_and_cancel_workflows(authenticated_client, checkin_factory, grant_system_permission, open_queue, organization, user_factory):
    user = user_factory()
    grant_queue_permissions(
        user,
        grant_system_permission,
        organization,
        "queueing_entry.create",
        "queueing_entry.call",
        "queueing_entry.skip",
        "queueing_entry.start_service",
        "queueing_entry.complete_service",
        "queueing_entry.cancel",
    )
    client = authenticated_client(user)
    skipped_entry = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")
    service_entry = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")
    cancel_entry = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")

    client.post(reverse("queueing-entries-call", kwargs={"pk": skipped_entry.data["id"]}), format="json")
    skip_response = client.post(reverse("queueing-entries-skip", kwargs={"pk": skipped_entry.data["id"]}), format="json")
    client.post(reverse("queueing-entries-call", kwargs={"pk": service_entry.data["id"]}), format="json")
    start_response = client.post(reverse("queueing-entries-start-service", kwargs={"pk": service_entry.data["id"]}), format="json")
    complete_response = client.post(reverse("queueing-entries-complete-service", kwargs={"pk": service_entry.data["id"]}), format="json")
    cancel_response = client.post(reverse("queueing-entries-cancel", kwargs={"pk": cancel_entry.data["id"]}), {"cancellation_reason": "Left"}, format="json")

    assert skip_response.data["status"] == QueueEntry.Status.SKIPPED
    assert start_response.data["status"] == QueueEntry.Status.IN_SERVICE
    assert complete_response.data["status"] == QueueEntry.Status.COMPLETED
    assert cancel_response.data["status"] == QueueEntry.Status.CANCELLED


@pytest.mark.django_db
def test_completed_entry_cannot_be_cancelled_normally(authenticated_client, checkin_factory, grant_system_permission, open_queue, organization, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create", "queueing_entry.call", "queueing_entry.start_service", "queueing_entry.complete_service", "queueing_entry.cancel")
    client = authenticated_client(user)
    entry = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")
    client.post(reverse("queueing-entries-call", kwargs={"pk": entry.data["id"]}), format="json")
    client.post(reverse("queueing-entries-start-service", kwargs={"pk": entry.data["id"]}), format="json")
    client.post(reverse("queueing-entries-complete-service", kwargs={"pk": entry.data["id"]}), format="json")

    response = client.post(reverse("queueing-entries-cancel", kwargs={"pk": entry.data["id"]}), {"cancellation_reason": "No"}, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_transfer_creates_destination_and_marks_source_transferred(authenticated_client, grant_system_permission, open_queue, organization, patient_checkin, second_open_queue, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create", "queueing_entry.transfer")
    client = authenticated_client(user)
    entry = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, patient_checkin), format="json")

    response = client.post(
        reverse("queueing-entries-transfer", kwargs={"pk": entry.data["id"]}),
        {"destination_queue_id": str(second_open_queue.id), "transfer_reason": "Wrong desk"},
        format="json",
    )

    source = QueueEntry.objects.get(pk=entry.data["id"])
    destination = QueueEntry.objects.get(pk=response.data["destination_queue_entry"])
    assert response.status_code == 201
    assert source.status == QueueEntry.Status.TRANSFERRED
    assert destination.status == QueueEntry.Status.WAITING
    assert destination.patient_checkin_id == source.patient_checkin_id
    assert destination.sequence_number == 1


@pytest.mark.django_db
def test_transfer_can_happen_from_in_service_to_lab_or_pharmacy_queue(authenticated_client, checkin_factory, grant_system_permission, open_queue, organization, second_open_queue, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create", "queueing_entry.call", "queueing_entry.start_service", "queueing_entry.transfer")
    client = authenticated_client(user)
    entry = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")
    client.post(reverse("queueing-entries-call", kwargs={"pk": entry.data["id"]}), format="json")
    client.post(reverse("queueing-entries-start-service", kwargs={"pk": entry.data["id"]}), format="json")

    response = client.post(
        reverse("queueing-entries-transfer", kwargs={"pk": entry.data["id"]}),
        {"destination_queue_id": str(second_open_queue.id), "transfer_reason": "Send to laboratory"},
        format="json",
    )

    assert response.status_code == 201
    assert QueueEntry.objects.get(pk=entry.data["id"]).status == QueueEntry.Status.TRANSFERRED
    assert QueueEntry.objects.get(pk=response.data["destination_queue_entry"]).status == QueueEntry.Status.WAITING


@pytest.mark.django_db
def test_transfer_cannot_happen_from_terminal_status(authenticated_client, checkin_factory, grant_system_permission, open_queue, organization, second_open_queue, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create", "queueing_entry.call", "queueing_entry.start_service", "queueing_entry.complete_service", "queueing_entry.transfer")
    client = authenticated_client(user)
    entry = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")
    client.post(reverse("queueing-entries-call", kwargs={"pk": entry.data["id"]}), format="json")
    client.post(reverse("queueing-entries-start-service", kwargs={"pk": entry.data["id"]}), format="json")
    client.post(reverse("queueing-entries-complete-service", kwargs={"pk": entry.data["id"]}), format="json")

    response = client.post(
        reverse("queueing-entries-transfer", kwargs={"pk": entry.data["id"]}),
        {"destination_queue_id": str(second_open_queue.id), "transfer_reason": "Too late"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_queue_entry_events_are_created_for_core_workflows(authenticated_client, checkin_factory, grant_system_permission, open_queue, organization, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create", "queueing_entry.call", "queueing_entry.skip", "queueing_priority.manage", "queueing_entry.view")
    client = authenticated_client(user)
    entry = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")
    client.post(reverse("queueing-entries-call", kwargs={"pk": entry.data["id"]}), format="json")
    client.post(reverse("queueing-entries-skip", kwargs={"pk": entry.data["id"]}), format="json")
    client.post(reverse("queueing-entries-change-priority", kwargs={"pk": entry.data["id"]}), {"priority_level": 1, "priority_reason": "Needs help"}, format="json")

    response = client.get(reverse("queueing-entries-events", kwargs={"pk": entry.data["id"]}))

    event_types = [event["event_type"] for event in response.data]
    assert QueueEntryEvent.EventType.JOINED in event_types
    assert QueueEntryEvent.EventType.CALLED in event_types
    assert QueueEntryEvent.EventType.SKIPPED in event_types
    assert QueueEntryEvent.EventType.PRIORITY_CHANGED in event_types


@pytest.mark.django_db
def test_appointment_linked_queue_entry_updates_appointment_status_to_queued_in_service_completed(authenticated_client, grant_system_permission, open_queue, organization, patient_checkin, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create", "queueing_entry.call", "queueing_entry.start_service", "queueing_entry.complete_service")
    client = authenticated_client(user)
    entry = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, patient_checkin), format="json")
    patient_checkin.appointment.refresh_from_db()
    queued_status = patient_checkin.appointment.status
    client.post(reverse("queueing-entries-call", kwargs={"pk": entry.data["id"]}), format="json")
    client.post(reverse("queueing-entries-start-service", kwargs={"pk": entry.data["id"]}), format="json")
    patient_checkin.appointment.refresh_from_db()
    in_service_status = patient_checkin.appointment.status
    client.post(reverse("queueing-entries-complete-service", kwargs={"pk": entry.data["id"]}), format="json")
    patient_checkin.appointment.refresh_from_db()

    assert queued_status == Appointment.Status.QUEUED
    assert in_service_status == Appointment.Status.IN_SERVICE
    assert patient_checkin.appointment.status == Appointment.Status.COMPLETED


@pytest.mark.django_db
def test_queue_position_is_calculated_and_not_stored(authenticated_client, checkin_factory, grant_system_permission, open_queue, organization, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create")
    client = authenticated_client(user)

    response = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")

    assert response.status_code == 201
    assert response.data["queue_position"] == 1
    assert not hasattr(QueueEntry.objects.get(pk=response.data["id"]), "queue_position")


@pytest.mark.django_db(transaction=True)
def test_event_rows_are_append_only_if_db_trigger_exists(authenticated_client, checkin_factory, grant_system_permission, open_queue, organization, user_factory):
    user = user_factory()
    grant_queue_permissions(user, grant_system_permission, organization, "queueing_entry.create")
    client = authenticated_client(user)
    entry = client.post(reverse("queueing-entries-list"), entry_payload(open_queue, checkin_factory()), format="json")
    event = QueueEntryEvent.objects.get(queue_entry_id=entry.data["id"], event_type=QueueEntryEvent.EventType.JOINED)

    with pytest.raises(DatabaseError):
        QueueEntryEvent.objects.filter(pk=event.id).update(reason="Mutated")
