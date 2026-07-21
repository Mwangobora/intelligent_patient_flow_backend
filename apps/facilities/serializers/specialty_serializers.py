from __future__ import annotations

from rest_framework import serializers

from apps.facilities.models import FacilitySpecialty, Specialty


class SpecialtyListSerializer(serializers.ModelSerializer):
    parent_specialty_name = serializers.CharField(source="parent_specialty.name", read_only=True)

    class Meta:
        model = Specialty
        fields = ["id", "parent_specialty", "parent_specialty_name", "name", "code", "description", "is_active"]


class SpecialtyDetailSerializer(SpecialtyListSerializer):
    class Meta(SpecialtyListSerializer.Meta):
        fields = SpecialtyListSerializer.Meta.fields + ["created_at", "updated_at"]


class SpecialtyCreateSerializer(serializers.Serializer):
    parent_specialty_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class SpecialtyUpdateSerializer(SpecialtyCreateSerializer):
    name = serializers.CharField(required=False)


class FacilitySpecialtyDetailSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    specialty_name = serializers.CharField(source="specialty.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = FacilitySpecialty
        fields = [
            "id",
            "facility",
            "facility_name",
            "specialty",
            "specialty_name",
            "department",
            "department_name",
            "appointment_duration_minutes",
            "accepts_appointments",
            "accepts_walk_ins",
            "requires_referral",
            "is_active",
            "created_at",
            "updated_at",
        ]


class FacilitySpecialtyCreateSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    specialty_id = serializers.UUIDField()
    department_id = serializers.UUIDField(required=False, allow_null=True)
    appointment_duration_minutes = serializers.IntegerField()
    accepts_appointments = serializers.BooleanField(required=False, default=True)
    accepts_walk_ins = serializers.BooleanField(required=False, default=False)
    requires_referral = serializers.BooleanField(required=False, default=False)


class FacilitySpecialtyUpdateSerializer(FacilitySpecialtyCreateSerializer):
    facility_id = serializers.UUIDField(required=False)
    specialty_id = serializers.UUIDField(required=False)
    appointment_duration_minutes = serializers.IntegerField(required=False)
