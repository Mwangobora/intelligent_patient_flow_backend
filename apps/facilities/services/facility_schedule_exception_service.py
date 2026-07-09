from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.facilities.models import FacilityScheduleException
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    clean_optional_text,
    ensure_unique_active_schedule_exception_shape,
    get_facility_for_update,
    get_schedule_exception_for_update,
    range_minutes,
    require_positive_smallint,
    validate_open_close_shape,
)


@transaction.atomic
def create_facility_schedule_exception(
    *,
    facility_id,
    exception_date,
    period_order: int = 1,
    is_closed: bool = False,
    opens_at=None,
    closes_at=None,
    closes_next_day: bool = False,
    is_24_hours: bool = False,
    reason: str | None = None,
) -> FacilityScheduleException:
    facility = get_facility_for_update(facility_id, require_active=True)
    normalized_period_order = require_positive_smallint(value=period_order, label="Period order")
    validate_open_close_shape(
        is_24_hours=is_24_hours,
        is_closed=is_closed,
        opens_at=opens_at,
        closes_at=closes_at,
        closes_next_day=closes_next_day,
        closed_label="Closed exceptions",
    )

    new_start = new_end = None
    if not is_closed and not is_24_hours:
        new_start, new_end = range_minutes(
            opens_at=opens_at,
            closes_at=closes_at,
            closes_next_day=closes_next_day,
            is_24_hours=False,
        )
    ensure_unique_active_schedule_exception_shape(
        facility=facility,
        exception_date=exception_date,
        is_closed=is_closed,
        is_24_hours=is_24_hours,
        new_start=new_start,
        new_end=new_end,
    )

    try:
        return FacilityScheduleException.objects.create(
            facility=facility,
            exception_date=exception_date,
            period_order=normalized_period_order,
            is_closed=is_closed,
            opens_at=opens_at,
            closes_at=closes_at,
            closes_next_day=closes_next_day,
            is_24_hours=is_24_hours,
            reason=clean_optional_text(reason),
        )
    except IntegrityError as exc:
        raise ConflictError("Facility schedule exception could not be created because it already exists.") from exc


@transaction.atomic
def update_facility_schedule_exception(
    *,
    facility_schedule_exception_id,
    **updates,
) -> FacilityScheduleException:
    schedule_exception = get_schedule_exception_for_update(facility_schedule_exception_id)
    allowed_fields = {
        "facility_id",
        "exception_date",
        "period_order",
        "is_closed",
        "opens_at",
        "closes_at",
        "closes_next_day",
        "is_24_hours",
        "reason",
    }
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        raise ValidationError(f"Unsupported schedule exception update fields: {', '.join(sorted(unexpected_fields))}.")

    facility = (
        get_facility_for_update(updates["facility_id"], require_active=True)
        if "facility_id" in updates
        else get_facility_for_update(schedule_exception.facility_id, require_active=True)
    )
    exception_date = updates.get("exception_date", schedule_exception.exception_date)
    period_order = require_positive_smallint(
        value=updates.get("period_order", schedule_exception.period_order),
        label="Period order",
    )
    is_closed = updates.get("is_closed", schedule_exception.is_closed)
    opens_at = updates.get("opens_at", schedule_exception.opens_at)
    closes_at = updates.get("closes_at", schedule_exception.closes_at)
    closes_next_day = updates.get("closes_next_day", schedule_exception.closes_next_day)
    is_24_hours = updates.get("is_24_hours", schedule_exception.is_24_hours)

    validate_open_close_shape(
        is_24_hours=is_24_hours,
        is_closed=is_closed,
        opens_at=opens_at,
        closes_at=closes_at,
        closes_next_day=closes_next_day,
        closed_label="Closed exceptions",
    )

    new_start = new_end = None
    if not is_closed and not is_24_hours:
        new_start, new_end = range_minutes(
            opens_at=opens_at,
            closes_at=closes_at,
            closes_next_day=closes_next_day,
            is_24_hours=False,
        )
    ensure_unique_active_schedule_exception_shape(
        facility=facility,
        exception_date=exception_date,
        schedule_exception_id=schedule_exception.id,
        is_closed=is_closed,
        is_24_hours=is_24_hours,
        new_start=new_start,
        new_end=new_end,
    )

    schedule_exception.facility = facility
    schedule_exception.exception_date = exception_date
    schedule_exception.period_order = period_order
    schedule_exception.is_closed = is_closed
    schedule_exception.opens_at = opens_at
    schedule_exception.closes_at = closes_at
    schedule_exception.closes_next_day = closes_next_day
    schedule_exception.is_24_hours = is_24_hours
    if "reason" in updates:
        schedule_exception.reason = clean_optional_text(updates["reason"])

    try:
        schedule_exception.save()
    except IntegrityError as exc:
        raise ConflictError("Facility schedule exception could not be updated because it already exists.") from exc
    return schedule_exception


@transaction.atomic
def deactivate_facility_schedule_exception(*, facility_schedule_exception_id) -> FacilityScheduleException:
    schedule_exception = get_schedule_exception_for_update(facility_schedule_exception_id)
    if not schedule_exception.is_active:
        return schedule_exception

    schedule_exception.is_active = False
    schedule_exception.save(update_fields=["is_active", "updated_at"])
    return schedule_exception
