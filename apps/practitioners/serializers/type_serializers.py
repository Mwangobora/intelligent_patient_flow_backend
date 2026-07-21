from __future__ import annotations

from rest_framework import serializers

from apps.practitioners.models import PractitionerCredentialType, PractitionerType


class PractitionerTypeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PractitionerType
        fields = ["id", "name", "code", "description", "requires_license", "is_active"]


class PractitionerTypeDetailSerializer(PractitionerTypeListSerializer):
    class Meta(PractitionerTypeListSerializer.Meta):
        fields = PractitionerTypeListSerializer.Meta.fields + ["created_at", "updated_at"]


class PractitionerTypeCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    requires_license = serializers.BooleanField(required=False, default=False)


class PractitionerTypeUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    requires_license = serializers.BooleanField(required=False)


class PractitionerCredentialTypeListSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = PractitionerCredentialType
        fields = [
            "id",
            "organization",
            "organization_name",
            "name",
            "code",
            "description",
            "country_code",
            "requires_expiry_date",
            "requires_verification",
            "is_active",
        ]


class PractitionerCredentialTypeDetailSerializer(PractitionerCredentialTypeListSerializer):
    class Meta(PractitionerCredentialTypeListSerializer.Meta):
        fields = PractitionerCredentialTypeListSerializer.Meta.fields + ["created_at", "updated_at"]


class PractitionerCredentialTypeCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    requires_expiry_date = serializers.BooleanField(required=False, default=False)
    requires_verification = serializers.BooleanField(required=False, default=True)


class PractitionerCredentialTypeUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    requires_expiry_date = serializers.BooleanField(required=False)
    requires_verification = serializers.BooleanField(required=False)
