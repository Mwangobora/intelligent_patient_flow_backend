from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.patients._helpers import translate_domain_error
from apps.patients.models import PatientAccessGrant
from apps.patients.selectors import get_patient_access_grant_by_id, get_patient_by_id, list_patient_access_grants
from apps.patients.serializers import (
    PatientAccessGrantCreateSerializer,
    PatientAccessGrantDetailSerializer,
    PatientAccessGrantReactivateSerializer,
    PatientAccessGrantRevokeSerializer,
)
from apps.patients.services import grant_patient_access, reactivate_patient_access_grant, revoke_patient_access

from .base import PATIENT_DOCS_TAG, PatientsBaseViewSet, _bool_query_param


@extend_schema(tags=[PATIENT_DOCS_TAG])
class PatientAccessGrantViewSet(PatientsBaseViewSet):
    queryset = PatientAccessGrant.objects.all()
    serializer_class = PatientAccessGrantDetailSerializer
    permission_map = {action: "patients_access_grant.manage" for action in ["list", "retrieve", "create", "revoke", "reactivate"]}

    def get_serializer_class(self):
        return {
            "create": PatientAccessGrantCreateSerializer,
            "revoke": PatientAccessGrantRevokeSerializer,
            "reactivate": PatientAccessGrantReactivateSerializer,
        }.get(self.action, PatientAccessGrantDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            patient = get_patient_by_id(self.kwargs.get("patient_pk") or request.data.get("patient_id"))
            if patient is None:
                return None, None
            return patient.organization_id, patient.registered_facility_id
        if self.action in {"retrieve", "revoke", "reactivate"}:
            grant = get_patient_access_grant_by_id(self.kwargs.get("pk"))
            if grant is None:
                return None, None
            return grant.patient.organization_id, grant.patient.registered_facility_id
        patient = get_patient_by_id(self.kwargs.get("patient_pk") or request.query_params.get("patient_id"))
        if patient is not None:
            return patient.organization_id, patient.registered_facility_id
        return request.query_params.get("organization_id"), request.query_params.get("registered_facility_id")

    def list(self, request, patient_pk=None):
        queryset = list_patient_access_grants(
            patient_id=patient_pk or request.query_params.get("patient_id"),
            grantee_user_id=request.query_params.get("grantee_user_id"),
            role_id=request.query_params.get("role_id"),
            organization_id=request.query_params.get("organization_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(PatientAccessGrantDetailSerializer(queryset, many=True).data)

    def create(self, request, patient_pk=None):
        serializer = PatientAccessGrantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        patient_id = patient_pk or data.pop("patient_id", None)
        if patient_id is None:
            return Response({"detail": "patient_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            grant = grant_patient_access(
                patient_id=patient_id,
                **data,
                granted_by_id=request.user.id,
                created_by_id=request.user.id,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientAccessGrantDetailSerializer(grant).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        grant = get_patient_access_grant_by_id(pk)
        if grant is None:
            return Response({"detail": "Patient access grant not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PatientAccessGrantDetailSerializer(grant).data)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        serializer = PatientAccessGrantRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            grant = revoke_patient_access(
                grant_id=pk,
                revoked_by_id=request.user.id,
                revoked_reason=serializer.validated_data["revoked_reason"],
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientAccessGrantDetailSerializer(grant).data)

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        serializer = PatientAccessGrantReactivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            grant = reactivate_patient_access_grant(
                grant_id=pk,
                granted_by_id=request.user.id,
                **serializer.validated_data,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientAccessGrantDetailSerializer(grant).data)
