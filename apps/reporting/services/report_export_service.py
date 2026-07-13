from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.reporting.models import ReportExport
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    get_facility,
    get_organization,
    get_report_export,
    get_user,
    safe_failure_reason,
    validate_export_format,
    validate_parameters,
    validate_report_type,
    validate_scope,
)


@transaction.atomic
def create_report_export(
    *,
    organization_id,
    report_type: str,
    export_format: str,
    parameters: dict | None = None,
    facility_id=None,
    requested_by_id=None,
    expires_at=None,
) -> ReportExport:
    validate_report_type(report_type)
    validate_export_format(export_format)
    organization = get_organization(organization_id)
    facility = get_facility(facility_id) if facility_id else None
    validate_scope(organization=organization, facility=facility)
    requested_by = get_user(requested_by_id)
    safe_parameters = validate_parameters(parameters)

    try:
        return ReportExport.objects.create(
            organization=organization,
            facility=facility,
            report_type=report_type,
            export_format=export_format,
            parameters=safe_parameters,
            requested_by=requested_by,
            expires_at=expires_at,
        )
    except IntegrityError as exc:
        raise ConflictError("Report export conflicts with an existing record.") from exc


@transaction.atomic
def mark_report_processing(*, report_export_id) -> ReportExport:
    report_export = get_report_export(report_export_id, lock=True)
    if report_export.status == ReportExport.Status.CANCELLED:
        raise ValidationError("Cancelled report cannot be generated.")
    if report_export.status == ReportExport.Status.COMPLETED:
        return report_export
    report_export.status = ReportExport.Status.PROCESSING
    report_export.failed_at = None
    report_export.failure_reason = None
    report_export.save(update_fields=["status", "failed_at", "failure_reason", "updated_at"])
    return report_export


@transaction.atomic
def mark_report_completed(*, report_export_id, storage_key: str, row_count: int, generated_at=None, expires_at=None) -> ReportExport:
    if row_count < 0:
        raise ValidationError("row_count cannot be negative.")
    report_export = get_report_export(report_export_id, lock=True)
    if report_export.status == ReportExport.Status.CANCELLED:
        raise ValidationError("Cancelled report cannot be completed.")
    generated_time = generated_at or timezone.now()
    if expires_at and expires_at <= generated_time:
        raise ValidationError("expires_at must be after generated_at.")
    report_export.status = ReportExport.Status.COMPLETED
    report_export.storage_key = storage_key
    report_export.row_count = row_count
    report_export.generated_at = generated_time
    report_export.expires_at = expires_at or report_export.expires_at
    report_export.failed_at = None
    report_export.failure_reason = None
    report_export.save(
        update_fields=[
            "status",
            "storage_key",
            "row_count",
            "generated_at",
            "expires_at",
            "failed_at",
            "failure_reason",
            "updated_at",
        ]
    )
    return report_export


@transaction.atomic
def mark_report_failed(*, report_export_id, failure_reason: str | Exception, failed_at=None) -> ReportExport:
    report_export = get_report_export(report_export_id, lock=True)
    report_export.status = ReportExport.Status.FAILED
    report_export.failed_at = failed_at or timezone.now()
    report_export.failure_reason = safe_failure_reason(failure_reason)
    report_export.save(update_fields=["status", "failed_at", "failure_reason", "updated_at"])
    return report_export


@transaction.atomic
def mark_report_expired(*, report_export_id) -> ReportExport:
    report_export = get_report_export(report_export_id, lock=True)
    if report_export.status != ReportExport.Status.COMPLETED:
        raise ValidationError("Only completed reports can be expired.")
    report_export.status = ReportExport.Status.EXPIRED
    report_export.save(update_fields=["status", "updated_at"])
    return report_export


@transaction.atomic
def cancel_report_export(*, report_export_id) -> ReportExport:
    report_export = get_report_export(report_export_id, lock=True)
    if report_export.status == ReportExport.Status.COMPLETED:
        raise ValidationError("Completed report cannot be cancelled.")
    if report_export.status == ReportExport.Status.CANCELLED:
        return report_export
    report_export.status = ReportExport.Status.CANCELLED
    report_export.save(update_fields=["status", "updated_at"])
    return report_export
