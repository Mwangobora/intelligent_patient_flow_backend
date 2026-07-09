from __future__ import annotations

from datetime import date
from itertools import count

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, RolePermission, User, UserMembership, UserRoleAssignment
from apps.facilities.models import Department, Facility, FacilitySpecialty, FacilityType, Organization, Specialty
from apps.practitioners.models import (
    Practitioner,
    PractitionerCredentialType,
    PractitionerFacilityAssignment,
    PractitionerType,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_factory():
    sequence = count(1)

    def create_user(**overrides):
        index = next(sequence)
        defaults = {
            "email": f"practitioner-user-{index}@example.com",
            "phone_number": f"+255744000{index:03d}",
            "password": "Password123!",
            "first_name": "Practitioner",
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
        permission, _ = Permission.objects.get_or_create(code=code, defaults=defaults)
        for field, value in defaults.items():
            setattr(permission, field, value)
        permission.save()
        return permission

    return create_permission


@pytest.fixture
def role_factory():
    sequence = count(1)

    def create_role(**overrides):
        index = next(sequence)
        defaults = {
            "name": f"Practitioner Role {index}",
            "code": f"PRACTITIONER_ROLE_{index}",
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

        if scope == "organization":
            UserMembership.objects.get_or_create(
                user=user,
                organization=organization,
                facility=None,
            )
        elif scope == "facility":
            UserMembership.objects.get_or_create(
                user=user,
                organization=organization or facility.organization,
                facility=facility,
            )

        UserRoleAssignment.objects.create(user=user, role=role)
        return permission

    return grant


@pytest.fixture
def organization():
    return Organization.objects.create(name="Practitioner Org", code="PRACTITIONER_ORG")


@pytest.fixture
def second_organization():
    return Organization.objects.create(name="Other Practitioner Org", code="OTHER_PRACTITIONER_ORG")


@pytest.fixture
def facility_type():
    return FacilityType.objects.create(name="Hospital", code="HOSPITAL")


@pytest.fixture
def facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Main Practitioner Facility",
        code="PRAC_MAIN_FACILITY",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def second_facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Secondary Practitioner Facility",
        code="PRAC_SECOND_FACILITY",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def other_org_facility(second_organization, facility_type):
    return Facility.objects.create(
        organization=second_organization,
        facility_type=facility_type,
        name="Other Org Facility",
        code="OTHER_ORG_PRAC_FAC",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def department(facility):
    return Department.objects.create(facility=facility, name="Outpatient", code="OUTPATIENT")


@pytest.fixture
def other_facility_department(second_facility):
    return Department.objects.create(facility=second_facility, name="Emergency", code="EMERGENCY")


@pytest.fixture
def specialty():
    return Specialty.objects.create(name="Cardiology", code="CARDIOLOGY")


@pytest.fixture
def other_specialty():
    return Specialty.objects.create(name="Neurology", code="NEUROLOGY")


@pytest.fixture
def facility_specialty(facility, specialty):
    return FacilitySpecialty.objects.create(
        facility=facility,
        specialty=specialty,
        appointment_duration_minutes=30,
    )


@pytest.fixture
def department_facility_specialty(facility, department, specialty):
    return FacilitySpecialty.objects.create(
        facility=facility,
        department=department,
        specialty=specialty,
        appointment_duration_minutes=20,
    )


@pytest.fixture
def other_facility_specialty(second_facility, other_specialty):
    return FacilitySpecialty.objects.create(
        facility=second_facility,
        specialty=other_specialty,
        appointment_duration_minutes=25,
    )


@pytest.fixture
def practitioner_type():
    return PractitionerType.objects.create(name="Doctor", code="DOCTOR")


@pytest.fixture
def inactive_practitioner_type():
    return PractitionerType.objects.create(name="Inactive Type", code="INACTIVE_TYPE", is_active=False)


@pytest.fixture
def practitioner(organization, practitioner_type):
    return Practitioner.objects.create(
        organization=organization,
        practitioner_type=practitioner_type,
        practitioner_number="PRAC-000100",
        first_name="Amina",
        last_name="Care",
        email="amina.care@example.com",
        phone_number="+255712000111",
    )


@pytest.fixture
def practitioner_user(user_factory):
    return user_factory(email="linked-practitioner@example.com", phone_number="+255755123456")


@pytest.fixture
def practitioner_with_user(organization, practitioner_type, practitioner_user):
    return Practitioner.objects.create(
        organization=organization,
        user=practitioner_user,
        practitioner_type=practitioner_type,
        practitioner_number="PRAC-000101",
        first_name="Linked",
        last_name="Practitioner",
    )


@pytest.fixture
def facility_assignment(practitioner, facility):
    return PractitionerFacilityAssignment.objects.create(
        practitioner=practitioner,
        facility=facility,
        starts_on=date(2026, 1, 1),
        is_primary=True,
    )


@pytest.fixture
def credential_type_global():
    return PractitionerCredentialType.objects.create(
        name="Medical License",
        code="MEDICAL_LICENSE",
        requires_expiry_date=True,
    )


@pytest.fixture
def credential_type_org(organization):
    return PractitionerCredentialType.objects.create(
        organization=organization,
        name="Staff ID",
        code="STAFF_ID",
    )
