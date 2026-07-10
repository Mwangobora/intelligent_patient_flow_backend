from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import DatabaseError
from django.urls import reverse
from django.utils import timezone

from apps.intelligence.models import QueueWaitTimePrediction
from apps.queueing.models import QueueEntry
from apps.scheduling.models import AppointmentSlot


def grant_intelligence_permissions(user, grant_system_permission, organization, *codes):
    for code in codes:
        grant_system_permission(user=user, permission_code=code, scope="organization", organization=organization)


@pytest.mark.django_db
def test_unauthenticated_users_cannot_access_protected_intelligence_endpoints(api_client):
    response = api_client.get(reverse("intelligence-predictions-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_unauthorized_user_cannot_create_prediction(authenticated_client, queue_entry, user_factory):
    user = user_factory()
    client = authenticated_client(user)

    response = client.post(
        reverse("intelligence-predictions-list"),
        {
            "queue_entry_id": str(queue_entry.id),
            "predicted_wait_minutes": 5,
            "prediction_method": QueueWaitTimePrediction.PredictionMethod.RULE_BASED,
        },
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_authorized_user_can_create_rule_based_prediction(authenticated_client, grant_system_permission, organization, queue_entry, user_factory):
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_prediction.create")
    client = authenticated_client(user)

    response = client.post(reverse("intelligence-predictions-rule-based"), {"queue_entry_id": str(queue_entry.id)}, format="json")

    assert response.status_code == 201
    assert response.data["prediction_method"] == QueueWaitTimePrediction.PredictionMethod.RULE_BASED


@pytest.mark.django_db
@pytest.mark.parametrize("status", [QueueEntry.Status.COMPLETED, QueueEntry.Status.CANCELLED, QueueEntry.Status.TRANSFERRED])
def test_prediction_cannot_be_created_for_terminal_queue_entry(authenticated_client, grant_system_permission, organization, queue_entry, status, user_factory):
    queue_entry.status = status
    if status == QueueEntry.Status.COMPLETED:
        queue_entry.called_at = queue_entry.joined_at
        queue_entry.service_started_at = queue_entry.joined_at + timedelta(minutes=1)
        queue_entry.service_completed_at = queue_entry.joined_at + timedelta(minutes=2)
    elif status == QueueEntry.Status.CANCELLED:
        queue_entry.cancelled_at = queue_entry.joined_at + timedelta(minutes=1)
        queue_entry.cancelled_by = user_factory()
        queue_entry.cancellation_reason = "Cancelled"
    queue_entry.save()
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_prediction.create")
    client = authenticated_client(user)

    response = client.post(reverse("intelligence-predictions-rule-based"), {"queue_entry_id": str(queue_entry.id)}, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_predicted_wait_minutes_cannot_be_negative(authenticated_client, grant_system_permission, organization, queue_entry, user_factory):
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_prediction.create")
    client = authenticated_client(user)

    response = client.post(
        reverse("intelligence-predictions-list"),
        {
            "queue_entry_id": str(queue_entry.id),
            "predicted_wait_minutes": -1,
            "prediction_method": QueueWaitTimePrediction.PredictionMethod.RULE_BASED,
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_confidence_score_must_be_between_zero_and_one(authenticated_client, grant_system_permission, organization, queue_entry, user_factory):
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_prediction.create")
    client = authenticated_client(user)

    response = client.post(
        reverse("intelligence-predictions-list"),
        {
            "queue_entry_id": str(queue_entry.id),
            "predicted_wait_minutes": 5,
            "prediction_method": QueueWaitTimePrediction.PredictionMethod.RULE_BASED,
            "confidence_score": "1.5000",
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_machine_learning_prediction_requires_model_version(authenticated_client, grant_system_permission, organization, queue_entry, user_factory):
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_prediction.create")
    client = authenticated_client(user)

    response = client.post(
        reverse("intelligence-predictions-list"),
        {
            "queue_entry_id": str(queue_entry.id),
            "predicted_wait_minutes": 5,
            "prediction_method": QueueWaitTimePrediction.PredictionMethod.MACHINE_LEARNING,
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_machine_learning_placeholder_returns_clear_not_configured_error(authenticated_client, grant_system_permission, organization, queue_entry, user_factory):
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_prediction.create")
    client = authenticated_client(user)

    response = client.post(reverse("intelligence-predictions-machine-learning"), {"queue_entry_id": str(queue_entry.id)}, format="json")

    assert response.status_code == 400
    assert "not configured" in str(response.data).lower()


@pytest.mark.django_db
def test_latest_prediction_returns_newest_prediction_by_generated_at(authenticated_client, grant_system_permission, organization, queue_entry, user_factory):
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_prediction.create", "intelligence_prediction.view")
    client = authenticated_client(user)
    older = queue_entry.joined_at + timedelta(minutes=1)
    newer = queue_entry.joined_at + timedelta(minutes=2)
    client.post(
        reverse("intelligence-predictions-list"),
        {"queue_entry_id": str(queue_entry.id), "predicted_wait_minutes": 20, "prediction_method": "rule_based", "generated_at": older.isoformat()},
        format="json",
    )
    client.post(
        reverse("intelligence-predictions-list"),
        {"queue_entry_id": str(queue_entry.id), "predicted_wait_minutes": 10, "prediction_method": "rule_based", "generated_at": newer.isoformat()},
        format="json",
    )

    response = client.get(reverse("intelligence-queue-entries-latest-prediction", kwargs={"pk": queue_entry.id}))

    assert response.status_code == 200
    assert response.data["predicted_wait_minutes"] == 10


@pytest.mark.django_db
def test_prediction_list_does_not_expose_sensitive_patient_data(authenticated_client, grant_system_permission, organization, queue_entry, user_factory):
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_prediction.create", "intelligence_prediction.view")
    client = authenticated_client(user)
    client.post(reverse("intelligence-predictions-rule-based"), {"queue_entry_id": str(queue_entry.id)}, format="json")

    response = client.get(reverse("intelligence-predictions-list"))

    payload = response.data[0]
    assert "patient_number" not in payload
    assert "first_name" not in payload
    assert "last_name" not in payload


@pytest.mark.django_db
def test_rule_based_prediction_counts_active_entries_ahead_correctly(authenticated_client, checkin_factory, grant_system_permission, organization, queue, queue_entry, user_factory):
    QueueEntry.objects.create(queue=queue, patient_checkin=checkin_factory(), sequence_number=2, priority_level=2, priority_reason="Urgent", joined_at=queue_entry.joined_at + timedelta(minutes=1))
    queue_entry.sequence_number = 3
    queue_entry.save(update_fields=["sequence_number", "updated_at"])
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_prediction.create")
    client = authenticated_client(user)

    response = client.post(reverse("intelligence-predictions-rule-based"), {"queue_entry_id": str(queue_entry.id)}, format="json")

    assert response.status_code == 201
    assert response.data["predicted_wait_minutes"] == 15


@pytest.mark.django_db
def test_rule_based_prediction_uses_fallback_average_when_no_history(authenticated_client, checkin_factory, grant_system_permission, organization, queue, user_factory):
    entry = QueueEntry.objects.create(queue=queue, patient_checkin=checkin_factory(), sequence_number=2, joined_at=timezone.now())
    ahead = QueueEntry.objects.create(queue=queue, patient_checkin=checkin_factory(), sequence_number=1, joined_at=entry.joined_at - timedelta(minutes=1))
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_prediction.create")
    client = authenticated_client(user)

    response = client.post(reverse("intelligence-predictions-rule-based"), {"queue_entry_id": str(entry.id)}, format="json")

    assert ahead.status == QueueEntry.Status.WAITING
    assert response.status_code == 201
    assert response.data["predicted_wait_minutes"] == 15


@pytest.mark.django_db
def test_rule_based_prediction_uses_historical_completed_service_durations(authenticated_client, checkin_factory, completed_entry, grant_system_permission, organization, queue_entry, user_factory):
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_prediction.create")
    client = authenticated_client(user)
    queue_entry.sequence_number = 4
    queue_entry.save(update_fields=["sequence_number", "updated_at"])
    QueueEntry.objects.create(
        queue=queue_entry.queue,
        patient_checkin=checkin_factory(),
        sequence_number=3,
        joined_at=queue_entry.joined_at - timedelta(minutes=1),
    )

    response = client.post(reverse("intelligence-predictions-rule-based"), {"queue_entry_id": str(queue_entry.id)}, format="json")

    assert completed_entry.service_completed_at is not None
    assert response.status_code == 201
    assert response.data["predicted_wait_minutes"] == 20


@pytest.mark.django_db
def test_arrival_forecast_returns_grouped_data_by_day_and_hour(authenticated_client, checkin_factory, facility, grant_system_permission, organization, user_factory):
    checkin_factory(checked_in_at=timezone.now() - timedelta(days=1))
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_forecast.view")
    client = authenticated_client(user)

    response = client.get(
        reverse("intelligence-arrival-forecast-list"),
        {"facility_id": str(facility.id), "date_from": (timezone.localdate() - timedelta(days=2)).isoformat(), "date_to": timezone.localdate().isoformat()},
    )

    assert response.status_code == 200
    assert response.data
    assert {"day_of_week", "hour_of_day", "total_arrivals", "average_arrivals"} <= set(response.data[0])


@pytest.mark.django_db
def test_arrival_forecast_does_not_create_prediction_rows(authenticated_client, checkin_factory, facility, grant_system_permission, organization, user_factory):
    checkin_factory()
    before = QueueWaitTimePrediction.objects.count()
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_forecast.view")
    client = authenticated_client(user)

    response = client.get(
        reverse("intelligence-arrival-forecast-list"),
        {"facility_id": str(facility.id), "date_from": timezone.localdate().isoformat(), "date_to": timezone.localdate().isoformat()},
    )

    assert response.status_code == 200
    assert QueueWaitTimePrediction.objects.count() == before


@pytest.mark.django_db
def test_slot_suggestion_returns_only_available_online_bookable_future_slots(authenticated_client, appointment_slot, facility_specialty, grant_system_permission, organization, user_factory):
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_slot_suggestion.view")
    client = authenticated_client(user)

    response = client.get(
        reverse("intelligence-slot-suggestions-list"),
        {"facility_specialty_id": str(facility_specialty.id), "date_from": timezone.localdate().isoformat(), "date_to": (timezone.localdate() + timedelta(days=1)).isoformat()},
    )

    assert response.status_code == 200
    assert [row["appointment_slot_id"] for row in response.data] == [str(appointment_slot.id)]


@pytest.mark.django_db
def test_slot_suggestion_excludes_full_blocked_cancelled_or_past_slots(authenticated_client, appointment_slot, facility_specialty, grant_system_permission, organization, practitioner_shift, user_factory):
    now = timezone.now()
    AppointmentSlot.objects.create(practitioner_shift=practitioner_shift, facility_specialty=facility_specialty, starts_at=now + timedelta(minutes=90), ends_at=now + timedelta(minutes=120), capacity=1, booked_count=1, status=AppointmentSlot.Status.FULL)
    AppointmentSlot.objects.create(practitioner_shift=practitioner_shift, facility_specialty=facility_specialty, starts_at=now + timedelta(minutes=120), ends_at=now + timedelta(minutes=150), capacity=1, booked_count=0, status=AppointmentSlot.Status.BLOCKED)
    AppointmentSlot.objects.create(practitioner_shift=practitioner_shift, facility_specialty=facility_specialty, starts_at=now + timedelta(minutes=150), ends_at=now + timedelta(minutes=180), capacity=1, booked_count=0, status=AppointmentSlot.Status.CANCELLED)
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_slot_suggestion.view")
    client = authenticated_client(user)

    response = client.get(
        reverse("intelligence-slot-suggestions-list"),
        {"facility_specialty_id": str(facility_specialty.id), "date_from": timezone.localdate().isoformat(), "date_to": (timezone.localdate() + timedelta(days=1)).isoformat()},
    )

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["appointment_slot_id"] == str(appointment_slot.id)


@pytest.mark.django_db
def test_slot_suggestion_does_not_book_or_modify_booked_count(authenticated_client, appointment_slot, facility_specialty, grant_system_permission, organization, user_factory):
    before = appointment_slot.booked_count
    user = user_factory()
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_slot_suggestion.view")
    client = authenticated_client(user)

    response = client.get(
        reverse("intelligence-slot-suggestions-list"),
        {"facility_specialty_id": str(facility_specialty.id), "date_from": timezone.localdate().isoformat(), "date_to": (timezone.localdate() + timedelta(days=1)).isoformat()},
    )

    appointment_slot.refresh_from_db()
    assert response.status_code == 200
    assert appointment_slot.booked_count == before


@pytest.mark.django_db
def test_evaluation_computes_actual_wait_and_absolute_error(authenticated_client, grant_system_permission, organization, queue_entry, user_factory):
    user = user_factory()
    started_at = queue_entry.joined_at + timedelta(minutes=12)
    prediction = QueueWaitTimePrediction.objects.create(queue_entry=queue_entry, predicted_wait_minutes=10, prediction_method="rule_based", generated_at=queue_entry.joined_at + timedelta(minutes=1))
    queue_entry.status = QueueEntry.Status.IN_SERVICE
    queue_entry.called_at = queue_entry.joined_at
    queue_entry.service_started_at = started_at
    queue_entry.save(update_fields=["status", "called_at", "service_started_at", "updated_at"])
    grant_intelligence_permissions(user, grant_system_permission, organization, "intelligence_prediction.evaluate")
    client = authenticated_client(user)

    response = client.get(reverse("intelligence-prediction-evaluation-list"))

    row = next(item for item in response.data if item["prediction_id"] == str(prediction.id))
    assert response.status_code == 200
    assert row["actual_wait_minutes"] == 12
    assert row["absolute_error_minutes"] == 2


@pytest.mark.django_db(transaction=True)
def test_predictions_are_append_only_if_db_trigger_exists(queue_entry):
    prediction = QueueWaitTimePrediction.objects.create(queue_entry=queue_entry, predicted_wait_minutes=5, prediction_method="rule_based", generated_at=queue_entry.joined_at + timedelta(minutes=1))

    with pytest.raises(DatabaseError):
        QueueWaitTimePrediction.objects.filter(pk=prediction.id).update(predicted_wait_minutes=6)
