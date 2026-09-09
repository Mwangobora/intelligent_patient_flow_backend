from __future__ import annotations

import pytest

from apps.facilities.models import Organization
from apps.laboratory.models import LabOrder, LabOrderItem

pytestmark = pytest.mark.django_db


def create_lab_test(auth_client, organization, code="FBC"):
    response = auth_client.post(
        "/api/v1/laboratory/tests/",
        {
            "organization_id": str(organization.id),
            "code": code,
            "name": "Full Blood Count",
            "specimen_type": "Blood",
            "turnaround_minutes": 60,
        },
        format="json",
    )
    assert response.status_code == 201
    return response.data


def test_create_lab_test_and_component(auth_client, organization):
    lab_test = create_lab_test(auth_client, organization, code="hb")
    component = auth_client.post(
        "/api/v1/laboratory/test-components/",
        {
            "lab_test_id": lab_test["id"],
            "code": "wbc",
            "name": "White blood cells",
            "unit": "10^9/L",
            "reference_low": "4.0000",
            "reference_high": "11.0000",
            "display_order": 1,
        },
        format="json",
    )
    search = auth_client.get("/api/v1/laboratory/tests/?search=blood")

    assert lab_test["code"] == "HB"
    assert component.status_code == 201
    assert component.data["code"] == "WBC"
    assert search.status_code == 200
    assert search.data[0]["name"] == "Full Blood Count"


def test_create_lab_order_from_encounter(
    auth_client, organization, encounter, practitioner_assignment
):
    lab_test = create_lab_test(auth_client, organization)
    response = auth_client.post(
        "/api/v1/laboratory/orders/",
        {
            "encounter_id": str(encounter.id),
            "ordered_by_practitioner_facility_assignment_id": str(practitioner_assignment.id),
            "lab_test_ids": [lab_test["id"]],
            "priority": "urgent",
            "clinical_notes": "Fever and fatigue",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["order_number"].startswith("LAB-")
    assert response.data["status"] == LabOrder.Status.ORDERED
    assert response.data["items"][0]["lab_test_name"] == "Full Blood Count"


def test_cross_organization_lab_test_is_rejected(auth_client, encounter, practitioner_assignment):
    other_org = Organization.objects.create(name="Other Org", code="OTHER_LAB_ORG")
    lab_test = create_lab_test(auth_client, other_org, code="MAL")
    response = auth_client.post(
        "/api/v1/laboratory/orders/",
        {
            "encounter_id": str(encounter.id),
            "ordered_by_practitioner_facility_assignment_id": str(practitioner_assignment.id),
            "lab_test_ids": [lab_test["id"]],
        },
        format="json",
    )

    assert response.status_code == 400


def test_specimen_collection_and_receiving(
    auth_client, organization, encounter, practitioner_assignment
):
    lab_test = create_lab_test(auth_client, organization)
    order = auth_client.post(
        "/api/v1/laboratory/orders/",
        {
            "encounter_id": str(encounter.id),
            "ordered_by_practitioner_facility_assignment_id": str(practitioner_assignment.id),
            "lab_test_ids": [lab_test["id"]],
        },
        format="json",
    ).data
    item_id = order["items"][0]["id"]

    specimen = auth_client.post(
        "/api/v1/laboratory/specimens/",
        {
            "lab_order_item_id": item_id,
            "specimen_type": "Blood",
            "collected_by_practitioner_facility_assignment_id": str(practitioner_assignment.id),
        },
        format="json",
    )
    received = auth_client.post(
        f"/api/v1/laboratory/specimens/{specimen.data['id']}/receive/",
        {"received_by_practitioner_facility_assignment_id": str(practitioner_assignment.id)},
        format="json",
    )

    assert specimen.status_code == 201
    assert specimen.data["specimen_number"].startswith("SPEC-")
    assert specimen.data["status"] == "collected"
    assert received.status_code == 200
    assert received.data["status"] == "received"


def test_result_entry_and_verification(
    auth_client, organization, encounter, practitioner_assignment
):
    lab_test = create_lab_test(auth_client, organization)
    component = auth_client.post(
        "/api/v1/laboratory/test-components/",
        {"lab_test_id": lab_test["id"], "code": "HB", "name": "Hemoglobin", "unit": "g/dL"},
        format="json",
    ).data
    order = auth_client.post(
        "/api/v1/laboratory/orders/",
        {
            "encounter_id": str(encounter.id),
            "ordered_by_practitioner_facility_assignment_id": str(practitioner_assignment.id),
            "lab_test_ids": [lab_test["id"]],
        },
        format="json",
    ).data
    item_id = order["items"][0]["id"]

    result = auth_client.post(
        "/api/v1/laboratory/results/",
        {
            "lab_order_item_id": item_id,
            "lab_test_component_id": component["id"],
            "value_numeric": "13.5000",
            "abnormal_flag": "normal",
            "entered_by_practitioner_facility_assignment_id": str(practitioner_assignment.id),
        },
        format="json",
    )
    verified = auth_client.post(
        f"/api/v1/laboratory/results/{result.data['id']}/verify/",
        {"verified_by_practitioner_facility_assignment_id": str(practitioner_assignment.id)},
        format="json",
    )

    assert result.status_code == 201
    assert result.data["component_code"] == "HB"
    assert verified.status_code == 200
    assert verified.data["verified_at"] is not None
    assert LabOrderItem.objects.get(pk=item_id).status == LabOrderItem.Status.VERIFIED
