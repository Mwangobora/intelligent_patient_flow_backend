from __future__ import annotations

from rest_framework import serializers


class SlotSuggestionInputSerializer(serializers.Serializer):
    facility_specialty_id = serializers.UUIDField()
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    practitioner_id = serializers.UUIDField(required=False, allow_null=True)


class SlotSuggestionOutputSerializer(serializers.Serializer):
    appointment_slot_id = serializers.UUIDField()
    practitioner_shift_id = serializers.UUIDField()
    facility_specialty_id = serializers.UUIDField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    capacity = serializers.IntegerField()
    booked_count = serializers.IntegerField()
    booking_ratio = serializers.FloatField()
    historical_average_wait_minutes = serializers.FloatField(allow_null=True)
