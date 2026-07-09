from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.patients._helpers import translate_domain_error
from apps.patients.models import PatientAddress, PatientIdentifier, PatientIdentifierType
from apps.patients.selectors import (
    get_identifier_type_by_id,
    get_patient_address_by_id,
    get_patient_by_id,
    get_patient_identifier_by_id,
    list_identifier_types,
    list_patient_addresses,
    list_patient_identifiers,
)
from apps.patients.serializers import (
    PatientAddressCreateSerializer,
    PatientAddressDetailSerializer,
    PatientAddressUpdateSerializer,
    PatientIdentifierCreateSerializer,
    PatientIdentifierDetailSerializer,
    PatientIdentifierTypeCreateSerializer,
    PatientIdentifierTypeDetailSerializer,
    PatientIdentifierTypeListSerializer,
    PatientIdentifierTypeUpdateSerializer,
)
from apps.patients.services import (
    add_patient_address,
    add_patient_identifier,
    create_patient_identifier_type,
    deactivate_patient_address,
    deactivate_patient_identifier,
    deactivate_patient_identifier_type,
    set_primary_patient_address,
    set_primary_patient_identifier,
    update_patient_address,
    update_patient_identifier_type,
    verify_patient_identifier,
)

from .base import PATIENT_DOCS_TAG, PatientsBaseViewSet, _bool_query_param


