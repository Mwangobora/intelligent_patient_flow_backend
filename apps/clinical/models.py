from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.checkins.models import PatientCheckin
from apps.facilities.models import Department, Facility, FacilitySpecialty
from apps.patients.models import Patient
from apps.practitioners.models import PractitionerFacilityAssignment
from apps.scheduling.models import Appointment
from common.db import TimeStampedModel


class Encounter(TimeStampedModel):
    class EncounterType(models.TextChoices):
        OUTPATIENT = "outpatient", "Outpatient"
        EMERGENCY = "emergency", "Emergency"
        INPATIENT = "inpatient", "Inpatient"
        FOLLOW_UP = "follow_up", "Follow Up"
        TELEMEDICINE = "telemedicine", "Telemedicine"

    class Status(models.TextChoices):
        OPENED = "opened", "Opened"
        TRIAGE = "triage", "Triage"
        WAITING_PRACTITIONER = "waiting_practitioner", "Waiting Practitioner"
        IN_CONSULTATION = "in_consultation", "In Consultation"
        AWAITING_LAB = "awaiting_lab", "Awaiting Lab"
        AWAITING_IMAGING = "awaiting_imaging", "Awaiting Imaging"
        AWAITING_REVIEW = "awaiting_review", "Awaiting Review"
        AWAITING_PHARMACY = "awaiting_pharmacy", "Awaiting Pharmacy"
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting Payment"
        ADMITTED = "admitted", "Admitted"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="encounters")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="encounters")
    patient_checkin = models.ForeignKey(
        PatientCheckin, on_delete=models.PROTECT, related_name="encounters"
    )
    appointment = models.ForeignKey(
        Appointment, on_delete=models.PROTECT, related_name="encounters", blank=True, null=True
    )
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="encounters", blank=True, null=True
    )
    facility_specialty = models.ForeignKey(
        FacilitySpecialty,
        on_delete=models.PROTECT,
        related_name="encounters",
        blank=True,
        null=True,
    )
    attending_practitioner_facility_assignment = models.ForeignKey(
        PractitionerFacilityAssignment,
        on_delete=models.PROTECT,
        related_name="attending_encounters",
        blank=True,
        null=True,
    )
    encounter_number = models.CharField(max_length=50)
    encounter_type = models.CharField(max_length=30, choices=EncounterType.choices)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPENED)
    opened_at = models.DateTimeField(default=timezone.now)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="opened_encounters",
        blank=True,
        null=True,
    )
    completed_at = models.DateTimeField(blank=True, null=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="completed_encounters",
        blank=True,
        null=True,
    )
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="cancelled_encounters",
        blank=True,
        null=True,
    )
    cancellation_reason = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        db_table = "encounters"
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "encounter_number"], name="uq_encounters_facility_number"
            ),
            models.UniqueConstraint(
                fields=["patient_checkin"],
                condition=~Q(status__in=["completed", "cancelled"]),
                name="uq_encounters_active_checkin",
            ),
            models.CheckConstraint(
                condition=Q(
                    encounter_type__in=[
                        "outpatient",
                        "emergency",
                        "inpatient",
                        "follow_up",
                        "telemedicine",
                    ]
                ),
                name="ck_encounters_type",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "opened",
                        "triage",
                        "waiting_practitioner",
                        "in_consultation",
                        "awaiting_lab",
                        "awaiting_imaging",
                        "awaiting_review",
                        "awaiting_pharmacy",
                        "awaiting_payment",
                        "admitted",
                        "completed",
                        "cancelled",
                    ]
                ),
                name="ck_encounters_status",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status="completed")
                    & Q(completed_at__isnull=True)
                    & Q(completed_by__isnull=True)
                )
                | (Q(status="completed") & Q(completed_at__isnull=False)),
                name="ck_encounters_completion",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status="cancelled")
                    & Q(cancelled_at__isnull=True)
                    & Q(cancelled_by__isnull=True)
                    & Q(cancellation_reason__isnull=True)
                )
                | (
                    Q(status="cancelled")
                    & Q(cancelled_at__isnull=False)
                    & Q(cancellation_reason__isnull=False)
                ),
                name="ck_encounters_cancellation",
            ),
        ]
        indexes = [
            models.Index(fields=["patient", "opened_at"], name="idx_encounters_patient_time"),
            models.Index(
                fields=["facility", "status", "opened_at"], name="idx_encounters_fac_status"
            ),
            models.Index(fields=["patient_checkin"], name="idx_encounters_checkin"),
        ]


