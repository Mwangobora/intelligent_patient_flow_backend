from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.checkins.models import PatientCheckin
from apps.clinical._helpers import translate_domain_error
from apps.clinical.models import (
    ClinicalNote,
    DiagnosisCode,
    Encounter,
    EncounterDiagnosis,
    TriageAssessment,
    VitalSign,
)
from apps.clinical.selectors import (
    get_clinical_note_by_id,
    get_diagnosis_code_by_id,
    get_encounter_by_id,
    get_encounter_diagnosis_by_id,
    get_triage_assessment_by_id,
    get_vital_sign_by_id,
    list_clinical_notes,
    list_diagnosis_codes,
    list_encounter_diagnoses,
    list_encounter_status_history,
    list_encounters,
    list_triage_assessments,
    list_vital_signs,
)
from apps.clinical.serializers import (
    ClinicalNoteCreateSerializer,
    ClinicalNoteDetailSerializer,
    DiagnosisCodeCreateSerializer,
    DiagnosisCodeDetailSerializer,
    DiagnosisCodeUpdateSerializer,
    EncounterCancelSerializer,
    EncounterCompleteSerializer,
    EncounterCreateSerializer,
    EncounterDiagnosisCreateSerializer,
    EncounterDiagnosisDetailSerializer,
    EncounterDetailSerializer,
    EncounterStatusChangeSerializer,
    EncounterStatusHistorySerializer,
    EncounterUpdateSerializer,
    TriageAssessmentCreateSerializer,
    TriageAssessmentDetailSerializer,
    TriageAssessmentUpdateSerializer,
    VitalSignCreateSerializer,
    VitalSignDetailSerializer,
)
from apps.clinical.services import (
    cancel_encounter,
    change_encounter_status,
    complete_encounter,
    create_clinical_note,
    create_diagnosis_code,
    create_encounter,
    create_encounter_diagnosis,
    create_triage_assessment,
    create_vital_sign,
    update_diagnosis_code,
    update_encounter,
    update_triage_assessment,
)

from .base import CLINICAL_DOCS_TAG, ClinicalBaseViewSet, _bool_query_param


