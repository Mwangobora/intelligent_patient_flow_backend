from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.billing.models import (
    EncounterCharge,
    Invoice,
    InvoiceItem,
    Payment,
    PaymentRefund,
    Service,
    ServicePrice,
)
from apps.clinical.models import Encounter
from apps.facilities.models import Facility
from common.exceptions import ConflictError, NotFoundError, ValidationError


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_code(code: str) -> str:
    cleaned = code.strip().upper()
    if not cleaned:
        raise ValidationError("Code is required.")
    return cleaned


def _normalize_currency(currency: str | None) -> str:
    return (currency or "TZS").strip().upper()


def _money(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _get_service(service_id, *, for_update=False) -> Service:
    queryset = Service.objects.select_related("organization")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    service = queryset.filter(pk=service_id).first()
    if service is None:
        raise NotFoundError("Billing service not found.")
    return service


def _get_price(price_id, *, for_update=False) -> ServicePrice:
    queryset = ServicePrice.objects.select_related("service", "service__organization", "facility")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    price = queryset.filter(pk=price_id).first()
    if price is None:
        raise NotFoundError("Service price not found.")
    return price


def _get_encounter(encounter_id, *, for_update=False) -> Encounter:
    queryset = Encounter.objects.select_related("facility", "facility__organization", "patient")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    encounter = queryset.filter(pk=encounter_id).first()
    if encounter is None:
        raise NotFoundError("Encounter not found.")
    return encounter


def _get_charge(charge_id, *, for_update=False) -> EncounterCharge:
    queryset = EncounterCharge.objects.select_related(
        "encounter", "encounter__facility", "encounter__patient", "service"
    )
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    charge = queryset.filter(pk=charge_id).first()
    if charge is None:
        raise NotFoundError("Encounter charge not found.")
    return charge


def _get_invoice(invoice_id, *, for_update=False) -> Invoice:
    queryset = Invoice.objects.select_related("facility", "patient", "encounter").prefetch_related(
        "items"
    )
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    invoice = queryset.filter(pk=invoice_id).first()
    if invoice is None:
        raise NotFoundError("Invoice not found.")
    return invoice


def _get_payment(payment_id, *, for_update=False) -> Payment:
    queryset = Payment.objects.select_related("facility", "patient")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    payment = queryset.filter(pk=payment_id).first()
    if payment is None:
        raise NotFoundError("Payment not found.")
    return payment


def _ranges_overlap(start_a, end_a, start_b, end_b) -> bool:
    max_date = timezone.datetime.max.date()
    return start_a <= (end_b or max_date) and start_b <= (end_a or max_date)


def _validate_price_window(*, service, facility_id, effective_from, effective_to, exclude_id=None):
    queryset = ServicePrice.objects.filter(service=service, facility_id=facility_id, is_active=True)
    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)
    for price in queryset:
        if _ranges_overlap(effective_from, effective_to, price.effective_from, price.effective_to):
            raise ConflictError("Active service price dates overlap an existing price.")


def _current_price(*, service, facility_id, price_date) -> ServicePrice:
    base_filter = Q(service=service, is_active=True, effective_from__lte=price_date) & (
        Q(effective_to__isnull=True) | Q(effective_to__gte=price_date)
    )
    price = (
        ServicePrice.objects.filter(base_filter, facility_id=facility_id)
        .order_by("-effective_from")
        .first()
    )
    if price:
        return price
    price = (
        ServicePrice.objects.filter(base_filter, facility__isnull=True)
        .order_by("-effective_from")
        .first()
    )
    if price is None:
        raise NotFoundError("No active service price is available for this service.")
    return price