class EncounterStatusHistory(models.Model):
    class ChangeSource(models.TextChoices):
        SYSTEM = "system", "System"
        RECEPTION = "reception", "Reception"
        TRIAGE = "triage", "Triage"
        CLINICAL = "clinical", "Clinical"
        LAB = "lab", "Lab"
        IMAGING = "imaging", "Imaging"
        PHARMACY = "pharmacy", "Pharmacy"
        BILLING = "billing", "Billing"
        ADMIN = "admin", "Admin"

    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4, editable=False)
    encounter = models.ForeignKey(
        Encounter, on_delete=models.PROTECT, related_name="status_history"
    )
    from_status = models.CharField(
        max_length=30, choices=Encounter.Status.choices, blank=True, null=True
    )
    to_status = models.CharField(max_length=30, choices=Encounter.Status.choices)
    change_source = models.CharField(
        max_length=30, choices=ChangeSource.choices, default=ChangeSource.SYSTEM
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="changed_encounter_statuses",
        blank=True,
        null=True,
    )
    reason = models.CharField(max_length=250, blank=True, null=True)
    changed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "encounter_status_history"
        constraints = [
            models.UniqueConstraint(
                fields=["encounter"],
                condition=Q(from_status__isnull=True),
                name="uq_encounter_status_history_initial",
            ),
        ]
        indexes = [
            models.Index(fields=["encounter", "changed_at"], name="idx_enc_status_hist_time"),
        ]


class TriageAssessment(TimeStampedModel):
    encounter = models.ForeignKey(
        Encounter, on_delete=models.PROTECT, related_name="triage_assessments"
    )
    performed_by_practitioner_facility_assignment = models.ForeignKey(
        PractitionerFacilityAssignment,
        on_delete=models.PROTECT,
        related_name="triage_assessments",
        blank=True,
        null=True,
    )
    triage_level = models.SmallIntegerField()
    chief_complaint_encrypted = models.TextField(blank=True, null=True)
    pain_score = models.SmallIntegerField(blank=True, null=True)
    mobility_status = models.CharField(max_length=30, blank=True, null=True)
    consciousness_level = models.CharField(max_length=30, blank=True, null=True)
    notes_encrypted = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "triage_assessments"
        constraints = [
            models.CheckConstraint(
                condition=Q(triage_level__gte=1, triage_level__lte=4),
                name="ck_triage_assessments_level",
            ),
            models.CheckConstraint(
                condition=Q(pain_score__isnull=True) | Q(pain_score__gte=0, pain_score__lte=10),
                name="ck_triage_assessments_pain",
            ),
            models.CheckConstraint(
                condition=Q(completed_at__isnull=True) | Q(completed_at__gte=F("started_at")),
                name="ck_triage_assessments_time",
            ),
        ]


class VitalSign(models.Model):
    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name="vital_signs")
    recorded_by_practitioner_facility_assignment = models.ForeignKey(
        PractitionerFacilityAssignment,
        on_delete=models.PROTECT,
        related_name="recorded_vital_signs",
        blank=True,
        null=True,
    )
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    systolic_bp = models.SmallIntegerField(blank=True, null=True)
    diastolic_bp = models.SmallIntegerField(blank=True, null=True)
    heart_rate = models.SmallIntegerField(blank=True, null=True)
    respiratory_rate = models.SmallIntegerField(blank=True, null=True)
    oxygen_saturation = models.SmallIntegerField(blank=True, null=True)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    height_cm = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    blood_glucose = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    pain_score = models.SmallIntegerField(blank=True, null=True)
    recorded_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "vital_signs"
        indexes = [
            models.Index(fields=["encounter", "recorded_at"], name="idx_vital_signs_enc_time")
        ]


