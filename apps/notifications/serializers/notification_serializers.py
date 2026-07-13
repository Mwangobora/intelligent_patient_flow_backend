from __future__ import annotations

from rest_framework import serializers

from apps.notifications.models import PatientNotification


class PatientNotificationCreateInputSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    appointment_id = serializers.UUIDField(required=False, allow_null=True)
    queue_entry_id = serializers.UUIDField(required=False, allow_null=True)
    notification_type = serializers.ChoiceField(choices=PatientNotification.NotificationType.choices)
    channel = serializers.ChoiceField(choices=PatientNotification.Channel.choices)
    recipient_user_id = serializers.UUIDField(required=False, allow_null=True)
    destination = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    subject = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    body = serializers.CharField()
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)


class NotificationCancelInputSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=250)


class MarkReadInputSerializer(serializers.Serializer):
    read_at = serializers.DateTimeField(required=False, allow_null=True)


class PatientNotificationOutputSerializer(serializers.ModelSerializer):
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)

    class Meta:
        model = PatientNotification
        fields = [
            "id",
            "patient",
            "patient_number",
            "appointment",
            "queue_entry",
            "notification_type",
            "channel",
            "recipient_user",
            "scheduled_for",
            "status",
            "attempt_count",
            "last_attempt_at",
            "sent_at",
            "delivered_at",
            "read_at",
            "failed_at",
            "failure_reason",
            "provider_message_id",
            "idempotency_key",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class NotificationDeliveryStatusOutputSerializer(PatientNotificationOutputSerializer):
    pass
