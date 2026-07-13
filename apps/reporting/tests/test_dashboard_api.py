from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.checkins.models import PatientCheckin
from apps.facilities.models import Facility, FacilitySpecialty, ServicePoint, ServicePointType, Specialty
from apps.intelligence.models import QueueWaitTimePrediction
from apps.patients.models import Patient
from apps.queueing.models import Queue, QueueEntry
from apps.reporting.models import ReportExport
from apps.scheduling.models import Appointment


pytestmark = pytest.mark.django_db


def _grant_dashboard_permission(user, grant_system_permission, organization=None, facility=None):
    grant_system_permission(
        user=user,
        permission_code="reporting_analytics.view",
        scope="organization" if organization and facility is None else "facility" if facility else "platform",
        organization=organization,
        facility=facility,
    )


def _dashboard_query(organization, facility=None, **overrides):
    query = {"organization_id": str(organization.id)}
    if facility:
        query["facility_id"] = str(facility.id)
    query.update({key: str(value) for key, value in overrides.items() if value is not None})
    return query


def _create_walkin_checkin(*, facility, patient, facility_specialty, user, checked_in_at=None, method=PatientCheckin.CheckinMethod.RECEPTION):
    return PatientCheckin.objects.create(
        facility=facility,
        patient=patient,
        appointment=None,
        facility_specialty=facility_specialty,
        checkin_method=method,
        checked_in_by=user,
        checked_in_at=checked_in_at or timezone.now(),
    )


def _create_entry(*, queue, checkin, sequence_number, status, joined_at=None, priority_level=0, priority_reason=None):
    joined_at = joined_at or timezone.now()
    timestamps = {}
    if status in {QueueEntry.Status.CALLED, QueueEntry.Status.IN_SERVICE, QueueEntry.Status.COMPLETED}:
        timestamps["called_at"] = joined_at + timedelta(minutes=2)
    if status in {QueueEntry.Status.IN_SERVICE, QueueEntry.Status.COMPLETED}:
        timestamps["service_started_at"] = joined_at + timedelta(minutes=5)
    if status == QueueEntry.Status.COMPLETED:
        timestamps["service_completed_at"] = joined_at + timedelta(minutes=20)
    if status == QueueEntry.Status.CANCELLED:
        timestamps["cancelled_at"] = joined_at + timedelta(minutes=3)
    return QueueEntry.objects.create(
        queue=queue,
        patient_checkin=checkin,
        sequence_number=sequence_number,
        status=status,
        joined_at=joined_at,
        priority_level=priority_level,
        priority_reason=priority_reason,
        **timestamps,
    )


def test_unauthenticated_user_cannot_access_dashboard(api_client, organization):
    response = api_client.get("/api/v1/reporting/dashboard/overview/", {"organization_id": str(organization.id)})

    assert response.status_code == 401


def test_unauthorized_user_cannot_access_dashboard(authenticated_client, user_factory, organization):
    client = authenticated_client(user_factory())

    response = client.get("/api/v1/reporting/dashboard/overview/", {"organization_id": str(organization.id)})

    assert response.status_code == 403


def test_authorized_user_can_access_overview(
    authenticated_client,
    user_factory,
    grant_system_permission,
    organization,
    facility,
    patient,
    completed_appointment,
    completed_queue_entry,
):
    user = user_factory()
    _grant_dashboard_permission(user, grant_system_permission, organization=organization)
    client = authenticated_client(user)

    response = client.get("/api/v1/reporting/dashboard/overview/", _dashboard_query(organization, facility))

    assert response.status_code == 200
    assert response.data["total_patients"] == 1
    assert response.data["total_appointments_today"] >= 1
    assert response.data["total_checkins_today"] >= 1
    assert response.data["completed_visits_today"] >= 1
    assert response.data["average_wait_minutes_today"] == 10.0


def test_facility_filter_restricts_dashboard_results(
    authenticated_client,
    user_factory,
    grant_system_permission,
    organization,
    facility,
    other_organization,
    other_facility,
):
    user = user_factory()
    _grant_dashboard_permission(user, grant_system_permission, facility=facility)
    client = authenticated_client(user)
    Patient.objects.create(organization=organization, registered_facility=facility, patient_number="FAC-PAT-001", first_name="A", last_name="One")
    Patient.objects.create(organization=other_organization, registered_facility=other_facility, patient_number="FAC-PAT-002", first_name="B", last_name="Two")

    response = client.get("/api/v1/reporting/dashboard/overview/", _dashboard_query(organization, facility))

    assert response.status_code == 200
    assert response.data["total_patients"] == 1


