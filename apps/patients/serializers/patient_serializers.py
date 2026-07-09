from __future__ import annotations

from rest_framework import serializers

from apps.patients.models import Patient


class PatientListSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    registered_facility_name = serializers.CharField(source="registered_facility.name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id",
            "organization",
            "organization_name",
            "user",
            "user_email",
            "registered_facility",
            "registered_facility_name",
            "patient_number",
            "first_name",
            "middle_name",
            "last_name",
            "date_of_birth",
            "date_of_birth_is_estimated",
            "sex_code",
            "email",
            "phone_number",
            "is_active",
        ]


class PatientDetailSerializer(PatientListSerializer):
    class Meta(PatientListSerializer.Meta):
        fields = PatientListSerializer.Meta.fields + ["created_at", "updated_at"]


class PatientCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    user_id = serializers.UUIDField(required=False, allow_null=True)
    registered_facility_id = serializers.UUIDField(required=False, allow_null=True)
    first_name = serializers.CharField()
    middle_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    last_name = serializers.CharField()
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    date_of_birth_is_estimated = serializers.BooleanField(required=False, default=False)
    sex_code = serializers.ChoiceField(required=False, allow_null=True, choices=Patient.SexCode.choices)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PatientUpdateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField(required=False, allow_null=True)
    registered_facility_id = serializers.UUIDField(required=False, allow_null=True)
    first_name = serializers.CharField(required=False)
    middle_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    last_name = serializers.CharField(required=False)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    date_of_birth_is_estimated = serializers.BooleanField(required=False)
    sex_code = serializers.ChoiceField(required=False, allow_null=True, choices=Patient.SexCode.choices)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
