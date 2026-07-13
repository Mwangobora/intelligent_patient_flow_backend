from __future__ import annotations

from io import BytesIO
from zipfile import is_zipfile

import pytest
from django.utils import timezone

from apps.reporting.models import ReportExport
from apps.reporting.services import create_report_export, generate_report_export, mark_report_failed


pytestmark = pytest.mark.django_db


def _grant_reporting_permissions(user, grant_system_permission, *codes):
    for code in codes:
        grant_system_permission(user=user, permission_code=code)


def _grant_all_reporting_permissions(user, grant_system_permission):
    _grant_reporting_permissions(
        user,
        grant_system_permission,
        "reporting_report.view",
        "reporting_report.generate",
        "reporting_report.download",
        "reporting_report.cancel",
        "reporting_analytics.view",
    )


def _payload(organization, facility, **overrides):
    payload = {
        "organization_id": str(organization.id),
        "facility_id": str(facility.id),
        "report_type": "patient_waiting_time",
        "export_format": "csv",
        "parameters": {},
    }
    payload.update(overrides)
    return payload


def _stream_bytes(response) -> bytes:
    return b"".join(response.streaming_content)


@pytest.fixture
def private_storage(settings, tmp_path):
    settings.PRIVATE_MEDIA_ROOT = tmp_path / "private_media"
    return settings.PRIVATE_MEDIA_ROOT


def test_unauthenticated_users_cannot_access_reporting_endpoints(api_client):
    response = api_client.get("/api/v1/reporting/exports/")
    assert response.status_code == 401


def test_unauthorized_users_cannot_generate_reports(authenticated_client, user_factory, organization, facility):
    user = user_factory()
    client = authenticated_client(user)

    response = client.post("/api/v1/reporting/exports/", _payload(organization, facility), format="json")

    assert response.status_code == 403


def test_authorized_user_can_create_report_export(authenticated_client, user_factory, grant_system_permission, organization, facility):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post("/api/v1/reporting/exports/", _payload(organization, facility), format="json")

    assert response.status_code == 201
    assert response.data["status"] == ReportExport.Status.PENDING
    assert "storage_key" not in response.data


@pytest.mark.parametrize("export_format", ["csv", "xlsx", "pdf", "docx"])
def test_export_format_supports_required_formats(authenticated_client, user_factory, grant_system_permission, organization, facility, export_format):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post("/api/v1/reporting/exports/", _payload(organization, facility, export_format=export_format), format="json")

    assert response.status_code == 201
    assert response.data["export_format"] == export_format


def test_invalid_export_format_fails(authenticated_client, user_factory, grant_system_permission, organization, facility):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post("/api/v1/reporting/exports/", _payload(organization, facility, export_format="txt"), format="json")

    assert response.status_code == 400


def test_report_type_is_validated(authenticated_client, user_factory, grant_system_permission, organization, facility):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post("/api/v1/reporting/exports/", _payload(organization, facility, report_type="unknown"), format="json")

    assert response.status_code == 400


def test_facility_must_belong_to_organization(authenticated_client, user_factory, grant_system_permission, organization, other_facility):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post("/api/v1/reporting/exports/", _payload(organization, other_facility), format="json")

    assert response.status_code == 400


def test_parameters_date_to_cannot_be_before_date_from(authenticated_client, user_factory, grant_system_permission, organization, facility):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post(
        "/api/v1/reporting/exports/",
        _payload(organization, facility, parameters={"date_from": "2026-07-13", "date_to": "2026-07-12"}),
        format="json",
    )

    assert response.status_code == 400


def test_parameters_do_not_accept_plaintext_sensitive_patient_identifiers(authenticated_client, user_factory, grant_system_permission, organization, facility):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post("/api/v1/reporting/exports/", _payload(organization, facility, parameters={"patient_name": "Jane Doe"}), format="json")

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("export_format", "content_type", "assertion"),
    [
        ("csv", "text/csv", lambda content: b"Patient Waiting Time Report" in content),
        ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", lambda content: is_zipfile(BytesIO(content))),
        ("pdf", "application/pdf", lambda content: content.startswith(b"%PDF")),
        ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", lambda content: is_zipfile(BytesIO(content))),
    ],
)
def test_generate_and_download_real_report_files(
    authenticated_client,
    user_factory,
    grant_system_permission,
    organization,
    facility,
    completed_queue_entry,
    private_storage,
    export_format,
    content_type,
    assertion,
):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    create_response = client.post("/api/v1/reporting/exports/", _payload(organization, facility, export_format=export_format), format="json")

    generate_response = client.post(f"/api/v1/reporting/exports/{create_response.data['id']}/generate/")
    report_export = ReportExport.objects.get(pk=create_response.data["id"])
    download_response = client.get(f"/api/v1/reporting/exports/{report_export.id}/download/")
    content = _stream_bytes(download_response)

    assert generate_response.status_code == 200
    assert generate_response.data["status"] == ReportExport.Status.COMPLETED
    assert report_export.storage_key
    assert report_export.generated_at is not None
    assert download_response.status_code == 200
    assert download_response["Content-Type"] == content_type
    assert assertion(content)


