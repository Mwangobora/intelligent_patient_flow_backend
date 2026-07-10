from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.scheduling.models import PractitionerAvailabilityPeriod
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    daterange_overlap,
    get_availability_period,
    get_practitioner_facility_assignment,
    get_user,
    normalize_optional_text,
    time_overlap,
    validate_time_range,
)


def _validate_availability_shape(*, practitioner_facility_assignment, day_of_week, starts_at, ends_at, valid_from, valid_until) -> None:
    if not practitioner_facility_assignment.is_active:
        raise ValidationError("Practitioner facility assignment must be active.")
    if day_of_week < 1 or day_of_week > 7:
        raise ValidationError("day_of_week must be between 1 and 7.")
    validate_time_range(starts_at=starts_at, ends_at=ends_at, label="Availability period")
    if valid_until is not None and valid_until < valid_from:
        raise ValidationError("valid_until must be greater than or equal to valid_from.")
    if valid_from < practitioner_facility_assignment.starts_on:
        raise ValidationError("Availability period must remain within facility assignment dates.")
    if practitioner_facility_assignment.ends_on is not None and (valid_until is None or valid_until > practitioner_facility_assignment.ends_on):
        raise ValidationError("Availability period must remain within facility assignment dates.")


def _ensure_no_overlap(
    *,
    practitioner_facility_assignment,
    day_of_week,
    starts_at,
    ends_at,
    valid_from,
    valid_until,
    exclude_id=None,
) -> None:
    queryset = PractitionerAvailabilityPeriod.objects.select_for_update().filter(
        practitioner_facility_assignment=practitioner_facility_assignment,
        day_of_week=day_of_week,
        is_active=True,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    for existing in queryset:
        if daterange_overlap(existing.valid_from, existing.valid_until, valid_from, valid_until) and time_overlap(
            existing.starts_at,
            existing.ends_at,
            starts_at,
            ends_at,
        ):
            raise ConflictError("Practitioner availability overlaps another active period.")


@transaction.atomic
def create_availability_period(
    *,
    practitioner_facility_assignment_id,
    day_of_week,
    starts_at,
    ends_at,
    valid_from,
    valid_until=None,
    is_available_for_appointments: bool = True,
    created_by_id=None,
) -> PractitionerAvailabilityPeriod:
    practitioner_facility_assignment = get_practitioner_facility_assignment(
        practitioner_facility_assignment_id,
        active_only=True,
        for_update=True,
    )
    created_by = get_user(created_by_id, field_label="Creator user", active_only=True) if created_by_id is not None else None
    _validate_availability_shape(
        practitioner_facility_assignment=practitioner_facility_assignment,
        day_of_week=day_of_week,
        starts_at=starts_at,
        ends_at=ends_at,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    _ensure_no_overlap(
        practitioner_facility_assignment=practitioner_facility_assignment,
        day_of_week=day_of_week,
        starts_at=starts_at,
        ends_at=ends_at,
        valid_from=valid_from,
        valid_until=valid_until,
    )
    try:
        return PractitionerAvailabilityPeriod.objects.create(
            practitioner_facility_assignment=practitioner_facility_assignment,
            day_of_week=day_of_week,
            starts_at=starts_at,
            ends_at=ends_at,
            valid_from=valid_from,
            valid_until=valid_until,
            is_available_for_appointments=bool(is_available_for_appointments),
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Availability period could not be created because a conflicting record already exists.") from exc


@transaction.atomic
def update_availability_period(*, availability_period_id, **updates) -> PractitionerAvailabilityPeriod:
    availability_period = get_availability_period(availability_period_id, active_only=True, for_update=True)
    allowed_fields = {
        "day_of_week",
        "starts_at",
        "ends_at",
        "valid_from",
        "valid_until",
        "is_available_for_appointments",
    }
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        raise ValidationError(f"Unsupported availability update fields: {', '.join(sorted(unexpected_fields))}.")

    next_day_of_week = updates.get("day_of_week", availability_period.day_of_week)
    next_starts_at = updates.get("starts_at", availability_period.starts_at)
    next_ends_at = updates.get("ends_at", availability_period.ends_at)
    next_valid_from = updates.get("valid_from", availability_period.valid_from)
    next_valid_until = updates.get("valid_until", availability_period.valid_until)
    _validate_availability_shape(
        practitioner_facility_assignment=availability_period.practitioner_facility_assignment,
        day_of_week=next_day_of_week,
        starts_at=next_starts_at,
        ends_at=next_ends_at,
        valid_from=next_valid_from,
        valid_until=next_valid_until,
    )
    _ensure_no_overlap(
        practitioner_facility_assignment=availability_period.practitioner_facility_assignment,
        day_of_week=next_day_of_week,
        starts_at=next_starts_at,
        ends_at=next_ends_at,
        valid_from=next_valid_from,
        valid_until=next_valid_until,
        exclude_id=availability_period.pk,
    )

    availability_period.day_of_week = next_day_of_week
    availability_period.starts_at = next_starts_at
    availability_period.ends_at = next_ends_at
    availability_period.valid_from = next_valid_from
    availability_period.valid_until = next_valid_until
    if "is_available_for_appointments" in updates:
        availability_period.is_available_for_appointments = bool(updates["is_available_for_appointments"])
    try:
        availability_period.save()
    except IntegrityError as exc:
        raise ConflictError("Availability period could not be updated because a conflicting record already exists.") from exc
    return availability_period


@transaction.atomic
def deactivate_availability_period(*, availability_period_id) -> PractitionerAvailabilityPeriod:
    availability_period = get_availability_period(availability_period_id, for_update=True)
    if not availability_period.is_active:
        return availability_period
    availability_period.is_active = False
    availability_period.save(update_fields=["is_active", "updated_at"])
    return availability_period
