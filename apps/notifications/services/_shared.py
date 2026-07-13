from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.notifications.models import PatientNotification, UserPushDevice
from apps.patients.models import Patient
from apps.queueing.models import QueueEntry
from apps.scheduling.models import Appointment
from common.exceptions import NotFoundError, ValidationError

User = get_user_model()


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def safe_failure_reason(reason: str | None) -> str:
    return (clean_optional_text(reason) or "Notification delivery failed.")[:250]


def get_patient(patient_id, *, lock: bool = False) -> Patient:
    queryset = Patient.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    patient = queryset.filter(pk=patient_id).first()
    if patient is None:
        raise NotFoundError("Patient not found.")
    return patient


def get_user(user_id, *, lock: bool = False):
    queryset = User.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    user = queryset.filter(pk=user_id).first()
    if user is None:
        raise NotFoundError("User not found.")
    return user


def get_appointment(appointment_id, *, lock: bool = False) -> Appointment:
    queryset = Appointment.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    appointment = queryset.filter(pk=appointment_id).first()
    if appointment is None:
        raise NotFoundError("Appointment not found.")
    return appointment


def get_queue_entry(queue_entry_id, *, lock: bool = False) -> QueueEntry:
    queryset = QueueEntry.objects.select_related("patient_checkin")
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    queue_entry = queryset.filter(pk=queue_entry_id).first()
    if queue_entry is None:
        raise NotFoundError("Queue entry not found.")
    return queue_entry


def get_notification(notification_id, *, lock: bool = False) -> PatientNotification:
    queryset = PatientNotification.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    notification = queryset.filter(pk=notification_id).first()
    if notification is None:
        raise NotFoundError("Notification not found.")
    return notification


def get_push_device(device_id, *, lock: bool = False) -> UserPushDevice:
    queryset = UserPushDevice.objects.all()
    if lock:
        queryset = queryset.select_for_update()
    device = queryset.filter(pk=device_id).first()
    if device is None:
        raise NotFoundError("Push device not found.")
    return device


def validate_patient_is_active(patient: Patient) -> None:
    if not patient.is_active:
        raise ValidationError("Patient must be active.")


def validate_user_is_active(user) -> None:
    if not user.is_active:
        raise ValidationError("User must be active.")


def validate_recipient_user(patient: Patient, recipient_user) -> None:
    if recipient_user is None:
        return
    validate_user_is_active(recipient_user)
    if patient.user_id != recipient_user.id:
        raise ValidationError("Notification recipient user must be linked to the patient.")


def validate_notification_source(*, patient: Patient, appointment: Appointment | None, queue_entry: QueueEntry | None) -> None:
    if appointment is not None and queue_entry is not None:
        raise ValidationError("Only one direct notification source is allowed.")
    if appointment is not None and appointment.patient_id != patient.id:
        raise ValidationError("Notification appointment does not belong to the patient.")
    if queue_entry is not None and queue_entry.patient_checkin.patient_id != patient.id:
        raise ValidationError("Notification queue entry does not belong to the patient.")


def resolve_scheduled_for(scheduled_for=None):
    return scheduled_for or timezone.now()
