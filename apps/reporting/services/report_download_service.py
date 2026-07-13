from __future__ import annotations

from django.http import FileResponse
from django.utils import timezone

from apps.accounts.permissions import user_has_permission
from apps.reporting.models import ReportExport
from common.exceptions import NotFoundError, ValidationError

from ._shared import get_report_export
from .report_file_service import CONTENT_TYPES, get_report_file_path_or_content


def validate_report_download_permission(*, user, report_export: ReportExport) -> None:
    if not user_has_permission(
        user,
        "reporting_report.download",
        organization=report_export.organization_id,
        facility=report_export.facility_id,
    ):
        raise ValidationError("You do not have permission to download this report.")


def _safe_filename(report_export: ReportExport) -> str:
    generated_date = (report_export.generated_at or timezone.now()).date().isoformat()
    return f"{report_export.report_type}-{generated_date}-{report_export.id}.{report_export.export_format}"


def get_report_download_response(*, report_export_id, user) -> FileResponse:
    report_export = get_report_export(report_export_id)
    validate_report_download_permission(user=user, report_export=report_export)
    if report_export.status != ReportExport.Status.COMPLETED:
        raise ValidationError("Only completed reports can be downloaded.")
    if report_export.expires_at and report_export.expires_at <= timezone.now():
        raise ValidationError("Report export has expired.")
    if not report_export.storage_key:
        raise NotFoundError("Report file not found.")

    file_path = get_report_file_path_or_content(storage_key=report_export.storage_key)
    return FileResponse(
        file_path.open("rb"),
        as_attachment=True,
        filename=_safe_filename(report_export),
        content_type=CONTENT_TYPES[report_export.export_format],
    )
