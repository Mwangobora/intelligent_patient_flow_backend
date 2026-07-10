from __future__ import annotations

from apps.scheduling.models import AppointmentSlot


def list_appointment_slots(
    *,
    practitioner_shift_id=None,
    facility_id=None,
    practitioner_id=None,
    facility_specialty_id=None,
    starts_from=None,
    ends_to=None,
    status=None,
    only_available: bool = True,
):
    queryset = AppointmentSlot.objects.select_related(
        "practitioner_shift",
        "practitioner_shift__practitioner_facility_assignment",
        "practitioner_shift__practitioner_facility_assignment__practitioner",
        "practitioner_shift__practitioner_facility_assignment__facility",
        "facility_specialty",
        "facility_specialty__specialty",
        "facility_specialty__department",
    )
    if practitioner_shift_id:
        queryset = queryset.filter(practitioner_shift_id=practitioner_shift_id)
    if facility_id:
        queryset = queryset.filter(practitioner_shift__practitioner_facility_assignment__facility_id=facility_id)
    if practitioner_id:
        queryset = queryset.filter(practitioner_shift__practitioner_facility_assignment__practitioner_id=practitioner_id)
    if facility_specialty_id:
        queryset = queryset.filter(facility_specialty_id=facility_specialty_id)
    if starts_from:
        queryset = queryset.filter(starts_at__gte=starts_from)
    if ends_to:
        queryset = queryset.filter(ends_at__lte=ends_to)
    if status:
        queryset = queryset.filter(status=status)
    elif only_available:
        queryset = queryset.filter(status=AppointmentSlot.Status.AVAILABLE, is_online_bookable=True)
    return queryset.order_by("starts_at")


def get_appointment_slot_by_id(slot_id):
    return list_appointment_slots(only_available=False).filter(pk=slot_id).first()


def available_slots(*, facility_id=None, facility_specialty_id=None, starts_from=None, ends_to=None):
    return list_appointment_slots(
        facility_id=facility_id,
        facility_specialty_id=facility_specialty_id,
        starts_from=starts_from,
        ends_to=ends_to,
        only_available=True,
    )
