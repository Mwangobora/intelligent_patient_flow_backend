from __future__ import annotations

from apps.scheduling.models import PractitionerAvailabilityPeriod


def list_availability_periods(
    *,
    practitioner_facility_assignment_id=None,
    facility_id=None,
    practitioner_id=None,
    day_of_week=None,
    is_active: bool | None = None,
):
    queryset = PractitionerAvailabilityPeriod.objects.select_related(
        "practitioner_facility_assignment",
        "practitioner_facility_assignment__practitioner",
        "practitioner_facility_assignment__facility",
        "created_by",
    )
    if practitioner_facility_assignment_id:
        queryset = queryset.filter(practitioner_facility_assignment_id=practitioner_facility_assignment_id)
    if facility_id:
        queryset = queryset.filter(practitioner_facility_assignment__facility_id=facility_id)
    if practitioner_id:
        queryset = queryset.filter(practitioner_facility_assignment__practitioner_id=practitioner_id)
    if day_of_week:
        queryset = queryset.filter(day_of_week=day_of_week)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("practitioner_facility_assignment_id", "day_of_week", "starts_at")


def get_availability_period_by_id(availability_period_id):
    return list_availability_periods().filter(pk=availability_period_id).first()
