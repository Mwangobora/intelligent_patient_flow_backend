from __future__ import annotations

from django.db.models import Q

from apps.facilities.models import ServicePoint, ServicePointType


def list_service_point_types(*, is_active: bool | None = None, search: str | None = None):
    queryset = ServicePointType.objects.all()
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
    return queryset.order_by("name")


def get_service_point_type_by_id(service_point_type_id):
    return ServicePointType.objects.filter(pk=service_point_type_id).first()


def list_service_points(*, facility_id=None, department_id=None, is_active: bool | None = None, search: str | None = None):
    queryset = ServicePoint.objects.select_related("facility", "department", "service_point_type")
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if department_id:
        queryset = queryset.filter(department_id=department_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
    return queryset.order_by("facility__name", "display_order", "name")


def get_service_point_by_id(service_point_id):
    return ServicePoint.objects.select_related("facility", "department", "service_point_type").filter(pk=service_point_id).first()
