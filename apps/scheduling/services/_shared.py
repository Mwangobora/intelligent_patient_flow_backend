from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db.models import Prefetch, Q
from django.utils import timezone

from apps.facilities.models import (
    ConsultationRoom,
    Facility,
    FacilityFlowSetting,
    FacilityOperatingHour,
    FacilityScheduleException,
    FacilitySpecialty,
    ServicePoint,
)
from apps.patients.models import Patient
from apps.practitioners.models import (
    PractitionerDepartmentAssignment,
    PractitionerFacilityAssignment,
    PractitionerSpecialtyAssignment,
)
from apps.scheduling.models import (
    Appointment,
    AppointmentStatusHistory,
    AppointmentSlot,
    PractitionerAvailabilityPeriod,
    PractitionerLeaveRequest,
    PractitionerShift,
)
from common.exceptions import NotFoundError, ValidationError

User = get_user_model()

ACTIVE_APPOINTMENT_STATUSES = (
    Appointment.Status.PENDING,
    Appointment.Status.CONFIRMED,
    Appointment.Status.CHECKED_IN,
    Appointment.Status.QUEUED,
    Appointment.Status.IN_SERVICE,
)
TERMINAL_APPOINTMENT_STATUSES = (
    Appointment.Status.COMPLETED,
    Appointment.Status.CANCELLED,
    Appointment.Status.NO_SHOW,
    Appointment.Status.RESCHEDULED,
)


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def get_user(user_id, *, field_label: str = "User", active_only: bool = False, for_update: bool = False):
    queryset = User.objects
    if for_update:
        queryset = queryset.select_for_update()
    try:
        user = queryset.get(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not user.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return user


def get_facility(facility_id, *, field_label: str = "Facility", active_only: bool = False, for_update: bool = False) -> Facility:
    queryset = Facility.objects.select_related("organization")
    if for_update:
        queryset = queryset.select_for_update()
    try:
        facility = queryset.get(pk=facility_id)
    except Facility.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not facility.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return facility


def get_patient(patient_id, *, field_label: str = "Patient", active_only: bool = False, for_update: bool = False) -> Patient:
    if for_update:
        queryset = Patient.objects.select_for_update().select_related("organization")
    else:
        queryset = Patient.objects.select_related("organization", "registered_facility")
    try:
        patient = queryset.get(pk=patient_id)
    except Patient.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not patient.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return patient


def get_facility_specialty(
    facility_specialty_id,
    *,
    field_label: str = "Facility specialty",
    active_only: bool = False,
    for_update: bool = False,
) -> FacilitySpecialty:
    queryset = FacilitySpecialty.objects.select_related("facility", "specialty")
    if for_update:
        queryset = queryset.select_for_update()
    else:
        queryset = queryset.select_related("department")
    try:
        facility_specialty = queryset.get(pk=facility_specialty_id)
    except FacilitySpecialty.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not facility_specialty.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return facility_specialty


def get_practitioner_facility_assignment(
    assignment_id,
    *,
    field_label: str = "Practitioner facility assignment",
    active_only: bool = False,
    for_update: bool = False,
) -> PractitionerFacilityAssignment:
    queryset = PractitionerFacilityAssignment.objects.select_related("practitioner", "practitioner__organization", "facility")
    if for_update:
        queryset = queryset.select_for_update()
    try:
        assignment = queryset.get(pk=assignment_id)
    except PractitionerFacilityAssignment.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not assignment.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return assignment


def get_practitioner_department_assignment(
    assignment_id,
    *,
    field_label: str = "Practitioner department assignment",
    active_only: bool = False,
    for_update: bool = False,
) -> PractitionerDepartmentAssignment:
    queryset = PractitionerDepartmentAssignment.objects.select_related(
        "practitioner_facility_assignment",
        "practitioner_facility_assignment__practitioner",
        "practitioner_facility_assignment__facility",
        "department",
        "department__facility",
    )
    if for_update:
        queryset = queryset.select_for_update()
    try:
        assignment = queryset.get(pk=assignment_id)
    except PractitionerDepartmentAssignment.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not assignment.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return assignment


def get_practitioner_specialty_assignment(
    assignment_id,
    *,
    field_label: str = "Practitioner specialty assignment",
    active_only: bool = False,
    for_update: bool = False,
) -> PractitionerSpecialtyAssignment:
    queryset = PractitionerSpecialtyAssignment.objects.select_related(
        "practitioner_facility_assignment",
        "practitioner_facility_assignment__practitioner",
        "practitioner_facility_assignment__facility",
        "facility_specialty",
        "facility_specialty__facility",
        "facility_specialty__specialty",
    )
    if for_update:
        queryset = queryset.select_for_update()
    else:
        queryset = queryset.select_related("facility_specialty__department")
    try:
        assignment = queryset.get(pk=assignment_id)
    except PractitionerSpecialtyAssignment.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not assignment.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return assignment


def get_service_point(service_point_id, *, field_label: str = "Service point", active_only: bool = False, for_update: bool = False) -> ServicePoint:
    if for_update:
        queryset = ServicePoint.objects.select_for_update().select_related("facility")
    else:
        queryset = ServicePoint.objects.select_related("facility", "department")
    try:
        service_point = queryset.get(pk=service_point_id)
    except ServicePoint.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not service_point.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return service_point


def get_consultation_room(
    consultation_room_id,
    *,
    field_label: str = "Consultation room",
    active_only: bool = False,
    for_update: bool = False,
) -> ConsultationRoom:
    if for_update:
        queryset = ConsultationRoom.objects.select_for_update().select_related("facility")
    else:
        queryset = ConsultationRoom.objects.select_related("facility", "department")
    try:
        consultation_room = queryset.get(pk=consultation_room_id)
    except ConsultationRoom.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not consultation_room.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return consultation_room


def get_availability_period(
    availability_period_id,
    *,
    field_label: str = "Availability period",
    active_only: bool = False,
    for_update: bool = False,
) -> PractitionerAvailabilityPeriod:
    queryset = PractitionerAvailabilityPeriod.objects.select_related(
        "practitioner_facility_assignment",
        "practitioner_facility_assignment__facility",
        "practitioner_facility_assignment__practitioner",
    )
    if for_update:
        queryset = queryset.select_for_update()
    try:
        availability_period = queryset.get(pk=availability_period_id)
    except PractitionerAvailabilityPeriod.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc
    if active_only and not availability_period.is_active:
        raise ValidationError(f"{field_label} must be active.")
    return availability_period


def get_leave_request(
    leave_request_id,
    *,
    field_label: str = "Leave request",
    for_update: bool = False,
) -> PractitionerLeaveRequest:
    queryset = PractitionerLeaveRequest.objects.select_related(
        "practitioner_facility_assignment",
        "practitioner_facility_assignment__facility",
        "practitioner_facility_assignment__practitioner",
    )
    if for_update:
        queryset = queryset.select_for_update()
    try:
        return queryset.get(pk=leave_request_id)
    except PractitionerLeaveRequest.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc


def get_shift(shift_id, *, field_label: str = "Practitioner shift", for_update: bool = False) -> PractitionerShift:
    if for_update:
        queryset = PractitionerShift.objects.select_for_update().select_related(
            "practitioner_facility_assignment",
            "practitioner_facility_assignment__facility",
            "practitioner_facility_assignment__practitioner",
        )
    else:
        queryset = PractitionerShift.objects.select_related(
            "practitioner_facility_assignment",
            "practitioner_facility_assignment__facility",
            "practitioner_facility_assignment__practitioner",
            "practitioner_department_assignment",
            "service_point",
            "consultation_room",
        )
    try:
        return queryset.get(pk=shift_id)
    except PractitionerShift.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc


def get_appointment_slot(slot_id, *, field_label: str = "Appointment slot", for_update: bool = False) -> AppointmentSlot:
    queryset = AppointmentSlot.objects.select_related("practitioner_shift", "facility_specialty")
    if for_update:
        queryset = queryset.select_for_update()
    else:
        queryset = queryset.select_related(
            "practitioner_shift__practitioner_facility_assignment__practitioner",
            "facility_specialty__specialty",
        )
    try:
        return queryset.get(pk=slot_id)
    except AppointmentSlot.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc


def get_appointment(appointment_id, *, field_label: str = "Appointment", for_update: bool = False) -> Appointment:
    if for_update:
        queryset = Appointment.objects.select_for_update().select_related(
            "facility",
            "facility__organization",
            "patient",
            "patient__organization",
            "facility_specialty",
        )
    else:
        queryset = Appointment.objects.select_related(
            "facility",
            "facility__organization",
            "patient",
            "patient__organization",
            "facility_specialty",
            "facility_specialty__specialty",
            "practitioner_facility_assignment",
            "practitioner_specialty_assignment",
            "practitioner_shift",
            "appointment_slot",
            "cancelled_by",
            "created_by",
        ).prefetch_related(Prefetch("status_history", queryset=AppointmentStatusHistory.objects.order_by("changed_at")))
    try:
        return queryset.get(pk=appointment_id)
    except Appointment.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} not found.") from exc


