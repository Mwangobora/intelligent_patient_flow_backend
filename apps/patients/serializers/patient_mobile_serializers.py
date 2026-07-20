from __future__ import annotations

from rest_framework import serializers

from apps.checkins.serializers import CheckinOutputSerializer


class PatientAppointmentSummarySerializer(serializers.Serializer):
    appointment_id = serializers.UUIDField()
    appointment_number = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    facility = serializers.DictField()
    specialty = serializers.DictField(allow_null=True)
    department = serializers.DictField(allow_null=True)


class PatientCheckinEligibilityQuerySerializer(serializers.Serializer):
    appointment_id = serializers.UUIDField()


class PatientCheckinEligibilitySerializer(serializers.Serializer):
    appointment_id = serializers.UUIDField()
    can_check_in = serializers.BooleanField()
    reason = serializers.CharField(allow_null=True)
    appointment_status = serializers.CharField()
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    facility = serializers.DictField()
    specialty = serializers.DictField(allow_null=True)
    department = serializers.DictField(allow_null=True)
    existing_checkin = serializers.DictField(allow_null=True)
    has_active_token = serializers.BooleanField()
    token_expires_at = serializers.DateTimeField(allow_null=True)


class PatientAppointmentCheckinResponseSerializer(serializers.Serializer):
    checkin = serializers.DictField()
    queue_entry = serializers.DictField(allow_null=True)
    message = serializers.CharField()


class PatientQrTokenIssueResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    appointment_id = serializers.UUIDField()
    raw_token = serializers.CharField()
    expires_at = serializers.DateTimeField()


class PatientQrConsumeInputSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True, trim_whitespace=True)


class PatientQueueCurrentSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField(allow_null=True)
    queue_number = serializers.CharField(allow_null=True)
    queue_name = serializers.CharField(allow_null=True)
    service_point = serializers.DictField(allow_null=True)
    facility = serializers.DictField(allow_null=True)
    status = serializers.CharField(allow_null=True)
    priority_label = serializers.CharField(allow_null=True)
    estimated_wait_minutes = serializers.IntegerField(allow_null=True)
    people_ahead = serializers.IntegerField(allow_null=True)
    joined_at = serializers.DateTimeField(allow_null=True)
    called_at = serializers.DateTimeField(allow_null=True)
    service_started_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    last_updated_at = serializers.DateTimeField()


class PatientQueueHistorySerializer(PatientQueueCurrentSerializer):
    cancelled_at = serializers.DateTimeField(allow_null=True)


class PatientQueueHistoryResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = PatientQueueHistorySerializer(many=True)
