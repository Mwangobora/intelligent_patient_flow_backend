from __future__ import annotations

from django.db.models import Q

from apps.facilities.models import FacilitySpecialty, Specialty


def list_specialties(*, is_active: bool | None = None, search: str | None = None):
    queryset = Specialty.objects.select_related("parent_specialty")
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
    return queryset.order_by("name")


def get_specialty_by_id(specialty_id):
    return Specialty.objects.select_related("parent_specialty").filter(pk=specialty_id).first()


def list_facility_specialties(
    *,
    facility_id=None,
    specialty_id=None,
    department_id=None,
    is_active: bool | None = None,
):
    queryset = FacilitySpecialty.objects.select_related("facility", "specialty", "department")
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if specialty_id:
        queryset = queryset.filter(specialty_id=specialty_id)
    if department_id:
        queryset = queryset.filter(department_id=department_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("facility__name", "specialty__name")


def get_facility_specialty_by_id(facility_specialty_id):
    return FacilitySpecialty.objects.select_related("facility", "specialty", "department").filter(pk=facility_specialty_id).first()
