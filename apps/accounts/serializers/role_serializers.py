from __future__ import annotations

from rest_framework import serializers

from apps.accounts.models import Role, RolePermission, UserMembership, UserRoleAssignment


class BlankableUUIDField(serializers.UUIDField):
    def to_internal_value(self, data):
        if data == "":
            return None
        return super().to_internal_value(data)


class RolePermissionSummarySerializer(serializers.ModelSerializer):
    permission_code = serializers.CharField(source="permission.code", read_only=True)
    permission_name = serializers.CharField(source="permission.name", read_only=True)

    class Meta:
        model = RolePermission
        fields = ["id", "permission", "permission_code", "permission_name", "is_active"]


class RoleListSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "code",
            "description",
            "organization",
            "organization_name",
            "facility",
            "facility_name",
            "is_active",
        ]


class RoleDetailSerializer(RoleListSerializer):
    role_permissions = RolePermissionSummarySerializer(many=True, read_only=True)

    class Meta(RoleListSerializer.Meta):
        fields = RoleListSerializer.Meta.fields + ["role_permissions"]


class RoleCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    organization_id = BlankableUUIDField(required=False, allow_null=True)
    facility_id = BlankableUUIDField(required=False, allow_null=True)


class RoleUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    organization_id = BlankableUUIDField(required=False, allow_null=True)
    facility_id = BlankableUUIDField(required=False, allow_null=True)


class RolePermissionActionSerializer(serializers.Serializer):
    permission_id = serializers.UUIDField()


class OrganizationMembershipCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    organization_id = serializers.UUIDField()
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    created_by_id = serializers.UUIDField(required=False, allow_null=True)


class FacilityMembershipCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    organization_id = serializers.UUIDField()
    facility_id = serializers.UUIDField()
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    created_by_id = serializers.UUIDField(required=False, allow_null=True)


class EndMembershipSerializer(serializers.Serializer):
    ends_at = serializers.DateTimeField(required=False, allow_null=True)


class RoleAssignmentCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    role_id = serializers.UUIDField()
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    assigned_by_id = serializers.UUIDField(required=False, allow_null=True)


class RoleAssignmentReactivateSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField(required=False, allow_null=True)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    assigned_by_id = serializers.UUIDField(required=False, allow_null=True)


class MembershipSummarySerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True)

    class Meta:
        model = UserMembership
        fields = [
            "id",
            "user",
            "organization",
            "organization_name",
            "facility",
            "facility_name",
            "starts_at",
            "ends_at",
            "is_active",
        ]


class RoleAssignmentSummarySerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    role_code = serializers.CharField(source="role.code", read_only=True)

    class Meta:
        model = UserRoleAssignment
        fields = ["id", "user", "role", "role_name", "role_code", "starts_at", "ends_at", "is_active"]
