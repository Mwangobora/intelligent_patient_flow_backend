from __future__ import annotations

from apps.facilities.models import FacilityOperatingHour, FacilityScheduleException


def list_operating_hours(*, facility_id=None, day_of_week=None, is_active: bool | None = None):
    queryset = FacilityOperatingHour.objects.select_related("facility")
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if day_of_week:
        queryset = queryset.filter(day_of_week=day_of_week)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("facility__name", "day_of_week", "period_order")


def get_operating_hour_by_id(operating_hour_id):
    return FacilityOperatingHour.objects.select_related("facility").filter(pk=operating_hour_id).first()


def list_schedule_exceptions(*, facility_id=None, exception_date=None, is_active: bool | None = None):
    queryset = FacilityScheduleException.objects.select_related("facility")
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if exception_date:
        queryset = queryset.filter(exception_date=exception_date)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("facility__name", "exception_date", "period_order")


def get_schedule_exception_by_id(schedule_exception_id):
    return FacilityScheduleException.objects.select_related("facility").filter(pk=schedule_exception_id).first()