def _next_invoice_number(*, facility, issued_at) -> str:
    prefix = f"INV-{issued_at:%Y%m%d}-"
    latest = (
        Invoice.objects.select_for_update()
        .filter(facility=facility, invoice_number__startswith=prefix)
        .order_by("-invoice_number")
        .values_list("invoice_number", flat=True)
        .first()
    )
    next_number = int(latest.rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"{prefix}{next_number:04d}"


def _next_payment_number(*, facility, received_at) -> str:
    prefix = f"PAY-{received_at:%Y%m%d}-"
    latest = (
        Payment.objects.select_for_update()
        .filter(facility=facility, payment_number__startswith=prefix)
        .order_by("-payment_number")
        .values_list("payment_number", flat=True)
        .first()
    )
    next_number = int(latest.rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"{prefix}{next_number:04d}"


@transaction.atomic
def create_service(**data) -> Service:
    try:
        return Service.objects.create(
            organization_id=data["organization_id"],
            code=_normalize_code(data["code"]),
            name=data["name"].strip(),
            description=_optional_text(data.get("description")),
            service_category=data["service_category"],
            is_active=data.get("is_active", True),
        )
    except IntegrityError as exc:
        raise ConflictError("A billing service with this code already exists.") from exc


@transaction.atomic
def update_service(*, service_id, **updates) -> Service:
    service = _get_service(service_id, for_update=True)
    for field in ["name", "description", "service_category", "is_active"]:
        if field in updates:
            value = (
                _optional_text(updates[field])
                if field in {"name", "description"}
                else updates[field]
            )
            setattr(service, field, value)
    if "code" in updates:
        service.code = _normalize_code(updates["code"])
    if "organization_id" in updates:
        service.organization_id = updates["organization_id"]
    try:
        service.save()
    except IntegrityError as exc:
        raise ConflictError("A billing service with this code already exists.") from exc
    return service


@transaction.atomic
def create_service_price(**data) -> ServicePrice:
    service = _get_service(data["service_id"])
    facility_id = data.get("facility_id")
    if facility_id:
        facility = Facility.objects.filter(pk=facility_id).first()
        if facility is None:
            raise NotFoundError("Facility not found.")
        if facility.organization_id != service.organization_id:
            raise ValidationError("Service price facility must belong to the service organization.")
    _validate_price_window(
        service=service,
        facility_id=facility_id,
        effective_from=data["effective_from"],
        effective_to=data.get("effective_to"),
    )
    return ServicePrice.objects.create(
        service=service,
        facility_id=facility_id,
        amount=data["amount"],
        currency=_normalize_currency(data.get("currency")),
        effective_from=data["effective_from"],
        effective_to=data.get("effective_to"),
        is_active=data.get("is_active", True),
    )


@transaction.atomic
def update_service_price(*, price_id, **updates) -> ServicePrice:
    price = _get_price(price_id, for_update=True)
    service = price.service
    if "service_id" in updates:
        service = _get_service(updates["service_id"])
        price.service = service
    if "facility_id" in updates:
        price.facility_id = updates["facility_id"]
    if price.facility_id:
        facility = Facility.objects.filter(pk=price.facility_id).first()
        if facility is None:
            raise NotFoundError("Facility not found.")
        if facility.organization_id != service.organization_id:
            raise ValidationError("Service price facility must belong to the service organization.")
    for field in ["amount", "effective_from", "effective_to", "is_active"]:
        if field in updates:
            setattr(price, field, updates[field])
    if "currency" in updates:
        price.currency = _normalize_currency(updates["currency"])
    if price.is_active:
        _validate_price_window(
            service=service,
            facility_id=price.facility_id,
            effective_from=price.effective_from,
            effective_to=price.effective_to,
            exclude_id=price.id,
        )
    price.save()
    return price


@transaction.atomic
def create_encounter_charge(
    *,
    encounter_id,
    service_id,
    quantity,
    source_type,
    created_by_id=None,
    unit_price=None,
    source_reference_id=None,
    performed_at=None,
) -> EncounterCharge:
    encounter = _get_encounter(encounter_id, for_update=True)
    service = _get_service(service_id)
    if service.organization_id != encounter.facility.organization_id:
        raise ValidationError("Encounter charge service must belong to the encounter organization.")
    if not service.is_active:
        raise ValidationError("Inactive services cannot be charged.")
    performed_time = performed_at or timezone.now()
    price = unit_price
    if price is None:
        price = _current_price(
            service=service,
            facility_id=encounter.facility_id,
            price_date=performed_time.date(),
        ).amount
    amount = _money(quantity * price)
    try:
        return EncounterCharge.objects.create(
            encounter=encounter,
            service=service,
            quantity=quantity,
            unit_price=price,
            amount=amount,
            source_type=source_type,
            source_reference_id=source_reference_id,
            performed_at=performed_time,
            created_by_id=created_by_id,
        )
    except IntegrityError as exc:
        raise ConflictError("This service has already been charged for the source record.") from exc


@transaction.atomic
def void_encounter_charge(
    *, charge_id, voided_by_id=None, void_reason, voided_at=None
) -> EncounterCharge:
    charge = _get_charge(charge_id, for_update=True)
    if charge.status == EncounterCharge.Status.VOIDED:
        raise ConflictError("Charge is already voided.")
    if charge.invoice_items.exists():
        raise ConflictError("Charge already belongs to an invoice and cannot be voided.")
    reason = _optional_text(void_reason)
    if not reason:
        raise ValidationError("Void reason is required.")
    charge.status = EncounterCharge.Status.VOIDED
    charge.voided_at = voided_at or timezone.now()
    charge.voided_by_id = voided_by_id
    charge.void_reason = reason
    charge.save()
    return charge


@transaction.atomic
def generate_invoice_from_charges(
    *, encounter_id, charge_ids=None, created_by_id=None, issued_at=None, due_at=None
) -> Invoice:
    encounter = _get_encounter(encounter_id, for_update=True)
    charges = EncounterCharge.objects.select_for_update().filter(
        encounter=encounter, status=EncounterCharge.Status.PENDING
    )
    if charge_ids:
        charges = charges.filter(pk__in=charge_ids)
    charges = list(charges.select_related("service"))
    if not charges:
        raise ValidationError("No billable pending charges are available for this encounter.")
    if len({charge.encounter_id for charge in charges}) != 1:
        raise ValidationError("All invoice charges must belong to one encounter.")
    issue_time = issued_at or timezone.now()
    if due_at and due_at < issue_time:
        raise ValidationError("Invoice due date cannot be before issued date.")
    subtotal = _money(sum((charge.amount for charge in charges), Decimal("0.00")))
    invoice = Invoice.objects.create(
        facility=encounter.facility,
        patient=encounter.patient,
        encounter=encounter,
        invoice_number=_next_invoice_number(facility=encounter.facility, issued_at=issue_time),
        status=Invoice.Status.ISSUED,
        subtotal=subtotal,
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=subtotal,
        paid_amount=Decimal("0.00"),
        balance_amount=subtotal,
        issued_at=issue_time,
        due_at=due_at,
        created_by_id=created_by_id,
    )
    InvoiceItem.objects.bulk_create(
        [
            InvoiceItem(
                invoice=invoice,
                encounter_charge=charge,
                service=charge.service,
                description=charge.service.name,
                quantity=charge.quantity,
                unit_price=charge.unit_price,
                line_total=charge.amount,
            )
            for charge in charges
        ]
    )
    EncounterCharge.objects.filter(pk__in=[charge.id for charge in charges]).update(
        status=EncounterCharge.Status.POSTED
    )
    return invoice


@transaction.atomic
def settle_invoice(
    *,
    invoice_id,
    amount,
    payment_method,
    received_by_id=None,
    currency=None,
    transaction_reference=None,
    received_at=None,
) -> Payment:
    invoice = _get_invoice(invoice_id, for_update=True)
    if invoice.status != Invoice.Status.ISSUED:
        raise ConflictError("Only issued invoices can be paid.")
    if _money(amount) != invoice.balance_amount:
        raise ValidationError("Payment amount must equal the full outstanding invoice balance.")
    received_time = received_at or timezone.now()
    payment = Payment.objects.create(
        facility=invoice.facility,
        patient=invoice.patient,
        payment_number=_next_payment_number(facility=invoice.facility, received_at=received_time),
        amount=invoice.balance_amount,
        currency=_normalize_currency(currency),
        payment_method=payment_method,
        transaction_reference=_optional_text(transaction_reference),
        status=Payment.Status.COMPLETED,
        received_by_id=received_by_id,
        received_at=received_time,
    )
    invoice.paid_amount = invoice.total_amount
    invoice.balance_amount = Decimal("0.00")
    invoice.status = Invoice.Status.PAID
    invoice.save(update_fields=["paid_amount", "balance_amount", "status", "updated_at"])
    return payment


@transaction.atomic
def cancel_invoice(*, invoice_id, reason) -> Invoice:
    invoice = _get_invoice(invoice_id, for_update=True)
    if invoice.status == Invoice.Status.PAID:
        raise ConflictError("Paid invoices cannot be cancelled.")
    if invoice.status == Invoice.Status.CANCELLED:
        return invoice
    if not _optional_text(reason):
        raise ValidationError("Cancellation reason is required.")
    if invoice.issued_at is None:
        invoice.issued_at = timezone.now()
    invoice.status = Invoice.Status.CANCELLED
    invoice.save(update_fields=["status", "issued_at", "updated_at"])
    return invoice


@transaction.atomic
def request_payment_refund(*, payment_id, amount, reason, requested_by_id=None) -> PaymentRefund:
    payment = _get_payment(payment_id, for_update=True)
    if payment.status != Payment.Status.COMPLETED:
        raise ConflictError("Only completed payments can be refunded.")
    if _money(amount) > payment.amount:
        raise ValidationError("Refund amount cannot exceed payment amount.")
    reason_text = _optional_text(reason)
    if not reason_text:
        raise ValidationError("Refund reason is required.")
    return PaymentRefund.objects.create(
        payment=payment,
        amount=amount,
        reason=reason_text,
        requested_by_id=requested_by_id,
    )


@transaction.atomic
def complete_payment_refund(
    *, refund_id, approved_by_id=None, transaction_reference=None, refunded_at=None
) -> PaymentRefund:
    refund = (
        PaymentRefund.objects.select_related("payment")
        .select_for_update()
        .filter(pk=refund_id)
        .first()
    )
    if refund is None:
        raise NotFoundError("Payment refund not found.")
    if refund.status == PaymentRefund.Status.COMPLETED:
        raise ConflictError("Refund is already completed.")
    refund.status = PaymentRefund.Status.COMPLETED
    refund.approved_by_id = approved_by_id
    refund.transaction_reference = _optional_text(transaction_reference)
    refund.refunded_at = refunded_at or timezone.now()
    refund.save()
    refund.payment.status = Payment.Status.REVERSED
    refund.payment.save(update_fields=["status", "updated_at"])
    return refund
