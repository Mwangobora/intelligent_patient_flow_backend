from __future__ import annotations

from rest_framework import serializers

from apps.clinical.models import (
    ClinicalNote,
    DiagnosisCode,
    Encounter,
    EncounterDiagnosis,
    EncounterStatusHistory,
    TriageAssessment,
    VitalSign,
)


class EncounterStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_email = serializers.CharField(source="changed_by.email", read_only=True)

    class Meta:
        model = EncounterStatusHistory
        fields = [
            "id",
            "encounter",
            "from_status",
            "to_status",
            "change_source",
            "changed_by",
            "changed_by_email",
            "reason",
            "changed_at",
            "created_at",
        ]
        read_only_fields = fields


class EncounterDetailSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)
    patient_name = serializers.SerializerMethodField()
    specialty_name = serializers.CharField(
        source="facility_specialty.specialty.name", read_only=True
    )
    department_name = serializers.CharField(source="department.name", read_only=True)
    practitioner_name = serializers.SerializerMethodField()

    class Meta:
        model = Encounter
        fields = [
            "id",
            "facility",
            "facility_name",
            "patient",
            "patient_number",
            "patient_name",
            "patient_checkin",
            "appointment",
            "department",
            "department_name",
            "facility_specialty",
            "specialty_name",
            "attending_practitioner_facility_assignment",
            "practitioner_name",
            "encounter_number",
            "encounter_type",
            "status",
            "opened_at",
            "opened_by",
            "completed_at",
            "completed_by",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "encounter_number",
            "status",
            "opened_by",
            "completed_at",
            "completed_by",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
        ]

    def get_patient_name(self, obj):
        return " ".join(
            part
            for part in [obj.patient.first_name, obj.patient.middle_name, obj.patient.last_name]
            if part
        )

    def get_practitioner_name(self, obj):
        assignment = obj.attending_practitioner_facility_assignment
        if assignment is None:
            return None
        practitioner = assignment.practitioner
        return " ".join(part for part in [practitioner.first_name, practitioner.last_name] if part)


class EncounterCreateSerializer(serializers.Serializer):
    patient_checkin_id = serializers.UUIDField()
    encounter_type = serializers.ChoiceField(
        choices=Encounter.EncounterType.choices, default=Encounter.EncounterType.OUTPATIENT
    )
    department_id = serializers.UUIDField(required=False, allow_null=True)
    facility_specialty_id = serializers.UUIDField(required=False, allow_null=True)
    attending_practitioner_facility_assignment_id = serializers.UUIDField(
        required=False, allow_null=True
    )
    opened_at = serializers.DateTimeField(required=False, allow_null=True)


class EncounterUpdateSerializer(serializers.Serializer):
    encounter_type = serializers.ChoiceField(
        choices=Encounter.EncounterType.choices, required=False
    )
    department_id = serializers.UUIDField(required=False, allow_null=True)
    facility_specialty_id = serializers.UUIDField(required=False, allow_null=True)
    attending_practitioner_facility_assignment_id = serializers.UUIDField(
        required=False, allow_null=True
    )


class EncounterStatusChangeSerializer(serializers.Serializer):
    to_status = serializers.ChoiceField(choices=Encounter.Status.choices)
    reason = serializers.CharField(
        max_length=250, required=False, allow_blank=True, allow_null=True
    )
    changed_at = serializers.DateTimeField(required=False, allow_null=True)


class EncounterCancelSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(max_length=250)
    cancelled_at = serializers.DateTimeField(required=False, allow_null=True)


class EncounterCompleteSerializer(serializers.Serializer):
    completed_at = serializers.DateTimeField(required=False, allow_null=True)


class TriageAssessmentDetailSerializer(serializers.ModelSerializer):
    patient_number = serializers.CharField(
        source="encounter.patient.patient_number", read_only=True
    )

    class Meta:
        model = TriageAssessment
        fields = [
            "id",
            "encounter",
            "patient_number",
            "performed_by_practitioner_facility_assignment",
            "triage_level",
            "pain_score",
            "mobility_status",
            "consciousness_level",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]


class TriageAssessmentCreateSerializer(serializers.Serializer):
    encounter_id = serializers.UUIDField()
    performed_by_practitioner_facility_assignment_id = serializers.UUIDField(
        required=False, allow_null=True
    )
    triage_level = serializers.IntegerField(min_value=1, max_value=4)
    chief_complaint = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    pain_score = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=10
    )
    mobility_status = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=30
    )
    consciousness_level = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=30
    )
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    started_at = serializers.DateTimeField(required=False, allow_null=True)
    completed_at = serializers.DateTimeField(required=False, allow_null=True)


