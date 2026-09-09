from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.clinical.models import Encounter
from apps.facilities.models import Organization
from apps.practitioners.models import PractitionerFacilityAssignment
from common.db import ActiveModel, TimeStampedModel


class LabTest(TimeStampedModel, ActiveModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="lab_tests"
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    specimen_type = models.CharField(max_length=80, blank=True, null=True)
    turnaround_minutes = models.IntegerField(blank=True, null=True)
    billing_service_id = models.UUIDField(blank=True, null=True)

    class Meta:
        db_table = "lab_tests"
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uq_lab_tests_org_code"),
            models.CheckConstraint(
                condition=Q(code=models.functions.Upper("code")), name="ck_lab_tests_code_upper"
            ),
            models.CheckConstraint(
                condition=Q(turnaround_minutes__isnull=True) | Q(turnaround_minutes__gt=0),
                name="ck_lab_tests_turnaround",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "is_active"], name="idx_lab_tests_org_active")
        ]


class LabTestComponent(TimeStampedModel, ActiveModel):
    lab_test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name="components")
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    unit = models.CharField(max_length=50, blank=True, null=True)
    reference_low = models.DecimalField(max_digits=18, decimal_places=4, blank=True, null=True)
    reference_high = models.DecimalField(max_digits=18, decimal_places=4, blank=True, null=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        db_table = "lab_test_components"
        constraints = [
            models.UniqueConstraint(
                fields=["lab_test", "code"], name="uq_lab_test_components_test_code"
            ),
            models.CheckConstraint(
                condition=Q(code=models.functions.Upper("code")),
                name="ck_lab_test_components_code_upper",
            ),
            models.CheckConstraint(
                condition=Q(reference_low__isnull=True)
                | Q(reference_high__isnull=True)
                | Q(reference_high__gte=F("reference_low")),
                name="ck_lab_test_components_reference",
            ),
            models.CheckConstraint(
                condition=Q(display_order__gte=0), name="ck_lab_test_components_order"
            ),
        ]
        indexes = [
            models.Index(fields=["lab_test", "display_order"], name="idx_lab_components_order")
        ]


class LabOrder(TimeStampedModel):
    class Priority(models.TextChoices):
        ROUTINE = "routine", "Routine"
        URGENT = "urgent", "Urgent"
        STAT = "stat", "Stat"

    class Status(models.TextChoices):
        ORDERED = "ordered", "Ordered"
        SAMPLE_COLLECTION = "sample_collection", "Sample Collection"
        PROCESSING = "processing", "Processing"
        PARTIALLY_RESULTED = "partially_resulted", "Partially Resulted"
        RESULTED = "resulted", "Resulted"
        VERIFIED = "verified", "Verified"
        CANCELLED = "cancelled", "Cancelled"

    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name="lab_orders")
    ordered_by_practitioner_facility_assignment = models.ForeignKey(
        PractitionerFacilityAssignment, on_delete=models.PROTECT, related_name="lab_orders"
    )
    order_number = models.CharField(max_length=50, unique=True)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.ROUTINE)
    clinical_notes_encrypted = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ORDERED)
    ordered_at = models.DateTimeField(default=timezone.now)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="cancelled_lab_orders",
        blank=True,
        null=True,
    )
    cancellation_reason = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        db_table = "lab_orders"
        constraints = [
            models.CheckConstraint(
                condition=Q(priority__in=["routine", "urgent", "stat"]),
                name="ck_lab_orders_priority",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "ordered",
                        "sample_collection",
                        "processing",
                        "partially_resulted",
                        "resulted",
                        "verified",
                        "cancelled",
                    ]
                ),
                name="ck_lab_orders_status",
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
                name="ck_lab_orders_cancellation",
            ),
        ]
        indexes = [
            models.Index(fields=["encounter", "ordered_at"], name="idx_lab_orders_encounter_time"),
            models.Index(fields=["status", "ordered_at"], name="idx_lab_orders_status_time"),
        ]


class LabOrderItem(TimeStampedModel):
    class Status(models.TextChoices):
        ORDERED = "ordered", "Ordered"
        SAMPLE_COLLECTION = "sample_collection", "Sample Collection"
        PROCESSING = "processing", "Processing"
        RESULTED = "resulted", "Resulted"
        VERIFIED = "verified", "Verified"
        CANCELLED = "cancelled", "Cancelled"

    lab_order = models.ForeignKey(LabOrder, on_delete=models.PROTECT, related_name="items")
    lab_test = models.ForeignKey(LabTest, on_delete=models.PROTECT, related_name="order_items")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ORDERED)
    ordered_at = models.DateTimeField(default=timezone.now)
    collected_at = models.DateTimeField(blank=True, null=True)
    processing_started_at = models.DateTimeField(blank=True, null=True)
    resulted_at = models.DateTimeField(blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "lab_order_items"
        constraints = [
            models.UniqueConstraint(
                fields=["lab_order", "lab_test"], name="uq_lab_order_items_order_test"
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "ordered",
                        "sample_collection",
                        "processing",
                        "resulted",
                        "verified",
                        "cancelled",
                    ]
                ),
                name="ck_lab_order_items_status",
            ),
        ]
        indexes = [models.Index(fields=["lab_order"], name="idx_lab_order_items_order")]


