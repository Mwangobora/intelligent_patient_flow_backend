from __future__ import annotations

from rest_framework import serializers

from apps.facilities.models import Department


class DepartmentListSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    parent_department_name = serializers.CharField(source="parent_department.name", read_only=True)

    class Meta:
        model = Department
        fields = [
            "id",
            "facility",
            "facility_name",
            "parent_department",
            "parent_department_name",
            "name",
            "code",
            "description",
            "is_active",
        ]


class DepartmentDetailSerializer(DepartmentListSerializer):
    class Meta(DepartmentListSerializer.Meta):
        fields = DepartmentListSerializer.Meta.fields + ["created_at", "updated_at"]


class DepartmentCreateSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    parent_department_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField()
    code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class DepartmentUpdateSerializer(DepartmentCreateSerializer):
    facility_id = serializers.UUIDField(required=False)
    name = serializers.CharField(required=False)
    regenerate_code = serializers.BooleanField(required=False, default=False)
