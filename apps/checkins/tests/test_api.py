from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.checkins.models import CheckinToken, PatientCheckin
from apps.checkins.services._crypto import build_token_hash
from apps.scheduling.models import Appointment


def appointment_checkin_payload(*, facility, patient, appointment, user):
    return {
        "facility_id": str(facility.id),
        "patient_id": str(patient.id),
        "appointment_id": str(appointment.id),
        "checkin_method": PatientCheckin.CheckinMethod.RECEPTION,
        "checked_in_by_id": str(user.id),
    }


@pytest.mark.django_db
def test_unauthenticated_users_cannot_access_protected_checkin_endpoints(api_client):
    response = api_client.get(reverse("checkins-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_unauthorized_user_cannot_create_checkin(authenticated_client, appointment, facility, patient, user_factory):
    user = user_factory()
    client = authenticated_client(user)

    response = client.post(
        reverse("checkins-appointment"),
        appointment_checkin_payload(facility=facility, patient=patient, appointment=appointment, user=user),
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_authorized_user_can_create_appointment_checkin(
    authenticated_client,
    appointment,
    facility,
    grant_system_permission,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_checkin.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(
        reverse("checkins-appointment"),
        appointment_checkin_payload(facility=facility, patient=patient, appointment=appointment, user=user),
        format="json",
    )

    assert response.status_code == 201
    assert str(response.data["appointment"]) == str(appointment.id)
    assert response.data["checkin_method"] == PatientCheckin.CheckinMethod.RECEPTION


@pytest.mark.django_db
def test_appointment_checkin_updates_appointment_status_to_checked_in(
    authenticated_client,
    appointment,
    facility,
    grant_system_permission,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_checkin.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(
        reverse("checkins-appointment"),
        appointment_checkin_payload(facility=facility, patient=patient, appointment=appointment, user=user),
        format="json",
    )

    appointment.refresh_from_db()
    assert response.status_code == 201
    assert appointment.status == Appointment.Status.CHECKED_IN


@pytest.mark.django_db
def test_cannot_check_in_cancelled_appointment(
    authenticated_client,
    appointment,
    facility,
    grant_system_permission,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    appointment.status = Appointment.Status.CANCELLED
    appointment.cancelled_at = timezone.now()
    appointment.cancelled_by = user
    appointment.cancellation_reason = "Cancelled"
    appointment.save()
    grant_system_permission(user=user, permission_code="checkins_checkin.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(
        reverse("checkins-appointment"),
        appointment_checkin_payload(facility=facility, patient=patient, appointment=appointment, user=user),
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_cannot_check_in_completed_appointment(
    authenticated_client,
    appointment,
    facility,
    grant_system_permission,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    appointment.status = Appointment.Status.COMPLETED
    appointment.save(update_fields=["status", "updated_at"])
    grant_system_permission(user=user, permission_code="checkins_checkin.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(
        reverse("checkins-appointment"),
        appointment_checkin_payload(facility=facility, patient=patient, appointment=appointment, user=user),
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_cannot_create_duplicate_non_voided_checkin_for_same_appointment(
    authenticated_client,
    appointment,
    facility,
    grant_system_permission,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_checkin.create", scope="organization", organization=organization)
    client = authenticated_client(user)
    payload = appointment_checkin_payload(facility=facility, patient=patient, appointment=appointment, user=user)

    first_response = client.post(reverse("checkins-appointment"), payload, format="json")
    second_response = client.post(reverse("checkins-appointment"), payload, format="json")

    assert first_response.status_code == 201
    assert second_response.status_code == 400


@pytest.mark.django_db
def test_walkin_checkin_requires_facility_specialty(authenticated_client, facility, grant_system_permission, organization, patient, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_checkin.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(
        reverse("checkins-walk-in"),
        {
            "facility_id": str(facility.id),
            "patient_id": str(patient.id),
            "checkin_method": PatientCheckin.CheckinMethod.RECEPTION,
            "checked_in_by_id": str(user.id),
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_walkin_specialty_must_belong_to_same_facility(
    authenticated_client,
    facility,
    grant_system_permission,
    organization,
    other_facility_specialty,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_checkin.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(
        reverse("checkins-walk-in"),
        {
            "facility_id": str(facility.id),
            "patient_id": str(patient.id),
            "facility_specialty_id": str(other_facility_specialty.id),
            "checkin_method": PatientCheckin.CheckinMethod.RECEPTION,
            "checked_in_by_id": str(user.id),
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_walkin_specialty_must_accept_walkins(
    authenticated_client,
    facility,
    grant_system_permission,
    non_walkin_specialty,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_checkin.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(
        reverse("checkins-walk-in"),
        {
            "facility_id": str(facility.id),
            "patient_id": str(patient.id),
            "facility_specialty_id": str(non_walkin_specialty.id),
            "checkin_method": PatientCheckin.CheckinMethod.RECEPTION,
            "checked_in_by_id": str(user.id),
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_void_checkin_sets_void_fields(
    authenticated_client,
    appointment,
    facility,
    grant_system_permission,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_checkin.create", scope="organization", organization=organization)
    grant_system_permission(user=user, permission_code="checkins_checkin.void", scope="organization", organization=organization)
    client = authenticated_client(user)
    create_response = client.post(
        reverse("checkins-appointment"),
        appointment_checkin_payload(facility=facility, patient=patient, appointment=appointment, user=user),
        format="json",
    )

    response = client.post(
        reverse("checkins-void", kwargs={"pk": create_response.data["id"]}),
        {"void_reason": "Incorrect arrival"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["voided_at"] is not None
    assert str(response.data["voided_by"]) == str(user.id)
    assert response.data["void_reason"] == "Incorrect arrival"


@pytest.mark.django_db
def test_cannot_void_checkin_twice(
    authenticated_client,
    appointment,
    facility,
    grant_system_permission,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_checkin.create", scope="organization", organization=organization)
    grant_system_permission(user=user, permission_code="checkins_checkin.void", scope="organization", organization=organization)
    client = authenticated_client(user)
    create_response = client.post(
        reverse("checkins-appointment"),
        appointment_checkin_payload(facility=facility, patient=patient, appointment=appointment, user=user),
        format="json",
    )

    first_response = client.post(reverse("checkins-void", kwargs={"pk": create_response.data["id"]}), {"void_reason": "One"}, format="json")
    second_response = client.post(reverse("checkins-void", kwargs={"pk": create_response.data["id"]}), {"void_reason": "Two"}, format="json")

    assert first_response.status_code == 200
    assert second_response.status_code == 400


@pytest.mark.django_db
def test_issue_qr_token_returns_raw_token_once(authenticated_client, appointment, grant_system_permission, organization, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_token.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    issue_response = client.post(reverse("checkin-tokens-issue"), {"appointment_id": str(appointment.id)}, format="json")
    detail_response = client.get(reverse("checkin-tokens-detail", kwargs={"pk": issue_response.data["id"]}))

    assert issue_response.status_code == 201
    assert issue_response.data["raw_token"]
    assert "raw_token" not in detail_response.data


@pytest.mark.django_db
def test_database_stores_token_hash_not_raw_token(authenticated_client, appointment, grant_system_permission, organization, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_token.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(reverse("checkin-tokens-issue"), {"appointment_id": str(appointment.id)}, format="json")

    token = CheckinToken.objects.get(pk=response.data["id"])
    assert response.status_code == 201
    assert token.token_hash != response.data["raw_token"]
    assert len(token.token_hash) == 64


@pytest.mark.django_db
def test_only_one_active_token_per_appointment(authenticated_client, appointment, grant_system_permission, organization, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_token.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    first_response = client.post(reverse("checkin-tokens-issue"), {"appointment_id": str(appointment.id)}, format="json")
    second_response = client.post(reverse("checkin-tokens-issue"), {"appointment_id": str(appointment.id)}, format="json")

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert CheckinToken.objects.filter(appointment=appointment, used_at__isnull=True, revoked_at__isnull=True).count() == 1


@pytest.mark.django_db
def test_reissuing_token_revokes_previous_unused_token(authenticated_client, appointment, grant_system_permission, organization, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_token.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    first_response = client.post(reverse("checkin-tokens-issue"), {"appointment_id": str(appointment.id)}, format="json")
    second_response = client.post(reverse("checkin-tokens-issue"), {"appointment_id": str(appointment.id)}, format="json")

    first_token = CheckinToken.objects.get(pk=first_response.data["id"])
    second_token = CheckinToken.objects.get(pk=second_response.data["id"])
    assert first_token.revoked_at is not None
    assert first_token.revoked_by_id == user.id
    assert second_token.revoked_at is None


@pytest.mark.django_db
def test_expired_token_cannot_be_consumed(authenticated_client, appointment, grant_system_permission, organization, user_factory):
    user = user_factory()
    raw_token = "expired-token"
    created_at = timezone.now() - timedelta(hours=2)
    CheckinToken.objects.create(
        appointment=appointment,
        token_hash=build_token_hash(raw_token),
        created_at=created_at,
        expires_at=timezone.now() - timedelta(hours=1),
        created_by=user,
    )
    grant_system_permission(user=user, permission_code="checkins_token.consume", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(reverse("checkin-tokens-consume"), {"raw_token": raw_token}, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_revoked_token_cannot_be_consumed(authenticated_client, appointment, grant_system_permission, organization, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_token.create", scope="organization", organization=organization)
    grant_system_permission(user=user, permission_code="checkins_token.revoke", scope="organization", organization=organization)
    grant_system_permission(user=user, permission_code="checkins_token.consume", scope="organization", organization=organization)
    client = authenticated_client(user)
    issue_response = client.post(reverse("checkin-tokens-issue"), {"appointment_id": str(appointment.id)}, format="json")
    client.post(reverse("checkin-tokens-revoke", kwargs={"pk": issue_response.data["id"]}), {"revocation_reason": "No longer needed"}, format="json")

    response = client.post(reverse("checkin-tokens-consume"), {"raw_token": issue_response.data["raw_token"]}, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_used_token_cannot_be_consumed_twice(authenticated_client, appointment, grant_system_permission, organization, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_token.create", scope="organization", organization=organization)
    grant_system_permission(user=user, permission_code="checkins_token.consume", scope="organization", organization=organization)
    client = authenticated_client(user)
    issue_response = client.post(reverse("checkin-tokens-issue"), {"appointment_id": str(appointment.id)}, format="json")

    first_response = client.post(reverse("checkin-tokens-consume"), {"raw_token": issue_response.data["raw_token"]}, format="json")
    second_response = client.post(reverse("checkin-tokens-consume"), {"raw_token": issue_response.data["raw_token"]}, format="json")

    assert first_response.status_code == 201
    assert second_response.status_code == 400


@pytest.mark.django_db
def test_token_consume_creates_checkin_and_marks_token_used(authenticated_client, appointment, grant_system_permission, organization, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_token.create", scope="organization", organization=organization)
    grant_system_permission(user=user, permission_code="checkins_token.consume", scope="organization", organization=organization)
    client = authenticated_client(user)
    issue_response = client.post(reverse("checkin-tokens-issue"), {"appointment_id": str(appointment.id)}, format="json")

    response = client.post(reverse("checkin-tokens-consume"), {"raw_token": issue_response.data["raw_token"]}, format="json")

    token = CheckinToken.objects.get(pk=issue_response.data["id"])
    appointment.refresh_from_db()
    assert response.status_code == 201
    assert token.used_at is not None
    assert str(token.patient_checkin_id) == str(response.data["id"])
    assert appointment.status == Appointment.Status.CHECKED_IN


@pytest.mark.django_db
def test_token_response_does_not_expose_token_hash(authenticated_client, appointment, grant_system_permission, organization, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_token.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(reverse("checkin-tokens-issue"), {"appointment_id": str(appointment.id)}, format="json")
    detail_response = client.get(reverse("checkin-tokens-detail", kwargs={"pk": response.data["id"]}))

    assert "token_hash" not in response.data
    assert "token_hash" not in detail_response.data


@pytest.mark.django_db
def test_raw_token_is_not_returned_by_list_or_detail_endpoint(authenticated_client, appointment, grant_system_permission, organization, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="checkins_token.create", scope="organization", organization=organization)
    client = authenticated_client(user)
    issue_response = client.post(reverse("checkin-tokens-issue"), {"appointment_id": str(appointment.id)}, format="json")

    list_response = client.get(reverse("checkin-tokens-list"), {"appointment_id": str(appointment.id)})
    detail_response = client.get(reverse("checkin-tokens-detail", kwargs={"pk": issue_response.data["id"]}))

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert all("raw_token" not in row for row in list_response.data)
    assert "raw_token" not in detail_response.data