@extend_schema(tags=[PATIENT_DOCS_TAG])
class PatientIdentifierTypeViewSet(PatientsBaseViewSet):
    queryset = PatientIdentifierType.objects.all()
    serializer_class = PatientIdentifierTypeDetailSerializer
    permission_map = {action: "patients_identifier_type.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {
            "list": PatientIdentifierTypeListSerializer,
            "retrieve": PatientIdentifierTypeDetailSerializer,
            "create": PatientIdentifierTypeCreateSerializer,
            "partial_update": PatientIdentifierTypeUpdateSerializer,
        }.get(self.action, PatientIdentifierTypeDetailSerializer)

    def get_permission_scope(self, request):
        if self.action in {"create", "list"}:
            return request.data.get("organization_id") if self.action == "create" else request.query_params.get("organization_id"), None
        identifier_type = get_identifier_type_by_id(self.kwargs.get("pk"))
        if identifier_type is None:
            return None, None
        return identifier_type.organization_id, None

    def list(self, request):
        include_global = request.query_params.get("include_global", "true").lower() != "false"
        queryset = list_identifier_types(
            organization_id=request.query_params.get("organization_id"),
            include_global=include_global,
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(PatientIdentifierTypeListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = PatientIdentifierTypeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            identifier_type = create_patient_identifier_type(**serializer.validated_data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientIdentifierTypeDetailSerializer(identifier_type).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        identifier_type = get_identifier_type_by_id(pk)
        if identifier_type is None:
            return Response({"detail": "Patient identifier type not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PatientIdentifierTypeDetailSerializer(identifier_type).data)

    def partial_update(self, request, pk=None):
        serializer = PatientIdentifierTypeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        regenerate_code = data.pop("regenerate_code", False)
        try:
            identifier_type = update_patient_identifier_type(identifier_type_id=pk, regenerate_code=regenerate_code, **data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientIdentifierTypeDetailSerializer(identifier_type).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            identifier_type = deactivate_patient_identifier_type(identifier_type_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientIdentifierTypeDetailSerializer(identifier_type).data)


@extend_schema(tags=[PATIENT_DOCS_TAG])
class PatientIdentifierViewSet(PatientsBaseViewSet):
    queryset = PatientIdentifier.objects.all()
    serializer_class = PatientIdentifierDetailSerializer
    permission_map = {action: "patients_identifier.manage" for action in ["list", "retrieve", "create", "verify", "set_primary", "deactivate"]}

    def get_serializer_class(self):
        return {"create": PatientIdentifierCreateSerializer}.get(self.action, PatientIdentifierDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            patient = get_patient_by_id(self.kwargs.get("patient_pk") or request.data.get("patient_id"))
            if patient is None:
                return None, None
            return patient.organization_id, patient.registered_facility_id
        if self.action in {"retrieve", "verify", "set_primary", "deactivate"}:
            identifier = get_patient_identifier_by_id(self.kwargs.get("pk"))
            if identifier is None:
                return None, None
            return identifier.patient.organization_id, identifier.patient.registered_facility_id
        patient = get_patient_by_id(self.kwargs.get("patient_pk") or request.query_params.get("patient_id"))
        if patient is not None:
            return patient.organization_id, patient.registered_facility_id
        return request.query_params.get("organization_id"), request.query_params.get("registered_facility_id")

    def list(self, request, patient_pk=None):
        queryset = list_patient_identifiers(
            patient_id=patient_pk or request.query_params.get("patient_id"),
            identifier_type_id=request.query_params.get("identifier_type_id"),
            organization_id=request.query_params.get("organization_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(PatientIdentifierDetailSerializer(queryset, many=True).data)

    def create(self, request, patient_pk=None):
        serializer = PatientIdentifierCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        patient_id = patient_pk or data.pop("patient_id", None)
        if patient_id is None:
            return Response({"detail": "patient_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            identifier = add_patient_identifier(patient_id=patient_id, **data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientIdentifierDetailSerializer(identifier).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        identifier = get_patient_identifier_by_id(pk)
        if identifier is None:
            return Response({"detail": "Patient identifier not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PatientIdentifierDetailSerializer(identifier).data)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        try:
            identifier = verify_patient_identifier(identifier_id=pk, verified_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientIdentifierDetailSerializer(identifier).data)

    @action(detail=True, methods=["post"], url_path="set-primary")
    def set_primary(self, request, pk=None):
        try:
            identifier = set_primary_patient_identifier(identifier_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientIdentifierDetailSerializer(identifier).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            identifier = deactivate_patient_identifier(identifier_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientIdentifierDetailSerializer(identifier).data)


@extend_schema(tags=[PATIENT_DOCS_TAG])
class PatientAddressViewSet(PatientsBaseViewSet):
    queryset = PatientAddress.objects.all()
    serializer_class = PatientAddressDetailSerializer
    permission_map = {action: "patients_address.manage" for action in ["list", "retrieve", "create", "partial_update", "set_primary", "deactivate"]}

    def get_serializer_class(self):
        return {
            "create": PatientAddressCreateSerializer,
            "partial_update": PatientAddressUpdateSerializer,
        }.get(self.action, PatientAddressDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            patient = get_patient_by_id(self.kwargs.get("patient_pk") or request.data.get("patient_id"))
            if patient is None:
                return None, None
            return patient.organization_id, patient.registered_facility_id
        if self.action in {"retrieve", "partial_update", "set_primary", "deactivate"}:
            address = get_patient_address_by_id(self.kwargs.get("pk"))
            if address is None:
                return None, None
            return address.patient.organization_id, address.patient.registered_facility_id
        patient = get_patient_by_id(self.kwargs.get("patient_pk") or request.query_params.get("patient_id"))
        if patient is not None:
            return patient.organization_id, patient.registered_facility_id
        return request.query_params.get("organization_id"), request.query_params.get("registered_facility_id")

    def list(self, request, patient_pk=None):
        queryset = list_patient_addresses(
            patient_id=patient_pk or request.query_params.get("patient_id"),
            organization_id=request.query_params.get("organization_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(PatientAddressDetailSerializer(queryset, many=True).data)

    def create(self, request, patient_pk=None):
        serializer = PatientAddressCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        patient_id = patient_pk or data.pop("patient_id", None)
        if patient_id is None:
            return Response({"detail": "patient_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            address = add_patient_address(patient_id=patient_id, **data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientAddressDetailSerializer(address).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        address = get_patient_address_by_id(pk)
        if address is None:
            return Response({"detail": "Patient address not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PatientAddressDetailSerializer(address).data)

    def partial_update(self, request, pk=None):
        serializer = PatientAddressUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            address = update_patient_address(address_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientAddressDetailSerializer(address).data)

    @action(detail=True, methods=["post"], url_path="set-primary")
    def set_primary(self, request, pk=None):
        try:
            address = set_primary_patient_address(address_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientAddressDetailSerializer(address).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            address = deactivate_patient_address(address_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientAddressDetailSerializer(address).data)
