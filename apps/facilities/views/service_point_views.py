from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.facilities._helpers import translate_domain_error
from apps.facilities.models import ConsultationRoom, ServicePoint, ServicePointType
from apps.facilities.selectors import (
    get_consultation_room_by_id,
    get_service_point_by_id,
    get_service_point_type_by_id,
    list_consultation_rooms,
    list_service_point_types,
    list_service_points,
)
from apps.facilities.serializers import (
    ConsultationRoomCreateSerializer,
    ConsultationRoomDetailSerializer,
    ConsultationRoomUpdateSerializer,
    ServicePointCreateSerializer,
    ServicePointDetailSerializer,
    ServicePointTypeCreateSerializer,
    ServicePointTypeDetailSerializer,
    ServicePointTypeListSerializer,
    ServicePointTypeUpdateSerializer,
    ServicePointUpdateSerializer,
)
from apps.facilities.services import (
    create_consultation_room,
    create_service_point,
    create_service_point_type,
    deactivate_consultation_room,
    deactivate_service_point,
    deactivate_service_point_type,
    update_consultation_room,
    update_service_point,
    update_service_point_type,
)

from .base import FACILITY_DOCS_TAG, FacilitiesBaseViewSet, _bool_query_param


@extend_schema(tags=[FACILITY_DOCS_TAG])
class ServicePointTypeViewSet(FacilitiesBaseViewSet):
    queryset = ServicePointType.objects.all()
    serializer_class = ServicePointTypeDetailSerializer
    permission_map = {action: "facilities_service_point.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {
            "list": ServicePointTypeListSerializer,
            "retrieve": ServicePointTypeDetailSerializer,
            "create": ServicePointTypeCreateSerializer,
            "partial_update": ServicePointTypeUpdateSerializer,
        }.get(self.action, ServicePointTypeDetailSerializer)

    def list(self, request):
        queryset = list_service_point_types(
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(ServicePointTypeListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = ServicePointTypeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            service_point_type = create_service_point_type(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ServicePointTypeDetailSerializer(service_point_type).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        service_point_type = get_service_point_type_by_id(pk)
        if service_point_type is None:
            return Response({"detail": "Service point type not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ServicePointTypeDetailSerializer(service_point_type).data)

    def partial_update(self, request, pk=None):
        serializer = ServicePointTypeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        regenerate_code = data.pop("regenerate_code", False)
        try:
            service_point_type = update_service_point_type(service_point_type_id=pk, regenerate_code=regenerate_code, **data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ServicePointTypeDetailSerializer(service_point_type).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            service_point_type = deactivate_service_point_type(service_point_type_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ServicePointTypeDetailSerializer(service_point_type).data)


@extend_schema(tags=[FACILITY_DOCS_TAG])
class ServicePointViewSet(FacilitiesBaseViewSet):
    queryset = ServicePoint.objects.all()
    serializer_class = ServicePointDetailSerializer
    permission_map = {action: "facilities_service_point.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {
            "create": ServicePointCreateSerializer,
            "partial_update": ServicePointUpdateSerializer,
        }.get(self.action, ServicePointDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            return None, request.data.get("facility_id")
        if self.action in {"retrieve", "partial_update", "deactivate"}:
            service_point = get_service_point_by_id(self.kwargs.get("pk"))
            if service_point is None:
                return None, None
            return service_point.facility.organization_id, service_point.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id") or self.kwargs.get("facility_pk")

    def list(self, request):
        queryset = list_service_points(
            facility_id=request.query_params.get("facility_id") or self.kwargs.get("facility_pk"),
            department_id=request.query_params.get("department_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(ServicePointDetailSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = ServicePointCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            service_point = create_service_point(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ServicePointDetailSerializer(service_point).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        service_point = get_service_point_by_id(pk)
        if service_point is None:
            return Response({"detail": "Service point not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ServicePointDetailSerializer(service_point).data)

    def partial_update(self, request, pk=None):
        serializer = ServicePointUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        regenerate_code = data.pop("regenerate_code", False)
        try:
            service_point = update_service_point(service_point_id=pk, regenerate_code=regenerate_code, **data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ServicePointDetailSerializer(service_point).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            service_point = deactivate_service_point(service_point_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ServicePointDetailSerializer(service_point).data)


@extend_schema(tags=[FACILITY_DOCS_TAG])
class ConsultationRoomViewSet(FacilitiesBaseViewSet):
    queryset = ConsultationRoom.objects.all()
    serializer_class = ConsultationRoomDetailSerializer
    permission_map = {action: "facilities_room.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {
            "create": ConsultationRoomCreateSerializer,
            "partial_update": ConsultationRoomUpdateSerializer,
        }.get(self.action, ConsultationRoomDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            return None, request.data.get("facility_id")
        if self.action in {"retrieve", "partial_update", "deactivate"}:
            room = get_consultation_room_by_id(self.kwargs.get("pk"))
            if room is None:
                return None, None
            return room.facility.organization_id, room.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id") or self.kwargs.get("facility_pk")

    def list(self, request):
        queryset = list_consultation_rooms(
            facility_id=request.query_params.get("facility_id") or self.kwargs.get("facility_pk"),
            department_id=request.query_params.get("department_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(ConsultationRoomDetailSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = ConsultationRoomCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            room = create_consultation_room(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ConsultationRoomDetailSerializer(room).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        room = get_consultation_room_by_id(pk)
        if room is None:
            return Response({"detail": "Consultation room not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ConsultationRoomDetailSerializer(room).data)

    def partial_update(self, request, pk=None):
        serializer = ConsultationRoomUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        regenerate_code = data.pop("regenerate_code", False)
        try:
            room = update_consultation_room(consultation_room_id=pk, regenerate_code=regenerate_code, **data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ConsultationRoomDetailSerializer(room).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            room = deactivate_consultation_room(consultation_room_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ConsultationRoomDetailSerializer(room).data)
