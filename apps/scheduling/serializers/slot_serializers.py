from __future__ import annotations

from rest_framework import serializers

from apps.scheduling.models import AppointmentSlot


class AppointmentSlotDetailSerializer(serializers.ModelSerializer):
    practitioner_number = serializers.CharField(
        source="practitioner_shift.practitioner_facility_assignment.practitioner.practitioner_number",
        read_only=True,
    )
    specialty_name = serializers.CharField(source="facility_specialty.specialty.name", read_only=True)

    class Meta:
        model = AppointmentSlot
        fields = [
            "id",
            "practitioner_shift",
            "practitioner_number",
            "facility_specialty",
            "specialty_name",
            "starts_at",
            "ends_at",
            "capacity",
            "booked_count",
            "status",
            "is_online_bookable",
            "created_at",
            "updated_at",
        ]


class AppointmentSlotCreateSerializer(serializers.Serializer):
    practitioner_shift_id = serializers.UUIDField()
    facility_specialty_id = serializers.UUIDField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    capacity = serializers.IntegerField(required=False, default=1)
    is_online_bookable = serializers.BooleanField(required=False, default=True)
