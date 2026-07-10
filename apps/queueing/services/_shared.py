from __future__ import annotations

from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.accounts.models import User
from apps.checkins.models import PatientCheckin
from apps.facilities.models import FacilityFlowSetting, FacilitySpecialty, ServicePoint
from apps.queueing.models import Queue, QueueEntry
from apps.scheduling.models import PractitionerShift
from common.exceptions import NotFoundError, ValidationError

ACTIVE_QUEUE_ENTRY_STATUSES = {
    QueueEntry.Status.WAITING,
    QueueEntry.Status.CALLED,
    QueueEntry.Status.SKIPPED,
}

TERMINAL_QUEUE_ENTRY_STATUSES = {
    QueueEntry.Status.COMPLETED,
    QueueEntry.Status.CANCELLED,
    QueueEntry.Status.TRANSFERRED,
}


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def get_user(user_id, *, field_label: str = "User", active_only: bool = False, for_update: bool = False) -> User:
    queryset = User.objects.all()
    if for_update:
        queryset = queryset.select_for_update()
    if active_only:
        queryset = queryset.filter(is_active=True)
    user = queryset.filter(pk=user_id).first()
    if user is None:
        raise NotFoundError(f"{field_label} not found.")
    return user


def get_service_point(service_point_id, *, active_only: bool = False, for_update: bool = False) -> ServicePoint:
    queryset = ServicePoint.objects.select_related("facility", "department")
    if for_update:
        queryset = ServicePoint.objects.select_for_update().select_related("facility")
    if active_only:
        queryset = queryset.filter(is_active=True)
    service_point = queryset.filter(pk=service_point_id).first()
    if service_point is None:
        raise NotFoundError("Service point not found.")
    return service_point


def get_facility_specialty(facility_specialty_id, *, active_only: bool = False, for_update: bool = False) -> FacilitySpecialty:
    queryset = FacilitySpecialty.objects.select_related("facility", "department", "specialty")
    if for_update:
        queryset = FacilitySpecialty.objects.select_for_update().select_related("facility", "specialty")
    if active_only:
        queryset = queryset.filter(is_active=True)
    specialty = queryset.filter(pk=facility_specialty_id).first()
    if specialty is None:
        raise NotFoundError("Facility specialty not found.")
    return specialty


def get_queue(queue_id, *, for_update: bool = False) -> Queue:
    queryset = Queue.objects.select_related(
        "service_point",
        "service_point__facility",
        "service_point__department",
        "facility_specialty",
        "facility_specialty__specialty",
        "facility_specialty__department",
    )
    if for_update:
        queryset = Queue.objects.select_for_update().select_related("service_point", "service_point__facility")
    queue = queryset.filter(pk=queue_id).first()
    if queue is None:
        raise NotFoundError("Queue not found.")
    return queue


def get_patient_checkin(checkin_id, *, for_update: bool = False) -> PatientCheckin:
    queryset = PatientCheckin.objects.select_related(
        "facility",
        "patient",
        "appointment",
        "appointment__facility_specialty",
        "facility_specialty",
    )
    if for_update:
        queryset = PatientCheckin.objects.select_for_update().select_related("facility", "patient")
    checkin = queryset.filter(pk=checkin_id).first()
    if checkin is None:
        raise NotFoundError("Patient check-in not found.")
    return checkin


def get_queue_entry(entry_id, *, for_update: bool = False) -> QueueEntry:
    queryset = QueueEntry.objects.select_related(
        "queue",
        "queue__service_point",
        "queue__service_point__facility",
        "queue__facility_specialty",
        "patient_checkin",
        "patient_checkin__appointment",
        "practitioner_shift",
        "created_by",
        "cancelled_by",
    )
    if for_update:
        queryset = QueueEntry.objects.select_for_update().select_related("queue", "queue__service_point", "queue__service_point__facility", "patient_checkin")
    entry = queryset.filter(pk=entry_id).first()
    if entry is None:
        raise NotFoundError("Queue entry not found.")
    return entry


