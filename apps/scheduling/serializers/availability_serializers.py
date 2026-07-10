from __future__ import annotations

from rest_framework import serializers

from apps.scheduling.models import PractitionerAvailabilityPeriod


class AvailabilityPeriodDetailSerializer(serializers.ModelSerializer):
    practitioner_name = serializers.CharField(
        source="practitioner_facility_assignment.practitioner.last_name",
        read_only=True,
    )
    facility_name = serializers.CharField(source="practitioner_facility_assignment.facility.name", read_only=True)

    class Meta:
        model = PractitionerAvailabilityPeriod
        fields = [
            "id",
            "practitioner_facility_assignment",
            "practitioner_name",
            "facility_name",
            "day_of_week",
            "starts_at",
            "ends_at",
            "valid_from",
            "valid_until",
            "is_available_for_appointments",
            "is_active",
            "created_at",
            "updated_at",
        ]


class AvailabilityPeriodCreateSerializer(serializers.Serializer):
    practitioner_facility_assignment_id = serializers.UUIDField()
    day_of_week = serializers.IntegerField()
    starts_at = serializers.TimeField()
    ends_at = serializers.TimeField()
    valid_from = serializers.DateField()
    valid_until = serializers.DateField(required=False, allow_null=True)
    is_available_for_appointments = serializers.BooleanField(required=False, default=True)


class AvailabilityPeriodUpdateSerializer(serializers.Serializer):
    day_of_week = serializers.IntegerField(required=False)
    starts_at = serializers.TimeField(required=False)
    ends_at = serializers.TimeField(required=False)
    valid_from = serializers.DateField(required=False)
    valid_until = serializers.DateField(required=False, allow_null=True)
    is_available_for_appointments = serializers.BooleanField(required=False)
