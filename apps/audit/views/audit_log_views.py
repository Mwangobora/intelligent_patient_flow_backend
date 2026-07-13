from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from apps.audit._helpers import translate_domain_error
from apps.audit.models import AuditLog
from apps.audit.selectors import get_audit_log_by_id, get_audit_summary, list_audit_logs
from apps.audit.serializers import (
    AuditLogCreateInputSerializer,
    AuditLogDetailOutputSerializer,
    AuditLogOutputSerializer,
    AuditLogQueryInputSerializer,
    AuditSummaryOutputSerializer,
)
from apps.audit.services import record_audit_log

from .base import AUDIT_DOCS_TAG, AuditBaseViewSet


def _log_scope(audit_log_id):
    audit_log = get_audit_log_by_id(audit_log_id)
    if audit_log is None:
        return None, None
    return audit_log.organization_id, audit_log.facility_id


@extend_schema(tags=[AUDIT_DOCS_TAG])
class AuditLogViewSet(AuditBaseViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogOutputSerializer
    permission_map = {
        "list": "audit_log.view",
        "retrieve": "audit_log.view",
        "create": "audit_log.create",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            return request.data.get("organization_id"), request.data.get("facility_id")
        if self.action == "retrieve":
            return _log_scope(self.kwargs.get("pk"))
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        serializer = AuditLogQueryInputSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        queryset = list_audit_logs(**serializer.validated_data)
        return Response(AuditLogOutputSerializer(queryset, many=True).data)

    def retrieve(self, request, pk=None):
        audit_log = get_audit_log_by_id(pk)
        if audit_log is None:
            return Response({"detail": "Audit log not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AuditLogDetailOutputSerializer(audit_log).data)

    def create(self, request):
        serializer = AuditLogCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            audit_log = record_audit_log(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AuditLogDetailOutputSerializer(audit_log).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=[AUDIT_DOCS_TAG])
class AuditSummaryViewSet(AuditBaseViewSet):
    permission_map = {"list": "audit_log.summary"}

    def get_permission_scope(self, request):
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        serializer = AuditLogQueryInputSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        summary = get_audit_summary(**serializer.validated_data)
        return Response(AuditSummaryOutputSerializer(summary).data)


@extend_schema(tags=[AUDIT_DOCS_TAG])
class ResourceAuditViewSet(AuditBaseViewSet):
    permission_map = {"list": "audit_log.view"}

    def get_permission_scope(self, request):
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request, resource_type=None, resource_id=None):
        queryset = list_audit_logs(resource_type=resource_type, resource_id=resource_id)
        return Response(AuditLogOutputSerializer(queryset, many=True).data)


@extend_schema(tags=[AUDIT_DOCS_TAG])
class ActorAuditViewSet(AuditBaseViewSet):
    permission_map = {"list": "audit_log.view"}

    def list(self, request, user_id=None):
        queryset = list_audit_logs(actor_user_id=user_id)
        return Response(AuditLogOutputSerializer(queryset, many=True).data)
