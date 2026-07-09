from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.practitioners._helpers import translate_domain_error
from apps.practitioners.models import (
    PractitionerDepartmentAssignment,
    PractitionerFacilityAssignment,
    PractitionerSpecialtyAssignment,
)
from apps.practitioners.selectors import (
    get_practitioner_by_id,
    get_practitioner_department_assignment_by_id,
    get_practitioner_facility_assignment_by_id,
    get_practitioner_specialty_assignment_by_id,
    list_practitioner_department_assignments,
    list_practitioner_facility_assignments,
    list_practitioner_specialty_assignments,
)
from apps.practitioners.serializers import (
    PractitionerDepartmentAssignmentCreateSerializer,
    PractitionerDepartmentAssignmentDetailSerializer,
    PractitionerDepartmentAssignmentUpdateSerializer,
    PractitionerFacilityAssignmentCreateSerializer,
    PractitionerFacilityAssignmentDetailSerializer,
    PractitionerFacilityAssignmentUpdateSerializer,
    PractitionerSpecialtyAssignmentCreateSerializer,
    PractitionerSpecialtyAssignmentDetailSerializer,
    PractitionerSpecialtyAssignmentUpdateSerializer,
)
from apps.practitioners.services import (
    assign_practitioner_to_department,
    assign_practitioner_to_facility,
    assign_practitioner_to_specialty,
    deactivate_department_assignment,
    deactivate_facility_assignment,
    deactivate_specialty_assignment,
    set_primary_department_assignment,
    set_primary_facility_assignment,
    set_primary_specialty_assignment,
    update_department_assignment,
    update_facility_assignment,
    update_specialty_assignment,
)

from .base import PRACTITIONER_DOCS_TAG, PractitionersBaseViewSet, _bool_query_param


