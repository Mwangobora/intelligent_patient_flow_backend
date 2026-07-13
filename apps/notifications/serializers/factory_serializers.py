from __future__ import annotations

from rest_framework import serializers

from apps.notifications.models import PatientNotification


class AppointmentNotificationFactoryInputSerializer(serializers.Serializer):
    appointment_id = serializers.UUIDField()
    channel = serializers.ChoiceField(required=False, choices=PatientNotification.Channel.choices, default=PatientNotification.Channel.IN_APP)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)


class QueueNotificationFactoryInputSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField()
    channel = serializers.ChoiceField(required=False, choices=PatientNotification.Channel.choices, default=PatientNotification.Channel.IN_APP)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)
