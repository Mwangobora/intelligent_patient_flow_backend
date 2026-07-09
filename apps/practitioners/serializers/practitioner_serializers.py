from __future__ import annotations

from rest_framework import serializers

from apps.practitioners.models import Practitioner


class PractitionerListSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    practitioner_type_name = serializers.CharField(source="practitioner_type.name", read_only=True)

    class Meta:
        model = Practitioner
        fields = [
            "id",
            "organization",
            "organization_name",
            "user",
            "user_email",
            "practitioner_type",
            "practitioner_type_name",
            "practitioner_number",
            "first_name",
            "middle_name",
            "last_name",
            "preferred_name",
            "email",
            "phone_number",
            "is_active",
        ]


class PractitionerDetailSerializer(PractitionerListSerializer):
    class Meta(PractitionerListSerializer.Meta):
        fields = PractitionerListSerializer.Meta.fields + ["created_at", "updated_at"]


class PractitionerCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    practitioner_type_id = serializers.UUIDField()
    user_id = serializers.UUIDField(required=False, allow_null=True)
    first_name = serializers.CharField()
    middle_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    last_name = serializers.CharField()
    preferred_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PractitionerUpdateSerializer(serializers.Serializer):
    practitioner_type_id = serializers.UUIDField(required=False)
    user_id = serializers.UUIDField(required=False, allow_null=True)
    first_name = serializers.CharField(required=False)
    middle_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    last_name = serializers.CharField(required=False)
    preferred_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