def get_facility_flow_settings(*, facility: Facility, for_update: bool = False) -> FacilityFlowSetting:
    queryset = FacilityFlowSetting.objects
    if for_update:
        queryset = queryset.select_for_update()
    flow_settings = queryset.filter(facility=facility).first()
    if flow_settings is not None:
        return flow_settings
    return FacilityFlowSetting(facility=facility)


def facility_timezone(facility: Facility) -> ZoneInfo:
    return ZoneInfo(facility.timezone)


def to_local_datetime(*, facility: Facility, value: datetime) -> datetime:
    dt = value
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone=timezone.utc)
    return timezone.localtime(dt, facility_timezone(facility))


def to_local_date(*, facility: Facility, value: datetime) -> date:
    return to_local_datetime(facility=facility, value=value).date()


def daterange_overlap(start_a, end_a, start_b, end_b) -> bool:
    effective_end_a = end_a or date.max
    effective_end_b = end_b or date.max
    return start_a <= effective_end_b and start_b <= effective_end_a


def time_overlap(start_a: time, end_a: time, start_b: time, end_b: time) -> bool:
    return start_a < end_b and start_b < end_a


def datetime_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def validate_datetime_range(*, starts_at: datetime, ends_at: datetime, label: str) -> None:
    if starts_at is None or ends_at is None:
        raise ValidationError(f"{label} start and end are required.")
    if ends_at <= starts_at:
        raise ValidationError(f"{label} end must be after start.")


