from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.patients._helpers import translate_domain_error
from apps.patients.models import Patient
from apps.patients.selectors import get_patient_by_id, list_patients
from apps.patients.serializers import (
    PatientCreateMobileAccountSerializer,
    PatientDetailSerializer,
    PatientListSerializer,
    PatientMobileAccountCreatedSerializer,
    PatientCreateSerializer,
    PatientUpdateSerializer,
)
from apps.patients.services import create_patient, deactivate_patient, reactivate_patient, update_patient
from apps.patients.services.patient_mobile_account_service import (
    _safe_patient_summary,
    create_mobile_account_for_existing_patient,
)

from .base import PATIENT_DOCS_TAG, PatientsBaseViewSet, _bool_query_param


@extend_schema(tags=[PATIENT_DOCS_TAG])
class PatientViewSet(PatientsBaseViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientDetailSerializer
    permission_map = {
        "list": "patients_patient.view",
        "retrieve": "patients_patient.view",
        "create": "patients_patient.create",
        "partial_update": "patients_patient.update",
        "deactivate": "patients_patient.deactivate",
        "reactivate": "patients_patient.deactivate",
        "create_mobile_account": "patients_patient.update",
    }

    def get_serializer_class(self):
        return {
            "list": PatientListSerializer,
            "retrieve": PatientDetailSerializer,
            "create": PatientCreateSerializer,
            "partial_update": PatientUpdateSerializer,
            "create_mobile_account": PatientCreateMobileAccountSerializer,
        }.get(self.action, PatientDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            return request.data.get("organization_id"), request.data.get("registered_facility_id")
        if self.action in {"retrieve", "partial_update", "deactivate", "reactivate"}:
            patient = get_patient_by_id(self.kwargs.get("pk"))
            if patient is None:
                return None, None
            return patient.organization_id, patient.registered_facility_id
        if self.action == "create_mobile_account":
            patient = get_patient_by_id(self.kwargs.get("pk"))
            if patient is None:
                return None, None
            return patient.organization_id, patient.registered_facility_id
        return request.query_params.get("organization_id"), request.query_params.get("registered_facility_id")

    def list(self, request):
        queryset = list_patients(
            organization_id=request.query_params.get("organization_id"),
            registered_facility_id=request.query_params.get("registered_facility_id"),
            user_id=request.query_params.get("user_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(PatientListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = PatientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            patient = create_patient(**serializer.validated_data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientDetailSerializer(patient).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        patient = get_patient_by_id(pk)
        if patient is None:
            return Response({"detail": "Patient not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PatientDetailSerializer(patient).data)

    def partial_update(self, request, pk=None):
        serializer = PatientUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            patient = update_patient(patient_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientDetailSerializer(patient).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            patient = deactivate_patient(patient_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientDetailSerializer(patient).data)

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        try:
            patient = reactivate_patient(patient_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientDetailSerializer(patient).data)

    @action(detail=True, methods=["post"], url_path="create-mobile-account")
    def create_mobile_account(self, request, pk=None):
        serializer = PatientCreateMobileAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user, patient, temporary_password, generated_password = create_mobile_account_for_existing_patient(
                patient_id=pk,
                **serializer.validated_data,
            )
        except Exception as exc:
            translate_domain_error(exc)

        payload = {
            "user": {
                "id": user.id,
                "email": user.email,
                "phone_number": user.phone_number,
                "first_name": user.first_name,
                "middle_name": user.middle_name,
                "last_name": user.last_name,
                "is_active": user.is_active,
            },
            "patient": _safe_patient_summary(patient),
            "temporary_password": temporary_password,
            "generated_password": generated_password,
        }
        return Response(PatientMobileAccountCreatedSerializer(payload).data, status=status.HTTP_201_CREATED)