def test_organization_filter_restricts_dashboard_results(
    authenticated_client,
    user_factory,
    grant_system_permission,
    organization,
    other_organization,
    facility,
    other_facility,
):
    user = user_factory()
    _grant_dashboard_permission(user, grant_system_permission, organization=organization)
    client = authenticated_client(user)
    Patient.objects.create(organization=organization, registered_facility=facility, patient_number="ORG-PAT-001", first_name="A", last_name="One")
    Patient.objects.create(organization=other_organization, registered_facility=other_facility, patient_number="ORG-PAT-002", first_name="B", last_name="Two")

    response = client.get("/api/v1/reporting/dashboard/overview/", _dashboard_query(organization))

    assert response.status_code == 200
    assert response.data["total_patients"] == 1


def test_facility_must_belong_to_organization(authenticated_client, user_factory, grant_system_permission, organization, other_facility):
    user = user_factory()
    _grant_dashboard_permission(user, grant_system_permission, organization=organization)
    client = authenticated_client(user)

    response = client.get("/api/v1/reporting/dashboard/overview/", _dashboard_query(organization, other_facility))

    assert response.status_code == 400


def test_date_range_filter_and_date_validation(
    authenticated_client,
    user_factory,
    grant_system_permission,
    organization,
    facility,
    patient,
    facility_specialty,
):
    user = user_factory()
    _grant_dashboard_permission(user, grant_system_permission, organization=organization)
    client = authenticated_client(user)
    today = timezone.localdate()
    old_start = timezone.now() - timedelta(days=7)
    Appointment.objects.create(
        facility=facility,
        patient=patient,
        facility_specialty=facility_specialty,
        appointment_number="OLD-DASH-APT",
        scheduled_start=old_start,
        scheduled_end=old_start + timedelta(minutes=30),
        status=Appointment.Status.CONFIRMED,
        booking_channel=Appointment.BookingChannel.RECEPTION,
    )

    response = client.get("/api/v1/reporting/dashboard/appointments/", _dashboard_query(organization, facility, date_from=today, date_to=today))
    invalid = client.get("/api/v1/reporting/dashboard/appointments/", _dashboard_query(organization, facility, date_from=today, date_to=today - timedelta(days=1)))

    assert response.status_code == 200
    assert response.data["appointments_total"] == 0
    assert invalid.status_code == 400


def test_appointments_dashboard_returns_status_and_hour_series(
    authenticated_client,
    user_factory,
    grant_system_permission,
    organization,
    facility,
    completed_appointment,
    appointment_slot,
):
    user = user_factory()
    _grant_dashboard_permission(user, grant_system_permission, organization=organization)
    client = authenticated_client(user)

    response = client.get("/api/v1/reporting/dashboard/appointments/", _dashboard_query(organization, facility))

    assert response.status_code == 200
    assert {"status": "completed", "count": 1} in response.data["appointments_by_status"]
    assert response.data["appointments_by_hour"]
    assert response.data["appointment_utilization_percentage"] == 50.0


def test_queue_dashboard_counts_and_next_entry_ordering(
    authenticated_client,
    user_factory,
    grant_system_permission,
    organization,
    facility,
    facility_specialty,
    queue,
    patient,
):
    user = user_factory()
    staff = user_factory()
    _grant_dashboard_permission(user, grant_system_permission, organization=organization)
    client = authenticated_client(user)
    base_time = timezone.now() - timedelta(minutes=30)
    normal = _create_walkin_checkin(facility=facility, patient=patient, facility_specialty=facility_specialty, user=staff, checked_in_at=base_time)
    urgent = _create_walkin_checkin(facility=facility, patient=patient, facility_specialty=facility_specialty, user=staff, checked_in_at=base_time + timedelta(minutes=1))
    called = _create_walkin_checkin(facility=facility, patient=patient, facility_specialty=facility_specialty, user=staff, checked_in_at=base_time + timedelta(minutes=2))
    in_service = _create_walkin_checkin(facility=facility, patient=patient, facility_specialty=facility_specialty, user=staff, checked_in_at=base_time + timedelta(minutes=3))
    skipped = _create_walkin_checkin(facility=facility, patient=patient, facility_specialty=facility_specialty, user=staff, checked_in_at=base_time + timedelta(minutes=4))
    _create_entry(queue=queue, checkin=normal, sequence_number=2, status=QueueEntry.Status.WAITING, joined_at=base_time)
    _create_entry(queue=queue, checkin=urgent, sequence_number=3, status=QueueEntry.Status.WAITING, joined_at=base_time + timedelta(minutes=1), priority_level=2, priority_reason="urgent")
    _create_entry(queue=queue, checkin=called, sequence_number=4, status=QueueEntry.Status.CALLED, joined_at=base_time + timedelta(minutes=2))
    _create_entry(queue=queue, checkin=in_service, sequence_number=5, status=QueueEntry.Status.IN_SERVICE, joined_at=base_time + timedelta(minutes=3))
    _create_entry(queue=queue, checkin=skipped, sequence_number=6, status=QueueEntry.Status.SKIPPED, joined_at=base_time + timedelta(minutes=4))

    response = client.get("/api/v1/reporting/dashboard/queues/", _dashboard_query(organization, facility))

    assert response.status_code == 200
    assert response.data["waiting_patients"] == 2
    assert response.data["called_patients"] == 1
    assert response.data["in_service_patients"] == 1
    assert response.data["skipped_patients"] == 1
    assert response.data["next_entries_summary"][0]["display_queue_number"] == "REC-003"


