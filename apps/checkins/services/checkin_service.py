from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.checkins.models import PatientCheckin
from apps.scheduling.models import Appointment
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    get_appointment,
    get_checkin,
    get_facility,
    get_facility_specialty,
    get_patient,
    get_user,
    move_appointment_to_checked_in,
    normalize_optional_text,
    validate_appointment_eligible_for_checkin,
    validate_checked_in_at,
    validate_patient_facility_scope,
)
from .checkin_queue_service import enqueue_checkin_after_arrival


def _validate_checkin_method(checkin_method: str) -> None:
    if checkin_method not in PatientCheckin.CheckinMethod.values:
        raise ValidationError("Invalid check-in method.")


def _validate_reception_actor(*, checkin_method: str, checked_in_by) -> None:
    if checkin_method == PatientCheckin.CheckinMethod.RECEPTION and checked_in_by is None:
        raise ValidationError("Reception check-in requires checked_in_by.")


def _active_checkin_exists_for_appointment(*, appointment: Appointment) -> bool:
    return PatientCheckin.objects.select_for_update().filter(
        appointment=appointment,
        voided_at__isnull=True,
    ).exists()


@transaction.atomic
def create_appointment_checkin(
    *,
    facility_id,
    patient_id,
    appointment_id,
    checkin_method,
    facility_specialty_id=None,
    checked_in_at=None,
    checked_in_by_id=None,
    notes: str | None = None,
) -> PatientCheckin:
    _validate_checkin_method(checkin_method)
    facility = get_facility(facility_id, active_only=True, for_update=True)
    patient = get_patient(patient_id, active_only=True, for_update=True)
    appointment = get_appointment(appointment_id, for_update=True)
    checked_in_by = get_user(checked_in_by_id, field_label="Checked-in by user", active_only=True) if checked_in_by_id is not None else None
    specialty = get_facility_specialty(facility_specialty_id, active_only=True, for_update=True) if facility_specialty_id is not None else appointment.facility_specialty
    checkin_time = checked_in_at or timezone.now()

    validate_patient_facility_scope(patient=patient, facility=facility)
    validate_appointment_eligible_for_checkin(appointment=appointment, patient=patient, facility=facility)
    validate_checked_in_at(checkin_time)
    _validate_reception_actor(checkin_method=checkin_method, checked_in_by=checked_in_by)

    if specialty.id != appointment.facility_specialty_id:
        raise ValidationError("Check-in specialty must match appointment specialty.")
    if _active_checkin_exists_for_appointment(appointment=appointment):
        raise ConflictError("Appointment already has a non-voided check-in.")

    try:
        checkin = PatientCheckin.objects.create(
            facility=facility,
            patient=patient,
            appointment=appointment,
            facility_specialty=specialty,
            checkin_method=checkin_method,
            checked_in_at=checkin_time,
            checked_in_by=checked_in_by,
            notes=normalize_optional_text(notes),
        )
    except IntegrityError as exc:
        raise ConflictError("Check-in could not be created because a conflicting record already exists.") from exc

    move_appointment_to_checked_in(appointment=appointment, changed_by_id=checked_in_by_id)
    enqueue_checkin_after_arrival(checkin_id=checkin.id, created_by_id=checked_in_by_id)
    checkin.refresh_from_db()
    return checkin


@transaction.atomic
def create_walkin_checkin(
    *,
    facility_id,
    patient_id,
    facility_specialty_id,
    checkin_method,
    checked_in_at=None,
    checked_in_by_id=None,
    notes: str | None = None,
) -> PatientCheckin:
    _validate_checkin_method(checkin_method)
    facility = get_facility(facility_id, active_only=True, for_update=True)
    patient = get_patient(patient_id, active_only=True, for_update=True)
    specialty = get_facility_specialty(facility_specialty_id, active_only=True, for_update=True)
    checked_in_by = get_user(checked_in_by_id, field_label="Checked-in by user", active_only=True) if checked_in_by_id is not None else None
    checkin_time = checked_in_at or timezone.now()

    validate_patient_facility_scope(patient=patient, facility=facility)
    validate_checked_in_at(checkin_time)
    _validate_reception_actor(checkin_method=checkin_method, checked_in_by=checked_in_by)

    if specialty.facility_id != facility.id:
        raise ValidationError("Walk-in specialty must belong to the selected facility.")
    if not specialty.accepts_walk_ins:
        raise ValidationError("Walk-in specialty must accept walk-ins.")

    try:
        return PatientCheckin.objects.create(
            facility=facility,
            patient=patient,
            appointment=None,
            facility_specialty=specialty,
            checkin_method=checkin_method,
            checked_in_at=checkin_time,
            checked_in_by=checked_in_by,
            notes=normalize_optional_text(notes),
        )
    except IntegrityError as exc:
        raise ConflictError("Walk-in check-in could not be created because a conflicting record already exists.") from exc


@transaction.atomic
def void_checkin(*, checkin_id, voided_by_id, void_reason: str, voided_at=None) -> PatientCheckin:
    checkin = get_checkin(checkin_id, for_update=True)
    voided_by = get_user(voided_by_id, field_label="Voided by user", active_only=True)
    normalized_reason = normalize_optional_text(void_reason)
    if normalized_reason is None:
        raise ValidationError("void_reason is required.")
    if checkin.voided_at is not None:
        raise ConflictError("Check-in is already voided.")

    void_time = voided_at or timezone.now()
    if void_time < checkin.checked_in_at:
        raise ValidationError("voided_at must be greater than or equal to checked_in_at.")

    checkin.voided_at = void_time
    checkin.voided_by = voided_by
    checkin.void_reason = normalized_reason
    try:
        checkin.save(update_fields=["voided_at", "voided_by", "void_reason", "updated_at"])
    except IntegrityError as exc:
        raise ConflictError("Check-in could not be voided because of a conflicting state.") from exc
    return checkin