class LabSpecimen(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COLLECTED = "collected", "Collected"
        RECEIVED = "received", "Received"
        REJECTED = "rejected", "Rejected"
        PROCESSING = "processing", "Processing"
        DISPOSED = "disposed", "Disposed"

    lab_order_item = models.ForeignKey(
        LabOrderItem, on_delete=models.PROTECT, related_name="specimens"
    )
    specimen_number = models.CharField(max_length=80, unique=True)
    specimen_type = models.CharField(max_length=80)
    collected_by_practitioner_facility_assignment = models.ForeignKey(
        PractitionerFacilityAssignment,
        on_delete=models.PROTECT,
        related_name="collected_lab_specimens",
        blank=True,
        null=True,
    )
    collected_at = models.DateTimeField(blank=True, null=True)
    received_by_practitioner_facility_assignment = models.ForeignKey(
        PractitionerFacilityAssignment,
        on_delete=models.PROTECT,
        related_name="received_lab_specimens",
        blank=True,
        null=True,
    )
    received_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    rejection_reason = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        db_table = "lab_specimens"
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "pending",
                        "collected",
                        "received",
                        "rejected",
                        "processing",
                        "disposed",
                    ]
                ),
                name="ck_lab_specimens_status",
            ),
            models.CheckConstraint(
                condition=(~Q(status="rejected") & Q(rejection_reason__isnull=True))
                | (Q(status="rejected") & Q(rejection_reason__isnull=False)),
                name="ck_lab_specimens_rejection",
            ),
        ]
        indexes = [models.Index(fields=["specimen_number"], name="idx_lab_specimens_number")]


class LabResultValue(TimeStampedModel):
    class AbnormalFlag(models.TextChoices):
        NORMAL = "normal", "Normal"
        LOW = "low", "Low"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    lab_order_item = models.ForeignKey(
        LabOrderItem, on_delete=models.PROTECT, related_name="result_values"
    )
    lab_test_component = models.ForeignKey(
        LabTestComponent,
        on_delete=models.PROTECT,
        related_name="result_values",
        blank=True,
        null=True,
    )
    value_numeric = models.DecimalField(max_digits=18, decimal_places=4, blank=True, null=True)
    value_text = models.TextField(blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True)
    reference_low = models.DecimalField(max_digits=18, decimal_places=4, blank=True, null=True)
    reference_high = models.DecimalField(max_digits=18, decimal_places=4, blank=True, null=True)
    abnormal_flag = models.CharField(
        max_length=20, choices=AbnormalFlag.choices, default=AbnormalFlag.NORMAL
    )
    entered_by_practitioner_facility_assignment = models.ForeignKey(
        PractitionerFacilityAssignment, on_delete=models.PROTECT, related_name="entered_lab_results"
    )
    entered_at = models.DateTimeField(default=timezone.now)
    verified_by_practitioner_facility_assignment = models.ForeignKey(
        PractitionerFacilityAssignment,
        on_delete=models.PROTECT,
        related_name="verified_lab_results",
        blank=True,
        null=True,
    )
    verified_at = models.DateTimeField(blank=True, null=True)
    notes_encrypted = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "lab_result_values"
        constraints = [
            models.CheckConstraint(
                condition=(Q(value_numeric__isnull=False) & Q(value_text__isnull=True))
                | (Q(value_numeric__isnull=True) & Q(value_text__isnull=False)),
                name="ck_lab_result_values_value",
            ),
            models.CheckConstraint(
                condition=Q(reference_low__isnull=True)
                | Q(reference_high__isnull=True)
                | Q(reference_high__gte=F("reference_low")),
                name="ck_lab_result_values_reference",
            ),
            models.CheckConstraint(
                condition=Q(abnormal_flag__in=["normal", "low", "high", "critical"]),
                name="ck_lab_result_values_abnormal",
            ),
            models.CheckConstraint(
                condition=(
                    Q(verified_at__isnull=True)
                    & Q(verified_by_practitioner_facility_assignment__isnull=True)
                )
                | (
                    Q(verified_at__isnull=False)
                    & Q(verified_by_practitioner_facility_assignment__isnull=False)
                ),
                name="ck_lab_result_values_verification",
            ),
        ]
        indexes = [models.Index(fields=["lab_order_item"], name="idx_lab_result_values_item")]
