from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.clinical.models import Encounter
from apps.facilities.models import Facility, Organization
from apps.patients.models import Patient
from common.db import ActiveModel, TimeStampedModel


class Service(TimeStampedModel, ActiveModel):
    class Category(models.TextChoices):
        CONSULTATION = "consultation", "Consultation"
        LABORATORY = "laboratory", "Laboratory"
        IMAGING = "imaging", "Imaging"
        PROCEDURE = "procedure", "Procedure"
        PHARMACY = "pharmacy", "Pharmacy"
        ADMISSION = "admission", "Admission"
        BED = "bed", "Bed"
        OTHER = "other", "Other"

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="billing_services"
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    service_category = models.CharField(max_length=30, choices=Category.choices)

    class Meta:
        db_table = "services"
        constraints = [
            models.UniqueConstraint(fields=["organization", "code"], name="uq_services_org_code"),
            models.CheckConstraint(
                condition=Q(code=models.functions.Upper("code")), name="ck_services_code_upper"
            ),
            models.CheckConstraint(
                condition=Q(
                    service_category__in=[
                        "consultation",
                        "laboratory",
                        "imaging",
                        "procedure",
                        "pharmacy",
                        "admission",
                        "bed",
                        "other",
                    ]
                ),
                name="ck_services_category",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "service_category", "is_active"],
                name="idx_services_org_category",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class ServicePrice(TimeStampedModel, ActiveModel):
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="prices")
    facility = models.ForeignKey(
        Facility, on_delete=models.PROTECT, related_name="service_prices", blank=True, null=True
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, default="TZS")
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "service_prices"
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="ck_service_prices_amount"),
            models.CheckConstraint(
                condition=Q(currency=models.functions.Upper("currency")),
                name="ck_service_prices_currency_upper",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=F("effective_from")),
                name="ck_service_prices_dates",
            ),
        ]
        indexes = [
            models.Index(
                fields=["service", "effective_from", "effective_to"],
                name="idx_service_prices_dates",
            )
        ]


class EncounterCharge(TimeStampedModel):
    class SourceType(models.TextChoices):
        CONSULTATION = "consultation", "Consultation"
        LAB = "lab", "Lab"
        IMAGING = "imaging", "Imaging"
        PROCEDURE = "procedure", "Procedure"
        PHARMACY = "pharmacy", "Pharmacy"
        BED = "bed", "Bed"
        MANUAL = "manual", "Manual"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        POSTED = "posted", "Posted"
        VOIDED = "voided", "Voided"

    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name="charges")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="encounter_charges")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    source_type = models.CharField(max_length=30, choices=SourceType.choices)
    source_reference_id = models.UUIDField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    performed_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_encounter_charges",
        blank=True,
        null=True,
    )
    voided_at = models.DateTimeField(blank=True, null=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="voided_encounter_charges",
        blank=True,
        null=True,
    )
    void_reason = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        db_table = "encounter_charges"
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0) & Q(unit_price__gte=0) & Q(amount__gte=0),
                name="ck_encounter_charges_money",
            ),
            models.CheckConstraint(
                condition=Q(amount=models.functions.Round(F("quantity") * F("unit_price"), 2)),
                name="ck_encounter_charges_amount",
            ),
            models.CheckConstraint(
                condition=Q(
                    source_type__in=[
                        "consultation",
                        "lab",
                        "imaging",
                        "procedure",
                        "pharmacy",
                        "bed",
                        "manual",
                    ]
                ),
                name="ck_encounter_charges_source",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "posted", "voided"]),
                name="ck_encounter_charges_status",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status="voided")
                    & Q(voided_at__isnull=True)
                    & Q(voided_by__isnull=True)
                    & Q(void_reason__isnull=True)
                )
                | (Q(status="voided") & Q(voided_at__isnull=False) & Q(void_reason__isnull=False)),
                name="ck_encounter_charges_void",
            ),
            models.UniqueConstraint(
                fields=["encounter", "service", "source_type", "source_reference_id"],
                condition=Q(source_reference_id__isnull=False) & ~Q(status="voided"),
                name="uq_encounter_charges_source",
            ),
        ]
        indexes = [
            models.Index(fields=["encounter", "status"], name="idx_enc_charges_enc_status"),
            models.Index(
                fields=["source_type", "source_reference_id"],
                condition=Q(source_reference_id__isnull=False),
                name="idx_enc_charges_source_lookup",
            ),
        ]


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PARTIALLY_PAID = "partially_paid", "Partially Paid"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="invoices")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="invoices")
    encounter = models.ForeignKey(
        Encounter, on_delete=models.PROTECT, related_name="invoices", blank=True, null=True
    )
    invoice_number = models.CharField(max_length=50)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    balance_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    issued_at = models.DateTimeField(blank=True, null=True)
    due_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_invoices",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "invoices"
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "invoice_number"], name="uq_invoices_facility_number"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["draft", "issued", "partially_paid", "paid", "cancelled"]),
                name="ck_invoices_status",
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0)
                & Q(discount_amount__gte=0)
                & Q(tax_amount__gte=0)
                & Q(total_amount__gte=0)
                & Q(paid_amount__gte=0)
                & Q(balance_amount__gte=0),
                name="ck_invoices_money",
            ),
            models.CheckConstraint(
                condition=Q(total_amount=F("subtotal") - F("discount_amount") + F("tax_amount"))
                & Q(balance_amount=F("total_amount") - F("paid_amount")),
                name="ck_invoices_totals",
            ),
            models.CheckConstraint(
                condition=Q(status="draft") | Q(issued_at__isnull=False),
                name="ck_invoices_issued",
            ),
            models.CheckConstraint(
                condition=Q(due_at__isnull=True)
                | Q(issued_at__isnull=True)
                | Q(due_at__gte=F("issued_at")),
                name="ck_invoices_due",
            ),
        ]
        indexes = [
            models.Index(fields=["patient", "issued_at"], name="idx_invoices_patient_time"),
            models.Index(
                fields=["facility", "status", "issued_at"], name="idx_invoices_fac_status"
            ),
        ]


