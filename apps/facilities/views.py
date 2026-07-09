from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import HasSystemPermission
from apps.facilities._helpers import translate_domain_error
from apps.facilities.models import (
    ConsultationRoom,
    Department,
    Facility,
    FacilityFlowSetting,
    FacilityOperatingHour,
    FacilityScheduleException,
    FacilitySpecialty,
    FacilityType,
    Organization,
    ServicePoint,
    ServicePointType,
    Specialty,
)
from apps.facilities.selectors import (
    get_consultation_room_by_id,
    get_department_by_id,
    get_facility_by_id,
    get_facility_specialty_by_id,
    get_facility_type_by_id,
    get_flow_setting_by_id,
    get_operating_hour_by_id,
    get_organization_by_id,
    get_schedule_exception_by_id,
    get_service_point_by_id,
    get_service_point_type_by_id,
    get_specialty_by_id,
    list_consultation_rooms,
    list_departments,
    list_facilities,
    list_facility_specialties,
    list_facility_types,
    list_flow_settings,
    list_operating_hours,
    list_organizations,
    list_schedule_exceptions,
    list_service_point_types,
    list_service_points,
    list_specialties,
)
from apps.facilities.serializers import (
    ConsultationRoomCreateSerializer,
    ConsultationRoomDetailSerializer,
    ConsultationRoomUpdateSerializer,
    DepartmentCreateSerializer,
    DepartmentDetailSerializer,
    DepartmentListSerializer,
    DepartmentUpdateSerializer,
    FacilityCreateSerializer,
    FacilityDetailSerializer,
    FacilityFlowSettingCreateSerializer,
    FacilityFlowSettingDetailSerializer,
    FacilityFlowSettingUpdateSerializer,
    FacilityListSerializer,
    FacilityOperatingHourCreateSerializer,
    FacilityOperatingHourDetailSerializer,
    FacilityOperatingHourUpdateSerializer,
    FacilityScheduleExceptionCreateSerializer,
    FacilityScheduleExceptionDetailSerializer,
    FacilityScheduleExceptionUpdateSerializer,
    FacilitySpecialtyCreateSerializer,
    FacilitySpecialtyDetailSerializer,
    FacilitySpecialtyUpdateSerializer,
    FacilityTypeCreateSerializer,
    FacilityTypeDetailSerializer,
    FacilityTypeListSerializer,
    FacilityTypeUpdateSerializer,
    FacilityUpdateSerializer,
    OrganizationCreateSerializer,
    OrganizationDetailSerializer,
    OrganizationListSerializer,
    OrganizationUpdateSerializer,
    ServicePointCreateSerializer,
    ServicePointDetailSerializer,
    ServicePointTypeCreateSerializer,
    ServicePointTypeDetailSerializer,
    ServicePointTypeListSerializer,
    ServicePointTypeUpdateSerializer,
    ServicePointUpdateSerializer,
    SpecialtyCreateSerializer,
    SpecialtyDetailSerializer,
    SpecialtyListSerializer,
    SpecialtyUpdateSerializer,
)
from apps.facilities.services import (
    create_consultation_room,
    create_department,
    create_facility,
    create_facility_flow_settings,
    create_facility_operating_hour,
    create_facility_schedule_exception,
    create_facility_specialty,
    create_facility_type,
    create_organization,
    create_service_point,
    create_service_point_type,
    create_specialty,
    deactivate_consultation_room,
    deactivate_department,
    deactivate_facility,
    deactivate_facility_operating_hour,
    deactivate_facility_schedule_exception,
    deactivate_facility_specialty,
    deactivate_facility_type,
    deactivate_organization,
    deactivate_service_point,
    deactivate_service_point_type,
    deactivate_specialty,
    update_consultation_room,
    update_department,
    update_facility,
    update_facility_flow_settings,
    update_facility_operating_hour,
    update_facility_schedule_exception,
    update_facility_specialty,
    update_facility_type,
    update_organization,
    update_service_point,
    update_service_point_type,
    update_specialty,
)


def _bool_query_param(value):
    if value is None:
        return None
    return value.lower() == "true"


class FacilitiesBaseViewSet(viewsets.GenericViewSet):
    permission_map: dict[str, str] = {}

    def get_permissions(self):
        self.required_permission = self.permission_map[self.action]
        return [HasSystemPermission()]


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


class _FacilityScopedManageViewSet(FacilitiesBaseViewSet):
    permission_map = {action: "facilities_department.manage" for action in []}

    def _list_scope(self, request):
        return request.query_params.get("facility_id") or self.kwargs.get("facility_pk")


