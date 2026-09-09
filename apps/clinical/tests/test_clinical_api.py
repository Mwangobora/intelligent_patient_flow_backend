from __future__ import annotations

import pytest

from apps.clinical.models import Encounter, EncounterStatusHistory


pytestmark = pytest.mark.django_db


def test_create_encounter_from_checkin(auth_client, checkin):
    response = auth_client.post(
        "/api/v1/clinical/encounters/",
        {"patient_checkin_id": str(checkin.id), "encounter_type": "outpatient"},
        format="json",
    )

    assert response.status_code == 201
    assert str(response.data["patient"]) == str(checkin.patient_id)
    assert str(response.data["facility"]) == str(checkin.facility_id)
    assert response.data["encounter_number"].startswith("ENC-")
    assert response.data["status"] == Encounter.Status.OPENED
    assert EncounterStatusHistory.objects.filter(
        encounter_id=response.data["id"], from_status__isnull=True
    ).exists()


def test_duplicate_active_encounter_is_blocked(auth_client, checkin):
    payload = {"patient_checkin_id": str(checkin.id), "encounter_type": "outpatient"}
    first = auth_client.post("/api/v1/clinical/encounters/", payload, format="json")
    second = auth_client.post("/api/v1/clinical/encounters/", payload, format="json")

    assert first.status_code == 201
    assert second.status_code == 400


def test_change_encounter_status_adds_history(auth_client, checkin):
    created = auth_client.post(
        "/api/v1/clinical/encounters/",
        {"patient_checkin_id": str(checkin.id), "encounter_type": "outpatient"},
        format="json",
    )

    response = auth_client.post(
        f"/api/v1/clinical/encounters/{created.data['id']}/change-status/",
        {"to_status": "triage", "reason": "Ready for triage"},
        format="json",
    )
    history = auth_client.get(f"/api/v1/clinical/encounters/{created.data['id']}/status-history/")

    assert response.status_code == 200
    assert response.data["status"] == "triage"
    assert len(history.data) == 2
    assert history.data[-1]["to_status"] == "triage"


def test_create_triage_vitals_note_and_diagnosis(auth_client, checkin, practitioner_assignment):
    encounter = auth_client.post(
        "/api/v1/clinical/encounters/",
        {
            "patient_checkin_id": str(checkin.id),
            "encounter_type": "outpatient",
            "attending_practitioner_facility_assignment_id": str(practitioner_assignment.id),
        },
        format="json",
    ).data

    triage = auth_client.post(
        "/api/v1/clinical/triage-assessments/",
        {"encounter_id": encounter["id"], "triage_level": 2, "pain_score": 4},
        format="json",
    )
    vitals = auth_client.post(
        "/api/v1/clinical/vital-signs/",
        {"encounter_id": encounter["id"], "temperature_c": "36.8", "heart_rate": 78},
        format="json",
    )
    note = auth_client.post(
        "/api/v1/clinical/notes/",
        {
            "encounter_id": encounter["id"],
            "practitioner_facility_assignment_id": str(practitioner_assignment.id),
            "note_type": "consultation",
        },
        format="json",
    )
    diagnosis_code = auth_client.post(
        "/api/v1/clinical/diagnosis-codes/",
        {"coding_system": "icd10", "code": "j06.9", "name": "Acute upper respiratory infection"},
        format="json",
    )
    diagnosis = auth_client.post(
        "/api/v1/clinical/encounter-diagnoses/",
        {
            "encounter_id": encounter["id"],
            "diagnosis_code_id": diagnosis_code.data["id"],
            "diagnosis_text": "Acute upper respiratory infection",
            "diagnosis_type": "confirmed",
            "is_primary": True,
        },
        format="json",
    )

    assert triage.status_code == 201
    assert vitals.status_code == 201
    assert note.status_code == 201
    assert diagnosis_code.status_code == 201
    assert diagnosis.status_code == 201
    assert diagnosis.data["diagnosis_code_value"] == "J06.9"


def test_patient_allergies_and_conditions(auth_client, patient):
    allergy = auth_client.post(
        "/api/v1/patients/allergies/",
        {"patient_id": str(patient.id), "allergen": "Penicillin", "reaction": "Rash"},
        format="json",
    )
    condition = auth_client.post(
        "/api/v1/patients/conditions/",
        {"patient_id": str(patient.id), "condition_name": "Hypertension", "status": "active"},
        format="json",
    )
    allergies = auth_client.get(f"/api/v1/patients/allergies/?patient_id={patient.id}")
    conditions = auth_client.get(f"/api/v1/patients/conditions/?patient_id={patient.id}")

    assert allergy.status_code == 201
    assert condition.status_code == 201
    assert allergies.data[0]["allergen"] == "Penicillin"
    assert conditions.data[0]["condition_name"] == "Hypertension"
