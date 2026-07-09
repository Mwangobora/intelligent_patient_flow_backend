from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.facilities._helpers import translate_domain_error
from apps.facilities.models import Facility, FacilityType, Organization
from apps.facilities.selectors import get_facility_by_id, get_facility_type_by_id, get_organization_by_id, list_facilities, list_facility_types, list_organizations
from apps.facilities.serializers import (
    FacilityCreateSerializer,
    FacilityDetailSerializer,
    FacilityListSerializer,
    FacilityTypeCreateSerializer,
    FacilityTypeDetailSerializer,
    FacilityTypeListSerializer,
    FacilityTypeUpdateSerializer,
    FacilityUpdateSerializer,
    OrganizationCreateSerializer,
    OrganizationDetailSerializer,
    OrganizationListSerializer,
    OrganizationUpdateSerializer,
)
from apps.facilities.services import (
    create_facility,
    create_facility_type,
    create_organization,
    deactivate_facility,
    deactivate_facility_type,
    deactivate_organization,
    update_facility,
    update_facility_type,
    update_organization,
)

from .base import FACILITY_DOCS_TAG, FacilitiesBaseViewSet, _bool_query_param


@extend_schema(tags=[FACILITY_DOCS_TAG])
class OrganizationViewSet(FacilitiesBaseViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationDetailSerializer
    permission_map = {
        "list": "facilities_organization.view",
        "retrieve": "facilities_organization.view",
        "create": "facilities_organization.create",
        "partial_update": "facilities_organization.update",
        "deactivate": "facilities_organization.deactivate",
    }

    def get_serializer_class(self):
        return {
            "list": OrganizationListSerializer,
            "retrieve": OrganizationDetailSerializer,
            "create": OrganizationCreateSerializer,
            "partial_update": OrganizationUpdateSerializer,
        }.get(self.action, OrganizationDetailSerializer)

    def get_permission_scope(self, request):
        if self.action in {"retrieve", "partial_update", "deactivate"}:
            return self.kwargs.get("pk"), None
        return None, None

    def list(self, request):
        queryset = list_organizations(
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(OrganizationListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = OrganizationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            organization = create_organization(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(OrganizationDetailSerializer(organization).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        organization = get_organization_by_id(pk)
        if organization is None:
            return Response({"detail": "Organization not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrganizationDetailSerializer(organization).data)

    def partial_update(self, request, pk=None):
        serializer = OrganizationUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            organization = update_organization(organization_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(OrganizationDetailSerializer(organization).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            organization = deactivate_organization(organization_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(OrganizationDetailSerializer(organization).data)


@extend_schema(tags=[FACILITY_DOCS_TAG])
class FacilityTypeViewSet(FacilitiesBaseViewSet):
    queryset = FacilityType.objects.all()
    serializer_class = FacilityTypeDetailSerializer
    permission_map = {
        "list": "facilities_facility_type.view",
        "retrieve": "facilities_facility_type.view",
        "create": "facilities_facility_type.create",
        "partial_update": "facilities_facility_type.update",
        "deactivate": "facilities_facility_type.deactivate",
    }

    def get_serializer_class(self):
        return {
            "list": FacilityTypeListSerializer,
            "retrieve": FacilityTypeDetailSerializer,
            "create": FacilityTypeCreateSerializer,
            "partial_update": FacilityTypeUpdateSerializer,
        }.get(self.action, FacilityTypeDetailSerializer)

    def list(self, request):
        queryset = list_facility_types(
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(FacilityTypeListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = FacilityTypeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            facility_type = create_facility_type(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityTypeDetailSerializer(facility_type).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        facility_type = get_facility_type_by_id(pk)
        if facility_type is None:
            return Response({"detail": "Facility type not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(FacilityTypeDetailSerializer(facility_type).data)

    def partial_update(self, request, pk=None):
        serializer = FacilityTypeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        regenerate_code = data.pop("regenerate_code", False)
        try:
            facility_type = update_facility_type(facility_type_id=pk, regenerate_code=regenerate_code, **data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityTypeDetailSerializer(facility_type).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            facility_type = deactivate_facility_type(facility_type_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityTypeDetailSerializer(facility_type).data)


@extend_schema(tags=[FACILITY_DOCS_TAG])
class FacilityViewSet(FacilitiesBaseViewSet):
    queryset = Facility.objects.all()
    serializer_class = FacilityDetailSerializer
    permission_map = {
        "list": "facilities_facility.view",
        "retrieve": "facilities_facility.view",
        "create": "facilities_facility.create",
        "partial_update": "facilities_facility.update",
        "deactivate": "facilities_facility.deactivate",
    }

    def get_serializer_class(self):
        return {
            "list": FacilityListSerializer,
            "retrieve": FacilityDetailSerializer,
            "create": FacilityCreateSerializer,
            "partial_update": FacilityUpdateSerializer,
        }.get(self.action, FacilityDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            return request.data.get("organization_id"), request.data.get("facility_id")
        if self.action in {"retrieve", "partial_update", "deactivate"}:
            facility = get_facility_by_id(self.kwargs.get("pk"))
            if facility is None:
                return None, None
            return facility.organization_id, facility.id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_facilities(
            organization_id=request.query_params.get("organization_id"),
            facility_type_id=request.query_params.get("facility_type_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(FacilityListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = FacilityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        data["timezone_name"] = data.pop("timezone", "Africa/Dar_es_Salaam")
        try:
            facility = create_facility(**data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityDetailSerializer(facility).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        facility = get_facility_by_id(pk)
        if facility is None:
            return Response({"detail": "Facility not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(FacilityDetailSerializer(facility).data)

    def partial_update(self, request, pk=None):
        serializer = FacilityUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        regenerate_code = data.pop("regenerate_code", False)
        try:
            facility = update_facility(facility_id=pk, regenerate_code=regenerate_code, **data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityDetailSerializer(facility).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            facility = deactivate_facility(facility_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(FacilityDetailSerializer(facility).data)
