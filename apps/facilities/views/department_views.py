from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.facilities._helpers import translate_domain_error
from apps.facilities.models import Department
from apps.facilities.selectors import get_department_by_id, list_departments
from apps.facilities.serializers import DepartmentCreateSerializer, DepartmentDetailSerializer, DepartmentListSerializer, DepartmentUpdateSerializer
from apps.facilities.services import create_department, deactivate_department, update_department

from .base import FACILITY_DOCS_TAG, FacilitiesBaseViewSet, _bool_query_param


@extend_schema(tags=[FACILITY_DOCS_TAG])
class DepartmentViewSet(FacilitiesBaseViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentDetailSerializer
    permission_map = {action: "facilities_department.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {
            "list": DepartmentListSerializer,
            "retrieve": DepartmentDetailSerializer,
            "create": DepartmentCreateSerializer,
            "partial_update": DepartmentUpdateSerializer,
        }.get(self.action, DepartmentDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            return None, request.data.get("facility_id")
        if self.action in {"retrieve", "partial_update", "deactivate"}:
            department = get_department_by_id(self.kwargs.get("pk"))
            if department is None:
                return None, None
            return department.facility.organization_id, department.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id") or self.kwargs.get("facility_pk")

    def list(self, request):
        queryset = list_departments(
            facility_id=request.query_params.get("facility_id") or self.kwargs.get("facility_pk"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(DepartmentListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = DepartmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            department = create_department(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(DepartmentDetailSerializer(department).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        department = get_department_by_id(pk)
        if department is None:
            return Response({"detail": "Department not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(DepartmentDetailSerializer(department).data)

    def partial_update(self, request, pk=None):
        serializer = DepartmentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        regenerate_code = data.pop("regenerate_code", False)
        try:
            department = update_department(department_id=pk, regenerate_code=regenerate_code, **data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(DepartmentDetailSerializer(department).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            department = deactivate_department(department_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(DepartmentDetailSerializer(department).data)
