from __future__ import annotations

from django.db.models import Q

from apps.billing.models import (
    EncounterCharge,
    Invoice,
    InvoiceItem,
    Payment,
    PaymentRefund,
    Service,
    ServicePrice,
)


def list_services(
    *, organization_id=None, service_category=None, is_active: bool | None = None, search=None
):
    queryset = Service.objects.select_related("organization")
    if organization_id:
        queryset = queryset.filter(organization_id=organization_id)
    if service_category:
        queryset = queryset.filter(service_category=service_category)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(code__icontains=search) | Q(name__icontains=search))
    return queryset.order_by("service_category", "name")


def get_service_by_id(service_id):
    return list_services().filter(pk=service_id).first()


def list_service_prices(*, service_id=None, facility_id=None, is_active: bool | None = None):
    queryset = ServicePrice.objects.select_related("service", "service__organization", "facility")
    if service_id:
        queryset = queryset.filter(service_id=service_id)
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("service__name", "facility__name", "-effective_from")


def get_service_price_by_id(price_id):
    return list_service_prices().filter(pk=price_id).first()


def list_encounter_charges(
    *, encounter_id=None, patient_id=None, facility_id=None, status=None, source_type=None
):
    queryset = EncounterCharge.objects.select_related(
        "encounter",
        "encounter__facility",
        "encounter__patient",
        "service",
        "created_by",
        "voided_by",
    )
    if encounter_id:
        queryset = queryset.filter(encounter_id=encounter_id)
    if patient_id:
        queryset = queryset.filter(encounter__patient_id=patient_id)
    if facility_id:
        queryset = queryset.filter(encounter__facility_id=facility_id)
    if status:
        queryset = queryset.filter(status=status)
    if source_type:
        queryset = queryset.filter(source_type=source_type)
    return queryset.order_by("-performed_at")


def get_encounter_charge_by_id(charge_id):
    return list_encounter_charges().filter(pk=charge_id).first()


def list_invoices(
    *, facility_id=None, patient_id=None, encounter_id=None, status=None, search=None
):
    queryset = Invoice.objects.select_related(
        "facility", "patient", "encounter", "created_by"
    ).prefetch_related("items")
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if patient_id:
        queryset = queryset.filter(patient_id=patient_id)
    if encounter_id:
        queryset = queryset.filter(encounter_id=encounter_id)
    if status:
        queryset = queryset.filter(status=status)
    if search:
        queryset = queryset.filter(
            Q(invoice_number__icontains=search)
            | Q(patient__patient_number__icontains=search)
            | Q(patient__first_name__icontains=search)
            | Q(patient__last_name__icontains=search)
        )
    return queryset.order_by("-created_at")


def get_invoice_by_id(invoice_id):
    return list_invoices().filter(pk=invoice_id).first()


def list_invoice_items(*, invoice_id=None):
    queryset = InvoiceItem.objects.select_related("invoice", "service", "encounter_charge")
    if invoice_id:
        queryset = queryset.filter(invoice_id=invoice_id)
    return queryset.order_by("created_at")


def get_invoice_item_by_id(item_id):
    return list_invoice_items().filter(pk=item_id).first()


def list_payments(*, facility_id=None, patient_id=None, status=None, search=None):
    queryset = Payment.objects.select_related("facility", "patient", "received_by")
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if patient_id:
        queryset = queryset.filter(patient_id=patient_id)
    if status:
        queryset = queryset.filter(status=status)
    if search:
        queryset = queryset.filter(
            Q(payment_number__icontains=search) | Q(transaction_reference__icontains=search)
        )
    return queryset.order_by("-received_at")


def get_payment_by_id(payment_id):
    return list_payments().filter(pk=payment_id).first()


def list_payment_refunds(*, payment_id=None, status=None):
    queryset = PaymentRefund.objects.select_related("payment", "requested_by", "approved_by")
    if payment_id:
        queryset = queryset.filter(payment_id=payment_id)
    if status:
        queryset = queryset.filter(status=status)
    return queryset.order_by("-created_at")


def get_payment_refund_by_id(refund_id):
    return list_payment_refunds().filter(pk=refund_id).first()
