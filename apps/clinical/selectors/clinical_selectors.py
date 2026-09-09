from __future__ import annotations

from django.db.models import Q

from apps.clinical.models import (
    ClinicalNote,
    DiagnosisCode,
    Encounter,
    EncounterDiagnosis,
    EncounterStatusHistory,
    TriageAssessment,
    VitalSign,
)


def base_encounter_queryset():
    return Encounter.objects.select_related(
        "facility",
        "patient",
        "patient_checkin",
        "appointment",
        "department",
        "facility_specialty__specialty",
        "attending_practitioner_facility_assignment__practitioner",
        "opened_by",
        "completed_by",
        "cancelled_by",
    )


def list_encounters(
    *,
    facility_id=None,
    patient_id=None,
    patient_checkin_id=None,
    appointment_id=None,
    status=None,
    search=None,
):
    queryset = base_encounter_queryset()
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if patient_id:
        queryset = queryset.filter(patient_id=patient_id)
    if patient_checkin_id:
        queryset = queryset.filter(patient_checkin_id=patient_checkin_id)
    if appointment_id:
        queryset = queryset.filter(appointment_id=appointment_id)
    if status:
        queryset = queryset.filter(status=status)
    if search:
        queryset = queryset.filter(
            Q(encounter_number__icontains=search)
            | Q(patient__patient_number__icontains=search)
            | Q(patient__first_name__icontains=search)
            | Q(patient__last_name__icontains=search)
        )
    return queryset.order_by("-opened_at")


def get_encounter_by_id(encounter_id):
    return base_encounter_queryset().filter(pk=encounter_id).first()


def list_encounter_status_history(*, encounter_id):
    return (
        EncounterStatusHistory.objects.select_related("changed_by")
        .filter(encounter_id=encounter_id)
        .order_by("changed_at")
    )


def list_triage_assessments(*, encounter_id=None, patient_id=None):
    queryset = TriageAssessment.objects.select_related(
        "encounter",
        "encounter__patient",
        "performed_by_practitioner_facility_assignment__practitioner",
    )
    if encounter_id:
        queryset = queryset.filter(encounter_id=encounter_id)
    if patient_id:
        queryset = queryset.filter(encounter__patient_id=patient_id)
    return queryset.order_by("-started_at")


def get_triage_assessment_by_id(assessment_id):
    return list_triage_assessments().filter(pk=assessment_id).first()


def list_vital_signs(*, encounter_id=None, patient_id=None):
    queryset = VitalSign.objects.select_related(
        "encounter",
        "encounter__patient",
        "recorded_by_practitioner_facility_assignment__practitioner",
    )
    if encounter_id:
        queryset = queryset.filter(encounter_id=encounter_id)
    if patient_id:
        queryset = queryset.filter(encounter__patient_id=patient_id)
    return queryset.order_by("-recorded_at")


def get_vital_sign_by_id(vital_id):
    return list_vital_signs().filter(pk=vital_id).first()


def list_clinical_notes(*, encounter_id=None, patient_id=None):
    queryset = ClinicalNote.objects.select_related(
        "encounter", "encounter__patient", "practitioner_facility_assignment__practitioner"
    )
    if encounter_id:
        queryset = queryset.filter(encounter_id=encounter_id)
    if patient_id:
        queryset = queryset.filter(encounter__patient_id=patient_id)
    return queryset.order_by("-created_at")


def get_clinical_note_by_id(note_id):
    return list_clinical_notes().filter(pk=note_id).first()


def list_diagnosis_codes(*, coding_system=None, is_active: bool | None = None, search=None):
    queryset = DiagnosisCode.objects.all()
    if coding_system:
        queryset = queryset.filter(coding_system__iexact=coding_system)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(
            Q(code__icontains=search) | Q(name__icontains=search) | Q(description__icontains=search)
        )
    return queryset.order_by("coding_system", "code")


def get_diagnosis_code_by_id(code_id):
    return DiagnosisCode.objects.filter(pk=code_id).first()


def list_encounter_diagnoses(*, encounter_id=None, patient_id=None):
    queryset = EncounterDiagnosis.objects.select_related(
        "encounter", "diagnosis_code", "diagnosed_by_practitioner_facility_assignment__practitioner"
    )
    if encounter_id:
        queryset = queryset.filter(encounter_id=encounter_id)
    if patient_id:
        queryset = queryset.filter(encounter__patient_id=patient_id)
    return queryset.order_by("-is_primary", "-diagnosed_at")


def get_encounter_diagnosis_by_id(diagnosis_id):
    return list_encounter_diagnoses().filter(pk=diagnosis_id).first()
