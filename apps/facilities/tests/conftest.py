from __future__ import annotations

from itertools import count

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, RolePermission, User, UserRoleAssignment
from apps.facilities.models import Department, Facility, FacilityType, Organization, Specialty


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_factory():
    sequence = count(1)

    def create_user(**overrides):
        index = next(sequence)
        defaults = {
            "email": f"facility-user-{index}@example.com",
            "phone_number": f"+255799000{index:03d}",
            "password": "Password123!",
            "first_name": "Facility",
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
def grant_system_permission():
    sequence = count(1)

    def grant(*, user: User, permission_code: str):
        module, action = permission_code.split(".", 1)
        defaults = {
            "name": permission_code.replace(".", " ").replace("_", " ").title(),
            "module": module,
            "action": action,
        }
        permission, _ = Permission.objects.get_or_create(
            code=permission_code,
            defaults=defaults,
        )
        for field, value in defaults.items():
            setattr(permission, field, value)
        permission.save()
        role = Role.objects.create(name=f"Facilities Role {next(sequence)}", code=f"FAC_ROLE_{next(sequence)}")
        RolePermission.objects.create(role=role, permission=permission)
        UserRoleAssignment.objects.create(user=user, role=role)
        return permission

    return grant


@pytest.fixture
def organization():
    return Organization.objects.create(name="Test Organization", code="TEST_ORG")


@pytest.fixture
def second_organization():
    return Organization.objects.create(name="Second Organization", code="SECOND_ORG")


@pytest.fixture
def facility_type():
    return FacilityType.objects.create(name="Hospital", code="HOSPITAL")


@pytest.fixture
def second_facility_type():
    return FacilityType.objects.create(name="Clinic", code="CLINIC")


@pytest.fixture
def facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Main Facility",
        code="MAIN_FACILITY",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def other_facility(second_organization, facility_type):
    return Facility.objects.create(
        organization=second_organization,
        facility_type=facility_type,
        name="Other Facility",
        code="OTHER_FACILITY",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def department(facility):
    return Department.objects.create(facility=facility, name="Outpatient", code="OUTPATIENT")


@pytest.fixture
def specialty():
    return Specialty.objects.create(name="Cardiology", code="CARDIOLOGY")