def validate_time_range(*, starts_at: time, ends_at: time, label: str) -> None:
    if starts_at is None or ends_at is None:
        raise ValidationError(f"{label} start and end are required.")
    if ends_at <= starts_at:
        raise ValidationError(f"{label} end must be after start.")


def appointment_local_minute_range(*, facility: Facility, scheduled_start: datetime, scheduled_end: datetime) -> tuple[date, int, int]:
    local_start = to_local_datetime(facility=facility, value=scheduled_start)
    local_end = to_local_datetime(facility=facility, value=scheduled_end)
    base_date = local_start.date()
    start_minutes = (local_start.hour * 60) + local_start.minute
    end_minutes = (local_end.hour * 60) + local_end.minute
    if local_end.date() > base_date:
        end_minutes += 1440 * (local_end.date() - base_date).days
    return base_date, start_minutes, end_minutes


def row_minute_range(*, opens_at: time | None, closes_at: time | None, closes_next_day: bool, is_24_hours: bool) -> tuple[int, int]:
    if is_24_hours:
        return 0, 1440
    start = (opens_at.hour * 60) + opens_at.minute
    end = (closes_at.hour * 60) + closes_at.minute
    if closes_next_day:
        end += 1440
    return start, end


def appointment_fits_rows(*, facility: Facility, scheduled_start: datetime, scheduled_end: datetime, rows) -> bool:
    _, appointment_start, appointment_end = appointment_local_minute_range(
        facility=facility,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
    )
    for row in rows:
        row_start, row_end = row_minute_range(
            opens_at=getattr(row, "opens_at", None),
            closes_at=getattr(row, "closes_at", None),
            closes_next_day=getattr(row, "closes_next_day", False),
            is_24_hours=getattr(row, "is_24_hours", False),
        )
        if appointment_start >= row_start and appointment_end <= row_end:
            return True
    return False


def ensure_appointment_within_facility_schedule(*, facility: Facility, scheduled_start: datetime, scheduled_end: datetime) -> None:
    validate_datetime_range(starts_at=scheduled_start, ends_at=scheduled_end, label="Appointment")
    local_date, _, _ = appointment_local_minute_range(
        facility=facility,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
    )
    schedule_exceptions = list(
        FacilityScheduleException.objects.filter(
            facility=facility,
            exception_date=local_date,
            is_active=True,
        ).order_by("period_order")
    )
    if schedule_exceptions:
        if any(exception.is_closed for exception in schedule_exceptions):
            raise ValidationError("Appointment time falls inside a facility closure.")
        if not appointment_fits_rows(
            facility=facility,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            rows=schedule_exceptions,
        ):
            raise ValidationError("Appointment time is outside facility schedule exceptions.")
        return

    operating_hours = list(
        FacilityOperatingHour.objects.filter(
            facility=facility,
            day_of_week=local_date.isoweekday(),
            is_active=True,
        ).order_by("period_order")
    )
    if not operating_hours:
        raise ValidationError("Appointment time falls outside facility operating hours.")
    if not appointment_fits_rows(
        facility=facility,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        rows=operating_hours,
    ):
        raise ValidationError("Appointment time falls outside facility operating hours.")


def ensure_within_assignment_dates(*, facility: Facility, starts_at: datetime, ends_at: datetime, assignment: PractitionerFacilityAssignment, label: str) -> None:
    local_start = to_local_date(facility=facility, value=starts_at)
    local_end = to_local_date(facility=facility, value=ends_at)
    if local_start < assignment.starts_on or (assignment.ends_on is not None and local_end > assignment.ends_on):
        raise ValidationError(f"{label} must remain within practitioner facility assignment dates.")