@extend_schema(tags=[PRACTITIONER_DOCS_TAG])
class PractitionerFacilityAssignmentViewSet(PractitionersBaseViewSet):
    queryset = PractitionerFacilityAssignment.objects.all()
    serializer_class = PractitionerFacilityAssignmentDetailSerializer
    permission_map = {action: "practitioners_assignment.manage" for action in ["list", "retrieve", "create", "partial_update", "set_primary", "deactivate"]}

    def get_serializer_class(self):
        return {
            "create": PractitionerFacilityAssignmentCreateSerializer,
            "partial_update": PractitionerFacilityAssignmentUpdateSerializer,
        }.get(self.action, PractitionerFacilityAssignmentDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            practitioner = get_practitioner_by_id(self.kwargs.get("practitioner_pk") or request.data.get("practitioner_id"))
            if practitioner is None:
                return None, None
            return practitioner.organization_id, request.data.get("facility_id")
        if self.action in {"retrieve", "partial_update", "set_primary", "deactivate"}:
            assignment = get_practitioner_facility_assignment_by_id(self.kwargs.get("pk"))
            if assignment is None:
                return None, None
            return assignment.practitioner.organization_id, assignment.facility_id
        practitioner = get_practitioner_by_id(self.kwargs.get("practitioner_pk") or request.query_params.get("practitioner_id"))
        if practitioner is not None:
            return practitioner.organization_id, request.query_params.get("facility_id")
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request, practitioner_pk=None):
        queryset = list_practitioner_facility_assignments(
            practitioner_id=practitioner_pk or request.query_params.get("practitioner_id"),
            facility_id=request.query_params.get("facility_id"),
            organization_id=request.query_params.get("organization_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(PractitionerFacilityAssignmentDetailSerializer(queryset, many=True).data)

    def create(self, request, practitioner_pk=None):
        serializer = PractitionerFacilityAssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        practitioner_id = practitioner_pk or data.pop("practitioner_id", None)
        if practitioner_id is None:
            return Response({"detail": "practitioner_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            assignment = assign_practitioner_to_facility(
                practitioner_id=practitioner_id,
                **data,
                assigned_by_id=request.user.id,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerFacilityAssignmentDetailSerializer(assignment).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        assignment = get_practitioner_facility_assignment_by_id(pk)
        if assignment is None:
            return Response({"detail": "Practitioner facility assignment not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PractitionerFacilityAssignmentDetailSerializer(assignment).data)

    def partial_update(self, request, pk=None):
        serializer = PractitionerFacilityAssignmentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = update_facility_assignment(assignment_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerFacilityAssignmentDetailSerializer(assignment).data)

    @action(detail=True, methods=["post"], url_path="set-primary")
    def set_primary(self, request, pk=None):
        try:
            assignment = set_primary_facility_assignment(assignment_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerFacilityAssignmentDetailSerializer(assignment).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            assignment = deactivate_facility_assignment(assignment_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerFacilityAssignmentDetailSerializer(assignment).data)


@extend_schema(tags=[PRACTITIONER_DOCS_TAG])
class PractitionerDepartmentAssignmentViewSet(PractitionersBaseViewSet):
    queryset = PractitionerDepartmentAssignment.objects.all()
    serializer_class = PractitionerDepartmentAssignmentDetailSerializer
    permission_map = {action: "practitioners_assignment.manage" for action in ["list", "retrieve", "create", "partial_update", "set_primary", "deactivate"]}

    def get_serializer_class(self):
        return {
            "create": PractitionerDepartmentAssignmentCreateSerializer,
            "partial_update": PractitionerDepartmentAssignmentUpdateSerializer,
        }.get(self.action, PractitionerDepartmentAssignmentDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            assignment = get_practitioner_facility_assignment_by_id(
                self.kwargs.get("practitioner_facility_assignment_pk") or request.data.get("practitioner_facility_assignment_id")
            )
            if assignment is None:
                return None, None
            return assignment.practitioner.organization_id, assignment.facility_id
        if self.action in {"retrieve", "partial_update", "set_primary", "deactivate"}:
            assignment = get_practitioner_department_assignment_by_id(self.kwargs.get("pk"))
            if assignment is None:
                return None, None
            return assignment.practitioner_facility_assignment.practitioner.organization_id, assignment.practitioner_facility_assignment.facility_id
        pfa = get_practitioner_facility_assignment_by_id(
            self.kwargs.get("practitioner_facility_assignment_pk") or request.query_params.get("practitioner_facility_assignment_id")
        )
        if pfa is not None:
            return pfa.practitioner.organization_id, pfa.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request, practitioner_facility_assignment_pk=None):
        queryset = list_practitioner_department_assignments(
            practitioner_facility_assignment_id=practitioner_facility_assignment_pk or request.query_params.get("practitioner_facility_assignment_id"),
            department_id=request.query_params.get("department_id"),
            facility_id=request.query_params.get("facility_id"),
            organization_id=request.query_params.get("organization_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(PractitionerDepartmentAssignmentDetailSerializer(queryset, many=True).data)

    def create(self, request, practitioner_facility_assignment_pk=None):
        serializer = PractitionerDepartmentAssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        practitioner_facility_assignment_id = practitioner_facility_assignment_pk or data.pop("practitioner_facility_assignment_id", None)
        if practitioner_facility_assignment_id is None:
            return Response({"detail": "practitioner_facility_assignment_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            assignment = assign_practitioner_to_department(
                practitioner_facility_assignment_id=practitioner_facility_assignment_id,
                **data,
                assigned_by_id=request.user.id,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerDepartmentAssignmentDetailSerializer(assignment).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        assignment = get_practitioner_department_assignment_by_id(pk)
        if assignment is None:
            return Response({"detail": "Practitioner department assignment not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PractitionerDepartmentAssignmentDetailSerializer(assignment).data)

    def partial_update(self, request, pk=None):
        serializer = PractitionerDepartmentAssignmentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = update_department_assignment(assignment_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerDepartmentAssignmentDetailSerializer(assignment).data)

    @action(detail=True, methods=["post"], url_path="set-primary")
    def set_primary(self, request, pk=None):
        try:
            assignment = set_primary_department_assignment(assignment_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerDepartmentAssignmentDetailSerializer(assignment).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            assignment = deactivate_department_assignment(assignment_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerDepartmentAssignmentDetailSerializer(assignment).data)


@extend_schema(tags=[PRACTITIONER_DOCS_TAG])
class PractitionerSpecialtyAssignmentViewSet(PractitionersBaseViewSet):
    queryset = PractitionerSpecialtyAssignment.objects.all()
    serializer_class = PractitionerSpecialtyAssignmentDetailSerializer
    permission_map = {action: "practitioners_assignment.manage" for action in ["list", "retrieve", "create", "partial_update", "set_primary", "deactivate"]}

    def get_serializer_class(self):
        return {
            "create": PractitionerSpecialtyAssignmentCreateSerializer,
            "partial_update": PractitionerSpecialtyAssignmentUpdateSerializer,
        }.get(self.action, PractitionerSpecialtyAssignmentDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            assignment = get_practitioner_facility_assignment_by_id(
                self.kwargs.get("practitioner_facility_assignment_pk") or request.data.get("practitioner_facility_assignment_id")
            )
            if assignment is None:
                return None, None
            return assignment.practitioner.organization_id, assignment.facility_id
        if self.action in {"retrieve", "partial_update", "set_primary", "deactivate"}:
            assignment = get_practitioner_specialty_assignment_by_id(self.kwargs.get("pk"))
            if assignment is None:
                return None, None
            return assignment.practitioner_facility_assignment.practitioner.organization_id, assignment.practitioner_facility_assignment.facility_id
        pfa = get_practitioner_facility_assignment_by_id(
            self.kwargs.get("practitioner_facility_assignment_pk") or request.query_params.get("practitioner_facility_assignment_id")
        )
        if pfa is not None:
            return pfa.practitioner.organization_id, pfa.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request, practitioner_facility_assignment_pk=None):
        queryset = list_practitioner_specialty_assignments(
            practitioner_facility_assignment_id=practitioner_facility_assignment_pk or request.query_params.get("practitioner_facility_assignment_id"),
            facility_specialty_id=request.query_params.get("facility_specialty_id"),
            facility_id=request.query_params.get("facility_id"),
            specialty_id=request.query_params.get("specialty_id"),
            department_id=request.query_params.get("department_id"),
            organization_id=request.query_params.get("organization_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(PractitionerSpecialtyAssignmentDetailSerializer(queryset, many=True).data)

    def create(self, request, practitioner_facility_assignment_pk=None):
        serializer = PractitionerSpecialtyAssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        practitioner_facility_assignment_id = practitioner_facility_assignment_pk or data.pop("practitioner_facility_assignment_id", None)
        if practitioner_facility_assignment_id is None:
            return Response({"detail": "practitioner_facility_assignment_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            assignment = assign_practitioner_to_specialty(
                practitioner_facility_assignment_id=practitioner_facility_assignment_id,
                **data,
                assigned_by_id=request.user.id,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerSpecialtyAssignmentDetailSerializer(assignment).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        assignment = get_practitioner_specialty_assignment_by_id(pk)
        if assignment is None:
            return Response({"detail": "Practitioner specialty assignment not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PractitionerSpecialtyAssignmentDetailSerializer(assignment).data)

    def partial_update(self, request, pk=None):
        serializer = PractitionerSpecialtyAssignmentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = update_specialty_assignment(assignment_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerSpecialtyAssignmentDetailSerializer(assignment).data)

    @action(detail=True, methods=["post"], url_path="set-primary")
    def set_primary(self, request, pk=None):
        try:
            assignment = set_primary_specialty_assignment(assignment_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerSpecialtyAssignmentDetailSerializer(assignment).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            assignment = deactivate_specialty_assignment(assignment_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerSpecialtyAssignmentDetailSerializer(assignment).data)
