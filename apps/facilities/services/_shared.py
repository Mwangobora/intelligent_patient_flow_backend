from __future__ import annotations

from datetime import date, time

from apps.accounts.models import User
from apps.facilities.models import (
    ConsultationRoom,
    Department,
    Facility,
    FacilityFlowSetting,
    FacilityOperatingHour,
    FacilityScheduleException,
    FacilitySpecialty,
    FacilityType,
    Organization,
    ServicePoint,
    ServicePointType,
    Specialty,
)
from common.exceptions import ConflictError, NotFoundError, ValidationError


def clean_optional_text(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def require_non_empty_name(*, value: str | None, label: str) -> str:
    if not value or not value.strip():
        raise ValidationError(f"{label} is required.")
    return value.strip()


def require_positive_smallint(*, value, label: str, allow_zero: bool = False) -> int:
    if value is None:
        raise ValidationError(f"{label} is required.")
    if allow_zero:
        if value < 0:
            raise ValidationError(f"{label} must be greater than or equal to 0.")
    elif value <= 0:
        raise ValidationError(f"{label} must be greater than 0.")
    return int(value)


def get_user(user_id, *, field_label: str) -> User:
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} user not found.") from exc


def get_organization_for_update(organization_id, *, require_active: bool = False) -> Organization:
    try:
        organization = Organization.objects.select_for_update().get(pk=organization_id)
    except Organization.DoesNotExist as exc:
        raise NotFoundError("Organization not found.") from exc

    if require_active and not organization.is_active:
        raise ValidationError("Organization must be active.")
    return organization


def get_facility_type_for_update(facility_type_id, *, require_active: bool = False) -> FacilityType:
    try:
        facility_type = FacilityType.objects.select_for_update().get(pk=facility_type_id)
    except FacilityType.DoesNotExist as exc:
        raise NotFoundError("Facility type not found.") from exc

    if require_active and not facility_type.is_active:
        raise ValidationError("Facility type must be active.")
    return facility_type


def get_facility_for_update(facility_id, *, require_active: bool = False) -> Facility:
    try:
        facility = Facility.objects.select_for_update().get(pk=facility_id)
    except Facility.DoesNotExist as exc:
        raise NotFoundError("Facility not found.") from exc

    if require_active and not facility.is_active:
        raise ValidationError("Facility must be active.")
    return facility


def get_department_for_update(department_id, *, require_active: bool = False) -> Department:
    try:
        department = Department.objects.select_for_update().get(pk=department_id)
    except Department.DoesNotExist as exc:
        raise NotFoundError("Department not found.") from exc

    if require_active and not department.is_active:
        raise ValidationError("Department must be active.")
    return department


def get_specialty_for_update(specialty_id, *, require_active: bool = False) -> Specialty:
    try:
        specialty = Specialty.objects.select_for_update().get(pk=specialty_id)
    except Specialty.DoesNotExist as exc:
        raise NotFoundError("Specialty not found.") from exc

    if require_active and not specialty.is_active:
        raise ValidationError("Specialty must be active.")
    return specialty


def get_service_point_type_for_update(service_point_type_id, *, require_active: bool = False) -> ServicePointType:
    try:
        service_point_type = ServicePointType.objects.select_for_update().get(pk=service_point_type_id)
    except ServicePointType.DoesNotExist as exc:
        raise NotFoundError("Service point type not found.") from exc

    if require_active and not service_point_type.is_active:
        raise ValidationError("Service point type must be active.")
    return service_point_type


def get_service_point_for_update(service_point_id) -> ServicePoint:
    try:
        return ServicePoint.objects.select_for_update().get(pk=service_point_id)
    except ServicePoint.DoesNotExist as exc:
        raise NotFoundError("Service point not found.") from exc


def get_consultation_room_for_update(room_id) -> ConsultationRoom:
    try:
        return ConsultationRoom.objects.select_for_update().get(pk=room_id)
    except ConsultationRoom.DoesNotExist as exc:
        raise NotFoundError("Consultation room not found.") from exc


def get_facility_specialty_for_update(facility_specialty_id) -> FacilitySpecialty:
    try:
        return FacilitySpecialty.objects.select_for_update().get(pk=facility_specialty_id)
    except FacilitySpecialty.DoesNotExist as exc:
        raise NotFoundError("Facility specialty not found.") from exc


def get_operating_hour_for_update(operating_hour_id) -> FacilityOperatingHour:
    try:
        return FacilityOperatingHour.objects.select_for_update().get(pk=operating_hour_id)
    except FacilityOperatingHour.DoesNotExist as exc:
        raise NotFoundError("Facility operating hour not found.") from exc


def get_schedule_exception_for_update(schedule_exception_id) -> FacilityScheduleException:
    try:
        return FacilityScheduleException.objects.select_for_update().get(pk=schedule_exception_id)
    except FacilityScheduleException.DoesNotExist as exc:
        raise NotFoundError("Facility schedule exception not found.") from exc


def get_flow_setting_for_update(flow_setting_id) -> FacilityFlowSetting:
    try:
        return FacilityFlowSetting.objects.select_for_update().get(pk=flow_setting_id)
    except FacilityFlowSetting.DoesNotExist as exc:
        raise NotFoundError("Facility flow settings not found.") from exc


def ensure_department_in_facility(*, department: Department | None, facility: Facility, message: str) -> None:
    if department is not None and department.facility_id != facility.id:
        raise ValidationError(message)


