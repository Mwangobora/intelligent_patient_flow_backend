from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.scheduling._helpers import translate_domain_error
from apps.scheduling.models import PractitionerAvailabilityPeriod
from apps.scheduling.selectors import get_availability_period_by_id, list_availability_periods
from apps.scheduling.services._shared import get_practitioner_facility_assignment
from apps.scheduling.serializers import (
    AvailabilityPeriodCreateSerializer,
    AvailabilityPeriodDetailSerializer,
    AvailabilityPeriodUpdateSerializer,
)
from apps.scheduling.services import (
    create_availability_period,
    deactivate_availability_period,
    update_availability_period,
)

from .base import SCHEDULING_DOCS_TAG, SchedulingBaseViewSet, _bool_query_param


@extend_schema(tags=[SCHEDULING_DOCS_TAG])
class AvailabilityViewSet(SchedulingBaseViewSet):
    queryset = PractitionerAvailabilityPeriod.objects.all()
    serializer_class = AvailabilityPeriodDetailSerializer
    permission_map = {action: "scheduling_availability.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {
            "create": AvailabilityPeriodCreateSerializer,
            "partial_update": AvailabilityPeriodUpdateSerializer,
        }.get(self.action, AvailabilityPeriodDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            assignment_id = request.data.get("practitioner_facility_assignment_id")
            if not assignment_id:
                return None, None
            assignment = get_practitioner_facility_assignment(assignment_id)
            return assignment.practitioner.organization_id, assignment.facility_id
        availability = get_availability_period_by_id(self.kwargs.get("pk")) if self.action in {"retrieve", "partial_update", "deactivate"} else None
        if availability is not None:
            return availability.practitioner_facility_assignment.practitioner.organization_id, availability.practitioner_facility_assignment.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_availability_periods(
            practitioner_facility_assignment_id=request.query_params.get("practitioner_facility_assignment_id"),
            facility_id=request.query_params.get("facility_id"),
            practitioner_id=request.query_params.get("practitioner_id"),
            day_of_week=request.query_params.get("day_of_week"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(AvailabilityPeriodDetailSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = AvailabilityPeriodCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            availability = create_availability_period(**serializer.validated_data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AvailabilityPeriodDetailSerializer(availability).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        availability = get_availability_period_by_id(pk)
        if availability is None:
            return Response({"detail": "Availability period not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AvailabilityPeriodDetailSerializer(availability).data)

    def partial_update(self, request, pk=None):
        serializer = AvailabilityPeriodUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            availability = update_availability_period(availability_period_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AvailabilityPeriodDetailSerializer(availability).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            availability = deactivate_availability_period(availability_period_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AvailabilityPeriodDetailSerializer(availability).data)
