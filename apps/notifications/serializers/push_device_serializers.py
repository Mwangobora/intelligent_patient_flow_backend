from __future__ import annotations

from rest_framework import serializers

from apps.notifications.models import UserPushDevice


class PushDeviceRegisterInputSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    platform = serializers.ChoiceField(choices=UserPushDevice.Platform.choices)
    raw_token = serializers.CharField(write_only=True)
    device_name = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)
    app_version = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=30)


class PushDeviceRevokeInputSerializer(serializers.Serializer):
    pass


class PushDeviceOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPushDevice
        fields = [
            "id",
            "user",
            "platform",
            "device_name",
            "app_version",
            "last_seen_at",
            "is_active",
            "revoked_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
