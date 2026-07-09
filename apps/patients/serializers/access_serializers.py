from __future__ import annotations

from rest_framework import serializers

from apps.patients.models import PatientAccessGrant


class PatientAccessGrantDetailSerializer(serializers.ModelSerializer):
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)
    grantee_user_email = serializers.CharField(source="grantee_user.email", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    related_person_name = serializers.SerializerMethodField()
    granted_by_email = serializers.CharField(source="granted_by.email", read_only=True)
    revoked_by_email = serializers.CharField(source="revoked_by.email", read_only=True)

    class Meta:
        model = PatientAccessGrant
        fields = [
            "id",
            "patient",
            "patient_number",
            "related_person",
            "related_person_name",
            "grantee_user",
            "grantee_user_email",
            "role",
            "role_name",
            "granted_by",
            "granted_by_email",
            "starts_at",
            "ends_at",
            "is_active",
            "revoked_at",
            "revoked_by",
            "revoked_by_email",
            "revocation_reason",
            "created_at",
            "updated_at",
        ]

    def get_related_person_name(self, obj) -> str:
        names = [obj.related_person.first_name, obj.related_person.middle_name, obj.related_person.last_name]
        return " ".join(name for name in names if name).strip()


class PatientAccessGrantCreateSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField(required=False)
    related_person_id = serializers.UUIDField()
    grantee_user_id = serializers.UUIDField()
    role_id = serializers.UUIDField()
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)


class PatientAccessGrantRevokeSerializer(serializers.Serializer):
    revoked_reason = serializers.CharField()


class PatientAccessGrantReactivateSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
