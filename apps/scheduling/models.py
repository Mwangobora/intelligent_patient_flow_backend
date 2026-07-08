from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.facilities.models import Facility, FacilitySpecialty
from apps.patients.models import Patient
from apps.practitioners.models import (
    PractitionerDepartmentAssignment,
    PractitionerFacilityAssignment,
    PractitionerSpecialtyAssignment,
)
from common.db import ActiveModel, TimeStampedModel


class PractitionerAvailabilityPeriod(TimeStampedModel, ActiveModel):
    practitioner_facility_assignment = models.ForeignKey(PractitionerFacilityAssignment, on_delete=models.PROTECT, related_name="availability_periods")
    day_of_week = models.SmallIntegerField()
    starts_at = models.TimeField()
    ends_at = models.TimeField()
    valid_from = models.DateField()
    valid_until = models.DateField(blank=True, null=True)
    is_available_for_appointments = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_practitioner_availability_periods", blank=True, null=True)

    class Meta:
        db_table = "practitioner_availability_periods"
        constraints = [
            models.UniqueConstraint(fields=["practitioner_facility_assignment", "day_of_week", "starts_at", "ends_at", "valid_from"], name="uq_practitioner_availability_exact"),
            models.CheckConstraint(condition=Q(day_of_week__gte=1, day_of_week__lte=7), name="ck_practitioner_availability_day"),
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="ck_practitioner_availability_times"),
            models.CheckConstraint(condition=Q(valid_until__isnull=True) | Q(valid_until__gte=F("valid_from")), name="ck_practitioner_availability_dates"),
        ]
        indexes = [
            models.Index(fields=["practitioner_facility_assignment", "day_of_week", "is_active"], name="idx_practitioner_availability_lookup"),
            models.Index(fields=["valid_from", "valid_until"], name="idx_practitioner_availability_dates"),
        ]

  
class PractitionerLeaveRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    practitioner_facility_assignment = models.ForeignKey(PractitionerFacilityAssignment, on_delete=models.PROTECT, related_name="leave_requests")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.CharField(max_length=250, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="requested_practitioner_leave_requests", blank=True, null=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="decided_practitioner_leave_requests", blank=True, null=True)
    decided_at = models.DateTimeField(blank=True, null=True)
    decision_note = models.CharField(max_length=250, blank=True, null=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="cancelled_practitioner_leave_requests", blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancellation_reason = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        db_table = "practitioner_leave_requests"
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="ck_practitioner_leave_times"),
            models.CheckConstraint(condition=Q(status__in=[c for c, _ in Status.choices]), name="ck_practitioner_leave_status"),
            models.CheckConstraint(
                condition=(
                    (Q(status=Status.PENDING) & Q(decided_by__isnull=True) & Q(decided_at__isnull=True) & Q(cancelled_by__isnull=True) & Q(cancelled_at__isnull=True) & Q(cancellation_reason__isnull=True))
                    | (Q(status__in=[Status.APPROVED, Status.REJECTED]) & Q(decided_by__isnull=False) & Q(decided_at__isnull=False) & Q(cancelled_by__isnull=True) & Q(cancelled_at__isnull=True) & Q(cancellation_reason__isnull=True))
                    | (Q(status=Status.CANCELLED) & Q(cancelled_by__isnull=False) & Q(cancelled_at__isnull=False) & Q(cancellation_reason__isnull=False))
                ),
                name="ck_practitioner_leave_state",
            ),
        ]
        indexes = [models.Index(fields=["practitioner_facility_assignment", "status", "starts_at", "ends_at"], name="idx_practitioner_leave_lookup")]