class DepartmentViewSet(FacilitiesBaseViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentDetailSerializer
    permission_map = {action: "facilities_department.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {"list": DepartmentListSerializer, "retrieve": DepartmentDetailSerializer, "create": DepartmentCreateSerializer, "partial_update": DepartmentUpdateSerializer}.get(self.action, DepartmentDetailSerializer)

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
        queryset = list_departments(facility_id=request.query_params.get("facility_id") or self.kwargs.get("facility_pk"), is_active=_bool_query_param(request.query_params.get("is_active")), search=request.query_params.get("search"))
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


class SpecialtyViewSet(FacilitiesBaseViewSet):
    queryset = Specialty.objects.all()
    serializer_class = SpecialtyDetailSerializer
    permission_map = {action: "facilities_specialty.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {"list": SpecialtyListSerializer, "retrieve": SpecialtyDetailSerializer, "create": SpecialtyCreateSerializer, "partial_update": SpecialtyUpdateSerializer}.get(self.action, SpecialtyDetailSerializer)

    def list(self, request):
        queryset = list_specialties(is_active=_bool_query_param(request.query_params.get("is_active")), search=request.query_params.get("search"))
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


class FacilitySpecialtyViewSet(FacilitiesBaseViewSet):
    queryset = FacilitySpecialty.objects.all()
    serializer_class = FacilitySpecialtyDetailSerializer
    permission_map = {action: "facilities_specialty.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {"create": FacilitySpecialtyCreateSerializer, "partial_update": FacilitySpecialtyUpdateSerializer}.get(self.action, FacilitySpecialtyDetailSerializer)

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


class ServicePointTypeViewSet(FacilitiesBaseViewSet):
    queryset = ServicePointType.objects.all()
    serializer_class = ServicePointTypeDetailSerializer
    permission_map = {action: "facilities_service_point.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {"list": ServicePointTypeListSerializer, "retrieve": ServicePointTypeDetailSerializer, "create": ServicePointTypeCreateSerializer, "partial_update": ServicePointTypeUpdateSerializer}.get(self.action, ServicePointTypeDetailSerializer)

    def list(self, request):
        queryset = list_service_point_types(is_active=_bool_query_param(request.query_params.get("is_active")), search=request.query_params.get("search"))
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


class ServicePointViewSet(FacilitiesBaseViewSet):
    queryset = ServicePoint.objects.all()
    serializer_class = ServicePointDetailSerializer
    permission_map = {action: "facilities_service_point.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {"create": ServicePointCreateSerializer, "partial_update": ServicePointUpdateSerializer}.get(self.action, ServicePointDetailSerializer)

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
        queryset = list_service_points(facility_id=request.query_params.get("facility_id") or self.kwargs.get("facility_pk"), department_id=request.query_params.get("department_id"), is_active=_bool_query_param(request.query_params.get("is_active")), search=request.query_params.get("search"))
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


class ConsultationRoomViewSet(FacilitiesBaseViewSet):
    queryset = ConsultationRoom.objects.all()
    serializer_class = ConsultationRoomDetailSerializer
    permission_map = {action: "facilities_room.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {"create": ConsultationRoomCreateSerializer, "partial_update": ConsultationRoomUpdateSerializer}.get(self.action, ConsultationRoomDetailSerializer)

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
        queryset = list_consultation_rooms(facility_id=request.query_params.get("facility_id") or self.kwargs.get("facility_pk"), department_id=request.query_params.get("department_id"), is_active=_bool_query_param(request.query_params.get("is_active")), search=request.query_params.get("search"))
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


class FacilityOperatingHourViewSet(FacilitiesBaseViewSet):
    queryset = FacilityOperatingHour.objects.all()
    serializer_class = FacilityOperatingHourDetailSerializer
    permission_map = {action: "facilities_schedule.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {"create": FacilityOperatingHourCreateSerializer, "partial_update": FacilityOperatingHourUpdateSerializer}.get(self.action, FacilityOperatingHourDetailSerializer)

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
        queryset = list_operating_hours(facility_id=request.query_params.get("facility_id") or self.kwargs.get("facility_pk"), day_of_week=request.query_params.get("day_of_week"), is_active=_bool_query_param(request.query_params.get("is_active")))
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


class FacilityScheduleExceptionViewSet(FacilitiesBaseViewSet):
    queryset = FacilityScheduleException.objects.all()
    serializer_class = FacilityScheduleExceptionDetailSerializer
    permission_map = {action: "facilities_schedule.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {"create": FacilityScheduleExceptionCreateSerializer, "partial_update": FacilityScheduleExceptionUpdateSerializer}.get(self.action, FacilityScheduleExceptionDetailSerializer)

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
        queryset = list_schedule_exceptions(facility_id=request.query_params.get("facility_id") or self.kwargs.get("facility_pk"), exception_date=request.query_params.get("exception_date"), is_active=_bool_query_param(request.query_params.get("is_active")))
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


class FacilityFlowSettingViewSet(FacilitiesBaseViewSet):
    queryset = FacilityFlowSetting.objects.all()
    serializer_class = FacilityFlowSettingDetailSerializer
    permission_map = {action: "facilities_settings.manage" for action in ["list", "retrieve", "create", "partial_update"]}

    def get_serializer_class(self):
        return {"create": FacilityFlowSettingCreateSerializer, "partial_update": FacilityFlowSettingUpdateSerializer}.get(self.action, FacilityFlowSettingDetailSerializer)

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
