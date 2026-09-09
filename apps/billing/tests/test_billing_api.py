from __future__ import annotations

from datetime import date

import pytest

from apps.billing.models import EncounterCharge, Invoice, Payment
from apps.facilities.models import Organization

pytestmark = pytest.mark.django_db


def create_service(auth_client, organization, code="CONS-GEN"):
    response = auth_client.post(
        "/api/v1/billing/services/",
        {
            "organization_id": str(organization.id),
            "code": code,
            "name": "General consultation",
            "service_category": "consultation",
        },
        format="json",
    )
    assert response.status_code == 201
    return response.data


def create_price(auth_client, service, facility=None, amount="15000.00"):
    response = auth_client.post(
        "/api/v1/billing/service-prices/",
        {
            "service_id": service["id"],
            "facility_id": str(facility.id) if facility else None,
            "amount": amount,
            "currency": "tzs",
            "effective_from": date.today().isoformat(),
        },
        format="json",
    )
    assert response.status_code == 201
    return response.data


def create_charge(auth_client, encounter, service, quantity="1.00"):
    response = auth_client.post(
        "/api/v1/billing/encounter-charges/",
        {
            "encounter_id": str(encounter.id),
            "service_id": service["id"],
            "quantity": quantity,
            "source_type": "consultation",
            "source_reference_id": str(encounter.id),
        },
        format="json",
    )
    assert response.status_code == 201
    return response.data


def create_invoice(auth_client, encounter, charge):
    response = auth_client.post(
        "/api/v1/billing/invoices/",
        {"encounter_id": str(encounter.id), "charge_ids": [charge["id"]]},
        format="json",
    )
    assert response.status_code == 201
    return response.data


def test_service_price_and_charge_creation(auth_client, organization, facility, encounter):
    service = create_service(auth_client, organization, code="consult")
    price = create_price(auth_client, service, facility=facility)
    charge = create_charge(auth_client, encounter, service, quantity="2.00")

    assert service["code"] == "CONSULT"
    assert price["currency"] == "TZS"
    assert charge["unit_price"] == "15000.00"
    assert charge["amount"] == "30000.00"
    assert charge["status"] == EncounterCharge.Status.PENDING


def test_overlapping_service_prices_are_rejected(auth_client, organization, facility):
    service = create_service(auth_client, organization)
    create_price(auth_client, service, facility=facility)
    response = auth_client.post(
        "/api/v1/billing/service-prices/",
        {
            "service_id": service["id"],
            "facility_id": str(facility.id),
            "amount": "20000.00",
            "currency": "TZS",
            "effective_from": date.today().isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400


def test_cross_organization_service_charge_is_rejected(auth_client, encounter):
    other_org = Organization.objects.create(name="Other Billing Org", code="OTHER_BILL_ORG")
    service = create_service(auth_client, other_org, code="LAB-FEE")
    response = auth_client.post(
        "/api/v1/billing/encounter-charges/",
        {
            "encounter_id": str(encounter.id),
            "service_id": service["id"],
            "quantity": "1.00",
            "unit_price": "5000.00",
            "source_type": "manual",
        },
        format="json",
    )

    assert response.status_code == 400


def test_invoice_generation_posts_charges(auth_client, organization, facility, encounter):
    service = create_service(auth_client, organization)
    create_price(auth_client, service, facility=facility)
    charge = create_charge(auth_client, encounter, service)
    invoice = create_invoice(auth_client, encounter, charge)
    posted_charge = auth_client.get(f"/api/v1/billing/encounter-charges/{charge['id']}/")

    assert invoice["invoice_number"].startswith("INV-")
    assert invoice["status"] == Invoice.Status.ISSUED
    assert invoice["total_amount"] == "15000.00"
    assert invoice["balance_amount"] == "15000.00"
    assert posted_charge.data["status"] == EncounterCharge.Status.POSTED


def test_invoice_requires_full_payment_amount(auth_client, organization, facility, encounter):
    service = create_service(auth_client, organization)
    create_price(auth_client, service, facility=facility)
    invoice = create_invoice(auth_client, encounter, create_charge(auth_client, encounter, service))

    partial = auth_client.post(
        f"/api/v1/billing/invoices/{invoice['id']}/settle/",
        {"amount": "1000.00", "payment_method": "cash"},
        format="json",
    )
    exact = auth_client.post(
        f"/api/v1/billing/invoices/{invoice['id']}/settle/",
        {"amount": "15000.00", "payment_method": "cash"},
        format="json",
    )
    paid_invoice = auth_client.get(f"/api/v1/billing/invoices/{invoice['id']}/")

    assert partial.status_code == 400
    assert exact.status_code == 201
    assert exact.data["status"] == Payment.Status.COMPLETED
    assert paid_invoice.data["status"] == Invoice.Status.PAID
    assert paid_invoice.data["paid_amount"] == "15000.00"
    assert paid_invoice.data["balance_amount"] == "0.00"


def test_refund_reverses_completed_payment(auth_client, organization, facility, encounter):
    service = create_service(auth_client, organization)
    create_price(auth_client, service, facility=facility)
    invoice = create_invoice(auth_client, encounter, create_charge(auth_client, encounter, service))
    payment = auth_client.post(
        f"/api/v1/billing/invoices/{invoice['id']}/settle/",
        {"amount": "15000.00", "payment_method": "cash"},
        format="json",
    ).data
    refund = auth_client.post(
        "/api/v1/billing/payment-refunds/",
        {"payment_id": payment["id"], "amount": "15000.00", "reason": "Duplicate receipt"},
        format="json",
    )
    completed = auth_client.post(
        f"/api/v1/billing/payment-refunds/{refund.data['id']}/complete/",
        {},
        format="json",
    )
    reversed_payment = auth_client.get(f"/api/v1/billing/payments/{payment['id']}/")

    assert refund.status_code == 201
    assert completed.status_code == 200
    assert completed.data["status"] == "completed"
    assert reversed_payment.data["status"] == Payment.Status.REVERSED
