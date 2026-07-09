from __future__ import annotations

from django.db.models import Q

from apps.facilities.models import Department


def list_departments(*, facility_id=None, is_active: bool | None = None, search: str | None = None):
    queryset = Department.objects.select_related("facility", "parent_department")
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
    return queryset.order_by("facility__name", "name")


def get_department_by_id(department_id):
    return Department.objects.select_related("facility", "parent_department").filter(pk=department_id).first()