class PractitionerShift(TimeStampedModel):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    practitioner_facility_assignment = models.ForeignKey(PractitionerFacilityAssignment, on_delete=models.PROTECT, related_name="shifts")
    practitioner_department_assignment = models.ForeignKey(PractitionerDepartmentAssignment, on_delete=models.PROTECT, related_name="shifts", blank=True, null=True)
    service_point = models.ForeignKey("facilities.ServicePoint", on_delete=models.PROTECT, related_name="practitioner_shifts", blank=True, null=True)
    consultation_room = models.ForeignKey("facilities.ConsultationRoom", on_delete=models.PROTECT, related_name="practitioner_shifts", blank=True, null=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    actual_started_at = models.DateTimeField(blank=True, null=True)
    actual_ended_at = models.DateTimeField(blank=True, null=True)
    accepts_appointments = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    notes = models.CharField(max_length=250, blank=True, null=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="cancelled_practitioner_shifts", blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancellation_reason = models.CharField(max_length=250, blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_practitioner_shifts", blank=True, null=True)

    class Meta:
        db_table = "practitioner_shifts"
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="ck_practitioner_shifts_times"),
            models.CheckConstraint(condition=Q(status__in=[c for c, _ in Status.choices]), name="ck_practitioner_shifts_status"),
            models.CheckConstraint(condition=Q(actual_ended_at__isnull=True) | (Q(actual_started_at__isnull=False) & Q(actual_ended_at__gt=F("actual_started_at"))), name="ck_practitioner_shifts_actual_times"),
        ]
        indexes = [
            models.Index(fields=["practitioner_facility_assignment", "starts_at", "ends_at"], name="idx_practitioner_shifts_practitioner_time"),
            models.Index(fields=["practitioner_department_assignment"], name="idx_practitioner_shifts_department"),
            models.Index(fields=["service_point", "starts_at", "ends_at"], name="idx_practitioner_shifts_service_point_time"),
            models.Index(fields=["consultation_room", "starts_at", "ends_at"], name="idx_practitioner_shifts_room_time"),
            models.Index(fields=["status"], name="idx_practitioner_shifts_status"),
        ]



class AppointmentSlot(TimeStampedModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        FULL = "full", "Full"
        BLOCKED = "blocked", "Blocked"
        CANCELLED = "cancelled", "Cancelled"

    practitioner_shift = models.ForeignKey(PractitionerShift, on_delete=models.PROTECT, related_name="appointment_slots")
    facility_specialty = models.ForeignKey(FacilitySpecialty, on_delete=models.PROTECT, related_name="appointment_slots")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    capacity = models.SmallIntegerField(default=1)
    booked_count = models.SmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    is_online_bookable = models.BooleanField(default=True)

    class Meta:
        db_table = "appointment_slots"
        constraints = [
            models.UniqueConstraint(fields=["practitioner_shift", "facility_specialty", "starts_at", "ends_at"], name="uq_appointment_slots_exact"),
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="ck_appointment_slots_times"),
            models.CheckConstraint(condition=Q(capacity__gt=0), name="ck_appointment_slots_capacity"),
            models.CheckConstraint(condition=Q(booked_count__gte=0) & Q(booked_count__lte=F("capacity")), name="ck_appointment_slots_booked_count"),
            models.CheckConstraint(condition=Q(status__in=[c for c, _ in Status.choices]), name="ck_appointment_slots_status"),
        ]
        indexes = [
            models.Index(fields=["practitioner_shift", "starts_at"], name="idx_appointment_slots_shift_time"),
            models.Index(fields=["facility_specialty", "starts_at"], name="idx_appointment_slots_specialty_time"),
            models.Index(fields=["starts_at"], name="idx_appointment_slots_available", condition=Q(status="available", is_online_bookable=True)),
        ]



class Appointment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CHECKED_IN = "checked_in", "Checked In"
        QUEUED = "queued", "Queued"
        IN_SERVICE = "in_service", "In Service"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No Show"
        RESCHEDULED = "rescheduled", "Rescheduled"

    class BookingChannel(models.TextChoices):
        MOBILE = "mobile", "Mobile"
        WEB = "web", "Web"
        RECEPTION = "reception", "Reception"
        API = "api", "API"

    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="appointments")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="appointments")
    facility_specialty = models.ForeignKey(FacilitySpecialty, on_delete=models.PROTECT, related_name="appointments")
    practitioner_facility_assignment = models.ForeignKey(PractitionerFacilityAssignment, on_delete=models.PROTECT, related_name="appointments", blank=True, null=True)
    practitioner_specialty_assignment = models.ForeignKey(PractitionerSpecialtyAssignment, on_delete=models.PROTECT, related_name="appointments", blank=True, null=True)
    practitioner_shift = models.ForeignKey(PractitionerShift, on_delete=models.PROTECT, related_name="appointments", blank=True, null=True)
    appointment_slot = models.ForeignKey("scheduling.AppointmentSlot", on_delete=models.PROTECT, related_name="appointments", blank=True, null=True)
    appointment_number = models.CharField(max_length=50)
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    booking_channel = models.CharField(max_length=20, choices=BookingChannel.choices)
    reason_for_visit_encrypted = models.TextField(blank=True, null=True)
    rescheduled_from = models.ForeignKey("self", on_delete=models.PROTECT, related_name="reschedules", blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="cancelled_appointments", blank=True, null=True)
    cancellation_reason = models.CharField(max_length=250, blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_appointments", blank=True, null=True)

    class Meta:
        db_table = "appointments"
        constraints = [
            models.UniqueConstraint(fields=["facility", "appointment_number"], name="uq_appointments_facility_number"),
            models.CheckConstraint(condition=Q(scheduled_end__gt=F("scheduled_start")), name="ck_appointments_times"),
            models.CheckConstraint(condition=Q(status__in=[c for c, _ in Status.choices]), name="ck_appointments_status"),
            models.CheckConstraint(condition=Q(booking_channel__in=[c for c, _ in BookingChannel.choices]), name="ck_appointments_booking_channel"),
            models.CheckConstraint(condition=Q(rescheduled_from__isnull=True) | ~Q(rescheduled_from=F("id")), name="ck_appointments_no_self_reschedule"),
            models.CheckConstraint(
                condition=(
                    (Q(status=Status.CANCELLED) & Q(cancelled_at__isnull=False) & Q(cancelled_by__isnull=False) & Q(cancellation_reason__isnull=False))
                    | (Q(status__in=[c for c, _ in Status.choices if c != Status.CANCELLED]) & Q(cancelled_at__isnull=True) & Q(cancelled_by__isnull=True) & Q(cancellation_reason__isnull=True))
                ),
                name="ck_appointments_cancellation",
            ),
            models.CheckConstraint(
                condition=((Q(practitioner_facility_assignment__isnull=True) & Q(practitioner_specialty_assignment__isnull=True) & Q(practitioner_shift__isnull=True) & Q(appointment_slot__isnull=True))
                           | (Q(practitioner_facility_assignment__isnull=False) & Q(practitioner_specialty_assignment__isnull=False))),
                name="ck_appointments_practitioner_assignment_bundle",
            ),
        ]
        indexes = [
            models.Index(fields=["facility", "scheduled_start"], name="idx_appointments_facility_time"),
            models.Index(fields=["patient", "scheduled_start"], name="idx_appointments_patient_time"),
            models.Index(fields=["facility_specialty", "scheduled_start"], name="idx_appointments_specialty_time"),
            models.Index(fields=["practitioner_facility_assignment", "scheduled_start"], name="idx_appointments_practitioner_time"),
            models.Index(fields=["practitioner_shift"], name="idx_appointments_shift"),
            models.Index(fields=["appointment_slot"], name="idx_appointments_slot"),
            models.Index(fields=["status", "scheduled_start"], name="idx_appointments_status_time"),
            models.Index(fields=["rescheduled_from"], name="idx_appointments_rescheduled_from"),
        ]

    # TODO: enforce appointment validation triggers and PostgreSQL exclusion constraints from the SQL file in a custom migration.


class AppointmentStatusHistory(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CHECKED_IN = "checked_in", "Checked In"
        QUEUED = "queued", "Queued"
        IN_SERVICE = "in_service", "In Service"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No Show"
        RESCHEDULED = "rescheduled", "Rescheduled"

    class ChangeSource(models.TextChoices):
        WEB = "web", "Web"
        MOBILE = "mobile", "Mobile"
        RECEPTION = "reception", "Reception"
        SYSTEM = "system", "System"
        API = "api", "API"

    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4, editable=False)
    appointment = models.ForeignKey(Appointment, on_delete=models.PROTECT, related_name="status_history")
    from_status = models.CharField(max_length=20, choices=Status.choices, blank=True, null=True)
    to_status = models.CharField(max_length=20, choices=Status.choices)
    change_source = models.CharField(max_length=20, choices=ChangeSource.choices)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="changed_appointment_statuses", blank=True, null=True)
    reason = models.CharField(max_length=250, blank=True, null=True)
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "appointment_status_history"
        constraints = [
            models.UniqueConstraint(fields=["appointment"], condition=Q(from_status__isnull=True), name="uq_appointment_history_one_initial"),
            models.CheckConstraint(condition=Q(from_status__isnull=True) | Q(from_status__in=[c for c, _ in Status.choices]), name="ck_appointment_history_from_status"),
            models.CheckConstraint(condition=Q(to_status__in=[c for c, _ in Status.choices]), name="ck_appointment_history_to_status"),
            models.CheckConstraint(condition=Q(change_source__in=[c for c, _ in ChangeSource.choices]), name="ck_appointment_history_source"),
            models.CheckConstraint(condition=Q(from_status__isnull=True) | ~Q(from_status=F("to_status")), name="ck_appointment_history_change"),
        ]
        indexes = [
            models.Index(fields=["appointment", "changed_at"], name="idx_appointment_history_appointment_time"),
            models.Index(fields=["to_status", "changed_at"], name="idx_appointment_history_status_time"),
        ]
