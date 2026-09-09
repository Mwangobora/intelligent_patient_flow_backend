from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from apps.patients._helpers import translate_domain_error
from apps.patients.models import PatientAllergy, PatientCondition
from apps.patients.selectors import (
    get_patient_allergy_by_id,
    get_patient_by_id,
    get_patient_condition_by_id,
    list_patient_allergies,
    list_patient_conditions,
)
from apps.patients.serializers import (
    PatientAllergyCreateSerializer,
    PatientAllergyDetailSerializer,
    PatientAllergyUpdateSerializer,
    PatientConditionCreateSerializer,
    PatientConditionDetailSerializer,
    PatientConditionUpdateSerializer,
)
from apps.patients.services import (
    create_patient_allergy,
    create_patient_condition,
    update_patient_allergy,
    update_patient_condition,
)

from .base import PATIENT_DOCS_TAG, PatientsBaseViewSet


@extend_schema(tags=[PATIENT_DOCS_TAG])
class PatientAllergyViewSet(PatientsBaseViewSet):
    queryset = PatientAllergy.objects.all()
    serializer_class = PatientAllergyDetailSerializer
    permission_map = {
        "list": "patients_allergy.manage",
        "retrieve": "patients_allergy.manage",
        "create": "patients_allergy.manage",
        "partial_update": "patients_allergy.manage",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            patient = get_patient_by_id(
                self.kwargs.get("patient_pk") or request.data.get("patient_id")
            )
        elif self.action in {"retrieve", "partial_update"}:
            allergy = get_patient_allergy_by_id(self.kwargs.get("pk"))
            patient = allergy.patient if allergy else None
        else:
            patient = get_patient_by_id(
                self.kwargs.get("patient_pk") or request.query_params.get("patient_id")
            )
        return (
            (patient.organization_id, patient.registered_facility_id)
            if patient
            else (
                request.query_params.get("organization_id"),
                request.query_params.get("registered_facility_id"),
            )
        )

    def list(self, request, patient_pk=None):
        queryset = list_patient_allergies(
            patient_id=patient_pk or request.query_params.get("patient_id"),
            status=request.query_params.get("status"),
            search=request.query_params.get("search"),
        )
        return Response(PatientAllergyDetailSerializer(queryset, many=True).data)

    def create(self, request, patient_pk=None):
        serializer = PatientAllergyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        patient_id = patient_pk or data.pop("patient_id", None)
        try:
            allergy = create_patient_allergy(
                patient_id=patient_id, **data, recorded_by_id=request.user.id
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(
            PatientAllergyDetailSerializer(allergy).data, status=status.HTTP_201_CREATED
        )

    def retrieve(self, request, pk=None):
        allergy = get_patient_allergy_by_id(pk)
        return (
            Response(PatientAllergyDetailSerializer(allergy).data)
            if allergy
            else Response(
                {"detail": "Patient allergy not found."}, status=status.HTTP_404_NOT_FOUND
            )
        )

    def partial_update(self, request, pk=None):
        serializer = PatientAllergyUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            allergy = update_patient_allergy(allergy_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientAllergyDetailSerializer(allergy).data)


@extend_schema(tags=[PATIENT_DOCS_TAG])
class PatientConditionViewSet(PatientsBaseViewSet):
    queryset = PatientCondition.objects.all()
    serializer_class = PatientConditionDetailSerializer
    permission_map = {
        "list": "patients_condition.manage",
        "retrieve": "patients_condition.manage",
        "create": "patients_condition.manage",
        "partial_update": "patients_condition.manage",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            patient = get_patient_by_id(
                self.kwargs.get("patient_pk") or request.data.get("patient_id")
            )
        elif self.action in {"retrieve", "partial_update"}:
            condition = get_patient_condition_by_id(self.kwargs.get("pk"))
            patient = condition.patient if condition else None
        else:
            patient = get_patient_by_id(
                self.kwargs.get("patient_pk") or request.query_params.get("patient_id")
            )
        return (
            (patient.organization_id, patient.registered_facility_id)
            if patient
            else (
                request.query_params.get("organization_id"),
                request.query_params.get("registered_facility_id"),
            )
        )

    def list(self, request, patient_pk=None):
        queryset = list_patient_conditions(
            patient_id=patient_pk or request.query_params.get("patient_id"),
            status=request.query_params.get("status"),
            search=request.query_params.get("search"),
        )
        return Response(PatientConditionDetailSerializer(queryset, many=True).data)

    def create(self, request, patient_pk=None):
        serializer = PatientConditionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        patient_id = patient_pk or data.pop("patient_id", None)
        try:
            condition = create_patient_condition(
                patient_id=patient_id, **data, recorded_by_id=request.user.id
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(
            PatientConditionDetailSerializer(condition).data, status=status.HTTP_201_CREATED
        )

    def retrieve(self, request, pk=None):
        condition = get_patient_condition_by_id(pk)
        return (
            Response(PatientConditionDetailSerializer(condition).data)
            if condition
            else Response(
                {"detail": "Patient condition not found."}, status=status.HTTP_404_NOT_FOUND
            )
        )

    def partial_update(self, request, pk=None):
        serializer = PatientConditionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            condition = update_patient_condition(condition_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientConditionDetailSerializer(condition).data)
