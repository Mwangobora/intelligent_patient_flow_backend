from __future__ import annotations

from rest_framework import serializers

from apps.queueing.models import Queue


class QueueCreateSerializer(serializers.Serializer):
    service_point_id = serializers.UUIDField()
    facility_specialty_id = serializers.UUIDField(required=False, allow_null=True)
    queue_date = serializers.DateField(required=False, allow_null=True)


class QueueStatusActionSerializer(serializers.Serializer):
    at = serializers.DateTimeField(required=False, allow_null=True)


class QueueOutputSerializer(serializers.ModelSerializer):
    service_point_name = serializers.CharField(source="service_point.name", read_only=True)
    service_point_code = serializers.CharField(source="service_point.code", read_only=True)
    facility = serializers.UUIDField(source="service_point.facility_id", read_only=True)
    facility_name = serializers.CharField(source="service_point.facility.name", read_only=True)
    specialty_name = serializers.CharField(source="facility_specialty.specialty.name", read_only=True)

    class Meta:
        model = Queue
        fields = [
            "id",
            "service_point",
            "service_point_name",
            "service_point_code",
            "facility",
            "facility_name",
            "facility_specialty",
            "specialty_name",
            "queue_date",
            "next_sequence_number",
            "status",
            "opened_at",
            "opened_by",
            "paused_at",
            "closed_at",
            "closed_by",
            "created_by",
            "created_at",
            "updated_at",
        ]
