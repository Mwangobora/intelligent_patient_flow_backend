from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.reporting._helpers import translate_domain_error
from apps.reporting.models import ReportExport
from apps.reporting.selectors import get_report_export_by_id, list_report_exports
from apps.reporting.serializers import ReportExportCreateInputSerializer, ReportExportOutputSerializer
from apps.reporting.services import cancel_report_export, create_report_export, generate_report_export, get_report_download_response

from .base import REPORTING_DOCS_TAG, ReportingBaseViewSet


def _export_scope(report_export_id):
    report_export = get_report_export_by_id(report_export_id)
    if report_export is None:
        return None, None
    return report_export.organization_id, report_export.facility_id


@extend_schema(tags=[REPORTING_DOCS_TAG])
class ReportExportViewSet(ReportingBaseViewSet):
    queryset = ReportExport.objects.all()
    serializer_class = ReportExportOutputSerializer
    permission_map = {
        "list": "reporting_report.view",
        "retrieve": "reporting_report.view",
        "create": "reporting_report.generate",
        "generate": "reporting_report.generate",
        "cancel": "reporting_report.cancel",
        "download": "reporting_report.download",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            return request.data.get("organization_id"), request.data.get("facility_id")
        if self.action in {"retrieve", "generate", "cancel", "download"}:
            return _export_scope(self.kwargs.get("pk"))
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_report_exports(
            organization_id=request.query_params.get("organization_id"),
            facility_id=request.query_params.get("facility_id"),
            report_type=request.query_params.get("report_type"),
            status=request.query_params.get("status"),
            requested_by_id=request.query_params.get("requested_by_id"),
        )
        return Response(ReportExportOutputSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = ReportExportCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            report_export = create_report_export(requested_by_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ReportExportOutputSerializer(report_export).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        report_export = get_report_export_by_id(pk)
        if report_export is None:
            return Response({"detail": "Report export not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ReportExportOutputSerializer(report_export).data)

    @action(detail=True, methods=["post"], url_path="generate")
    def generate(self, request, pk=None):
        try:
            report_export = generate_report_export(report_export_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ReportExportOutputSerializer(report_export).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        try:
            report_export = cancel_report_export(report_export_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ReportExportOutputSerializer(report_export).data)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        try:
            return get_report_download_response(report_export_id=pk, user=request.user)
        except Exception as exc:
            translate_domain_error(exc)
