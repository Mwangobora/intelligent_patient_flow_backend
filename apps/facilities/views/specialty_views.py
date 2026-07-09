from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.facilities._helpers import translate_domain_error
from apps.facilities.models import FacilitySpecialty, Specialty
from apps.facilities.selectors import get_facility_specialty_by_id, get_specialty_by_id, list_facility_specialties, list_specialties
from apps.facilities.serializers import (
    FacilitySpecialtyCreateSerializer,
    FacilitySpecialtyDetailSerializer,
    FacilitySpecialtyUpdateSerializer,
    SpecialtyCreateSerializer,
    SpecialtyDetailSerializer,
    SpecialtyListSerializer,
    SpecialtyUpdateSerializer,
)
from apps.facilities.services import (
    create_facility_specialty,
    create_specialty,
    deactivate_facility_specialty,
    deactivate_specialty,
    update_facility_specialty,
    update_specialty,
)

from .base import FACILITY_DOCS_TAG, FacilitiesBaseViewSet, _bool_query_param


@extend_schema(tags=[FACILITY_DOCS_TAG])
class SpecialtyViewSet(FacilitiesBaseViewSet):
    queryset = Specialty.objects.all()
    serializer_class = SpecialtyDetailSerializer
    permission_map = {action: "facilities_specialty.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {
            "list": SpecialtyListSerializer,
            "retrieve": SpecialtyDetailSerializer,
            "create": SpecialtyCreateSerializer,
            "partial_update": SpecialtyUpdateSerializer,
        }.get(self.action, SpecialtyDetailSerializer)

    def list(self, request):
        queryset = list_specialties(
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(SpecialtyListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = SpecialtyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            specialty = create_specialty(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(SpecialtyDetailSerializer(specialty).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        specialty = get_specialty_by_id(pk)
        if specialty is None:
            return Response({"detail": "Specialty not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(SpecialtyDetailSerializer(specialty).data)

    def partial_update(self, request, pk=None):
        serializer = SpecialtyUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        regenerate_code = data.pop("regenerate_code", False)
        try:
            specialty = update_specialty(specialty_id=pk, regenerate_code=regenerate_code, **data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(SpecialtyDetailSerializer(specialty).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            specialty = deactivate_specialty(specialty_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(SpecialtyDetailSerializer(specialty).data)


@extend_schema(tags=[FACILITY_DOCS_TAG])
class FacilitySpecialtyViewSet(FacilitiesBaseViewSet):
    queryset = FacilitySpecialty.objects.all()
    serializer_class = FacilitySpecialtyDetailSerializer
    permission_map = {action: "facilities_specialty.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {
            "create": FacilitySpecialtyCreateSerializer,
            "partial_update": FacilitySpecialtyUpdateSerializer,
        }.get(self.action, FacilitySpecialtyDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            return None, request.data.get("facility_id")
        if self.action in {"retrieve", "partial_update", "deactivate"}:
            facility_specialty = get_facility_specialty_by_id(self.kwargs.get("pk"))
            if facility_specialty is None:
                return None, None
            return facility_specialty.facility.organization_id, facility_specialty.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id") or self.kwargs.get("facility_pk")

    def list(self, request):
        queryset = list_facility_specialties(
            facility_id=request.query_params.get("facility_id") or self.kwargs.get("facility_pk"),
            specialty_id=request.query_params.get("specialty_id"),
            department_id=request.query_params.get("department_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(FacilitySpecialtyDetailSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = FacilitySpecialtyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            facility_specialty = create_facility_specialty(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilitySpecialtyDetailSerializer(facility_specialty).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        facility_specialty = get_facility_specialty_by_id(pk)
        if facility_specialty is None:
            return Response({"detail": "Facility specialty not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(FacilitySpecialtyDetailSerializer(facility_specialty).data)

    def partial_update(self, request, pk=None):
        serializer = FacilitySpecialtyUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            facility_specialty = update_facility_specialty(facility_specialty_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilitySpecialtyDetailSerializer(facility_specialty).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            facility_specialty = deactivate_facility_specialty(facility_specialty_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilitySpecialtyDetailSerializer(facility_specialty).data)
