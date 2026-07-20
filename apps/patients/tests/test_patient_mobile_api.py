from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.checkins.models import PatientCheckin
from apps.checkins.services import issue_checkin_token
from apps.checkins.services._crypto import build_token_hash
from apps.facilities.models import Department, FacilitySpecialty, ServicePoint, ServicePointType, Specialty
from apps.patients.models import Patient
from apps.queueing.models import Queue, QueueEntry
from apps.scheduling.models import Appointment


@pytest.fixture
def patient_mobile_client(authenticated_client, patient_user):
    return authenticated_client(patient_user)


@pytest.fixture
def department(facility):
    return Department.objects.create(facility=facility, name="Outpatient", code="OUTPATIENT")


@pytest.fixture
def specialty():
    return Specialty.objects.create(name="General Medicine", code="GENERAL_MEDICINE")


@pytest.fixture
def facility_specialty(facility, department, specialty):
    return FacilitySpecialty.objects.create(
        facility=facility,
        department=department,
        specialty=specialty,
        appointment_duration_minutes=30,
        accepts_appointments=True,
        accepts_walk_ins=True,
    )


@pytest.fixture
def service_point_type():
    return ServicePointType.objects.create(name="Reception Desk", code="RECEPTION_DESK")


@pytest.fixture
def service_point(facility, department, service_point_type):
    return ServicePoint.objects.create(
        facility=facility,
        department=department,
        service_point_type=service_point_type,
        name="OPD Desk",
        code="OPD",
    )


@pytest.fixture
def appointment(patient_with_user, facility, facility_specialty):
    now = timezone.now()
    return Appointment.objects.create(
        facility=facility,
        patient=patient_with_user,
        facility_specialty=facility_specialty,
        appointment_number="APT-MOBILE-001",
        scheduled_start=now + timedelta(minutes=5),
        scheduled_end=now + timedelta(minutes=35),
        status=Appointment.Status.CONFIRMED,
        booking_channel=Appointment.BookingChannel.MOBILE,
    )


@pytest.fixture
def open_queue(service_point, facility_specialty):
    return Queue.objects.create(
        service_point=service_point,
        facility_specialty=facility_specialty,
        queue_date=timezone.localdate(),
        status=Queue.Status.OPEN,
        opened_at=timezone.now() - timedelta(minutes=10),
    )


def _create_checkin(*, patient, facility, appointment=None, facility_specialty=None):
    return PatientCheckin.objects.create(
        facility=facility,
        patient=patient,
        appointment=appointment,
        facility_specialty=facility_specialty,
        checkin_method=PatientCheckin.CheckinMethod.MOBILE,
        checked_in_at=timezone.now() - timedelta(minutes=5),
    )


@pytest.mark.django_db
def test_patient_can_view_own_checkin_eligibility(patient_mobile_client, appointment):
    response = patient_mobile_client.get(
        reverse("patient-checkin-eligibility"),
        {"appointment_id": str(appointment.id)},
    )

    assert response.status_code == 200
    assert response.data["appointment_id"] == str(appointment.id)
    assert response.data["can_check_in"] is True
    assert response.data["facility"]["name"] == appointment.facility.name


