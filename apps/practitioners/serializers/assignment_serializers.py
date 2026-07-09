from __future__ import annotations

from rest_framework import serializers

from apps.practitioners.models import (
    PractitionerDepartmentAssignment,
    PractitionerFacilityAssignment,
    PractitionerSpecialtyAssignment,
)


class PractitionerFacilityAssignmentDetailSerializer(serializers.ModelSerializer):
    practitioner_number = serializers.CharField(source="practitioner.practitioner_number", read_only=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True)

    class Meta:
        model = PractitionerFacilityAssignment
        fields = [
            "id",
            "practitioner",
            "practitioner_number",
            "facility",
            "facility_name",
            "starts_on",
            "ends_on",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]


class PractitionerFacilityAssignmentCreateSerializer(serializers.Serializer):
    practitioner_id = serializers.UUIDField(required=False)
    facility_id = serializers.UUIDField()
    starts_on = serializers.DateField()
    ends_on = serializers.DateField(required=False, allow_null=True)
    is_primary = serializers.BooleanField(required=False, default=False)


class PractitionerFacilityAssignmentUpdateSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField(required=False)
    starts_on = serializers.DateField(required=False)
    ends_on = serializers.DateField(required=False, allow_null=True)
    is_primary = serializers.BooleanField(required=False)


class PractitionerDepartmentAssignmentDetailSerializer(serializers.ModelSerializer):
    practitioner_number = serializers.CharField(source="practitioner_facility_assignment.practitioner.practitioner_number", read_only=True)
    facility_name = serializers.CharField(source="practitioner_facility_assignment.facility.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = PractitionerDepartmentAssignment
        fields = [
            "id",
            "practitioner_facility_assignment",
            "practitioner_number",
            "facility_name",
            "department",
            "department_name",
            "starts_on",
            "ends_on",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]


class PractitionerDepartmentAssignmentCreateSerializer(serializers.Serializer):
    practitioner_facility_assignment_id = serializers.UUIDField(required=False)
    department_id = serializers.UUIDField()
    starts_on = serializers.DateField()
    ends_on = serializers.DateField(required=False, allow_null=True)
    is_primary = serializers.BooleanField(required=False, default=False)


class PractitionerDepartmentAssignmentUpdateSerializer(serializers.Serializer):
    department_id = serializers.UUIDField(required=False)
    starts_on = serializers.DateField(required=False)
    ends_on = serializers.DateField(required=False, allow_null=True)
    is_primary = serializers.BooleanField(required=False)


class PractitionerSpecialtyAssignmentDetailSerializer(serializers.ModelSerializer):
    practitioner_number = serializers.CharField(source="practitioner_facility_assignment.practitioner.practitioner_number", read_only=True)
    facility_name = serializers.CharField(source="practitioner_facility_assignment.facility.name", read_only=True)
    specialty_name = serializers.CharField(source="facility_specialty.specialty.name", read_only=True)
    department_name = serializers.CharField(source="facility_specialty.department.name", read_only=True)

    class Meta:
        model = PractitionerSpecialtyAssignment
        fields = [
            "id",
            "practitioner_facility_assignment",
            "practitioner_number",
            "facility_name",
            "facility_specialty",
            "specialty_name",
            "department_name",
            "starts_on",
            "ends_on",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]


class PractitionerSpecialtyAssignmentCreateSerializer(serializers.Serializer):
    practitioner_facility_assignment_id = serializers.UUIDField(required=False)
    facility_specialty_id = serializers.UUIDField()
    starts_on = serializers.DateField()
    ends_on = serializers.DateField(required=False, allow_null=True)
    is_primary = serializers.BooleanField(required=False, default=False)


class PractitionerSpecialtyAssignmentUpdateSerializer(serializers.Serializer):
    facility_specialty_id = serializers.UUIDField(required=False)
    starts_on = serializers.DateField(required=False)
    ends_on = serializers.DateField(required=False, allow_null=True)
    is_primary = serializers.BooleanField(required=False)
