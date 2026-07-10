from __future__ import annotations

from rest_framework import serializers

from apps.checkins.models import CheckinToken


class IssueCheckinTokenInputSerializer(serializers.Serializer):
    appointment_id = serializers.UUIDField()
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class ConsumeCheckinTokenInputSerializer(serializers.Serializer):
    raw_token = serializers.CharField(write_only=True)
    checked_in_at = serializers.DateTimeField(required=False, allow_null=True)
    checked_in_by_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=250)


class RevokeCheckinTokenInputSerializer(serializers.Serializer):
    revocation_reason = serializers.CharField(max_length=250)
    revoked_at = serializers.DateTimeField(required=False, allow_null=True)


class CheckinTokenSafeOutputSerializer(serializers.ModelSerializer):
    appointment_number = serializers.CharField(source="appointment.appointment_number", read_only=True)
    patient_number = serializers.CharField(source="appointment.patient.patient_number", read_only=True)
    facility_name = serializers.CharField(source="appointment.facility.name", read_only=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = CheckinToken
        fields = [
            "id",
            "appointment",
            "appointment_number",
            "patient_number",
            "facility_name",
            "expires_at",
            "used_at",
            "patient_checkin",
            "revoked_at",
            "revoked_by",
            "revocation_reason",
            "created_by",
            "created_at",
            "is_active",
        ]

    def get_is_active(self, obj):
        return obj.used_at is None and obj.revoked_at is None


class IssuedCheckinTokenOutputSerializer(CheckinTokenSafeOutputSerializer):
    raw_token = serializers.CharField(read_only=True)

    class Meta(CheckinTokenSafeOutputSerializer.Meta):
        fields = CheckinTokenSafeOutputSerializer.Meta.fields + ["raw_token"]
