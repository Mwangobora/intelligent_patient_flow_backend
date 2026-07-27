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
    profile_picture_url = serializers.SerializerMethodField()

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
            "profile_picture_url",
            "email_verified_at",
            "phone_verified_at",
            "date_joined",
        ]

    def get_profile_picture_url(self, obj):
        if not obj.profile_picture:
            return None
        request = self.context.get("request")
        url = obj.profile_picture.url
        return request.build_absolute_uri(url) if request else url


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


class CurrentUserSerializer(UserSummarySerializer):
    has_global_access = serializers.SerializerMethodField()
    linked_patient_id = serializers.SerializerMethodField()
    patient_summary = serializers.SerializerMethodField()
    memberships = MembershipSummarySerializer(many=True, read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta(UserSummarySerializer.Meta):
        fields = UserSummarySerializer.Meta.fields + [
            "has_global_access",
            "linked_patient_id",
            "patient_summary",
            "memberships",
            "permissions",
        ]

    def get_has_global_access(self, obj):
        return bool(obj.is_superuser)

    def get_linked_patient_id(self, obj):
        patient = self._get_linked_patient(obj)
        return str(patient.id) if patient else None

    def get_patient_summary(self, obj):
        patient = self._get_linked_patient(obj)
        if patient is None:
            return None
        return {
            "id": patient.id,
            "patient_number": patient.patient_number,
            "first_name": patient.first_name,
            "middle_name": patient.middle_name,
            "last_name": patient.last_name,
            "registered_facility": patient.registered_facility_id,
            "registered_facility_name": patient.registered_facility.name if patient.registered_facility else None,
            "organization": patient.organization_id,
            "organization_name": patient.organization.name,
            "is_active": patient.is_active,
        }

    def _get_linked_patient(self, obj):
        if hasattr(obj, "_current_serializer_patient"):
            return obj._current_serializer_patient

        from apps.patients.models import Patient

        patient = (
            Patient.objects.select_related("organization", "registered_facility")
            .filter(user=obj, is_active=True)
            .order_by("created_at")
            .first()
        )
        obj._current_serializer_patient = patient
        return patient

    def get_permissions(self, obj):
        from apps.accounts.selectors.permission_selectors import get_user_effective_permissions

        return list(get_user_effective_permissions(user=obj).values_list("code", flat=True))


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
    profile_picture = serializers.FileField(required=False, allow_null=True)

    def validate_profile_picture(self, value):
        if value is None:
            return value
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("Profile picture must be 2 MB or smaller.")
        content_type = getattr(value, "content_type", "")
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise serializers.ValidationError("Upload a JPEG, PNG, or WebP image.")
        return value
