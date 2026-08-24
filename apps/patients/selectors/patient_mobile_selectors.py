from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from apps.checkins.models import CheckinToken, PatientCheckin
from apps.facilities.models import FacilityFlowSetting
from apps.intelligence.selectors import get_latest_prediction_for_queue_entry
from apps.patients.models import Patient
from apps.queueing.models import QueueEntry
from apps.queueing.selectors import calculate_queue_position
from apps.queueing.services._shared import build_display_queue_number
from apps.scheduling.models import Appointment


PATIENT_CURRENT_QUEUE_STATUSES = {
    QueueEntry.Status.WAITING,
    QueueEntry.Status.CALLED,
    QueueEntry.Status.SKIPPED,
    QueueEntry.Status.IN_SERVICE,
    QueueEntry.Status.TRANSFERRED,
}

PATIENT_QUEUE_HISTORY_STATUSES = {
    QueueEntry.Status.COMPLETED,
    QueueEntry.Status.CANCELLED,
    QueueEntry.Status.SKIPPED,
    QueueEntry.Status.TRANSFERRED,
}


@dataclass(frozen=True)
class PatientCheckinEligibility:
    appointment: Appointment
    can_check_in: bool
    reason: str | None
    existing_checkin: PatientCheckin | None
    active_token: CheckinToken | None


def get_authenticated_patient(user) -> Patient | None:
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return None
    return (
        Patient.objects.select_related("organization", "registered_facility", "user")
        .filter(user=user, is_active=True)
        .order_by("created_at")
        .first()
    )


def get_patient_appointment(*, patient: Patient, appointment_id) -> Appointment | None:
    return (
        Appointment.objects.select_related(
            "facility",
            "facility__organization",
            "facility_specialty",
            "facility_specialty__specialty",
            "facility_specialty__department",
        )
        .filter(pk=appointment_id, patient=patient)
        .first()
    )


def get_active_checkin_for_appointment(*, appointment: Appointment) -> PatientCheckin | None:
    return (
        PatientCheckin.objects.select_related("facility", "facility_specialty", "facility_specialty__specialty")
        .filter(appointment=appointment, voided_at__isnull=True)
        .order_by("-checked_in_at")
        .first()
    )


