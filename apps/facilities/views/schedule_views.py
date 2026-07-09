from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.facilities._helpers import translate_domain_error
from apps.facilities.models import FacilityFlowSetting, FacilityOperatingHour, FacilityScheduleException
from apps.facilities.selectors import get_flow_setting_by_id, get_operating_hour_by_id, get_schedule_exception_by_id, list_flow_settings, list_operating_hours, list_schedule_exceptions
from apps.facilities.serializers import (
    FacilityFlowSettingCreateSerializer,
    FacilityFlowSettingDetailSerializer,
    FacilityFlowSettingUpdateSerializer,
    FacilityOperatingHourCreateSerializer,
    FacilityOperatingHourDetailSerializer,
    FacilityOperatingHourUpdateSerializer,
    FacilityScheduleExceptionCreateSerializer,
    FacilityScheduleExceptionDetailSerializer,
    FacilityScheduleExceptionUpdateSerializer,
)
from apps.facilities.services import (
    create_facility_flow_settings,
    create_facility_operating_hour,
    create_facility_schedule_exception,
    deactivate_facility_operating_hour,
    deactivate_facility_schedule_exception,
    update_facility_flow_settings,
    update_facility_operating_hour,
    update_facility_schedule_exception,
)

from .base import FACILITY_DOCS_TAG, FacilitiesBaseViewSet, _bool_query_param


@extend_schema(tags=[FACILITY_DOCS_TAG])
class FacilityOperatingHourViewSet(FacilitiesBaseViewSet):
    queryset = FacilityOperatingHour.objects.all()
    serializer_class = FacilityOperatingHourDetailSerializer
    permission_map = {action: "facilities_schedule.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {
            "create": FacilityOperatingHourCreateSerializer,
            "partial_update": FacilityOperatingHourUpdateSerializer,
        }.get(self.action, FacilityOperatingHourDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            return None, request.data.get("facility_id")
        if self.action in {"retrieve", "partial_update", "deactivate"}:
            operating_hour = get_operating_hour_by_id(self.kwargs.get("pk"))
            if operating_hour is None:
                return None, None
            return operating_hour.facility.organization_id, operating_hour.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id") or self.kwargs.get("facility_pk")

    def list(self, request):
        queryset = list_operating_hours(
            facility_id=request.query_params.get("facility_id") or self.kwargs.get("facility_pk"),
            day_of_week=request.query_params.get("day_of_week"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(FacilityOperatingHourDetailSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = FacilityOperatingHourCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            operating_hour = create_facility_operating_hour(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityOperatingHourDetailSerializer(operating_hour).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        operating_hour = get_operating_hour_by_id(pk)
        if operating_hour is None:
            return Response({"detail": "Facility operating hour not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(FacilityOperatingHourDetailSerializer(operating_hour).data)

    def partial_update(self, request, pk=None):
        serializer = FacilityOperatingHourUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            operating_hour = update_facility_operating_hour(facility_operating_hour_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityOperatingHourDetailSerializer(operating_hour).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            operating_hour = deactivate_facility_operating_hour(facility_operating_hour_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityOperatingHourDetailSerializer(operating_hour).data)


@extend_schema(tags=[FACILITY_DOCS_TAG])
class FacilityScheduleExceptionViewSet(FacilitiesBaseViewSet):
    queryset = FacilityScheduleException.objects.all()
    serializer_class = FacilityScheduleExceptionDetailSerializer
    permission_map = {action: "facilities_schedule.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {
            "create": FacilityScheduleExceptionCreateSerializer,
            "partial_update": FacilityScheduleExceptionUpdateSerializer,
        }.get(self.action, FacilityScheduleExceptionDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            return None, request.data.get("facility_id")
        if self.action in {"retrieve", "partial_update", "deactivate"}:
            schedule_exception = get_schedule_exception_by_id(self.kwargs.get("pk"))
            if schedule_exception is None:
                return None, None
            return schedule_exception.facility.organization_id, schedule_exception.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id") or self.kwargs.get("facility_pk")

    def list(self, request):
        queryset = list_schedule_exceptions(
            facility_id=request.query_params.get("facility_id") or self.kwargs.get("facility_pk"),
            exception_date=request.query_params.get("exception_date"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(FacilityScheduleExceptionDetailSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = FacilityScheduleExceptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            schedule_exception = create_facility_schedule_exception(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityScheduleExceptionDetailSerializer(schedule_exception).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        schedule_exception = get_schedule_exception_by_id(pk)
        if schedule_exception is None:
            return Response({"detail": "Facility schedule exception not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(FacilityScheduleExceptionDetailSerializer(schedule_exception).data)

    def partial_update(self, request, pk=None):
        serializer = FacilityScheduleExceptionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            schedule_exception = update_facility_schedule_exception(facility_schedule_exception_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityScheduleExceptionDetailSerializer(schedule_exception).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            schedule_exception = deactivate_facility_schedule_exception(facility_schedule_exception_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityScheduleExceptionDetailSerializer(schedule_exception).data)


@extend_schema(tags=[FACILITY_DOCS_TAG])
class FacilityFlowSettingViewSet(FacilitiesBaseViewSet):
    queryset = FacilityFlowSetting.objects.all()
    serializer_class = FacilityFlowSettingDetailSerializer
    permission_map = {action: "facilities_settings.manage" for action in ["list", "retrieve", "create", "partial_update"]}

    def get_serializer_class(self):
        return {
            "create": FacilityFlowSettingCreateSerializer,
            "partial_update": FacilityFlowSettingUpdateSerializer,
        }.get(self.action, FacilityFlowSettingDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            return None, request.data.get("facility_id")
        if self.action in {"retrieve", "partial_update"}:
            flow_settings = get_flow_setting_by_id(self.kwargs.get("pk"))
            if flow_settings is None:
                return None, None
            return flow_settings.facility.organization_id, flow_settings.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id") or self.kwargs.get("facility_pk")

    def list(self, request):
        queryset = list_flow_settings(facility_id=request.query_params.get("facility_id") or self.kwargs.get("facility_pk"))
        return Response(FacilityFlowSettingDetailSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = FacilityFlowSettingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            flow_settings = create_facility_flow_settings(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityFlowSettingDetailSerializer(flow_settings).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        flow_settings = get_flow_setting_by_id(pk)
        if flow_settings is None:
            return Response({"detail": "Facility flow settings not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(FacilityFlowSettingDetailSerializer(flow_settings).data)

    def partial_update(self, request, pk=None):
        serializer = FacilityFlowSettingUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            flow_settings = update_facility_flow_settings(facility_flow_setting_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityFlowSettingDetailSerializer(flow_settings).data)