class InvoiceItem(models.Model):
    id = models.UUIDField(primary_key=True, default=__import__("uuid").uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="items")
    encounter_charge = models.ForeignKey(
        EncounterCharge,
        on_delete=models.PROTECT,
        related_name="invoice_items",
        blank=True,
        null=True,
    )
    service = models.ForeignKey(
        Service, on_delete=models.PROTECT, related_name="invoice_items", blank=True, null=True
    )
    description = models.CharField(max_length=250)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=18, decimal_places=2)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "invoice_items"
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0)
                & Q(unit_price__gte=0)
                & Q(discount_amount__gte=0)
                & Q(tax_amount__gte=0)
                & Q(line_total__gte=0),
                name="ck_invoice_items_money",
            ),
            models.CheckConstraint(
                condition=Q(
                    line_total=models.functions.Round(F("quantity") * F("unit_price"), 2)
                    - F("discount_amount")
                    + F("tax_amount")
                ),
                name="ck_invoice_items_total",
            ),
        ]
        indexes = [models.Index(fields=["invoice"], name="idx_invoice_items_invoice")]


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        CARD = "card", "Card"
        BANK = "bank", "Bank"
        INSURANCE = "insurance", "Insurance"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REVERSED = "reversed", "Reversed"

    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="payments")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="payments")
    payment_number = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, default="TZS")
    payment_method = models.CharField(max_length=30, choices=Method.choices)
    transaction_reference = models.CharField(max_length=150, blank=True, null=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="received_payments",
        blank=True,
        null=True,
    )
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "payments"
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "payment_number"], name="uq_payments_facility_number"
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="ck_payments_amount"),
            models.CheckConstraint(
                condition=Q(currency=models.functions.Upper("currency")),
                name="ck_payments_currency_upper",
            ),
            models.CheckConstraint(
                condition=Q(
                    payment_method__in=[
                        "cash",
                        "mobile_money",
                        "card",
                        "bank",
                        "insurance",
                        "other",
                    ]
                ),
                name="ck_payments_method",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "completed", "failed", "reversed"]),
                name="ck_payments_status",
            ),
        ]
        indexes = [
            models.Index(fields=["patient", "received_at"], name="idx_payments_patient_time")
        ]


class PaymentRefund(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reason = models.CharField(max_length=250)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="requested_payment_refunds",
        blank=True,
        null=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_payment_refunds",
        blank=True,
        null=True,
    )
    refunded_at = models.DateTimeField(blank=True, null=True)
    transaction_reference = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        db_table = "payment_refunds"
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="ck_payment_refunds_amount"),
            models.CheckConstraint(
                condition=Q(
                    status__in=["pending", "approved", "rejected", "completed", "cancelled"]
                ),
                name="ck_payment_refunds_status",
            ),
            models.CheckConstraint(
                condition=~Q(status="completed") | Q(refunded_at__isnull=False),
                name="ck_payment_refunds_completion",
            ),
        ]
        indexes = [models.Index(fields=["payment"], name="idx_payment_refunds_payment")]
