from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.checkins.models import PatientCheckin
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
        email="clinical.admin@example.com",
        password="Password123!",
        first_name="Clinical",
        last_name="Admin",
        phone_number="+255711100001",
    )


@pytest.fixture
def auth_client(api_client, admin_user):
    refresh = RefreshToken.for_user(admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client


@pytest.fixture
def organization():
    return Organization.objects.create(name="Clinical Org", code="CLINICAL_ORG")


@pytest.fixture
def facility_type():
    return FacilityType.objects.create(name="Clinical Hospital", code="CLINICAL_HOSP")


@pytest.fixture
def facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Clinical Main Facility",
        code="CLINICAL_MAIN",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def department(facility):
    return Department.objects.create(facility=facility, name="Outpatient", code="OPD")


@pytest.fixture
def specialty():
    return Specialty.objects.create(name="General Medicine", code="GEN_MED")


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
        patient_number="CLIN-PAT-001",
        first_name="Neema",
        last_name="Kassim",
        phone_number="+255755111333",
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
        name="Doctor", code="DOCTOR", requires_license=True
    )
    practitioner = Practitioner.objects.create(
        organization=organization,
        practitioner_type=practitioner_type,
        practitioner_number="DOC-001",
        first_name="Asha",
        last_name="Mollel",
    )
    return PractitionerFacilityAssignment.objects.create(
        practitioner=practitioner,
        facility=facility,
        starts_on=timezone.localdate(),
        is_primary=True,
    )