def get_active_token_for_appointment(*, appointment: Appointment) -> CheckinToken | None:
    return (
        CheckinToken.objects.filter(
            appointment=appointment,
            used_at__isnull=True,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    )


def get_checkin_eligibility(*, patient: Patient, appointment_id) -> PatientCheckinEligibility | None:
    appointment = get_patient_appointment(patient=patient, appointment_id=appointment_id)
    if appointment is None:
        return None

    existing_checkin = get_active_checkin_for_appointment(appointment=appointment)
    active_token = get_active_token_for_appointment(appointment=appointment)
    reason = _checkin_block_reason(appointment=appointment, existing_checkin=existing_checkin)
    return PatientCheckinEligibility(
        appointment=appointment,
        can_check_in=reason is None,
        reason=reason,
        existing_checkin=existing_checkin,
        active_token=active_token,
    )


def get_next_checkin_eligibility_for_facility(*, patient: Patient, facility_id) -> PatientCheckinEligibility | None:
    appointments = (
        Appointment.objects.select_related(
            "facility",
            "facility__organization",
            "facility_specialty",
            "facility_specialty__specialty",
            "facility_specialty__department",
        )
        .filter(patient=patient, facility_id=facility_id)
        .exclude(
            status__in={
                Appointment.Status.CANCELLED,
                Appointment.Status.COMPLETED,
                Appointment.Status.NO_SHOW,
                Appointment.Status.RESCHEDULED,
            }
        )
        .order_by("scheduled_start")
    )

    fallback = None
    for appointment in appointments[:20]:
        existing_checkin = get_active_checkin_for_appointment(appointment=appointment)
        active_token = get_active_token_for_appointment(appointment=appointment)
        reason = _checkin_block_reason(appointment=appointment, existing_checkin=existing_checkin)
        eligibility = PatientCheckinEligibility(
            appointment=appointment,
            can_check_in=reason is None,
            reason=reason,
            existing_checkin=existing_checkin,
            active_token=active_token,
        )
        if eligibility.can_check_in:
            return eligibility
        fallback = fallback or eligibility
    return fallback


def checkin_block_reason(*, appointment: Appointment) -> str | None:
    return _checkin_block_reason(
        appointment=appointment,
        existing_checkin=get_active_checkin_for_appointment(appointment=appointment),
    )


def _checkin_block_reason(*, appointment: Appointment, existing_checkin: PatientCheckin | None) -> str | None:
    if existing_checkin is not None:
        return "already_checked_in"
    if appointment.status in {
        Appointment.Status.CANCELLED,
        Appointment.Status.COMPLETED,
        Appointment.Status.NO_SHOW,
        Appointment.Status.RESCHEDULED,
    }:
        return f"appointment_{appointment.status}"

    now = timezone.now()
    flow_settings = _get_flow_settings(appointment=appointment)
    early_minutes = flow_settings.early_checkin_minutes if flow_settings else 30
    late_minutes = flow_settings.late_checkin_grace_minutes if flow_settings else 15
    if now < appointment.scheduled_start - timezone.timedelta(minutes=early_minutes):
        return "too_early"
    if now > appointment.scheduled_end + timezone.timedelta(minutes=late_minutes):
        return "too_late"
    return None


def list_patient_queue_entries(*, patient: Patient, statuses: set[str] | None = None):
    queryset = QueueEntry.objects.select_related(
        "queue",
        "queue__service_point",
        "queue__service_point__service_point_type",
        "queue__service_point__facility",
        "patient_checkin",
        "patient_checkin__patient",
    ).filter(patient_checkin__patient=patient)
    if statuses is not None:
        queryset = queryset.filter(status__in=statuses)
    return queryset.order_by("-joined_at", "-created_at")


def get_current_patient_queue_entry(*, patient: Patient) -> QueueEntry | None:
    entries = list_patient_queue_entries(
        patient=patient,
        statuses=PATIENT_CURRENT_QUEUE_STATUSES,
    )
    return entries.order_by("-joined_at", "-created_at").first()


def build_patient_queue_payload(entry: QueueEntry | None) -> dict:
    if entry is None:
        return {
            "queue_entry_id": None,
            "queue_id": None,
            "queue_number": None,
            "queue_name": None,
            "service_point": None,
            "facility": None,
            "queue_status": None,
            "status": None,
            "priority_label": None,
            "estimated_wait_minutes": None,
            "people_ahead": None,
            "joined_at": None,
            "called_at": None,
            "service_started_at": None,
            "completed_at": None,
            "last_updated_at": timezone.now(),
        }

    prediction = get_latest_prediction_for_queue_entry(queue_entry_id=entry.id)
    queue_position = calculate_queue_position(entry=entry)
    people_ahead = max(queue_position - 1, 0) if queue_position is not None else None
    if people_ahead is None and entry.status in {QueueEntry.Status.CALLED, QueueEntry.Status.IN_SERVICE}:
        people_ahead = 0
    return {
        "queue_entry_id": entry.id,
        "queue_id": entry.queue_id,
        "queue_number": build_display_queue_number(queue=entry.queue, sequence_number=entry.sequence_number),
        "queue_name": entry.queue.service_point.name,
        "service_point": {
            "id": entry.queue.service_point_id,
            "name": entry.queue.service_point.name,
            "code": entry.queue.service_point.code,
            "type_name": entry.queue.service_point.service_point_type.name,
        },
        "facility": {
            "id": entry.queue.service_point.facility_id,
            "name": entry.queue.service_point.facility.name,
        },
        "queue_status": entry.queue.status,
        "status": entry.status,
        "priority_label": _priority_label(entry.priority_level),
        "estimated_wait_minutes": prediction.predicted_wait_minutes if prediction else None,
        "people_ahead": people_ahead,
        "joined_at": entry.joined_at,
        "called_at": entry.called_at,
        "service_started_at": entry.service_started_at,
        "completed_at": entry.service_completed_at,
        "last_updated_at": timezone.now(),
    }


def build_patient_queue_history_payload(entry: QueueEntry) -> dict:
    payload = build_patient_queue_payload(entry)
    payload["cancelled_at"] = entry.cancelled_at
    return payload


def _get_flow_settings(*, appointment: Appointment) -> FacilityFlowSetting | None:
    return FacilityFlowSetting.objects.filter(facility=appointment.facility).first()


def _priority_label(priority_level: int) -> str:
    return {
        1: "Priority",
        2: "Urgent",
        3: "Emergency",
    }.get(priority_level, "Normal")
