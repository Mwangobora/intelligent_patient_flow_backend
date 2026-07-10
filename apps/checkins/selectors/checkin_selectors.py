from __future__ import annotations

from apps.checkins.models import PatientCheckin


def list_checkins(
    *,
    facility_id=None,
    patient_id=None,
    appointment_id=None,
    checked_in_from=None,
    checked_in_to=None,
    is_voided=None,
):
    queryset = PatientCheckin.objects.select_related(
        "facility",
        "patient",
        "appointment",
        "facility_specialty",
        "facility_specialty__specialty",
        "checked_in_by",
        "voided_by",
    )
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if patient_id:
        queryset = queryset.filter(patient_id=patient_id)
    if appointment_id:
        queryset = queryset.filter(appointment_id=appointment_id)
    if checked_in_from:
        queryset = queryset.filter(checked_in_at__gte=checked_in_from)
    if checked_in_to:
        queryset = queryset.filter(checked_in_at__lte=checked_in_to)
    if is_voided is not None:
        queryset = queryset.filter(voided_at__isnull=not is_voided)
    return queryset.order_by("-checked_in_at")


def get_checkin_by_id(checkin_id):
    return list_checkins().filter(pk=checkin_id).first()
