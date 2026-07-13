from __future__ import annotations

from itertools import count

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, RolePermission, User, UserMembership, UserRoleAssignment
from apps.facilities.models import Facility, FacilityType, Organization


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_factory():
    sequence = count(1)

    def create_user(**overrides):
        index = next(sequence)
        defaults = {
            "email": f"audit-user-{index}@example.com",
            "phone_number": f"+255771000{index:03d}",
            "password": "Password123!",
            "first_name": "Audit",
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
        defaults = {"name": code.replace(".", " ").replace("_", " ").title(), "module": module, "action": action, "is_active": True}
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
        defaults = {"name": f"Audit Role {index}", "code": f"AUDIT_ROLE_{index}", "organization": None, "facility": None, "is_active": True}
        defaults.update(overrides)
        return Role.objects.create(**defaults)

    return create_role


@pytest.fixture
def grant_system_permission(permission_factory, role_factory):
    sequence = count(1)

    def grant(*, user: User, permission_code: str, scope: str = "platform", organization: Organization | None = None, facility: Facility | None = None):
        permission = permission_factory(permission_code)
        role_kwargs = {"organization": None, "facility": None}
        if scope == "organization":
            role_kwargs["organization"] = organization
        elif scope == "facility":
            role_kwargs["organization"] = organization or facility.organization
            role_kwargs["facility"] = facility
        role = role_factory(name=f"{permission_code} role", code=f"{permission_code.replace('.', '_').upper()}_{next(sequence)}", **role_kwargs)
        RolePermission.objects.create(role=role, permission=permission)
        if scope == "organization":
            UserMembership.objects.get_or_create(user=user, organization=organization, facility=None)
        elif scope == "facility":
            UserMembership.objects.get_or_create(user=user, organization=organization or facility.organization, facility=facility)
        UserRoleAssignment.objects.create(user=user, role=role)
        return permission

    return grant


@pytest.fixture
def organization():
    return Organization.objects.create(name="Audit Org", code="AUDIT_ORG")


@pytest.fixture
def facility_type():
    return FacilityType.objects.create(name="Audit Facility Type", code="AUDIT_FAC_TYPE")


@pytest.fixture
def facility(organization, facility_type):
    return Facility.objects.create(organization=organization, facility_type=facility_type, name="Audit Facility", code="AUDIT_FAC", timezone="Africa/Dar_es_Salaam")


@pytest.fixture
def audit_user(user_factory):
    return user_factory(email="audit.actor@example.com", phone_number="+255771111111")
