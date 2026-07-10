from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import User
from apps.checkins.models import CheckinToken, PatientCheckin
from apps.facilities.models import Facility, FacilitySpecialty
from apps.patients.models import Patient
from apps.scheduling.models import Appointment, AppointmentStatusHistory
from apps.scheduling.services import change_appointment_status, mark_checked_in
from common.exceptions import NotFoundError, ValidationError

TERMINAL_APPOINTMENT_STATUSES = {
    Appointment.Status.CANCELLED,
    Appointment.Status.COMPLETED,
    Appointment.Status.NO_SHOW,
    Appointment.Status.RESCHEDULED,
}

FUTURE_CHECKIN_GRACE = timedelta(minutes=5)


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


def get_facility(facility_id, *, active_only: bool = False, for_update: bool = False) -> Facility:
    queryset = Facility.objects.select_related("organization")
    if for_update:
        queryset = Facility.objects.select_for_update().select_related("organization")
    if active_only:
        queryset = queryset.filter(is_active=True)
    facility = queryset.filter(pk=facility_id).first()
    if facility is None:
        raise NotFoundError("Facility not found.")
    return facility


def get_patient(patient_id, *, active_only: bool = False, for_update: bool = False) -> Patient:
    queryset = Patient.objects.select_related("organization")
    if for_update:
        queryset = Patient.objects.select_for_update().select_related("organization")
    if active_only:
        queryset = queryset.filter(is_active=True)
    patient = queryset.filter(pk=patient_id).first()
    if patient is None:
        raise NotFoundError("Patient not found.")
    return patient


def get_facility_specialty(specialty_id, *, active_only: bool = False, for_update: bool = False) -> FacilitySpecialty:
    queryset = FacilitySpecialty.objects.select_related("facility", "specialty", "department")
    if for_update:
        queryset = FacilitySpecialty.objects.select_for_update().select_related("facility", "specialty")
    if active_only:
        queryset = queryset.filter(is_active=True)
    specialty = queryset.filter(pk=specialty_id).first()
    if specialty is None:
        raise NotFoundError("Facility specialty not found.")
    return specialty


def get_appointment(appointment_id, *, for_update: bool = False) -> Appointment:
    queryset = Appointment.objects.select_related("facility", "patient", "facility_specialty")
    if for_update:
        queryset = Appointment.objects.select_for_update().select_related("facility", "patient", "facility_specialty")
    appointment = queryset.filter(pk=appointment_id).first()
    if appointment is None:
        raise NotFoundError("Appointment not found.")
    return appointment


def get_checkin(checkin_id, *, for_update: bool = False) -> PatientCheckin:
    queryset = PatientCheckin.objects.select_related(
        "facility",
        "patient",
        "appointment",
        "facility_specialty",
        "checked_in_by",
        "voided_by",
    )
    if for_update:
        queryset = PatientCheckin.objects.select_for_update()
    checkin = queryset.filter(pk=checkin_id).first()
    if checkin is None:
        raise NotFoundError("Check-in not found.")
    return checkin


def get_token(token_id, *, for_update: bool = False) -> CheckinToken:
    queryset = CheckinToken.objects.select_related("appointment", "patient_checkin", "revoked_by", "created_by")
    if for_update:
        queryset = CheckinToken.objects.select_for_update()
    token = queryset.filter(pk=token_id).first()
    if token is None:
        raise NotFoundError("Check-in token not found.")
    return token


def validate_patient_facility_scope(*, patient: Patient, facility: Facility) -> None:
    if patient.organization_id != facility.organization_id:
        raise ValidationError("Patient must belong to the facility organization.")


def validate_checked_in_at(checked_in_at):
    if checked_in_at is not None and checked_in_at > timezone.now() + FUTURE_CHECKIN_GRACE:
        raise ValidationError("checked_in_at cannot be unreasonably in the future.")


def validate_appointment_eligible_for_checkin(*, appointment: Appointment, patient: Patient, facility: Facility) -> None:
    if appointment.patient_id != patient.id:
        raise ValidationError("Appointment patient does not match check-in patient.")
    if appointment.facility_id != facility.id:
        raise ValidationError("Appointment facility does not match check-in facility.")
    if appointment.status in TERMINAL_APPOINTMENT_STATUSES:
        raise ValidationError("Appointment status is not eligible for check-in.")


def move_appointment_to_checked_in(*, appointment: Appointment, changed_by_id=None) -> Appointment:
    if appointment.status == Appointment.Status.CHECKED_IN:
        return appointment
    if appointment.status == Appointment.Status.PENDING:
        appointment = change_appointment_status(
            appointment_id=appointment.id,
            to_status=Appointment.Status.CONFIRMED,
            changed_by_id=changed_by_id,
            change_source=AppointmentStatusHistory.ChangeSource.API,
        )
    return mark_checked_in(
        appointment_id=appointment.id,
        changed_by_id=changed_by_id,
        change_source=AppointmentStatusHistory.ChangeSource.API,
    )
