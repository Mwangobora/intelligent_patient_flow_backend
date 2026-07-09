from __future__ import annotations

from datetime import timedelta
from itertools import count

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, RolePermission, User, UserMembership, UserRoleAssignment
from apps.facilities.models import Facility, FacilityType, Organization
from apps.patients.models import (
    Patient,
    PatientIdentifierType,
    PatientRelatedPerson,
    RelationshipType,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def organization():
    return Organization.objects.create(name="Patient Org", code="PATIENT_ORG")


@pytest.fixture
def second_organization():
    return Organization.objects.create(name="Second Patient Org", code="SECOND_PATIENT_ORG")


@pytest.fixture
def facility_type():
    return FacilityType.objects.create(name="Hospital", code="HOSPITAL")


@pytest.fixture
def facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Patient Main Facility",
        code="PATIENT_MAIN_FACILITY",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def other_org_facility(second_organization, facility_type):
    return Facility.objects.create(
        organization=second_organization,
        facility_type=facility_type,
        name="Other Org Facility",
        code="OTHER_ORG_FACILITY",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def user_factory():
    sequence = count(1)

    def create_user(**overrides):
        index = next(sequence)
        defaults = {
            "email": f"patient-user-{index}@example.com",
            "phone_number": f"+255711000{index:03d}",
            "password": "Password123!",
            "first_name": "Patient",
            "last_name": f"User{index}",
        }
        defaults.update(overrides)
        return User.objects.create_user(**defaults)

    return create_user


@pytest.fixture
def authenticated_client(api_client):
    def authenticate(user: User):
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return api_client

    return authenticate


@pytest.fixture
def permission_factory():
    def create_permission(code: str, **overrides):
        module, action = code.split(".", 1)
        defaults = {
            "name": code.replace(".", " ").replace("_", " ").title(),
            "module": module,
            "action": action,
            "is_active": True,
        }
        defaults.update(overrides)
        return Permission.objects.create(code=code, **defaults)

    return create_permission


@pytest.fixture
def role_factory():
    sequence = count(1)

    def create_role(**overrides):
        index = next(sequence)
        defaults = {
            "name": f"Patient Role {index}",
            "code": f"PATIENT_ROLE_{index}",
            "organization": None,
            "facility": None,
            "is_active": True,
        }
        defaults.update(overrides)
        return Role.objects.create(**defaults)

    return create_role


@pytest.fixture
def grant_system_permission(permission_factory, role_factory):
    sequence = count(1)

    def grant(
        *,
        user: User,
        permission_code: str,
        scope: str = "platform",
        organization: Organization | None = None,
        facility: Facility | None = None,
    ):
        permission = permission_factory(permission_code)
        role_kwargs = {"organization": None, "facility": None}
        if scope == "organization":
            role_kwargs["organization"] = organization
        elif scope == "facility":
            role_kwargs["organization"] = organization or facility.organization
            role_kwargs["facility"] = facility

        role = role_factory(
            name=f"{permission_code} role",
            code=f"{permission_code.replace('.', '_').upper()}_{next(sequence)}",
            **role_kwargs,
        )
        RolePermission.objects.create(role=role, permission=permission)

        starts_at = timezone.now() - timedelta(minutes=5)
        if scope == "organization":
            UserMembership.objects.get_or_create(
                user=user,
                organization=organization,
                facility=None,
                defaults={"starts_at": starts_at},
            )
        elif scope == "facility":
            UserMembership.objects.get_or_create(
                user=user,
                organization=organization or facility.organization,
                facility=facility,
                defaults={"starts_at": starts_at},
            )

        UserRoleAssignment.objects.create(user=user, role=role, starts_at=starts_at)
        return permission

    return grant


@pytest.fixture
def patient(organization, facility):
    return Patient.objects.create(
        organization=organization,
        registered_facility=facility,
        patient_number="PAT-000001",
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        phone_number="+255712345678",
    )


@pytest.fixture
def patient_user(user_factory):
    return user_factory(email="patient-owner@example.com", phone_number="+255733444555")


@pytest.fixture
def patient_with_user(organization, facility, patient_user):
    return Patient.objects.create(
        organization=organization,
        user=patient_user,
        registered_facility=facility,
        patient_number="PAT-000010",
        first_name="Owner",
        last_name="Patient",
        email="owner.patient@example.com",
        phone_number="+255755111222",
    )


@pytest.fixture
def identifier_type_global():
    return PatientIdentifierType.objects.create(name="National ID", code="NATIONAL_ID")


@pytest.fixture
def identifier_type_org(organization):
    return PatientIdentifierType.objects.create(
        organization=organization,
        name="Hospital Number",
        code="HOSPITAL_NUMBER",
    )


@pytest.fixture
def relationship_type():
    return RelationshipType.objects.create(name="Guardian", code="GUARDIAN")


@pytest.fixture
def related_user(user_factory):
    return user_factory(email="related.user@example.com", phone_number="+255700123999")


@pytest.fixture
def related_person(patient, relationship_type, related_user):
    return PatientRelatedPerson.objects.create(
        patient=patient,
        relationship_type=relationship_type,
        linked_user=related_user,
        first_name="Grace",
        last_name="Helper",
        is_guardian=True,
        priority_order=1,
    )


@pytest.fixture
def access_role(organization):
    return Role.objects.create(
        organization=organization,
        name="Patient Delegate",
        code="PATIENT_DELEGATE",
    )
