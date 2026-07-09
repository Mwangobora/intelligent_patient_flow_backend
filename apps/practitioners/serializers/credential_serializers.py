from __future__ import annotations

from rest_framework import serializers

from apps.practitioners.models import PractitionerCredential


class PractitionerCredentialDetailSerializer(serializers.ModelSerializer):
    practitioner_number = serializers.CharField(source="practitioner.practitioner_number", read_only=True)
    credential_type_name = serializers.CharField(source="credential_type.name", read_only=True)
    verified_by_email = serializers.CharField(source="verified_by.email", read_only=True)

    class Meta:
        model = PractitionerCredential
        fields = [
            "id",
            "practitioner",
            "practitioner_number",
            "credential_type",
            "credential_type_name",
            "last_four",
            "issuing_authority",
            "issuing_country_code",
            "issued_on",
            "expires_on",
            "verification_status",
            "verified_at",
            "verified_by",
            "verified_by_email",
            "is_active",
            "created_at",
            "updated_at",
        ]


class PractitionerCredentialCreateSerializer(serializers.Serializer):
    practitioner_id = serializers.UUIDField(required=False)
    credential_type_id = serializers.UUIDField()
    credential_number = serializers.CharField()
    issuing_authority = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    issuing_country_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    issued_on = serializers.DateField(required=False, allow_null=True)
    expires_on = serializers.DateField(required=False, allow_null=True)


class PractitionerCredentialUpdateSerializer(serializers.Serializer):
    credential_type_id = serializers.UUIDField(required=False)
    credential_number = serializers.CharField(required=False)
    issuing_authority = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    issuing_country_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    issued_on = serializers.DateField(required=False, allow_null=True)
    expires_on = serializers.DateField(required=False, allow_null=True)
