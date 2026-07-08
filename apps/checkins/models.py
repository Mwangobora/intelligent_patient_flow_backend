from __future__ import annotations

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.facilities.models import Facility, FacilitySpecialty
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from common.db import TimeStampedModel

hash_validator = RegexValidator(regex=r"^[0-9A-Fa-f]{64}$", message="Hash values must be 64 hexadecimal characters.")


class PatientCheckin(TimeStampedModel):
    class CheckinMethod(models.TextChoices):
        RECEPTION = "reception", "Reception"
        MOBILE = "mobile", "Mobile"
        QR_CODE = "qr_code", "QR Code"
        SELF_SERVICE = "self_service", "Self Service"

    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="patient_checkins")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="checkins")
    appointment = models.ForeignKey(Appointment, on_delete=models.PROTECT, related_name="patient_checkins", blank=True, null=True)
    facility_specialty = models.ForeignKey(FacilitySpecialty, on_delete=models.PROTECT, related_name="patient_checkins", blank=True, null=True)
    checkin_method = models.CharField(max_length=20, choices=CheckinMethod.choices)
    checked_in_at = models.DateTimeField(default=timezone.now)
    checked_in_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="checked_in_patients", blank=True, null=True)
    notes = models.CharField(max_length=250, blank=True, null=True)
    voided_at = models.DateTimeField(blank=True, null=True)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="voided_patient_checkins", blank=True, null=True)
    void_reason = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        db_table = "patient_checkins"
        constraints = [
            models.UniqueConstraint(fields=["appointment"], condition=Q(appointment__isnull=False, voided_at__isnull=True), name="uq_patient_checkins_active_appointment"),
            models.CheckConstraint(condition=Q(checkin_method__in=[c for c, _ in CheckinMethod.choices]), name="ck_patient_checkins_method"),
            models.CheckConstraint(condition=Q(appointment__isnull=False) | Q(facility_specialty__isnull=False), name="ck_patient_checkins_walkin_specialty"),
            models.CheckConstraint(
                condition=((Q(voided_at__isnull=True) & Q(voided_by__isnull=True) & Q(void_reason__isnull=True))
                           | (Q(voided_at__isnull=False) & Q(voided_by__isnull=False) & Q(void_reason__isnull=False) & Q(voided_at__gte=F("checked_in_at")))),
                name="ck_patient_checkins_void",
            ),
        ]
        indexes = [
            models.Index(fields=["facility", "checked_in_at"], name="idx_patient_checkins_facility_time"),
            models.Index(fields=["patient", "checked_in_at"], name="idx_patient_checkins_patient_time"),
            models.Index(fields=["facility_specialty"], name="idx_patient_checkins_specialty"),
        ]

    # TODO: enforce patient check-in validation trigger from the SQL file in a custom migration.


class CheckinToken(models.Model):
    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4, editable=False)
    appointment = models.ForeignKey(Appointment, on_delete=models.PROTECT, related_name="checkin_tokens")
    token_hash = models.CharField(max_length=64, validators=[hash_validator])
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(blank=True, null=True)
    patient_checkin = models.ForeignKey(PatientCheckin, on_delete=models.PROTECT, related_name="checkin_tokens", blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="revoked_checkin_tokens", blank=True, null=True)
    revocation_reason = models.CharField(max_length=250, blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_checkin_tokens", blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "checkin_tokens"
        constraints = [
            models.UniqueConstraint(fields=["token_hash"], name="uq_checkin_tokens_hash"),
            models.UniqueConstraint(fields=["appointment"], condition=Q(used_at__isnull=True, revoked_at__isnull=True), name="uq_checkin_tokens_active_appointment"),
            models.UniqueConstraint(fields=["patient_checkin"], condition=Q(patient_checkin__isnull=False), name="uq_checkin_tokens_checkin"),
            models.CheckConstraint(condition=Q(token_hash__regex=r"^[0-9A-Fa-f]{64}$"), name="ck_checkin_tokens_hash"),
            models.CheckConstraint(condition=Q(expires_at__gt=F("created_at")), name="ck_checkin_tokens_expiry"),
        ]
        indexes = [
            models.Index(fields=["appointment"], name="idx_checkin_tokens_appointment"),
            models.Index(fields=["expires_at"], name="idx_checkin_tokens_expiry", condition=Q(used_at__isnull=True, revoked_at__isnull=True)),
        ]

    # TODO: enforce check-in token state and validation trigger from the SQL file in a custom migration.
