from __future__ import annotations

from rest_framework import serializers

from apps.queueing.models import QueueEntry
from apps.queueing.selectors import calculate_queue_position
from apps.queueing.services._shared import build_display_queue_number


class QueueEntryCreateSerializer(serializers.Serializer):
    queue_id = serializers.UUIDField()
    patient_checkin_id = serializers.UUIDField()
    practitioner_shift_id = serializers.UUIDField(required=False, allow_null=True)
    priority_level = serializers.IntegerField(required=False, default=0, min_value=0, max_value=3)
    priority_reason = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=250)
    joined_at = serializers.DateTimeField(required=False, allow_null=True)


class QueueEntryPrioritySerializer(serializers.Serializer):
    priority_level = serializers.IntegerField(min_value=0, max_value=3)
    priority_reason = serializers.CharField(max_length=250)


class QueueEntryCancelSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(max_length=250)
    cancelled_at = serializers.DateTimeField(required=False, allow_null=True)


class QueueEntryActionSerializer(serializers.Serializer):
    at = serializers.DateTimeField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=250)


class QueueEntryOutputSerializer(serializers.ModelSerializer):
    queue_status = serializers.CharField(source="queue.status", read_only=True)
    service_point_code = serializers.CharField(source="queue.service_point.code", read_only=True)
    service_point_name = serializers.CharField(source="queue.service_point.name", read_only=True)
    facility = serializers.UUIDField(source="queue.service_point.facility_id", read_only=True)
    display_queue_number = serializers.SerializerMethodField()
    queue_position = serializers.SerializerMethodField()
    patient_number = serializers.CharField(source="patient_checkin.patient.patient_number", read_only=True)
    patient_name = serializers.SerializerMethodField()
    appointment = serializers.UUIDField(source="patient_checkin.appointment_id", read_only=True)

    class Meta:
        model = QueueEntry
        fields = [
            "id",
            "queue",
            "queue_status",
            "service_point_code",
            "service_point_name",
            "facility",
            "patient_checkin",
            "patient_number",
            "patient_name",
            "appointment",
            "practitioner_shift",
            "sequence_number",
            "display_queue_number",
            "queue_position",
            "priority_level",
            "priority_reason",
            "status",
            "joined_at",
            "called_at",
            "service_started_at",
            "service_completed_at",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_display_queue_number(self, obj):
        return build_display_queue_number(queue=obj.queue, sequence_number=obj.sequence_number)

    def get_queue_position(self, obj):
        return calculate_queue_position(entry=obj)

    def get_patient_name(self, obj):
        patient = obj.patient_checkin.patient
        return " ".join(part for part in [patient.first_name, patient.last_name] if part)
