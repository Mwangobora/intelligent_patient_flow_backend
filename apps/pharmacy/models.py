from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.clinical.models import Encounter
from apps.facilities.models import Organization
from apps.practitioners.models import PractitionerFacilityAssignment
from common.db import ActiveModel, TimeStampedModel


class Medication(TimeStampedModel, ActiveModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="medications"
    )
    code = models.CharField(max_length=50)
    generic_name = models.CharField(max_length=200)
    brand_name = models.CharField(max_length=200, blank=True, null=True)
    strength = models.CharField(max_length=80, blank=True, null=True)
    strength_unit = models.CharField(max_length=50, blank=True, null=True)
    dosage_form = models.CharField(max_length=80, blank=True, null=True)
    route_default = models.CharField(max_length=80, blank=True, null=True)

    class Meta:
        db_table = "medications"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="uq_medications_org_code"
            ),
            models.CheckConstraint(
                condition=Q(code=models.functions.Upper("code")), name="ck_medications_code_upper"
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "is_active"], name="idx_medications_org_active")
        ]

    def __str__(self) -> str:
        return f"{self.generic_name} ({self.code})"


class Prescription(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PARTIALLY_DISPENSED = "partially_dispensed", "Partially Dispensed"
        DISPENSED = "dispensed", "Dispensed"
        CANCELLED = "cancelled", "Cancelled"

    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name="prescriptions")
    prescription_number = models.CharField(max_length=50, unique=True)
    prescribed_by_practitioner_facility_assignment = models.ForeignKey(
        PractitionerFacilityAssignment, on_delete=models.PROTECT, related_name="prescriptions"
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    prescribed_at = models.DateTimeField(default=timezone.now)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="cancelled_prescriptions",
        blank=True,
        null=True,
    )
    cancellation_reason = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        db_table = "prescriptions"
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "draft",
                        "active",
                        "partially_dispensed",
                        "dispensed",
                        "cancelled",
                    ]
                ),
                name="ck_prescriptions_status",
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
                name="ck_prescriptions_cancellation",
            ),
        ]
        indexes = [
            models.Index(fields=["encounter", "prescribed_at"], name="idx_prescriptions_enc_time"),
        ]

    def __str__(self) -> str:
        return self.prescription_number


class PrescriptionItem(TimeStampedModel):
    prescription = models.ForeignKey(Prescription, on_delete=models.PROTECT, related_name="items")
    medication = models.ForeignKey(
        Medication, on_delete=models.PROTECT, related_name="prescription_items"
    )
    dose = models.DecimalField(max_digits=12, decimal_places=3, blank=True, null=True)
    dose_unit = models.CharField(max_length=50, blank=True, null=True)
    route = models.CharField(max_length=80, blank=True, null=True)
    frequency = models.CharField(max_length=100)
    duration_value = models.IntegerField(blank=True, null=True)
    duration_unit = models.CharField(max_length=30, blank=True, null=True)
    quantity_prescribed = models.DecimalField(max_digits=12, decimal_places=3)
    instructions_encrypted = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "prescription_items"
        constraints = [
            models.CheckConstraint(
                condition=Q(dose__isnull=True) | Q(dose__gt=0),
                name="ck_prescription_items_dose",
            ),
            models.CheckConstraint(
                condition=Q(duration_value__isnull=True) | Q(duration_value__gt=0),
                name="ck_prescription_items_duration",
            ),
            models.CheckConstraint(
                condition=Q(quantity_prescribed__gt=0),
                name="ck_prescription_items_quantity",
            ),
        ]
        indexes = [models.Index(fields=["prescription"], name="idx_prescription_items_rx")]

    def __str__(self) -> str:
        return f"{self.prescription.prescription_number} - {self.medication.generic_name}"


class MedicationDispense(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIALLY_DISPENSED = "partially_dispensed", "Partially Dispensed"
        DISPENSED = "dispensed", "Dispensed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4, editable=False)
    prescription_item = models.ForeignKey(
        PrescriptionItem, on_delete=models.PROTECT, related_name="dispenses"
    )
    stock_batch_id = models.UUIDField(blank=True, null=True)
    quantity_dispensed = models.DecimalField(max_digits=12, decimal_places=3)
    dispensed_by_practitioner_facility_assignment = models.ForeignKey(
        PractitionerFacilityAssignment,
        on_delete=models.PROTECT,
        related_name="medication_dispenses",
    )
    dispensed_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DISPENSED)
    notes_encrypted = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "medication_dispenses"
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity_dispensed__gt=0), name="ck_medication_dispenses_quantity"
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=["pending", "partially_dispensed", "dispensed", "cancelled"]
                ),
                name="ck_medication_dispenses_status",
            ),
        ]
        indexes = [models.Index(fields=["prescription_item"], name="idx_medication_dispenses_item")]

    def __str__(self) -> str:
        return f"{self.prescription_item_id} - {self.quantity_dispensed}"
