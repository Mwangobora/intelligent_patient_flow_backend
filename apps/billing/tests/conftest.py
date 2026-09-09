from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.checkins.models import PatientCheckin
from apps.clinical.models import Encounter
from apps.facilities.models import (
    Department,
    Facility,
    FacilitySpecialty,
    FacilityType,
    Organization,
    Specialty,
)
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner, PractitionerFacilityAssignment, PractitionerType


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email="billing.admin@example.com",
        password="Password123!",
        first_name="Billing",
        last_name="Admin",
        phone_number="+255711700001",
    )


@pytest.fixture
def auth_client(api_client, admin_user):
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def organization():
    return Organization.objects.create(name="Billing Org", code="BILL_ORG")


@pytest.fixture
def facility_type():
    return FacilityType.objects.create(name="Billing Hospital", code="BILL_HOSP")


@pytest.fixture
def facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Billing Main Facility",
        code="BILL_MAIN",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def department(facility):
    return Department.objects.create(facility=facility, name="Outpatient", code="BILL_OPD")


@pytest.fixture
def specialty():
    return Specialty.objects.create(name="Billing General Medicine", code="BILL_GEN_MED")


@pytest.fixture
def facility_specialty(facility, department, specialty):
    return FacilitySpecialty.objects.create(
        facility=facility,
        department=department,
        specialty=specialty,
        appointment_duration_minutes=30,
        accepts_appointments=True,
        accepts_walk_ins=True,
    )


@pytest.fixture
def patient(organization, facility):
    return Patient.objects.create(
        organization=organization,
        registered_facility=facility,
        patient_number="BILL-PAT-001",
        first_name="Neema",
        last_name="Kassim",
        phone_number="+255755701333",
    )


@pytest.fixture
def checkin(facility, patient, facility_specialty, admin_user):
    return PatientCheckin.objects.create(
        facility=facility,
        patient=patient,
        facility_specialty=facility_specialty,
        checkin_method=PatientCheckin.CheckinMethod.RECEPTION,
        checked_in_at=timezone.now() - timedelta(minutes=5),
        checked_in_by=admin_user,
    )


@pytest.fixture
def practitioner_assignment(organization, facility):
    practitioner_type = PractitionerType.objects.create(
        name="Billing Doctor", code="BILL_DOCTOR", requires_license=True
    )
    practitioner = Practitioner.objects.create(
        organization=organization,
        practitioner_type=practitioner_type,
        practitioner_number="BILL-DOC-001",
        first_name="Asha",
        last_name="Mollel",
    )
    return PractitionerFacilityAssignment.objects.create(
        practitioner=practitioner,
        facility=facility,
        starts_on=timezone.localdate(),
        is_primary=True,
    )


@pytest.fixture
def encounter(
    facility, patient, checkin, department, facility_specialty, practitioner_assignment, admin_user
):
    return Encounter.objects.create(
        facility=facility,
        patient=patient,
        patient_checkin=checkin,
        department=department,
        facility_specialty=facility_specialty,
        attending_practitioner_facility_assignment=practitioner_assignment,
        encounter_number="BILL-ENC-001",
        encounter_type=Encounter.EncounterType.OUTPATIENT,
        opened_by=admin_user,
    )
