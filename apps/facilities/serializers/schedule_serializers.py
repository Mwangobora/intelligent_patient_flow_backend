from __future__ import annotations

from rest_framework import serializers

from apps.facilities.models import FacilityFlowSetting, FacilityOperatingHour, FacilityScheduleException


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