@extend_schema(tags=[CLINICAL_DOCS_TAG])
class EncounterViewSet(ClinicalBaseViewSet):
    queryset = Encounter.objects.all()
    serializer_class = EncounterDetailSerializer
    permission_map = {
        "list": "clinical_encounter.view",
        "retrieve": "clinical_encounter.view",
        "status_history": "clinical_encounter.view",
        "create": "clinical_encounter.create",
        "partial_update": "clinical_encounter.update",
        "change_status": "clinical_encounter.update",
        "complete": "clinical_encounter.complete",
        "cancel": "clinical_encounter.cancel",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            checkin = (
                PatientCheckin.objects.select_related("facility")
                .filter(pk=request.data.get("patient_checkin_id"))
                .first()
            )
            return (
                (checkin.facility.organization_id, checkin.facility_id) if checkin else (None, None)
            )
        if self.action in {
            "retrieve",
            "partial_update",
            "change_status",
            "complete",
            "cancel",
            "status_history",
        }:
            encounter = get_encounter_by_id(self.kwargs.get("pk"))
            return (
                (encounter.facility.organization_id, encounter.facility_id)
                if encounter
                else (None, None)
            )
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_encounters(
            facility_id=request.query_params.get("facility_id"),
            patient_id=request.query_params.get("patient_id"),
            patient_checkin_id=request.query_params.get("patient_checkin_id"),
            appointment_id=request.query_params.get("appointment_id"),
            status=request.query_params.get("status"),
            search=request.query_params.get("search"),
        )
        return Response(EncounterDetailSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = EncounterCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            encounter = create_encounter(**serializer.validated_data, opened_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(EncounterDetailSerializer(encounter).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        encounter = get_encounter_by_id(pk)
        if encounter is None:
            return Response({"detail": "Encounter not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(EncounterDetailSerializer(encounter).data)

    def partial_update(self, request, pk=None):
        serializer = EncounterUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            encounter = update_encounter(encounter_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(EncounterDetailSerializer(encounter).data)

    @action(detail=True, methods=["post"], url_path="change-status")
    def change_status(self, request, pk=None):
        serializer = EncounterStatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            encounter = change_encounter_status(
                encounter_id=pk, changed_by_id=request.user.id, **serializer.validated_data
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(EncounterDetailSerializer(encounter).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        serializer = EncounterCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            encounter = complete_encounter(
                encounter_id=pk,
                completed_by_id=request.user.id,
                completed_at=serializer.validated_data.get("completed_at"),
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(EncounterDetailSerializer(encounter).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        serializer = EncounterCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            encounter = cancel_encounter(
                encounter_id=pk, cancelled_by_id=request.user.id, **serializer.validated_data
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(EncounterDetailSerializer(encounter).data)

    @action(detail=True, methods=["get"], url_path="status-history")
    def status_history(self, request, pk=None):
        return Response(
            EncounterStatusHistorySerializer(
                list_encounter_status_history(encounter_id=pk), many=True
            ).data
        )


@extend_schema(tags=[CLINICAL_DOCS_TAG])
class TriageAssessmentViewSet(ClinicalBaseViewSet):
    queryset = TriageAssessment.objects.all()
    serializer_class = TriageAssessmentDetailSerializer
    permission_map = {
        "list": "clinical_triage.manage",
        "retrieve": "clinical_triage.manage",
        "create": "clinical_triage.manage",
        "partial_update": "clinical_triage.manage",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            encounter = get_encounter_by_id(request.data.get("encounter_id"))
        elif self.action in {"retrieve", "partial_update"}:
            assessment = get_triage_assessment_by_id(self.kwargs.get("pk"))
            encounter = assessment.encounter if assessment else None
        else:
            encounter = get_encounter_by_id(request.query_params.get("encounter_id"))
        return (
            (encounter.facility.organization_id, encounter.facility_id)
            if encounter
            else (
                request.query_params.get("organization_id"),
                request.query_params.get("facility_id"),
            )
        )

    def list(self, request):
        return Response(
            TriageAssessmentDetailSerializer(
                list_triage_assessments(
                    encounter_id=request.query_params.get("encounter_id"),
                    patient_id=request.query_params.get("patient_id"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = TriageAssessmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assessment = create_triage_assessment(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(
            TriageAssessmentDetailSerializer(assessment).data, status=status.HTTP_201_CREATED
        )

    def retrieve(self, request, pk=None):
        assessment = get_triage_assessment_by_id(pk)
        return (
            Response(TriageAssessmentDetailSerializer(assessment).data)
            if assessment
            else Response(
                {"detail": "Triage assessment not found."}, status=status.HTTP_404_NOT_FOUND
            )
        )

    def partial_update(self, request, pk=None):
        serializer = TriageAssessmentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            assessment = update_triage_assessment(assessment_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(TriageAssessmentDetailSerializer(assessment).data)


@extend_schema(tags=[CLINICAL_DOCS_TAG])
class VitalSignViewSet(ClinicalBaseViewSet):
    queryset = VitalSign.objects.all()
    serializer_class = VitalSignDetailSerializer
    permission_map = {
        "list": "clinical_vitals.manage",
        "retrieve": "clinical_vitals.manage",
        "create": "clinical_vitals.manage",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            encounter = get_encounter_by_id(request.data.get("encounter_id"))
        elif self.action == "retrieve":
            vital = get_vital_sign_by_id(self.kwargs.get("pk"))
            encounter = vital.encounter if vital else None
        else:
            encounter = get_encounter_by_id(request.query_params.get("encounter_id"))
        return (
            (encounter.facility.organization_id, encounter.facility_id)
            if encounter
            else (
                request.query_params.get("organization_id"),
                request.query_params.get("facility_id"),
            )
        )

    def list(self, request):
        return Response(
            VitalSignDetailSerializer(
                list_vital_signs(
                    encounter_id=request.query_params.get("encounter_id"),
                    patient_id=request.query_params.get("patient_id"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = VitalSignCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            vital = create_vital_sign(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(VitalSignDetailSerializer(vital).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        vital = get_vital_sign_by_id(pk)
        return (
            Response(VitalSignDetailSerializer(vital).data)
            if vital
            else Response({"detail": "Vital sign not found."}, status=status.HTTP_404_NOT_FOUND)
        )


@extend_schema(tags=[CLINICAL_DOCS_TAG])
class ClinicalNoteViewSet(ClinicalBaseViewSet):
    queryset = ClinicalNote.objects.all()
    serializer_class = ClinicalNoteDetailSerializer
    permission_map = {
        "list": "clinical_note.manage",
        "retrieve": "clinical_note.manage",
        "create": "clinical_note.manage",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            encounter = get_encounter_by_id(request.data.get("encounter_id"))
        elif self.action == "retrieve":
            note = get_clinical_note_by_id(self.kwargs.get("pk"))
            encounter = note.encounter if note else None
        else:
            encounter = get_encounter_by_id(request.query_params.get("encounter_id"))
        return (
            (encounter.facility.organization_id, encounter.facility_id)
            if encounter
            else (
                request.query_params.get("organization_id"),
                request.query_params.get("facility_id"),
            )
        )

    def list(self, request):
        return Response(
            ClinicalNoteDetailSerializer(
                list_clinical_notes(
                    encounter_id=request.query_params.get("encounter_id"),
                    patient_id=request.query_params.get("patient_id"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = ClinicalNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            note = create_clinical_note(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ClinicalNoteDetailSerializer(note).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        note = get_clinical_note_by_id(pk)
        return (
            Response(ClinicalNoteDetailSerializer(note).data)
            if note
            else Response({"detail": "Clinical note not found."}, status=status.HTTP_404_NOT_FOUND)
        )


@extend_schema(tags=[CLINICAL_DOCS_TAG])
class DiagnosisCodeViewSet(ClinicalBaseViewSet):
    queryset = DiagnosisCode.objects.all()
    serializer_class = DiagnosisCodeDetailSerializer
    permission_map = {
        "list": "clinical_diagnosis_code.manage",
        "retrieve": "clinical_diagnosis_code.manage",
        "create": "clinical_diagnosis_code.manage",
        "partial_update": "clinical_diagnosis_code.manage",
    }

    def list(self, request):
        queryset = list_diagnosis_codes(
            coding_system=request.query_params.get("coding_system"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(DiagnosisCodeDetailSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = DiagnosisCodeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            diagnosis = create_diagnosis_code(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(
            DiagnosisCodeDetailSerializer(diagnosis).data, status=status.HTTP_201_CREATED
        )

    def retrieve(self, request, pk=None):
        diagnosis = get_diagnosis_code_by_id(pk)
        return (
            Response(DiagnosisCodeDetailSerializer(diagnosis).data)
            if diagnosis
            else Response({"detail": "Diagnosis code not found."}, status=status.HTTP_404_NOT_FOUND)
        )

    def partial_update(self, request, pk=None):
        serializer = DiagnosisCodeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            diagnosis = update_diagnosis_code(code_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(DiagnosisCodeDetailSerializer(diagnosis).data)


@extend_schema(tags=[CLINICAL_DOCS_TAG])
class EncounterDiagnosisViewSet(ClinicalBaseViewSet):
    queryset = EncounterDiagnosis.objects.all()
    serializer_class = EncounterDiagnosisDetailSerializer
    permission_map = {
        "list": "clinical_diagnosis.manage",
        "retrieve": "clinical_diagnosis.manage",
        "create": "clinical_diagnosis.manage",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            encounter = get_encounter_by_id(request.data.get("encounter_id"))
        elif self.action == "retrieve":
            diagnosis = get_encounter_diagnosis_by_id(self.kwargs.get("pk"))
            encounter = diagnosis.encounter if diagnosis else None
        else:
            encounter = get_encounter_by_id(request.query_params.get("encounter_id"))
        return (
            (encounter.facility.organization_id, encounter.facility_id)
            if encounter
            else (
                request.query_params.get("organization_id"),
                request.query_params.get("facility_id"),
            )
        )

    def list(self, request):
        return Response(
            EncounterDiagnosisDetailSerializer(
                list_encounter_diagnoses(
                    encounter_id=request.query_params.get("encounter_id"),
                    patient_id=request.query_params.get("patient_id"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = EncounterDiagnosisCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            diagnosis = create_encounter_diagnosis(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(
            EncounterDiagnosisDetailSerializer(diagnosis).data, status=status.HTTP_201_CREATED
        )

    def retrieve(self, request, pk=None):
        diagnosis = get_encounter_diagnosis_by_id(pk)
        return (
            Response(EncounterDiagnosisDetailSerializer(diagnosis).data)
            if diagnosis
            else Response(
                {"detail": "Encounter diagnosis not found."}, status=status.HTTP_404_NOT_FOUND
            )
        )