@pytest.mark.django_db
def test_patient_cannot_view_another_patient_appointment_eligibility(
    patient_mobile_client,
    appointment,
    organization,
    facility,
    facility_specialty,
):
    other_patient = Patient.objects.create(
        organization=organization,
        registered_facility=facility,
        patient_number="PAT-OTHER-MOBILE",
        first_name="Other",
        last_name="Patient",
    )
    other_appointment = Appointment.objects.create(
        facility=facility,
        patient=other_patient,
        facility_specialty=facility_specialty,
        appointment_number="APT-MOBILE-OTHER",
        scheduled_start=appointment.scheduled_start,
        scheduled_end=appointment.scheduled_end,
        status=Appointment.Status.CONFIRMED,
        booking_channel=Appointment.BookingChannel.MOBILE,
    )

    response = patient_mobile_client.get(
        reverse("patient-checkin-eligibility"),
        {"appointment_id": str(other_appointment.id)},
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_patient_can_check_in_own_appointment_if_eligible(patient_mobile_client, appointment):
    response = patient_mobile_client.post(
        reverse("patient-appointment-checkin", kwargs={"appointment_id": appointment.id}),
        format="json",
    )

    assert response.status_code == 201
    assert str(response.data["checkin"]["appointment"]) == str(appointment.id)
    assert PatientCheckin.objects.filter(appointment=appointment, voided_at__isnull=True).exists()
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CHECKED_IN


@pytest.mark.django_db
def test_patient_can_issue_qr_token_for_own_appointment(patient_mobile_client, appointment):
    response = patient_mobile_client.post(
        reverse("patient-appointment-qr-token", kwargs={"appointment_id": appointment.id}),
        format="json",
    )

    assert response.status_code == 201
    assert response.data["appointment_id"] == str(appointment.id)
    assert response.data["raw_token"]
    assert "token_hash" not in response.data


@pytest.mark.django_db
def test_patient_can_consume_own_qr_token(patient_mobile_client, appointment):
    issue_response = patient_mobile_client.post(
        reverse("patient-appointment-qr-token", kwargs={"appointment_id": appointment.id}),
        format="json",
    )

    response = patient_mobile_client.post(
        reverse("patient-qr-consume"),
        {"token": issue_response.data["raw_token"]},
        format="json",
    )

    assert response.status_code == 201
    assert str(response.data["checkin"]["appointment"]) == str(appointment.id)
    assert PatientCheckin.objects.filter(appointment=appointment, voided_at__isnull=True).exists()


@pytest.mark.django_db
def test_patient_cannot_consume_another_patients_qr_token(
    patient_mobile_client,
    patient_with_user,
    user_factory,
    organization,
    facility,
    facility_specialty,
):
    other_user = user_factory(email="qr-other@example.com", phone_number="+255744111222")
    other_patient = Patient.objects.create(
        organization=organization,
        user=other_user,
        registered_facility=facility,
        patient_number="PAT-QR-OTHER",
        first_name="Other",
        last_name="Qr",
    )
    now = timezone.now()
    other_appointment = Appointment.objects.create(
        facility=facility,
        patient=other_patient,
        facility_specialty=facility_specialty,
        appointment_number="APT-QR-OTHER",
        scheduled_start=now + timedelta(minutes=5),
        scheduled_end=now + timedelta(minutes=35),
        status=Appointment.Status.CONFIRMED,
        booking_channel=Appointment.BookingChannel.MOBILE,
    )
    issued = issue_checkin_token(appointment_id=other_appointment.id, created_by_id=other_user.id)

    response = patient_mobile_client.post(
        reverse("patient-qr-consume"),
        {"token": issued.raw_token},
        format="json",
    )

    assert response.status_code == 403
    assert response.data["reason"] == "not_your_appointment"


@pytest.mark.django_db
def test_invalid_qr_token_fails_cleanly(patient_mobile_client, patient_with_user):
    response = patient_mobile_client.post(
        reverse("patient-qr-consume"),
        {"token": "not-a-valid-token"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["reason"] == "invalid_qr"


@pytest.mark.django_db
def test_qr_token_is_stored_as_hash_not_plaintext(patient_mobile_client, appointment):
    response = patient_mobile_client.post(
        reverse("patient-appointment-qr-token", kwargs={"appointment_id": appointment.id}),
        format="json",
    )

    raw_token = response.data["raw_token"]
    assert not PatientCheckin.objects.filter(notes__icontains=raw_token).exists()
    assert appointment.checkin_tokens.filter(token_hash=build_token_hash(raw_token)).exists()
    assert not appointment.checkin_tokens.filter(token_hash=raw_token).exists()


@pytest.mark.django_db
def test_duplicate_patient_checkin_is_blocked(patient_mobile_client, appointment):
    patient_mobile_client.post(reverse("patient-appointment-checkin", kwargs={"appointment_id": appointment.id}), format="json")

    response = patient_mobile_client.post(
        reverse("patient-appointment-checkin", kwargs={"appointment_id": appointment.id}),
        format="json",
    )

    assert response.status_code == 400
    assert response.data["reason"] == "already_checked_in"


@pytest.mark.django_db
def test_cancelled_appointment_checkin_is_blocked(patient_mobile_client, appointment, user_factory):
    appointment.status = Appointment.Status.CANCELLED
    appointment.cancelled_at = timezone.now()
    appointment.cancelled_by = user_factory()
    appointment.cancellation_reason = "Patient cancelled"
    appointment.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancellation_reason", "updated_at"])

    response = patient_mobile_client.post(
        reverse("patient-appointment-checkin", kwargs={"appointment_id": appointment.id}),
        format="json",
    )

    assert response.status_code == 400
    assert response.data["reason"] == "appointment_cancelled"


@pytest.mark.django_db
def test_patient_can_view_own_current_queue(patient_mobile_client, patient_with_user, facility, facility_specialty, open_queue):
    checkin = _create_checkin(
        patient=patient_with_user,
        facility=facility,
        facility_specialty=facility_specialty,
    )
    entry = QueueEntry.objects.create(
        queue=open_queue,
        patient_checkin=checkin,
        sequence_number=1,
        status=QueueEntry.Status.WAITING,
        joined_at=timezone.now() - timedelta(minutes=4),
    )

    response = patient_mobile_client.get(reverse("patient-current-queue"))

    assert response.status_code == 200
    assert response.data["queue_entry_id"] == str(entry.id)
    assert response.data["queue_number"] == "OPD-001"
    assert "patient_name" not in response.data


@pytest.mark.django_db
def test_patient_cannot_view_another_patients_queue(
    patient_mobile_client,
    organization,
    patient_with_user,
    facility,
    facility_specialty,
    open_queue,
):
    other_patient = Patient.objects.create(
        organization=organization,
        registered_facility=facility,
        patient_number="PAT-QUEUE-OTHER",
        first_name="Other",
        last_name="Queue",
    )
    checkin = _create_checkin(
        patient=other_patient,
        facility=facility,
        facility_specialty=facility_specialty,
    )
    QueueEntry.objects.create(
        queue=open_queue,
        patient_checkin=checkin,
        sequence_number=2,
        status=QueueEntry.Status.WAITING,
    )

    response = patient_mobile_client.get(reverse("patient-current-queue"))

    assert response.status_code == 200
    assert response.data["queue_entry_id"] is None


@pytest.mark.django_db
def test_empty_current_queue_returns_clean_response(patient_mobile_client, patient_with_user):
    response = patient_mobile_client.get(reverse("patient-current-queue"))

    assert response.status_code == 200
    assert response.data["queue_entry_id"] is None
    assert response.data["status"] is None


@pytest.mark.django_db
def test_queue_history_returns_only_own_entries(
    patient_mobile_client,
    organization,
    patient_with_user,
    facility,
    facility_specialty,
    open_queue,
):
    own_checkin = _create_checkin(patient=patient_with_user, facility=facility, facility_specialty=facility_specialty)
    own_entry = QueueEntry.objects.create(
        queue=open_queue,
        patient_checkin=own_checkin,
        sequence_number=3,
        status=QueueEntry.Status.COMPLETED,
        service_started_at=timezone.now() - timedelta(minutes=2),
        service_completed_at=timezone.now(),
    )
    other_patient = Patient.objects.create(
        organization=organization,
        registered_facility=facility,
        patient_number="PAT-HISTORY-OTHER",
        first_name="Other",
        last_name="History",
    )
    other_checkin = _create_checkin(patient=other_patient, facility=facility, facility_specialty=facility_specialty)
    QueueEntry.objects.create(
        queue=open_queue,
        patient_checkin=other_checkin,
        sequence_number=4,
        status=QueueEntry.Status.COMPLETED,
    )

    response = patient_mobile_client.get(reverse("patient-queue-history"))

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["queue_entry_id"] == str(own_entry.id)