def test_checkin_dashboard_returns_hour_and_method_series(
    authenticated_client,
    user_factory,
    grant_system_permission,
    organization,
    facility,
    patient,
    facility_specialty,
):
    user = user_factory()
    _grant_dashboard_permission(user, grant_system_permission, organization=organization)
    client = authenticated_client(user)
    _create_walkin_checkin(facility=facility, patient=patient, facility_specialty=facility_specialty, user=user, method=PatientCheckin.CheckinMethod.QR_CODE)

    response = client.get("/api/v1/reporting/dashboard/checkins/", _dashboard_query(organization, facility))

    assert response.status_code == 200
    assert response.data["total_checkins"] == 1
    assert response.data["qr_checkins"] == 1
    assert response.data["checkins_by_hour"]
    assert {"method": "qr_code", "count": 1} in response.data["checkins_by_method"]


def test_practitioner_dashboard_returns_workload_summary(
    authenticated_client,
    user_factory,
    grant_system_permission,
    organization,
    facility,
    practitioner_shift,
    completed_appointment,
):
    user = user_factory()
    _grant_dashboard_permission(user, grant_system_permission, organization=organization)
    client = authenticated_client(user)

    response = client.get("/api/v1/reporting/dashboard/practitioners/", _dashboard_query(organization, facility))

    assert response.status_code == 200
    assert response.data["active_practitioners_today"] == 1
    assert response.data["scheduled_shifts"] == 1
    assert response.data["workload_summary"][0]["completed_appointments"] == 1


def test_intelligence_dashboard_returns_prediction_error_summary(
    authenticated_client,
    user_factory,
    grant_system_permission,
    organization,
    facility,
    prediction,
):
    user = user_factory()
    _grant_dashboard_permission(user, grant_system_permission, organization=organization)
    client = authenticated_client(user)

    response = client.get("/api/v1/reporting/dashboard/intelligence/", _dashboard_query(organization, facility, date_to=timezone.localdate() + timedelta(days=1)))

    assert response.status_code == 200
    assert response.data["predictions_generated"] == 1
    assert response.data["rule_based_predictions"] == 1
    assert response.data["average_actual_wait_minutes"] == 10.0
    assert response.data["average_prediction_error_minutes"] == 3.0


def test_dashboard_responses_do_not_expose_sensitive_fields_or_create_rows(
    authenticated_client,
    user_factory,
    grant_system_permission,
    organization,
    facility,
    completed_appointment,
):
    user = user_factory()
    _grant_dashboard_permission(user, grant_system_permission, organization=organization)
    client = authenticated_client(user)
    report_count = ReportExport.objects.count()
    endpoints = [
        "/api/v1/reporting/dashboard/overview/",
        "/api/v1/reporting/dashboard/appointments/",
        "/api/v1/reporting/dashboard/queues/",
        "/api/v1/reporting/dashboard/checkins/",
        "/api/v1/reporting/dashboard/practitioners/",
        "/api/v1/reporting/dashboard/intelligence/",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint, _dashboard_query(organization, facility))
        assert response.status_code == 200
        rendered = str(response.data).lower()
        assert "body_encrypted" not in rendered
        assert "value_hash" not in rendered
        assert "token_hash" not in rendered
        assert "reason_for_visit_encrypted" not in rendered

    assert ReportExport.objects.count() == report_count