def test_failed_report_has_failed_at_and_failure_reason(organization):
    report_export = ReportExport.objects.create(organization=organization, report_type="broken_type", export_format=ReportExport.ExportFormat.CSV)

    result = generate_report_export(report_export_id=report_export.id)

    assert result.status == ReportExport.Status.FAILED
    assert result.failed_at is not None
    assert result.failure_reason


def test_download_requires_permission(authenticated_client, user_factory, grant_system_permission, organization, facility, completed_queue_entry, private_storage):
    user = user_factory()
    _grant_reporting_permissions(user, grant_system_permission, "reporting_report.generate")
    client = authenticated_client(user)
    report_export = create_report_export(organization_id=organization.id, facility_id=facility.id, report_type="patient_waiting_time", export_format="csv", requested_by_id=user.id)
    generate_report_export(report_export_id=report_export.id)

    response = client.get(f"/api/v1/reporting/exports/{report_export.id}/download/")

    assert response.status_code == 403


def test_download_fails_for_pending_report(authenticated_client, user_factory, grant_system_permission, organization, facility):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    report_export = create_report_export(organization_id=organization.id, facility_id=facility.id, report_type="patient_waiting_time", export_format="csv")

    response = client.get(f"/api/v1/reporting/exports/{report_export.id}/download/")

    assert response.status_code == 400


def test_download_fails_for_expired_report(authenticated_client, user_factory, grant_system_permission, organization, facility, completed_queue_entry, private_storage):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    report_export = create_report_export(organization_id=organization.id, facility_id=facility.id, report_type="patient_waiting_time", export_format="csv")
    completed = generate_report_export(report_export_id=report_export.id)
    completed.status = ReportExport.Status.EXPIRED
    completed.save(update_fields=["status", "updated_at"])

    response = client.get(f"/api/v1/reporting/exports/{completed.id}/download/")

    assert response.status_code == 400


def test_patient_waiting_time_analytics_returns_expected_waiting_minutes(authenticated_client, user_factory, grant_system_permission, organization, facility, completed_queue_entry):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.get(f"/api/v1/reporting/analytics/patient-waiting-time/?organization_id={organization.id}&facility_id={facility.id}")

    assert response.status_code == 200
    assert response.data["rows"][0]["waiting_minutes"] == 10


def test_appointment_utilization_analytics_returns_expected_totals(authenticated_client, user_factory, grant_system_permission, organization, facility, completed_appointment, appointment_slot):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.get(f"/api/v1/reporting/analytics/appointment-utilization/?organization_id={organization.id}&facility_id={facility.id}")

    assert response.status_code == 200
    row = response.data["rows"][0]
    assert row["total_slots"] == 1
    assert row["booked_slots"] == 2
    assert row["completed_appointments"] == 1


def test_doctor_workload_analytics_returns_expected_totals(authenticated_client, user_factory, grant_system_permission, organization, facility, practitioner_shift, completed_appointment):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.get(f"/api/v1/reporting/analytics/doctor-workload/?organization_id={organization.id}&facility_id={facility.id}")

    assert response.status_code == 200
    row = response.data["rows"][0]
    assert row["shifts_count"] == 1
    assert row["completed_appointments"] == 1


def test_daily_attendance_analytics_returns_expected_totals(authenticated_client, user_factory, grant_system_permission, organization, facility, checkin, completed_queue_entry):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.get(f"/api/v1/reporting/analytics/daily-attendance/?organization_id={organization.id}&facility_id={facility.id}")

    assert response.status_code == 200
    row = response.data["rows"][0]
    assert row["total_checkins"] == 1
    assert row["appointment_checkins"] == 1
    assert row["completed_queue_entries"] == 1


def test_prediction_accuracy_analytics_returns_absolute_error(authenticated_client, user_factory, grant_system_permission, organization, facility, prediction):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.get(f"/api/v1/reporting/analytics/prediction-accuracy/?organization_id={organization.id}&facility_id={facility.id}")

    assert response.status_code == 200
    assert response.data["rows"][0]["absolute_error_minutes"] == 3


def test_report_list_does_not_expose_sensitive_storage_fields(authenticated_client, user_factory, grant_system_permission, organization, facility):
    user = user_factory()
    _grant_all_reporting_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    create_report_export(organization_id=organization.id, facility_id=facility.id, report_type="patient_waiting_time", export_format="csv")

    response = client.get(f"/api/v1/reporting/exports/?organization_id={organization.id}")

    assert response.status_code == 200
    assert "storage_key" not in response.data[0]
    assert "encrypted" not in str(response.data[0]).lower()
    assert "hash" not in str(response.data[0]).lower()
