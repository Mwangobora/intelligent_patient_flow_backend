from __future__ import annotations

from rest_framework import serializers

from apps.accounts.models import Permission


class PermissionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "name", "code", "module", "action", "description", "is_active"]


class PermissionDetailSerializer(PermissionListSerializer):
    pass


class PermissionCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    module = serializers.CharField()
    action = serializers.CharField()
    code = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class PermissionUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    module = serializers.CharField(required=False)
    action = serializers.CharField(required=False)
    code = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    regenerate_code = serializers.BooleanField(required=False, default=False)
