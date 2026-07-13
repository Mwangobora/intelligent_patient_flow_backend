from __future__ import annotations

from apps.reporting.models import ReportExport


def report_export_queryset():
    return ReportExport.objects.select_related("organization", "facility", "requested_by").order_by("-created_at")


def list_report_exports(
    *,
    organization_id=None,
    facility_id=None,
    report_type=None,
    status=None,
    requested_by_id=None,
):
    queryset = report_export_queryset()
    if organization_id:
        queryset = queryset.filter(organization_id=organization_id)
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if report_type:
        queryset = queryset.filter(report_type=report_type)
    if status:
        queryset = queryset.filter(status=status)
    if requested_by_id:
        queryset = queryset.filter(requested_by_id=requested_by_id)
    return queryset


def get_report_export_by_id(report_export_id):
    return report_export_queryset().filter(pk=report_export_id).first()
