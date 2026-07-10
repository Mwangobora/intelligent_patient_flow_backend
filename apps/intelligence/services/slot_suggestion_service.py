from __future__ import annotations

from django.db.models import F
from django.utils import timezone

from apps.queueing.models import QueueEntry
from apps.scheduling.models import AppointmentSlot, PractitionerShift
from common.exceptions import ValidationError

from ._shared import SlotSuggestion


def _historical_average_wait_by_service_point(*, facility_specialty_id):
    entries = QueueEntry.objects.filter(
        queue__facility_specialty_id=facility_specialty_id,
        service_started_at__isnull=False,
    ).select_related("queue", "queue__service_point")

    totals: dict[object, list[int]] = {}
    for entry in entries:
        wait_minutes = max(int(round((entry.service_started_at - entry.joined_at).total_seconds() / 60)), 0)
        totals.setdefault(entry.queue.service_point_id, []).append(wait_minutes)
    return {service_point_id: sum(values) / len(values) for service_point_id, values in totals.items() if values}


def suggest_optimal_appointment_slots(*, facility_specialty_id, date_from, date_to, practitioner_id=None) -> list[SlotSuggestion]:
    if date_to and date_from and date_to < date_from:
        raise ValidationError("date_to must be greater than or equal to date_from.")

    queryset = AppointmentSlot.objects.select_related(
        "practitioner_shift",
        "practitioner_shift__practitioner_facility_assignment",
        "practitioner_shift__practitioner_facility_assignment__practitioner",
        "practitioner_shift__service_point",
        "facility_specialty",
    ).filter(
        facility_specialty_id=facility_specialty_id,
        status=AppointmentSlot.Status.AVAILABLE,
        is_online_bookable=True,
        booked_count__lt=F("capacity"),
        starts_at__gt=timezone.now(),
        practitioner_shift__status__in=[PractitionerShift.Status.SCHEDULED, PractitionerShift.Status.IN_PROGRESS],
        practitioner_shift__accepts_appointments=True,
    )
    if date_from:
        queryset = queryset.filter(starts_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(starts_at__date__lte=date_to)
    if practitioner_id:
        queryset = queryset.filter(practitioner_shift__practitioner_facility_assignment__practitioner_id=practitioner_id)

    historical_waits = _historical_average_wait_by_service_point(facility_specialty_id=facility_specialty_id)
    suggestions = []
    for slot in queryset:
        booking_ratio = slot.booked_count / slot.capacity if slot.capacity else 1
        service_point_id = slot.practitioner_shift.service_point_id
        historical_wait = historical_waits.get(service_point_id)
        wait_rank = historical_wait if historical_wait is not None else float("inf")
        suggestions.append(
            SlotSuggestion(
                appointment_slot_id=slot.id,
                practitioner_shift_id=slot.practitioner_shift_id,
                facility_specialty_id=slot.facility_specialty_id,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                capacity=slot.capacity,
                booked_count=slot.booked_count,
                booking_ratio=round(booking_ratio, 4),
                historical_average_wait_minutes=round(historical_wait, 2) if historical_wait is not None else None,
                score_rank=(wait_rank, booking_ratio, slot.starts_at),
            )
        )
    return sorted(suggestions, key=lambda suggestion: suggestion.score_rank)
