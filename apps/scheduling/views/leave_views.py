from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.scheduling._helpers import translate_domain_error
from apps.scheduling.models import PractitionerLeaveRequest
from apps.scheduling.selectors import get_leave_request_by_id, list_leave_requests
from apps.scheduling.services._shared import get_practitioner_facility_assignment
from apps.scheduling.serializers import (
    LeaveCancellationSerializer,
    LeaveDecisionSerializer,
    LeaveRequestCreateSerializer,
    LeaveRequestDetailSerializer,
)
from apps.scheduling.services import approve_leave, cancel_leave, reject_leave, request_leave

from .base import SCHEDULING_DOCS_TAG, SchedulingBaseViewSet


@extend_schema(tags=[SCHEDULING_DOCS_TAG])
class LeaveRequestViewSet(SchedulingBaseViewSet):
    queryset = PractitionerLeaveRequest.objects.all()
    serializer_class = LeaveRequestDetailSerializer
    permission_map = {action: "scheduling_leave.manage" for action in ["list", "retrieve", "create", "approve", "reject", "cancel"]}

    def get_serializer_class(self):
        return {
            "create": LeaveRequestCreateSerializer,
            "approve": LeaveDecisionSerializer,
            "reject": LeaveDecisionSerializer,
            "cancel": LeaveCancellationSerializer,
        }.get(self.action, LeaveRequestDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            assignment_id = request.data.get("practitioner_facility_assignment_id")
            if not assignment_id:
                return None, None
            assignment = get_practitioner_facility_assignment(assignment_id)
            return assignment.practitioner.organization_id, assignment.facility_id
        leave_request = get_leave_request_by_id(self.kwargs.get("pk")) if self.action in {"retrieve", "approve", "reject", "cancel"} else None
        if leave_request is not None:
            return leave_request.practitioner_facility_assignment.practitioner.organization_id, leave_request.practitioner_facility_assignment.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_leave_requests(
            practitioner_facility_assignment_id=request.query_params.get("practitioner_facility_assignment_id"),
            practitioner_id=request.query_params.get("practitioner_id"),
            facility_id=request.query_params.get("facility_id"),
            status=request.query_params.get("status"),
            starts_from=request.query_params.get("starts_from"),
            ends_to=request.query_params.get("ends_to"),
        )
        return Response(LeaveRequestDetailSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = LeaveRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            leave_request = request_leave(**serializer.validated_data, requested_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LeaveRequestDetailSerializer(leave_request).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        leave_request = get_leave_request_by_id(pk)
        if leave_request is None:
            return Response({"detail": "Leave request not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(LeaveRequestDetailSerializer(leave_request).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        serializer = LeaveDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            leave_request, affected_appointments = approve_leave(
                leave_request_id=pk,
                decided_by_id=request.user.id,
                **serializer.validated_data,
            )
        except Exception as exc:
            translate_domain_error(exc)
        payload = LeaveRequestDetailSerializer(leave_request).data
        payload["affected_appointment_ids"] = [str(appointment.id) for appointment in affected_appointments]
        return Response(payload)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        serializer = LeaveDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            leave_request = reject_leave(
                leave_request_id=pk,
                decided_by_id=request.user.id,
                **serializer.validated_data,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LeaveRequestDetailSerializer(leave_request).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        serializer = LeaveCancellationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            leave_request = cancel_leave(
                leave_request_id=pk,
                cancelled_by_id=request.user.id,
                **serializer.validated_data,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LeaveRequestDetailSerializer(leave_request).data)
