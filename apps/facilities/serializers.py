from __future__ import annotations

from rest_framework import serializers

from apps.facilities.models import (
    ConsultationRoom,
    Department,
    Facility,
    FacilityFlowSetting,
    FacilityOperatingHour,
    FacilityScheduleException,
    FacilitySpecialty,
    FacilityType,
    Organization,
    ServicePoint,
    ServicePointType,
    Specialty,
)


class OrganizationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "legal_name", "code", "email", "phone_number", "registration_number", "is_active"]


class OrganizationDetailSerializer(OrganizationListSerializer):
    class Meta(OrganizationListSerializer.Meta):
        fields = OrganizationListSerializer.Meta.fields + ["created_at", "updated_at"]


class OrganizationCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    legal_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    registration_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class OrganizationUpdateSerializer(OrganizationCreateSerializer):
    name = serializers.CharField(required=False)


class FacilityTypeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacilityType
        fields = ["id", "name", "code", "description", "is_active"]


class FacilityTypeDetailSerializer(FacilityTypeListSerializer):
    class Meta(FacilityTypeListSerializer.Meta):
        fields = FacilityTypeListSerializer.Meta.fields + ["created_at", "updated_at"]


class FacilityTypeCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class FacilityTypeUpdateSerializer(FacilityTypeCreateSerializer):
    name = serializers.CharField(required=False)
    regenerate_code = serializers.BooleanField(required=False, default=False)


class FacilityListSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    facility_type_name = serializers.CharField(source="facility_type.name", read_only=True)

    class Meta:
        model = Facility
        fields = [
            "id",
            "organization",
            "organization_name",
            "facility_type",
            "facility_type_name",
            "name",
            "code",
            "timezone",
            "is_primary",
            "is_active",
        ]


class FacilityDetailSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    facility_type_name = serializers.CharField(source="facility_type.name", read_only=True)

    class Meta:
        model = Facility
        fields = [
            "id",
            "organization",
            "organization_name",
            "facility_type",
            "facility_type_name",
            "name",
            "code",
            "license_number",
            "email",
            "phone_number",
            "address_line1",
            "address_line2",
            "country_code",
            "region",
            "district",
            "ward",
            "postal_code",
            "latitude",
            "longitude",
            "timezone",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]


class FacilityCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    facility_type_id = serializers.UUIDField()
    name = serializers.CharField()
    code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    license_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address_line1 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address_line2 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    region = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    district = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ward = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    postal_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    latitude = serializers.DecimalField(required=False, allow_null=True, max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(required=False, allow_null=True, max_digits=10, decimal_places=7)
    timezone = serializers.CharField(required=False, default="Africa/Dar_es_Salaam")
    is_primary = serializers.BooleanField(required=False, default=False)


class FacilityUpdateSerializer(FacilityCreateSerializer):
    organization_id = serializers.UUIDField(required=False)
    facility_type_id = serializers.UUIDField(required=False)
    name = serializers.CharField(required=False)
    regenerate_code = serializers.BooleanField(required=False, default=False)


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


class SpecialtyListSerializer(serializers.ModelSerializer):
    parent_specialty_name = serializers.CharField(source="parent_specialty.name", read_only=True)

    class Meta:
        model = Specialty
        fields = ["id", "parent_specialty", "parent_specialty_name", "name", "code", "description", "is_active"]


class SpecialtyDetailSerializer(SpecialtyListSerializer):
    class Meta(SpecialtyListSerializer.Meta):
        fields = SpecialtyListSerializer.Meta.fields + ["created_at", "updated_at"]


class SpecialtyCreateSerializer(serializers.Serializer):
    parent_specialty_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField()
    code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class SpecialtyUpdateSerializer(SpecialtyCreateSerializer):
    name = serializers.CharField(required=False)
    regenerate_code = serializers.BooleanField(required=False, default=False)


class FacilitySpecialtyDetailSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    specialty_name = serializers.CharField(source="specialty.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = FacilitySpecialty
        fields = [
            "id",
            "facility",
            "facility_name",
            "specialty",
            "specialty_name",
            "department",
            "department_name",
            "appointment_duration_minutes",
            "accepts_appointments",
            "accepts_walk_ins",
            "requires_referral",
            "is_active",
            "created_at",
            "updated_at",
        ]


class FacilitySpecialtyCreateSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    specialty_id = serializers.UUIDField()
    department_id = serializers.UUIDField(required=False, allow_null=True)
    appointment_duration_minutes = serializers.IntegerField()
    accepts_appointments = serializers.BooleanField(required=False, default=True)
    accepts_walk_ins = serializers.BooleanField(required=False, default=False)
    requires_referral = serializers.BooleanField(required=False, default=False)


class FacilitySpecialtyUpdateSerializer(FacilitySpecialtyCreateSerializer):
    facility_id = serializers.UUIDField(required=False)
    specialty_id = serializers.UUIDField(required=False)
    appointment_duration_minutes = serializers.IntegerField(required=False)


class ServicePointTypeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePointType
        fields = ["id", "name", "code", "description", "is_active"]


class ServicePointTypeDetailSerializer(ServicePointTypeListSerializer):
    class Meta(ServicePointTypeListSerializer.Meta):
        fields = ServicePointTypeListSerializer.Meta.fields + ["created_at", "updated_at"]


class ServicePointTypeCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ServicePointTypeUpdateSerializer(ServicePointTypeCreateSerializer):
    name = serializers.CharField(required=False)
    regenerate_code = serializers.BooleanField(required=False, default=False)


class ServicePointDetailSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    service_point_type_name = serializers.CharField(source="service_point_type.name", read_only=True)

    class Meta:
        model = ServicePoint
        fields = [
            "id",
            "facility",
            "facility_name",
            "department",
            "department_name",
            "service_point_type",
            "service_point_type_name",
            "name",
            "code",
            "location_description",
            "floor",
            "display_order",
            "is_active",
            "created_at",
            "updated_at",
        ]


class ServicePointCreateSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    department_id = serializers.UUIDField(required=False, allow_null=True)
    service_point_type_id = serializers.UUIDField()
    name = serializers.CharField()
    code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    location_description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    floor = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    display_order = serializers.IntegerField(required=False, default=0)


class ServicePointUpdateSerializer(ServicePointCreateSerializer):
    facility_id = serializers.UUIDField(required=False)
    service_point_type_id = serializers.UUIDField(required=False)
    name = serializers.CharField(required=False)
    regenerate_code = serializers.BooleanField(required=False, default=False)


class ConsultationRoomDetailSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = ConsultationRoom
        fields = [
            "id",
            "facility",
            "facility_name",
            "department",
            "department_name",
            "name",
            "code",
            "location_description",
            "floor",
            "capacity",
            "is_active",
            "created_at",
            "updated_at",
        ]


class ConsultationRoomCreateSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    department_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField()
    code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    location_description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    floor = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    capacity = serializers.IntegerField(required=False, default=1)


class ConsultationRoomUpdateSerializer(ConsultationRoomCreateSerializer):
    facility_id = serializers.UUIDField(required=False)
    name = serializers.CharField(required=False)
    regenerate_code = serializers.BooleanField(required=False, default=False)


class FacilityOperatingHourDetailSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)

    class Meta:
        model = FacilityOperatingHour
        fields = [
            "id",
            "facility",
            "facility_name",
            "day_of_week",
            "period_order",
            "opens_at",
            "closes_at",
            "closes_next_day",
            "is_24_hours",
            "is_active",
            "created_at",
            "updated_at",
        ]


class FacilityOperatingHourCreateSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    day_of_week = serializers.IntegerField()
    period_order = serializers.IntegerField(required=False, default=1)
    opens_at = serializers.TimeField(required=False, allow_null=True)
    closes_at = serializers.TimeField(required=False, allow_null=True)
    closes_next_day = serializers.BooleanField(required=False, default=False)
    is_24_hours = serializers.BooleanField(required=False, default=False)


class FacilityOperatingHourUpdateSerializer(FacilityOperatingHourCreateSerializer):
    facility_id = serializers.UUIDField(required=False)
    day_of_week = serializers.IntegerField(required=False)
    period_order = serializers.IntegerField(required=False)


class FacilityScheduleExceptionDetailSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)

    class Meta:
        model = FacilityScheduleException
        fields = [
            "id",
            "facility",
            "facility_name",
            "exception_date",
            "period_order",
            "is_closed",
            "opens_at",
            "closes_at",
            "closes_next_day",
            "is_24_hours",
            "reason",
            "is_active",
            "created_at",
            "updated_at",
        ]


class FacilityScheduleExceptionCreateSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    exception_date = serializers.DateField()
    period_order = serializers.IntegerField(required=False, default=1)
    is_closed = serializers.BooleanField(required=False, default=False)
    opens_at = serializers.TimeField(required=False, allow_null=True)
    closes_at = serializers.TimeField(required=False, allow_null=True)
    closes_next_day = serializers.BooleanField(required=False, default=False)
    is_24_hours = serializers.BooleanField(required=False, default=False)
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class FacilityScheduleExceptionUpdateSerializer(FacilityScheduleExceptionCreateSerializer):
    facility_id = serializers.UUIDField(required=False)
    exception_date = serializers.DateField(required=False)
    period_order = serializers.IntegerField(required=False)


class FacilityFlowSettingDetailSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = FacilityFlowSetting
        fields = [
            "id",
            "facility",
            "facility_name",
            "max_advance_booking_days",
            "minimum_booking_notice_minutes",
            "cancellation_cutoff_minutes",
            "reschedule_cutoff_minutes",
            "early_checkin_minutes",
            "late_checkin_grace_minutes",
            "no_show_after_minutes",
            "default_reminder_minutes_before",
            "queue_number_padding",
            "auto_create_daily_queues",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        ]


class FacilityFlowSettingCreateSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    max_advance_booking_days = serializers.IntegerField(required=False, default=30)
    minimum_booking_notice_minutes = serializers.IntegerField(required=False, default=0)
    cancellation_cutoff_minutes = serializers.IntegerField(required=False, default=60)
    reschedule_cutoff_minutes = serializers.IntegerField(required=False, default=60)
    early_checkin_minutes = serializers.IntegerField(required=False, default=30)
    late_checkin_grace_minutes = serializers.IntegerField(required=False, default=15)
    no_show_after_minutes = serializers.IntegerField(required=False, default=15)
    default_reminder_minutes_before = serializers.IntegerField(required=False, allow_null=True, default=1440)
    queue_number_padding = serializers.IntegerField(required=False, default=3)
    auto_create_daily_queues = serializers.BooleanField(required=False, default=False)
    created_by_id = serializers.UUIDField(required=False, allow_null=True)


class FacilityFlowSettingUpdateSerializer(FacilityFlowSettingCreateSerializer):
    facility_id = serializers.UUIDField(required=False)
