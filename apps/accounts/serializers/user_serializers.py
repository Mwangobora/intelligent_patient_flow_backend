from __future__ import annotations

from rest_framework import serializers

from apps.accounts.models import User, UserMembership, UserRoleAssignment


class MembershipSummarySerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True)

    class Meta:
        model = UserMembership
        fields = [
            "id",
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
        fields = [
            "id",
            "role",
            "role_name",
            "role_code",
            "starts_at",
            "ends_at",
            "is_active",
        ]


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone_number",
            "first_name",
            "middle_name",
            "last_name",
            "is_active",
            "email_verified_at",
            "phone_verified_at",
            "date_joined",
        ]


class UserListSerializer(UserSummarySerializer):
    class Meta(UserSummarySerializer.Meta):
        fields = [
            "id",
            "email",
            "phone_number",
            "first_name",
            "middle_name",
            "last_name",
            "is_active",
        ]


class UserDetailSerializer(UserSummarySerializer):
    memberships = MembershipSummarySerializer(many=True, read_only=True)
    role_assignments = RoleAssignmentSummarySerializer(many=True, read_only=True)

    class Meta(UserSummarySerializer.Meta):
        fields = UserSummarySerializer.Meta.fields + ["memberships", "role_assignments"]


class UserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)
    first_name = serializers.CharField()
    middle_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    last_name = serializers.CharField()


class UserUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    first_name = serializers.CharField(required=False)
    middle_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    last_name = serializers.CharField(required=False)


class MeUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False)
    middle_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    last_name = serializers.CharField(required=False)
