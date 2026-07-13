from __future__ import annotations

import json
from datetime import date, datetime

from django.contrib.auth import get_user_model

from apps.facilities.models import Facility, Organization
from apps.reporting.models import ReportExport
from common.exceptions import NotFoundError, ValidationError

User = get_user_model()


REPORT_TYPES = {
    "patient_waiting_time",
    "appointment_utilization",
    "doctor_workload",
    "daily_attendance",
    "prediction_accuracy",
}

SENSITIVE_PARAMETER_KEYS = {
    "patient_name",
    "first_name",
    "last_name",
    "phone",
    "phone_number",
    "email",
    "identifier",
    "identifier_value",
    "value_hash",
    "encrypted",
    "password",
}


def get_organization(organization_id, *, lock: bool = False) -> Organization:
    queryset = Organization.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    organization = queryset.filter(pk=organization_id).first()
    if organization is None:
        raise NotFoundError("Organization not found.")
    return organization


def get_facility(facility_id, *, lock: bool = False) -> Facility:
    queryset = Facility.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    facility = queryset.filter(pk=facility_id).first()
    if facility is None:
        raise NotFoundError("Facility not found.")
    return facility


def get_user(user_id):
    if user_id is None:
        return None
    user = get_user_model().objects.filter(pk=user_id).first()
    if user is None:
        raise NotFoundError("User not found.")
    return user


def get_report_export(report_export_id, *, lock: bool = False) -> ReportExport:
    queryset = ReportExport.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    report_export = queryset.filter(pk=report_export_id).first()
    if report_export is None:
        raise NotFoundError("Report export not found.")
    return report_export


def validate_report_type(report_type: str) -> None:
    if report_type not in REPORT_TYPES:
        raise ValidationError("Invalid report type.")


def validate_export_format(export_format: str) -> None:
    if export_format not in ReportExport.ExportFormat.values:
        raise ValidationError("Invalid export format.")


def validate_scope(*, organization: Organization, facility: Facility | None) -> None:
    if not organization.is_active:
        raise ValidationError("Organization must be active.")
    if facility is None:
        return
    if not facility.is_active:
        raise ValidationError("Facility must be active.")
    if facility.organization_id != organization.id:
        raise ValidationError("Facility must belong to the selected organization.")


def validate_parameters(parameters: dict | None) -> dict:
    if parameters is None:
        return {}
    if not isinstance(parameters, dict):
        raise ValidationError("Report parameters must be a JSON object.")

    try:
        json.dumps(parameters, default=str)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Report parameters must be JSON-safe.") from exc

    lowered_keys = {str(key).lower() for key in parameters.keys()}
    if lowered_keys & SENSITIVE_PARAMETER_KEYS:
        raise ValidationError("Report parameters must not contain plaintext sensitive patient information.")

    date_from = parse_report_date(parameters.get("date_from")) if parameters.get("date_from") else None
    date_to = parse_report_date(parameters.get("date_to")) if parameters.get("date_to") else None
    if date_from and date_to and date_to < date_from:
        raise ValidationError("date_to must be greater than or equal to date_from.")
    return parameters


def parse_report_date(value):
    if value is None or isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValidationError("Report date parameters must use YYYY-MM-DD format.") from exc


def safe_failure_reason(exc: Exception | str) -> str:
    return str(exc).splitlines()[0][:250] or "Report generation failed."