def ensure_parent_department_valid(*, department_id=None, parent_department: Department | None, facility: Facility) -> None:
    if parent_department is None:
        return
    if department_id is not None and parent_department.id == department_id:
        raise ValidationError("Department cannot be its own parent.")
    if parent_department.facility_id != facility.id:
        raise ValidationError("Parent department must belong to the same facility.")

    ancestor = parent_department
    while ancestor.parent_department_id is not None:
        if department_id is not None and ancestor.parent_department_id == department_id:
            raise ValidationError("Department hierarchy cycle detected.")
        ancestor = Department.objects.filter(pk=ancestor.parent_department_id).only("id", "parent_department_id").first()
        if ancestor is None:
            break


def ensure_parent_specialty_valid(*, specialty_id=None, parent_specialty: Specialty | None) -> None:
    if parent_specialty is None:
        return
    if specialty_id is not None and parent_specialty.id == specialty_id:
        raise ValidationError("Specialty cannot be its own parent.")

    ancestor = parent_specialty
    while ancestor.parent_specialty_id is not None:
        if specialty_id is not None and ancestor.parent_specialty_id == specialty_id:
            raise ValidationError("Specialty hierarchy cycle detected.")
        ancestor = Specialty.objects.filter(pk=ancestor.parent_specialty_id).only("id", "parent_specialty_id").first()
        if ancestor is None:
            break


def clock_minutes(value: time) -> int:
    return (value.hour * 60) + value.minute


def range_minutes(*, opens_at: time | None, closes_at: time | None, closes_next_day: bool, is_24_hours: bool) -> tuple[int, int]:
    if is_24_hours:
        return 0, 1440
    start = clock_minutes(opens_at)
    end = clock_minutes(closes_at) + (1440 if closes_next_day else 0)
    return start, end


def validate_open_close_shape(
    *,
    is_24_hours: bool,
    is_closed: bool | None = None,
    opens_at: time | None,
    closes_at: time | None,
    closes_next_day: bool,
    closed_label: str,
) -> None:
    if is_closed is True:
        if is_24_hours or opens_at is not None or closes_at is not None or closes_next_day:
            raise ValidationError(f"{closed_label} must not have open/close times or 24-hour mode.")
        return

    if is_24_hours:
        if opens_at is not None or closes_at is not None or closes_next_day:
            raise ValidationError("24-hour rows must not define open/close times.")
        return

    if opens_at is None or closes_at is None:
        raise ValidationError("Open and close times are required unless the row is closed or 24 hours.")
    if opens_at == closes_at:
        raise ValidationError("Open and close times cannot be equal.")
    if not closes_next_day and closes_at <= opens_at:
        raise ValidationError("Close time must be after open time unless closes_next_day is true.")


def time_ranges_overlap(first_start: int, first_end: int, second_start: int, second_end: int) -> bool:
    return first_start < second_end and second_start < first_end


def ensure_unique_active_schedule_exception_shape(
    *,
    facility: Facility,
    exception_date: date,
    schedule_exception_id=None,
    is_closed: bool,
    is_24_hours: bool,
    new_start: int | None = None,
    new_end: int | None = None,
) -> None:
    queryset = FacilityScheduleException.objects.select_for_update().filter(
        facility=facility,
        exception_date=exception_date,
        is_active=True,
    )
    if schedule_exception_id is not None:
        queryset = queryset.exclude(pk=schedule_exception_id)

    if is_closed or is_24_hours:
        if queryset.exists():
            raise ConflictError("Closed or 24-hour exception cannot coexist with another active period.")
        return

    if queryset.filter(is_closed=True).exists() or queryset.filter(is_24_hours=True).exists():
        raise ConflictError("Normal exception period cannot coexist with a closed or 24-hour exception.")

    for existing in queryset.only("opens_at", "closes_at", "closes_next_day", "is_24_hours"):
        existing_start, existing_end = range_minutes(
            opens_at=existing.opens_at,
            closes_at=existing.closes_at,
            closes_next_day=existing.closes_next_day,
            is_24_hours=existing.is_24_hours,
        )
        if time_ranges_overlap(new_start, new_end, existing_start, existing_end):
            raise ConflictError("Facility schedule exception overlaps another active period.")


def ensure_unique_active_operating_hours(
    *,
    facility: Facility,
    day_of_week: int,
    operating_hour_id=None,
    new_start: int,
    new_end: int,
) -> None:
    queryset = FacilityOperatingHour.objects.select_for_update().filter(
        facility=facility,
        day_of_week=day_of_week,
        is_active=True,
    )
    if operating_hour_id is not None:
        queryset = queryset.exclude(pk=operating_hour_id)

    for existing in queryset.only("opens_at", "closes_at", "closes_next_day", "is_24_hours", "day_of_week"):
        existing_day_start, existing_day_end = operating_day_range(existing)
        if (
            time_ranges_overlap(new_start, new_end, existing_day_start, existing_day_end)
            or time_ranges_overlap(new_start, new_end, existing_day_start + 10080, existing_day_end + 10080)
            or time_ranges_overlap(new_start, new_end, existing_day_start - 10080, existing_day_end - 10080)
        ):
            raise ConflictError("Facility operating hours overlap another active period.")


def operating_day_range(operating_hour: FacilityOperatingHour) -> tuple[int, int]:
    start, end = range_minutes(
        opens_at=operating_hour.opens_at,
        closes_at=operating_hour.closes_at,
        closes_next_day=operating_hour.closes_next_day,
        is_24_hours=operating_hour.is_24_hours,
    )
    offset = (operating_hour.day_of_week - 1) * 1440
    return offset + start, offset + end
