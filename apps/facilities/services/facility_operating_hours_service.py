from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.facilities.models import FacilityOperatingHour
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    ensure_unique_active_operating_hours,
    get_facility_for_update,
    get_operating_hour_for_update,
    operating_day_range,
    require_positive_smallint,
    validate_open_close_shape,
)


def _validate_day_of_week(day_of_week: int) -> int:
    if day_of_week < 1 or day_of_week > 7:
        raise ValidationError("Day of week must be between 1 and 7.")
    return int(day_of_week)


@transaction.atomic
def create_facility_operating_hour(
    *,
    facility_id,
    day_of_week: int,
    period_order: int = 1,
    opens_at=None,
    closes_at=None,
    closes_next_day: bool = False,
    is_24_hours: bool = False,
) -> FacilityOperatingHour:
    facility = get_facility_for_update(facility_id, require_active=True)
    normalized_day = _validate_day_of_week(day_of_week)
    normalized_period_order = require_positive_smallint(value=period_order, label="Period order")
    validate_open_close_shape(
        is_24_hours=is_24_hours,
        opens_at=opens_at,
        closes_at=closes_at,
        closes_next_day=closes_next_day,
        closed_label="Closed rows",
    )

    new_row = FacilityOperatingHour(
        facility=facility,
        day_of_week=normalized_day,
        period_order=normalized_period_order,
        opens_at=opens_at,
        closes_at=closes_at,
        closes_next_day=closes_next_day,
        is_24_hours=is_24_hours,
    )
    start, end = operating_day_range(new_row)
    ensure_unique_active_operating_hours(
        facility=facility,
        day_of_week=normalized_day,
        new_start=start,
        new_end=end,
    )

    try:
        return FacilityOperatingHour.objects.create(
            facility=facility,
            day_of_week=normalized_day,
            period_order=normalized_period_order,
            opens_at=opens_at,
            closes_at=closes_at,
            closes_next_day=closes_next_day,
            is_24_hours=is_24_hours,
        )
    except IntegrityError as exc:
        raise ConflictError("Facility operating hour could not be created because it already exists.") from exc


@transaction.atomic
def update_facility_operating_hour(
    *,
    facility_operating_hour_id,
    **updates,
) -> FacilityOperatingHour:
    operating_hour = get_operating_hour_for_update(facility_operating_hour_id)
    allowed_fields = {"facility_id", "day_of_week", "period_order", "opens_at", "closes_at", "closes_next_day", "is_24_hours"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        raise ValidationError(f"Unsupported facility operating hour update fields: {', '.join(sorted(unexpected_fields))}.")

    facility = (
        get_facility_for_update(updates["facility_id"], require_active=True)
        if "facility_id" in updates
        else get_facility_for_update(operating_hour.facility_id, require_active=True)
    )
    day_of_week = _validate_day_of_week(updates.get("day_of_week", operating_hour.day_of_week))
    period_order = require_positive_smallint(
        value=updates.get("period_order", operating_hour.period_order),
        label="Period order",
    )
    opens_at = updates.get("opens_at", operating_hour.opens_at)
    closes_at = updates.get("closes_at", operating_hour.closes_at)
    closes_next_day = updates.get("closes_next_day", operating_hour.closes_next_day)
    is_24_hours = updates.get("is_24_hours", operating_hour.is_24_hours)

    validate_open_close_shape(
        is_24_hours=is_24_hours,
        opens_at=opens_at,
        closes_at=closes_at,
        closes_next_day=closes_next_day,
        closed_label="Closed rows",
    )

    candidate = FacilityOperatingHour(
        facility=facility,
        day_of_week=day_of_week,
        period_order=period_order,
        opens_at=opens_at,
        closes_at=closes_at,
        closes_next_day=closes_next_day,
        is_24_hours=is_24_hours,
    )
    start, end = operating_day_range(candidate)
    ensure_unique_active_operating_hours(
        facility=facility,
        day_of_week=day_of_week,
        operating_hour_id=operating_hour.id,
        new_start=start,
        new_end=end,
    )

    operating_hour.facility = facility
    operating_hour.day_of_week = day_of_week
    operating_hour.period_order = period_order
    operating_hour.opens_at = opens_at
    operating_hour.closes_at = closes_at
    operating_hour.closes_next_day = closes_next_day
    operating_hour.is_24_hours = is_24_hours

    try:
        operating_hour.save()
    except IntegrityError as exc:
        raise ConflictError("Facility operating hour could not be updated because it already exists.") from exc
    return operating_hour


@transaction.atomic
def deactivate_facility_operating_hour(*, facility_operating_hour_id) -> FacilityOperatingHour:
    operating_hour = get_operating_hour_for_update(facility_operating_hour_id)
    if not operating_hour.is_active:
        return operating_hour

    operating_hour.is_active = False
    operating_hour.save(update_fields=["is_active", "updated_at"])
    return operating_hour
