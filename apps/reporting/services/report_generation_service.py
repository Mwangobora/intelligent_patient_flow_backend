from __future__ import annotations

from django.db import transaction

from apps.reporting.models import ReportExport
from apps.reporting.selectors import (
    get_appointment_utilization_data,
    get_daily_attendance_data,
    get_doctor_workload_data,
    get_patient_waiting_time_data,
    get_prediction_accuracy_data,
)
from common.exceptions import ValidationError

from ._shared import get_report_export, safe_failure_reason
from .report_export_service import mark_report_completed, mark_report_failed
from .report_file_service import render_report_file, save_report_file


REPORT_GENERATORS = {
    "patient_waiting_time": ("Patient Waiting Time Report", get_patient_waiting_time_data),
    "appointment_utilization": ("Appointment Utilization Report", get_appointment_utilization_data),
    "doctor_workload": ("Doctor Workload Report", get_doctor_workload_data),
    "daily_attendance": ("Daily Attendance Report", get_daily_attendance_data),
    "prediction_accuracy": ("Prediction Accuracy Report", get_prediction_accuracy_data),
}


def _metadata(report_export: ReportExport) -> dict:
    return {
        "organization": report_export.organization.name,
        "facility": report_export.facility.name if report_export.facility_id else "All facilities",
        "report_type": report_export.report_type,
        "export_format": report_export.export_format,
        "requested_by": str(report_export.requested_by_id or ""),
        "date_from": (report_export.parameters or {}).get("date_from", ""),
        "date_to": (report_export.parameters or {}).get("date_to", ""),
    }


def _generate_data(report_export: ReportExport) -> tuple[str, list[dict]]:
    try:
        title, selector = REPORT_GENERATORS[report_export.report_type]
    except KeyError as exc:
        raise ValidationError("Invalid report type.") from exc
    return title, selector(
        organization_id=report_export.organization_id,
        facility_id=report_export.facility_id,
        parameters=report_export.parameters or {},
    )


def generate_patient_waiting_time_report(*, organization_id, facility_id=None, parameters=None):
    return get_patient_waiting_time_data(organization_id=organization_id, facility_id=facility_id, parameters=parameters)


def generate_appointment_utilization_report(*, organization_id, facility_id=None, parameters=None):
    return get_appointment_utilization_data(organization_id=organization_id, facility_id=facility_id, parameters=parameters)


def generate_doctor_workload_report(*, organization_id, facility_id=None, parameters=None):
    return get_doctor_workload_data(organization_id=organization_id, facility_id=facility_id, parameters=parameters)


def generate_daily_attendance_report(*, organization_id, facility_id=None, parameters=None):
    return get_daily_attendance_data(organization_id=organization_id, facility_id=facility_id, parameters=parameters)


def generate_prediction_accuracy_report(*, organization_id, facility_id=None, parameters=None):
    return get_prediction_accuracy_data(organization_id=organization_id, facility_id=facility_id, parameters=parameters)


def generate_report_export(*, report_export_id) -> ReportExport:
    try:
        with transaction.atomic():
            report_export = get_report_export(report_export_id, lock=True)
            if report_export.status == ReportExport.Status.CANCELLED:
                raise ValidationError("Cancelled report should not be generated.")
            if report_export.status == ReportExport.Status.COMPLETED:
                return report_export
            report_export.status = ReportExport.Status.PROCESSING
            report_export.failed_at = None
            report_export.failure_reason = None
            report_export.save(update_fields=["status", "failed_at", "failure_reason", "updated_at"])

        report_export = ReportExport.objects.select_related("organization", "facility", "requested_by").get(pk=report_export_id)
        title, rows = _generate_data(report_export)
        content = render_report_file(report_export=report_export, title=title, rows=rows, metadata=_metadata(report_export))
        storage_key = save_report_file(report_export=report_export, content=content)
        return mark_report_completed(
            report_export_id=report_export.id,
            storage_key=storage_key,
            row_count=len(rows),
            expires_at=report_export.expires_at,
        )
    except Exception as exc:
        try:
            return mark_report_failed(report_export_id=report_export_id, failure_reason=safe_failure_reason(exc))
        except Exception:
            raise exc
