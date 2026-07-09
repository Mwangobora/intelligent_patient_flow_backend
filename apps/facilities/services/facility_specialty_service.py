from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.facilities.models import FacilitySpecialty
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    ensure_department_in_facility,
    get_department_for_update,
    get_facility_for_update,
    get_facility_specialty_for_update,
    get_specialty_for_update,
    require_positive_smallint,
)


@transaction.atomic
def create_facility_specialty(
    *,
    facility_id,
    specialty_id,
    appointment_duration_minutes,
    department_id=None,
    accepts_appointments: bool = True,
    accepts_walk_ins: bool = False,
    requires_referral: bool = False,
) -> FacilitySpecialty:
    facility = get_facility_for_update(facility_id, require_active=True)
    specialty = get_specialty_for_update(specialty_id, require_active=True)
    department = get_department_for_update(department_id, require_active=True) if department_id else None
    ensure_department_in_facility(
        department=department,
        facility=facility,
        message="Facility specialty department must belong to the same facility.",
    )
    duration = require_positive_smallint(
        value=appointment_duration_minutes,
        label="Appointment duration minutes",
    )

    try:
        return FacilitySpecialty.objects.create(
            facility=facility,
            specialty=specialty,
            department=department,
            appointment_duration_minutes=duration,
            accepts_appointments=accepts_appointments,
            accepts_walk_ins=accepts_walk_ins,
            requires_referral=requires_referral,
        )
    except IntegrityError as exc:
        raise ConflictError("Facility specialty could not be created because it already exists.") from exc


@transaction.atomic
def update_facility_specialty(
    *,
    facility_specialty_id,
    **updates,
) -> FacilitySpecialty:
    facility_specialty = get_facility_specialty_for_update(facility_specialty_id)
    allowed_fields = {
        "facility_id",
        "specialty_id",
        "department_id",
        "appointment_duration_minutes",
        "accepts_appointments",
        "accepts_walk_ins",
        "requires_referral",
    }
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        raise ValidationError(f"Unsupported facility specialty update fields: {', '.join(sorted(unexpected_fields))}.")

    facility = (
        get_facility_for_update(updates["facility_id"], require_active=True)
        if "facility_id" in updates
        else get_facility_for_update(facility_specialty.facility_id, require_active=True)
    )
    specialty = (
        get_specialty_for_update(updates["specialty_id"], require_active=True)
        if "specialty_id" in updates
        else get_specialty_for_update(facility_specialty.specialty_id, require_active=True)
    )
    department = (
        get_department_for_update(updates["department_id"], require_active=True)
        if "department_id" in updates and updates["department_id"] is not None
        else None if "department_id" in updates else facility_specialty.department
    )
    ensure_department_in_facility(
        department=department,
        facility=facility,
        message="Facility specialty department must belong to the same facility.",
    )

    facility_specialty.facility = facility
    facility_specialty.specialty = specialty
    facility_specialty.department = department
    if "appointment_duration_minutes" in updates:
        facility_specialty.appointment_duration_minutes = require_positive_smallint(
            value=updates["appointment_duration_minutes"],
            label="Appointment duration minutes",
        )
    if "accepts_appointments" in updates:
        facility_specialty.accepts_appointments = bool(updates["accepts_appointments"])
    if "accepts_walk_ins" in updates:
        facility_specialty.accepts_walk_ins = bool(updates["accepts_walk_ins"])
    if "requires_referral" in updates:
        facility_specialty.requires_referral = bool(updates["requires_referral"])

    try:
        facility_specialty.save()
    except IntegrityError as exc:
        raise ConflictError("Facility specialty could not be updated because it already exists.") from exc
    return facility_specialty


@transaction.atomic
def deactivate_facility_specialty(*, facility_specialty_id) -> FacilitySpecialty:
    facility_specialty = get_facility_specialty_for_update(facility_specialty_id)
    if not facility_specialty.is_active:
        return facility_specialty

    facility_specialty.is_active = False
    facility_specialty.save(update_fields=["is_active", "updated_at"])
    return facility_specialty
