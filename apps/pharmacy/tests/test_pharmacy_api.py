from __future__ import annotations

import pytest

from apps.facilities.models import Organization
from apps.pharmacy.models import Prescription

pytestmark = pytest.mark.django_db


def create_medication(auth_client, organization, code="PARA500"):
    response = auth_client.post(
        "/api/v1/pharmacy/medications/",
        {
            "organization_id": str(organization.id),
            "code": code,
            "generic_name": "Paracetamol",
            "brand_name": "Panadol",
            "strength": "500",
            "strength_unit": "mg",
            "dosage_form": "tablet",
            "route_default": "oral",
        },
        format="json",
    )
    assert response.status_code == 201
    return response.data


def create_prescription(
    auth_client, encounter, practitioner_assignment, medication, quantity="10.000"
):
    response = auth_client.post(
        "/api/v1/pharmacy/prescriptions/",
        {
            "encounter_id": str(encounter.id),
            "prescribed_by_practitioner_facility_assignment_id": str(practitioner_assignment.id),
            "items": [
                {
                    "medication_id": medication["id"],
                    "dose": "500.000",
                    "dose_unit": "mg",
                    "frequency": "Three times daily",
                    "duration_value": 5,
                    "duration_unit": "days",
                    "quantity_prescribed": quantity,
                    "instructions": "Take after meals",
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 201
    return response.data


def test_create_medication_and_search(auth_client, organization):
    medication = create_medication(auth_client, organization, code="para500")
    search = auth_client.get("/api/v1/pharmacy/medications/?search=panadol")

    assert medication["code"] == "PARA500"
    assert medication["generic_name"] == "Paracetamol"
    assert search.status_code == 200
    assert search.data[0]["brand_name"] == "Panadol"


def test_create_prescription_from_encounter(
    auth_client, organization, encounter, practitioner_assignment
):
    medication = create_medication(auth_client, organization)
    prescription = create_prescription(auth_client, encounter, practitioner_assignment, medication)

    assert prescription["prescription_number"].startswith("RX-")
    assert prescription["status"] == Prescription.Status.ACTIVE
    assert prescription["items"][0]["quantity_prescribed"] == "10.000"
    assert prescription["items"][0]["quantity_dispensed"] == "0.000"


def test_cross_organization_medication_is_rejected(auth_client, encounter, practitioner_assignment):
    other_org = Organization.objects.create(name="Other Pharmacy Org", code="OTHER_PHARM_ORG")
    medication = create_medication(auth_client, other_org, code="AMOX500")
    response = auth_client.post(
        "/api/v1/pharmacy/prescriptions/",
        {
            "encounter_id": str(encounter.id),
            "prescribed_by_practitioner_facility_assignment_id": str(practitioner_assignment.id),
            "items": [
                {
                    "medication_id": medication["id"],
                    "frequency": "Twice daily",
                    "quantity_prescribed": "6.000",
                }
            ],
        },
        format="json",
    )

    assert response.status_code == 400


def test_partial_and_full_dispensing_updates_status(
    auth_client, organization, encounter, practitioner_assignment
):
    medication = create_medication(auth_client, organization)
    prescription = create_prescription(auth_client, encounter, practitioner_assignment, medication)
    item_id = prescription["items"][0]["id"]

    first = auth_client.post(
        "/api/v1/pharmacy/dispenses/",
        {
            "prescription_item_id": item_id,
            "quantity_dispensed": "4.000",
            "dispensed_by_practitioner_facility_assignment_id": str(practitioner_assignment.id),
        },
        format="json",
    )
    after_partial = auth_client.get(f"/api/v1/pharmacy/prescriptions/{prescription['id']}/")
    second = auth_client.post(
        "/api/v1/pharmacy/dispenses/",
        {
            "prescription_item_id": item_id,
            "quantity_dispensed": "6.000",
            "dispensed_by_practitioner_facility_assignment_id": str(practitioner_assignment.id),
        },
        format="json",
    )
    after_full = auth_client.get(f"/api/v1/pharmacy/prescriptions/{prescription['id']}/")

    assert first.status_code == 201
    assert first.data["status"] == "partially_dispensed"
    assert after_partial.data["status"] == Prescription.Status.PARTIALLY_DISPENSED
    assert second.status_code == 201
    assert second.data["status"] == "dispensed"
    assert after_full.data["status"] == Prescription.Status.DISPENSED
    assert after_full.data["items"][0]["quantity_remaining"] == "0.000"


def test_over_dispense_is_rejected(auth_client, organization, encounter, practitioner_assignment):
    medication = create_medication(auth_client, organization)
    prescription = create_prescription(auth_client, encounter, practitioner_assignment, medication)
    item_id = prescription["items"][0]["id"]
    response = auth_client.post(
        "/api/v1/pharmacy/dispenses/",
        {
            "prescription_item_id": item_id,
            "quantity_dispensed": "11.000",
            "dispensed_by_practitioner_facility_assignment_id": str(practitioner_assignment.id),
        },
        format="json",
    )

    assert response.status_code == 400
