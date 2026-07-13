from __future__ import annotations

from rest_framework import serializers

from apps.reporting.models import ReportExport
from apps.reporting.services._shared import REPORT_TYPES


class ReportExportCreateInputSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    facility_id = serializers.UUIDField(required=False, allow_null=True)
    report_type = serializers.ChoiceField(choices=sorted(REPORT_TYPES))
    export_format = serializers.ChoiceField(choices=ReportExport.ExportFormat.choices)
    parameters = serializers.JSONField(required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_parameters(self, value):
        value = value or {}
        date_from = value.get("date_from")
        date_to = value.get("date_to")
        if date_from and date_to and str(date_to) < str(date_from):
            raise serializers.ValidationError("date_to must be greater than or equal to date_from.")
        blocked = {"patient_name", "first_name", "last_name", "phone", "phone_number", "email", "identifier", "value_hash", "encrypted"}
        if {str(key).lower() for key in value.keys()} & blocked:
            raise serializers.ValidationError("Parameters must not include plaintext sensitive patient information.")
        return value


class ReportExportOutputSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    file_available = serializers.SerializerMethodField()

    class Meta:
        model = ReportExport
        fields = [
            "id",
            "organization",
            "organization_name",
            "facility",
            "facility_name",
            "report_type",
            "export_format",
            "parameters",
            "status",
            "requested_by",
            "row_count",
            "generated_at",
            "expires_at",
            "failed_at",
            "failure_reason",
            "file_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_file_available(self, obj):
        return bool(obj.storage_key and obj.status == ReportExport.Status.COMPLETED)


class ReportDownloadMetadataOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    report_type = serializers.CharField()
    export_format = serializers.CharField()
    status = serializers.CharField()
    content_type = serializers.CharField()
    filename = serializers.CharField()


class AnalyticsQueryInputSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    facility_id = serializers.UUIDField(required=False, allow_null=True)
    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        if date_from and date_to and date_to < date_from:
            raise serializers.ValidationError("date_to must be greater than or equal to date_from.")
        return attrs


class ReportPreviewOutputSerializer(serializers.Serializer):
    rows = serializers.ListField(child=serializers.DictField(), read_only=True)
    row_count = serializers.IntegerField(read_only=True)