class ClinicalNote(TimeStampedModel):
    class NoteType(models.TextChoices):
        CONSULTATION = "consultation", "Consultation"
        PROGRESS = "progress", "Progress"
        REVIEW = "review", "Review"
        SPECIALIST = "specialist", "Specialist"
        DISCHARGE_NOTE = "discharge_note", "Discharge Note"
        ADDENDUM = "addendum", "Addendum"

    encounter = models.ForeignKey(
        Encounter, on_delete=models.PROTECT, related_name="clinical_notes"
    )
    practitioner_facility_assignment = models.ForeignKey(
        PractitionerFacilityAssignment, on_delete=models.PROTECT, related_name="clinical_notes"
    )
    note_type = models.CharField(max_length=30, choices=NoteType.choices)
    subjective_encrypted = models.TextField(blank=True, null=True)
    objective_encrypted = models.TextField(blank=True, null=True)
    assessment_encrypted = models.TextField(blank=True, null=True)
    plan_encrypted = models.TextField(blank=True, null=True)
    supersedes_note = models.ForeignKey(
        "self", on_delete=models.PROTECT, related_name="addenda", blank=True, null=True
    )
    signed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "clinical_notes"
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    note_type__in=[
                        "consultation",
                        "progress",
                        "review",
                        "specialist",
                        "discharge_note",
                        "addendum",
                    ]
                ),
                name="ck_clinical_notes_type",
            ),
            models.CheckConstraint(
                condition=Q(supersedes_note__isnull=True) | ~Q(supersedes_note=F("id")),
                name="ck_clinical_notes_supersede",
            ),
        ]
        indexes = [models.Index(fields=["encounter", "created_at"], name="idx_clin_notes_enc_time")]


class DiagnosisCode(TimeStampedModel):
    coding_system = models.CharField(max_length=30)
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=250)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "diagnosis_codes"
        constraints = [
            models.UniqueConstraint(
                fields=["coding_system", "code"], name="uq_diagnosis_codes_system_code"
            )
        ]
        indexes = [
            models.Index(fields=["coding_system", "code"], name="idx_diagnosis_codes_lookup")
        ]


class EncounterDiagnosis(models.Model):
    class DiagnosisType(models.TextChoices):
        PROVISIONAL = "provisional", "Provisional"
        DIFFERENTIAL = "differential", "Differential"
        CONFIRMED = "confirmed", "Confirmed"

    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name="diagnoses")
    diagnosis_code = models.ForeignKey(
        DiagnosisCode,
        on_delete=models.PROTECT,
        related_name="encounter_diagnoses",
        blank=True,
        null=True,
    )
    diagnosis_text = models.CharField(max_length=250)
    diagnosis_type = models.CharField(max_length=30, choices=DiagnosisType.choices)
    is_primary = models.BooleanField(default=False)
    diagnosed_by_practitioner_facility_assignment = models.ForeignKey(
        PractitionerFacilityAssignment,
        on_delete=models.PROTECT,
        related_name="encounter_diagnoses",
        blank=True,
        null=True,
    )
    notes_encrypted = models.TextField(blank=True, null=True)
    diagnosed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "encounter_diagnoses"
        constraints = [
            models.UniqueConstraint(
                fields=["encounter"],
                condition=Q(is_primary=True),
                name="uq_encounter_diagnoses_primary",
            ),
            models.CheckConstraint(
                condition=Q(diagnosis_type__in=["provisional", "differential", "confirmed"]),
                name="ck_encounter_diagnoses_type",
            ),
        ]
        indexes = [models.Index(fields=["encounter", "diagnosed_at"], name="idx_enc_diag_enc_time")]