class TriageAssessmentUpdateSerializer(TriageAssessmentCreateSerializer):
    encounter_id = serializers.UUIDField(required=False)
    triage_level = serializers.IntegerField(required=False, min_value=1, max_value=4)


class VitalSignDetailSerializer(serializers.ModelSerializer):
    patient_number = serializers.CharField(
        source="encounter.patient.patient_number", read_only=True
    )

    class Meta:
        model = VitalSign
        fields = "__all__"


class VitalSignCreateSerializer(serializers.Serializer):
    encounter_id = serializers.UUIDField()
    recorded_by_practitioner_facility_assignment_id = serializers.UUIDField(
        required=False, allow_null=True
    )
    temperature_c = serializers.DecimalField(
        required=False, allow_null=True, max_digits=4, decimal_places=1
    )
    systolic_bp = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    diastolic_bp = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    heart_rate = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    respiratory_rate = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    oxygen_saturation = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=100
    )
    weight_kg = serializers.DecimalField(
        required=False, allow_null=True, max_digits=6, decimal_places=2
    )
    height_cm = serializers.DecimalField(
        required=False, allow_null=True, max_digits=6, decimal_places=2
    )
    blood_glucose = serializers.DecimalField(
        required=False, allow_null=True, max_digits=6, decimal_places=2
    )
    pain_score = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=10
    )
    recorded_at = serializers.DateTimeField(required=False, allow_null=True)


class ClinicalNoteDetailSerializer(serializers.ModelSerializer):
    patient_number = serializers.CharField(
        source="encounter.patient.patient_number", read_only=True
    )

    class Meta:
        model = ClinicalNote
        fields = [
            "id",
            "encounter",
            "patient_number",
            "practitioner_facility_assignment",
            "note_type",
            "supersedes_note",
            "signed_at",
            "created_at",
            "updated_at",
        ]


class ClinicalNoteCreateSerializer(serializers.Serializer):
    encounter_id = serializers.UUIDField()
    practitioner_facility_assignment_id = serializers.UUIDField()
    note_type = serializers.ChoiceField(choices=ClinicalNote.NoteType.choices)
    subjective = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    objective = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    assessment = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    plan = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    supersedes_note_id = serializers.UUIDField(required=False, allow_null=True)
    signed_at = serializers.DateTimeField(required=False, allow_null=True)


class DiagnosisCodeDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosisCode
        fields = [
            "id",
            "coding_system",
            "code",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]


class DiagnosisCodeCreateSerializer(serializers.Serializer):
    coding_system = serializers.CharField(max_length=30)
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=250)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class DiagnosisCodeUpdateSerializer(DiagnosisCodeCreateSerializer):
    coding_system = serializers.CharField(required=False, max_length=30)
    code = serializers.CharField(required=False, max_length=50)
    name = serializers.CharField(required=False, max_length=250)
    is_active = serializers.BooleanField(required=False)


class EncounterDiagnosisDetailSerializer(serializers.ModelSerializer):
    diagnosis_code_value = serializers.CharField(source="diagnosis_code.code", read_only=True)
    diagnosis_code_name = serializers.CharField(source="diagnosis_code.name", read_only=True)

    class Meta:
        model = EncounterDiagnosis
        fields = [
            "id",
            "encounter",
            "diagnosis_code",
            "diagnosis_code_value",
            "diagnosis_code_name",
            "diagnosis_text",
            "diagnosis_type",
            "is_primary",
            "diagnosed_by_practitioner_facility_assignment",
            "diagnosed_at",
            "created_at",
        ]


class EncounterDiagnosisCreateSerializer(serializers.Serializer):
    encounter_id = serializers.UUIDField()
    diagnosis_code_id = serializers.UUIDField(required=False, allow_null=True)
    diagnosis_text = serializers.CharField(max_length=250)
    diagnosis_type = serializers.ChoiceField(choices=EncounterDiagnosis.DiagnosisType.choices)
    is_primary = serializers.BooleanField(required=False, default=False)
    diagnosed_by_practitioner_facility_assignment_id = serializers.UUIDField(
        required=False, allow_null=True
    )
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    diagnosed_at = serializers.DateTimeField(required=False, allow_null=True)
