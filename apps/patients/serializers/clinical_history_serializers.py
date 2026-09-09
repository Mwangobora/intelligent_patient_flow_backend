from __future__ import annotations

from rest_framework import serializers

from apps.patients.models import PatientAllergy, PatientCondition


class PatientAllergyDetailSerializer(serializers.ModelSerializer):
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)
    recorded_by_email = serializers.CharField(source="recorded_by.email", read_only=True)

    class Meta:
        model = PatientAllergy
        fields = [
            "id",
            "patient",
            "patient_number",
            "allergen",
            "allergy_type",
            "reaction",
            "severity",
            "status",
            "recorded_by",
            "recorded_by_email",
            "recorded_at",
            "resolved_at",
            "created_at",
            "updated_at",
        ]


class PatientAllergyCreateSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    allergen = serializers.CharField(max_length=150)
    allergy_type = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=50
    )
    reaction = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=250
    )
    severity = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=30
    )
    status = serializers.ChoiceField(
        choices=PatientAllergy.Status.choices, required=False, default=PatientAllergy.Status.ACTIVE
    )
    recorded_at = serializers.DateTimeField(required=False, allow_null=True)
    resolved_at = serializers.DateTimeField(required=False, allow_null=True)


class PatientAllergyUpdateSerializer(PatientAllergyCreateSerializer):
    patient_id = serializers.UUIDField(required=False)
    allergen = serializers.CharField(required=False, max_length=150)


class PatientConditionDetailSerializer(serializers.ModelSerializer):
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)
    diagnosis_code_value = serializers.CharField(source="diagnosis_code.code", read_only=True)
    diagnosis_code_name = serializers.CharField(source="diagnosis_code.name", read_only=True)
    recorded_by_email = serializers.CharField(source="recorded_by.email", read_only=True)

    class Meta:
        model = PatientCondition
        fields = [
            "id",
            "patient",
            "patient_number",
            "diagnosis_code",
            "diagnosis_code_value",
            "diagnosis_code_name",
            "condition_name",
            "status",
            "onset_date",
            "resolved_date",
            "recorded_by",
            "recorded_by_email",
            "created_at",
            "updated_at",
        ]


class PatientConditionCreateSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    diagnosis_code_id = serializers.UUIDField(required=False, allow_null=True)
    condition_name = serializers.CharField(max_length=200)
    status = serializers.ChoiceField(
        choices=PatientCondition.Status.choices,
        required=False,
        default=PatientCondition.Status.ACTIVE,
    )
    onset_date = serializers.DateField(required=False, allow_null=True)
    resolved_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PatientConditionUpdateSerializer(PatientConditionCreateSerializer):
    patient_id = serializers.UUIDField(required=False)
    condition_name = serializers.CharField(required=False, max_length=200)
