from __future__ import annotations

from rest_framework import serializers

from apps.scheduling.models import PractitionerShift


class PractitionerShiftDetailSerializer(serializers.ModelSerializer):
    practitioner_number = serializers.CharField(
        source="practitioner_facility_assignment.practitioner.practitioner_number",
        read_only=True,
    )
    facility_name = serializers.CharField(source="practitioner_facility_assignment.facility.name", read_only=True)
    service_point_name = serializers.CharField(source="service_point.name", read_only=True)
    consultation_room_name = serializers.CharField(source="consultation_room.name", read_only=True)

    class Meta:
        model = PractitionerShift
        fields = [
            "id",
            "practitioner_facility_assignment",
            "practitioner_number",
            "facility_name",
            "practitioner_department_assignment",
            "service_point",
            "service_point_name",
            "consultation_room",
            "consultation_room_name",
            "starts_at",
            "ends_at",
            "actual_started_at",
            "actual_ended_at",
            "accepts_appointments",
            "status",
            "notes",
            "cancelled_by",
            "cancelled_at",
            "cancellation_reason",
            "created_at",
            "updated_at",
        ]


class PractitionerShiftCreateSerializer(serializers.Serializer):
    practitioner_facility_assignment_id = serializers.UUIDField()
    practitioner_department_assignment_id = serializers.UUIDField(required=False, allow_null=True)
    service_point_id = serializers.UUIDField(required=False, allow_null=True)
    consultation_room_id = serializers.UUIDField(required=False, allow_null=True)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    accepts_appointments = serializers.BooleanField(required=False, default=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PractitionerShiftUpdateSerializer(serializers.Serializer):
    practitioner_department_assignment_id = serializers.UUIDField(required=False, allow_null=True)
    service_point_id = serializers.UUIDField(required=False, allow_null=True)
    consultation_room_id = serializers.UUIDField(required=False, allow_null=True)
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False)
    accepts_appointments = serializers.BooleanField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ShiftCancellationSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField()


class GenerateSlotsSerializer(serializers.Serializer):
    facility_specialty_id = serializers.UUIDField()
    capacity = serializers.IntegerField(required=False, default=1)
    is_online_bookable = serializers.BooleanField(required=False, default=True)
