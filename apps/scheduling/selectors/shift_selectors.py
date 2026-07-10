from __future__ import annotations

from django.db.models import Prefetch

from apps.scheduling.models import AppointmentSlot, PractitionerShift


def list_shifts(
    *,
    practitioner_facility_assignment_id=None,
    practitioner_id=None,
    facility_id=None,
    department_assignment_id=None,
    service_point_id=None,
    consultation_room_id=None,
    status=None,
    starts_from=None,
    ends_to=None,
):
    queryset = PractitionerShift.objects.select_related(
        "practitioner_facility_assignment",
        "practitioner_facility_assignment__practitioner",
        "practitioner_facility_assignment__facility",
        "practitioner_department_assignment",
        "practitioner_department_assignment__department",
        "service_point",
        "consultation_room",
        "created_by",
        "cancelled_by",
    ).prefetch_related(
        Prefetch("appointment_slots", queryset=AppointmentSlot.objects.order_by("starts_at"))
    )
    if practitioner_facility_assignment_id:
        queryset = queryset.filter(practitioner_facility_assignment_id=practitioner_facility_assignment_id)
    if practitioner_id:
        queryset = queryset.filter(practitioner_facility_assignment__practitioner_id=practitioner_id)
    if facility_id:
        queryset = queryset.filter(practitioner_facility_assignment__facility_id=facility_id)
    if department_assignment_id:
        queryset = queryset.filter(practitioner_department_assignment_id=department_assignment_id)
    if service_point_id:
        queryset = queryset.filter(service_point_id=service_point_id)
    if consultation_room_id:
        queryset = queryset.filter(consultation_room_id=consultation_room_id)
    if status:
        queryset = queryset.filter(status=status)
    if starts_from:
        queryset = queryset.filter(starts_at__gte=starts_from)
    if ends_to:
        queryset = queryset.filter(ends_at__lte=ends_to)
    return queryset.order_by("starts_at")


def get_shift_by_id(shift_id):
    return list_shifts().filter(pk=shift_id).first()


def practitioner_daily_schedule(*, practitioner_id, day_start, day_end):
    return list_shifts(
        practitioner_id=practitioner_id,
        starts_from=day_start,
        ends_to=day_end,
    )