def get_practitioner_shift(shift_id, *, for_update: bool = False) -> PractitionerShift:
    queryset = PractitionerShift.objects.select_related(
        "practitioner_facility_assignment",
        "practitioner_facility_assignment__practitioner",
        "practitioner_facility_assignment__facility",
        "service_point",
    )
    if for_update:
        queryset = PractitionerShift.objects.select_for_update().select_related(
            "practitioner_facility_assignment",
            "practitioner_facility_assignment__practitioner",
            "practitioner_facility_assignment__facility",
        )
    shift = queryset.filter(pk=shift_id).first()
    if shift is None:
        raise NotFoundError("Practitioner shift not found.")
    return shift


def facility_local_date(facility) -> object:
    return timezone.now().astimezone(ZoneInfo(facility.timezone)).date()


def get_queue_number_padding(*, queue: Queue) -> int:
    settings = FacilityFlowSetting.objects.filter(facility_id=queue.service_point.facility_id).first()
    return settings.queue_number_padding if settings is not None else 3


def build_display_queue_number(*, queue: Queue, sequence_number: int) -> str:
    padding = get_queue_number_padding(queue=queue)
    return f"{queue.service_point.code}-{sequence_number:0{padding}d}"


def validate_service_point_specialty_scope(*, service_point: ServicePoint, facility_specialty: FacilitySpecialty | None) -> None:
    if facility_specialty is None:
        return
    if facility_specialty.facility_id != service_point.facility_id:
        raise ValidationError("Queue specialty must belong to the service-point facility.")
    if service_point.department_id and facility_specialty.department_id and service_point.department_id != facility_specialty.department_id:
        raise ValidationError("Queue service point and specialty departments must match.")


def validate_priority(*, priority_level: int, priority_reason: str | None) -> None:
    if priority_level < 0 or priority_level > 3:
        raise ValidationError("priority_level must be between 0 and 3.")
    if priority_level > 0 and normalize_optional_text(priority_reason) is None:
        raise ValidationError("priority_reason is required when priority_level is above 0.")


def checkin_specialty_id(checkin: PatientCheckin):
    if checkin.facility_specialty_id is not None:
        return checkin.facility_specialty_id
    if checkin.appointment_id is not None:
        return checkin.appointment.facility_specialty_id
    return None


def validate_checkin_for_queue(*, checkin: PatientCheckin, queue: Queue) -> None:
    if checkin.voided_at is not None:
        raise ValidationError("Voided check-in cannot enter a queue.")
    if checkin.facility_id != queue.service_point.facility_id:
        raise ValidationError("Check-in facility must match queue facility.")
    if queue.facility_specialty_id is not None and checkin_specialty_id(checkin) != queue.facility_specialty_id:
        raise ValidationError("Queue entry specialty does not match check-in or appointment specialty.")


def validate_practitioner_shift_for_queue(*, practitioner_shift: PractitionerShift, queue: Queue) -> None:
    if practitioner_shift.status == PractitionerShift.Status.CANCELLED:
        raise ValidationError("Practitioner shift must not be cancelled.")
    if not practitioner_shift.practitioner_facility_assignment.practitioner.is_active:
        raise ValidationError("Practitioner must be active.")
    if practitioner_shift.practitioner_facility_assignment.facility_id != queue.service_point.facility_id:
        raise ValidationError("Practitioner shift must belong to the queue facility.")
    if practitioner_shift.service_point_id is not None and practitioner_shift.service_point_id != queue.service_point_id:
        raise ValidationError("Practitioner shift service point must match the queue service point.")


def ensure_entry_can_transition(*, entry: QueueEntry, allowed_statuses: set[str], action: str) -> None:
    if entry.status not in allowed_statuses:
        raise ValidationError(f"Queue entry cannot be {action} from status {entry.status}.")
