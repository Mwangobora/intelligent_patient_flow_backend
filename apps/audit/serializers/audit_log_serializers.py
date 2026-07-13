from __future__ import annotations

from rest_framework import serializers

from apps.audit.models import AuditLog
from apps.audit.services.audit_metadata_service import sanitize_audit_metadata


class SafeUserSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField(allow_null=True)
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)


class AuditLogCreateInputSerializer(serializers.Serializer):
    actor_user_id = serializers.UUIDField(required=False, allow_null=True)
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    facility_id = serializers.UUIDField(required=False, allow_null=True)
    action = serializers.CharField(max_length=50)
    resource_type = serializers.CharField(max_length=100)
    resource_id = serializers.UUIDField(required=False, allow_null=True)
    outcome = serializers.ChoiceField(choices=["success", "failure", "denied"], default="success")
    source = serializers.ChoiceField(choices=AuditLog.Source.choices, default=AuditLog.Source.ADMIN)
    request_id = serializers.UUIDField(required=False, allow_null=True)
    ip_address = serializers.IPAddressField(required=False, allow_null=True)
    user_agent = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=500)
    metadata = serializers.JSONField(required=False, allow_null=True)
    changes = serializers.JSONField(required=False, allow_null=True)
    occurred_at = serializers.DateTimeField(required=False, allow_null=True)


class AuditLogQueryInputSerializer(serializers.Serializer):
    actor_user_id = serializers.UUIDField(required=False)
    organization_id = serializers.UUIDField(required=False)
    facility_id = serializers.UUIDField(required=False)
    action = serializers.CharField(required=False)
    resource_type = serializers.CharField(required=False)
    resource_id = serializers.UUIDField(required=False)
    outcome = serializers.ChoiceField(required=False, choices=["success", "failure", "denied"])
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    search = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs.get("date_from") and attrs.get("date_to") and attrs["date_to"] < attrs["date_from"]:
            raise serializers.ValidationError("date_to must be greater than or equal to date_from.")
        return attrs


class AuditLogOutputSerializer(serializers.ModelSerializer):
    resource_type = serializers.CharField(source="entity_type", read_only=True)
    resource_id = serializers.UUIDField(source="entity_id", read_only=True)
    outcome = serializers.SerializerMethodField()
    method = serializers.SerializerMethodField()
    path = serializers.SerializerMethodField()
    status_code = serializers.SerializerMethodField()
    actor_user_summary = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    metadata = serializers.SerializerMethodField()
    changes = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor_user",
            "actor_user_summary",
            "organization",
            "organization_name",
            "facility",
            "facility_name",
            "action",
            "resource_type",
            "resource_id",
            "outcome",
            "source",
            "request_id",
            "ip_address",
            "user_agent",
            "method",
            "path",
            "status_code",
            "metadata",
            "changes",
            "occurred_at",
            "created_at",
        ]
        read_only_fields = fields

    def _metadata(self, obj):
        return sanitize_audit_metadata(obj.metadata or {})

    def get_metadata(self, obj):
        return self._metadata(obj)

    def get_changes(self, obj):
        return sanitize_audit_metadata(obj.changes or {})

    def get_outcome(self, obj):
        return self._metadata(obj).get("outcome")

    def get_method(self, obj):
        return self._metadata(obj).get("method")

    def get_path(self, obj):
        return self._metadata(obj).get("path")

    def get_status_code(self, obj):
        return self._metadata(obj).get("status_code")

    def get_actor_user_summary(self, obj):
        if not obj.actor_user_id:
            return None
        return {
            "id": obj.actor_user_id,
            "email": obj.actor_user.email,
            "first_name": obj.actor_user.first_name,
            "last_name": obj.actor_user.last_name,
        }


class AuditLogDetailOutputSerializer(AuditLogOutputSerializer):
    pass


class AuditSummaryOutputSerializer(serializers.Serializer):
    total_logs = serializers.IntegerField()
    success_count = serializers.IntegerField()
    failure_count = serializers.IntegerField()
    denied_count = serializers.IntegerField()
    top_actions = serializers.ListField(child=serializers.DictField())
    recent_critical_events = serializers.ListField(child=serializers.DictField())
    events_by_day = serializers.ListField(child=serializers.DictField())