def ensure_not_on_approved_leave(*, practitioner_facility_assignment: PractitionerFacilityAssignment, starts_at: datetime, ends_at: datetime, exclude_id=None) -> None:
    queryset = PractitionerLeaveRequest.objects.select_for_update().filter(
        practitioner_facility_assignment=practitioner_facility_assignment,
        status=PractitionerLeaveRequest.Status.APPROVED,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.filter(starts_at__lt=ends_at, ends_at__gt=starts_at).exists():
        raise ValidationError("Requested time overlaps approved practitioner leave.")


def availability_covers_time(*, practitioner_facility_assignment: PractitionerFacilityAssignment, starts_at: datetime, ends_at: datetime) -> bool:
    facility = practitioner_facility_assignment.facility
    local_start = to_local_datetime(facility=facility, value=starts_at)
    local_end = to_local_datetime(facility=facility, value=ends_at)
    if local_end.date() != local_start.date():
        return False

    periods = PractitionerAvailabilityPeriod.objects.filter(
        practitioner_facility_assignment=practitioner_facility_assignment,
        day_of_week=local_start.isoweekday(),
        is_active=True,
        is_available_for_appointments=True,
        valid_from__lte=local_start.date(),
    ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=local_end.date()))

    for period in periods:
        if period.starts_at <= local_start.timetz().replace(tzinfo=None) and period.ends_at >= local_end.timetz().replace(tzinfo=None):
            return True
    return False


def practitioner_has_specialty_assignment(
    *,
    practitioner_facility_assignment: PractitionerFacilityAssignment,
    facility_specialty: FacilitySpecialty,
    scheduled_start: datetime,
    scheduled_end: datetime,
) -> PractitionerSpecialtyAssignment | None:
    facility = practitioner_facility_assignment.facility
    local_start = to_local_date(facility=facility, value=scheduled_start)
    local_end = to_local_date(facility=facility, value=scheduled_end)
    queryset = PractitionerSpecialtyAssignment.objects.select_related("facility_specialty").filter(
        practitioner_facility_assignment=practitioner_facility_assignment,
        facility_specialty=facility_specialty,
        is_active=True,
        starts_on__lte=local_start,
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=local_end))
    return queryset.first()


def sync_slot_status(slot: AppointmentSlot) -> AppointmentSlot:
    if slot.status in {AppointmentSlot.Status.BLOCKED, AppointmentSlot.Status.CANCELLED}:
        return slot
    slot.status = AppointmentSlot.Status.FULL if slot.booked_count >= slot.capacity else AppointmentSlot.Status.AVAILABLE
    return slot


def active_appointment_overlap_queryset(*, exclude_id=None):
    queryset = Appointment.objects.select_for_update().filter(status__in=ACTIVE_APPOINTMENT_STATUSES)
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    return queryset


@dataclass(slots=True)
class FlowCutoffResult:
    facility_now: datetime
    facility_start: datetime


def get_facility_now_and_start(*, facility: Facility, scheduled_start: datetime) -> FlowCutoffResult:
    facility_start = to_local_datetime(facility=facility, value=scheduled_start)
    facility_now = timezone.now().astimezone(facility_timezone(facility))
    return FlowCutoffResult(facility_now=facility_now, facility_start=facility_start)


def enforce_booking_cutoffs(*, facility: Facility, scheduled_start: datetime, flow_settings: FacilityFlowSetting) -> None:
    result = get_facility_now_and_start(facility=facility, scheduled_start=scheduled_start)
    advance_days = (result.facility_start.date() - result.facility_now.date()).days
    if advance_days > flow_settings.max_advance_booking_days:
        raise ValidationError("Appointment exceeds the facility advance-booking limit.")
    minutes_until_start = (result.facility_start - result.facility_now).total_seconds() / 60
    if minutes_until_start < flow_settings.minimum_booking_notice_minutes:
        raise ValidationError("Appointment violates the facility minimum booking notice.")


def enforce_cancellation_cutoff(*, facility: Facility, scheduled_start: datetime, flow_settings: FacilityFlowSetting) -> None:
    result = get_facility_now_and_start(facility=facility, scheduled_start=scheduled_start)
    minutes_until_start = (result.facility_start - result.facility_now).total_seconds() / 60
    if minutes_until_start < flow_settings.cancellation_cutoff_minutes:
        raise ValidationError("Appointment is inside the facility cancellation cutoff.")


def enforce_reschedule_cutoff(*, facility: Facility, scheduled_start: datetime, flow_settings: FacilityFlowSetting) -> None:
    result = get_facility_now_and_start(facility=facility, scheduled_start=scheduled_start)
    minutes_until_start = (result.facility_start - result.facility_now).total_seconds() / 60
    if minutes_until_start < flow_settings.reschedule_cutoff_minutes:
        raise ValidationError("Appointment is inside the facility reschedule cutoff.")
