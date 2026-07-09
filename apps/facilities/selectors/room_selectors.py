from __future__ import annotations

from django.db.models import Q

from apps.facilities.models import ConsultationRoom


def list_consultation_rooms(*, facility_id=None, department_id=None, is_active: bool | None = None, search: str | None = None):
    queryset = ConsultationRoom.objects.select_related("facility", "department")
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if department_id:
        queryset = queryset.filter(department_id=department_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
    return queryset.order_by("facility__name", "name")


def get_consultation_room_by_id(room_id):
    return ConsultationRoom.objects.select_related("facility", "department").filter(pk=room_id).first()
