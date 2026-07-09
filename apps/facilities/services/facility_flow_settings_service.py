from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.facilities.models import FacilityFlowSetting
from common.exceptions import ConflictError, ValidationError

from ._shared import get_facility_for_update, get_flow_setting_for_update, get_user


def _validate_nonnegative(value, label: str) -> int:
    if value is None:
        raise ValidationError(f"{label} is required.")
    if value < 0:
        raise ValidationError(f"{label} must be greater than or equal to 0.")
    return int(value)


def _validate_flow_values(*, queue_number_padding, **values) -> dict:
    cleaned = {key: _validate_nonnegative(value, key.replace("_", " ").capitalize()) for key, value in values.items()}
    if queue_number_padding < 1 or queue_number_padding > 6:
        raise ValidationError("Queue number padding must be between 1 and 6.")
    cleaned["queue_number_padding"] = int(queue_number_padding)
    return cleaned


@transaction.atomic
def create_facility_flow_settings(
    *,
    facility_id,
    max_advance_booking_days: int = 30,
    minimum_booking_notice_minutes: int = 0,
    cancellation_cutoff_minutes: int = 60,
    reschedule_cutoff_minutes: int = 60,
    early_checkin_minutes: int = 30,
    late_checkin_grace_minutes: int = 15,
    no_show_after_minutes: int = 15,
    default_reminder_minutes_before: int | None = 1440,
    queue_number_padding: int = 3,
    auto_create_daily_queues: bool = False,
    created_by_id=None,
) -> FacilityFlowSetting:
    facility = get_facility_for_update(facility_id, require_active=True)
    if FacilityFlowSetting.objects.select_for_update().filter(facility=facility).exists():
        raise ConflictError("Facility flow settings already exist for this facility.")

    values = _validate_flow_values(
        max_advance_booking_days=max_advance_booking_days,
        minimum_booking_notice_minutes=minimum_booking_notice_minutes,
        cancellation_cutoff_minutes=cancellation_cutoff_minutes,
        reschedule_cutoff_minutes=reschedule_cutoff_minutes,
        early_checkin_minutes=early_checkin_minutes,
        late_checkin_grace_minutes=late_checkin_grace_minutes,
        no_show_after_minutes=no_show_after_minutes,
        queue_number_padding=queue_number_padding,
    )
    if default_reminder_minutes_before is not None:
        values["default_reminder_minutes_before"] = _validate_nonnegative(
            default_reminder_minutes_before,
            "Default reminder minutes before",
        )
    created_by = get_user(created_by_id, field_label="Creator") if created_by_id is not None else None

    try:
        return FacilityFlowSetting.objects.create(
            facility=facility,
            auto_create_daily_queues=auto_create_daily_queues,
            created_by=created_by,
            **values,
        )
    except IntegrityError as exc:
        raise ConflictError("Facility flow settings could not be created because they already exist.") from exc


@transaction.atomic
def update_facility_flow_settings(
    *,
    facility_flow_setting_id,
    **updates,
) -> FacilityFlowSetting:
    flow_settings = get_flow_setting_for_update(facility_flow_setting_id)
    allowed_fields = {
        "facility_id",
        "max_advance_booking_days",
        "minimum_booking_notice_minutes",
        "cancellation_cutoff_minutes",
        "reschedule_cutoff_minutes",
        "early_checkin_minutes",
        "late_checkin_grace_minutes",
        "no_show_after_minutes",
        "default_reminder_minutes_before",
        "queue_number_padding",
        "auto_create_daily_queues",
        "created_by_id",
    }
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        raise ValidationError(f"Unsupported facility flow settings update fields: {', '.join(sorted(unexpected_fields))}.")

    if "facility_id" in updates:
        facility = get_facility_for_update(updates["facility_id"], require_active=True)
        if FacilityFlowSetting.objects.select_for_update().exclude(pk=flow_settings.pk).filter(facility=facility).exists():
            raise ConflictError("Facility flow settings already exist for this facility.")
        flow_settings.facility = facility

    default_reminder = updates.get("default_reminder_minutes_before", flow_settings.default_reminder_minutes_before)
    values = _validate_flow_values(
        max_advance_booking_days=updates.get("max_advance_booking_days", flow_settings.max_advance_booking_days),
        minimum_booking_notice_minutes=updates.get("minimum_booking_notice_minutes", flow_settings.minimum_booking_notice_minutes),
        cancellation_cutoff_minutes=updates.get("cancellation_cutoff_minutes", flow_settings.cancellation_cutoff_minutes),
        reschedule_cutoff_minutes=updates.get("reschedule_cutoff_minutes", flow_settings.reschedule_cutoff_minutes),
        early_checkin_minutes=updates.get("early_checkin_minutes", flow_settings.early_checkin_minutes),
        late_checkin_grace_minutes=updates.get("late_checkin_grace_minutes", flow_settings.late_checkin_grace_minutes),
        no_show_after_minutes=updates.get("no_show_after_minutes", flow_settings.no_show_after_minutes),
        queue_number_padding=updates.get("queue_number_padding", flow_settings.queue_number_padding),
    )
    if default_reminder is None:
        values["default_reminder_minutes_before"] = None
    else:
        values["default_reminder_minutes_before"] = _validate_nonnegative(
            default_reminder,
            "Default reminder minutes before",
        )

    for field_name, value in values.items():
        setattr(flow_settings, field_name, value)

    if "auto_create_daily_queues" in updates:
        flow_settings.auto_create_daily_queues = bool(updates["auto_create_daily_queues"])
    if "created_by_id" in updates:
        flow_settings.created_by = get_user(updates["created_by_id"], field_label="Creator") if updates["created_by_id"] else None

    try:
        flow_settings.save()
    except IntegrityError as exc:
        raise ConflictError("Facility flow settings could not be updated because a unique value already exists.") from exc
    return flow_settings
