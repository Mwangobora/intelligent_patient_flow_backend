from __future__ import annotations

from django.db.models import Prefetch, Q

from apps.facilities.models import Facility, FacilityType


def list_facility_types(*, is_active: bool | None = None, search: str | None = None):
    queryset = FacilityType.objects.all()
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
    return queryset.order_by("name")


def get_facility_type_by_id(facility_type_id):
    return FacilityType.objects.filter(pk=facility_type_id).first()


def list_facilities(
    *,
    organization_id=None,
    facility_type_id=None,
    is_active: bool | None = None,
    search: str | None = None,
):
    queryset = Facility.objects.select_related("organization", "facility_type").prefetch_related(
        Prefetch("departments"),
        Prefetch("service_points"),
        Prefetch("consultation_rooms"),
        Prefetch("operating_hours"),
        Prefetch("schedule_exceptions"),
    )
    if organization_id:
        queryset = queryset.filter(organization_id=organization_id)
    if facility_type_id:
        queryset = queryset.filter(facility_type_id=facility_type_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
    return queryset.order_by("name")


def get_facility_by_id(facility_id):
    return (
        Facility.objects.select_related("organization", "facility_type")
        .prefetch_related(
            "departments",
            "facility_specialties__specialty",
            "service_points__service_point_type",
            "consultation_rooms",
            "operating_hours",
            "schedule_exceptions",
            "flow_settings",
        )
        .filter(pk=facility_id)
        .first()
    )
