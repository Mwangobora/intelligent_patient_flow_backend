from __future__ import annotations

from django.db.models import Prefetch

from apps.scheduling.models import Appointment, AppointmentStatusHistory


def list_appointments(
    *,
    facility_id=None,
    patient_id=None,
    practitioner_id=None,
    practitioner_facility_assignment_id=None,
    facility_specialty_id=None,
    status=None,
    starts_from=None,
    ends_to=None,
):
    queryset = Appointment.objects.select_related(
        "facility",
        "patient",
        "facility_specialty",
        "facility_specialty__specialty",
        "practitioner_facility_assignment",
        "practitioner_facility_assignment__practitioner",
        "practitioner_specialty_assignment",
        "practitioner_shift",
        "appointment_slot",
        "rescheduled_from",
        "cancelled_by",
        "created_by",
    ).prefetch_related(
        Prefetch("status_history", queryset=AppointmentStatusHistory.objects.order_by("-changed_at"))
    )
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if patient_id:
        queryset = queryset.filter(patient_id=patient_id)
    if practitioner_id:
        queryset = queryset.filter(practitioner_facility_assignment__practitioner_id=practitioner_id)
    if practitioner_facility_assignment_id:
        queryset = queryset.filter(practitioner_facility_assignment_id=practitioner_facility_assignment_id)
    if facility_specialty_id:
        queryset = queryset.filter(facility_specialty_id=facility_specialty_id)
    if status:
        queryset = queryset.filter(status=status)
    if starts_from:
        queryset = queryset.filter(scheduled_start__gte=starts_from)
    if ends_to:
        queryset = queryset.filter(scheduled_end__lte=ends_to)
    return queryset.order_by("scheduled_start")


def get_appointment_by_id(appointment_id):
    return list_appointments().filter(pk=appointment_id).first()


def get_appointment_status_history(*, appointment_id):
    return AppointmentStatusHistory.objects.select_related("changed_by").filter(appointment_id=appointment_id).order_by("changed_at")


def patient_appointment_history(*, patient_id):
    return list_appointments(patient_id=patient_id)


def practitioner_daily_schedule(*, practitioner_id, starts_from, ends_to):
    return list_appointments(practitioner_id=practitioner_id, starts_from=starts_from, ends_to=ends_to)
