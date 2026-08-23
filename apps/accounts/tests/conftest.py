from __future__ import annotations

from datetime import timedelta
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
def organization():
    return Organization.objects.create(name="Org One", code="ORG_ONE")


@pytest.fixture
def second_organization():
    return Organization.objects.create(name="Org Two", code="ORG_TWO")


@pytest.fixture
def facility_type():
    return FacilityType.objects.create(name="Hospital", code="HOSPITAL")


@pytest.fixture
def facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Main Facility",
        code="MAIN",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def second_facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Second Facility",
        code="SECOND",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def other_org_facility(second_organization, facility_type):
    return Facility.objects.create(
        organization=second_organization,
        facility_type=facility_type,
        name="Remote Facility",
        code="REMOTE",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def user_factory():
    sequence = count(1)

    def create_user(**overrides):
        index = next(sequence)
        defaults = {
            "email": f"user{index}@example.com",
            "phone_number": f"+255700000{index:03d}",
            "password": "Password123!",
            "first_name": "Test",
            "middle_name": None,
            "last_name": f"User{index}",
        }
        defaults.update(overrides)
        return User.objects.create_user(**defaults)

    return create_user


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email="admin@example.com",
        password="Password123!",
        first_name="Admin",
        last_name="User",
    )


@pytest.fixture
def authenticated_client(api_client):
    def authenticate(user: User) -> APIClient:
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return api_client

    return authenticate


@pytest.fixture
def permission_factory():
    def create_permission(code: str, **overrides) -> Permission:
        module, action = code.split(".", 1)
        values = {
            "name": overrides.pop("name", code.replace(".", " ").replace("_", " ").title()),
            "module": module,
            "action": action,
            "description": overrides.pop("description", None),
            "is_active": overrides.pop("is_active", True),
            **overrides,
        }
        permission, created = Permission.objects.get_or_create(code=code, defaults=values)
        if not created:
            for field, value in values.items():
                setattr(permission, field, value)
            permission.save(update_fields=[*values.keys(), "updated_at"])
        return permission

    return create_permission


@pytest.fixture
def role_factory():
    sequence = count(1)

    def create_role(**overrides) -> Role:
        index = next(sequence)
        defaults = {
            "name": f"Role {index}",
            "code": f"ROLE_{index}",
            "organization": None,
            "facility": None,
            "description": None,
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
        create_membership: bool = True,
        permission_is_active: bool = True,
        role_is_active: bool = True,
        role_permission_is_active: bool = True,
        assignment_is_active: bool = True,
        assignment_starts_at=None,
        assignment_ends_at=None,
    ):
        permission = permission_factory(permission_code, is_active=permission_is_active)
        role_kwargs = {"organization": None, "facility": None}
        if scope == "organization":
            role_kwargs["organization"] = organization
        elif scope == "facility":
            role_kwargs["organization"] = organization or facility.organization
            role_kwargs["facility"] = facility

        role = role_factory(
            name=f"{permission_code} {scope} role",
            code=f"{permission_code.replace('.', '_').upper()}_{next(sequence)}",
            is_active=role_is_active,
            **role_kwargs,
        )
        role_permission = RolePermission.objects.create(
            role=role,
            permission=permission,
            is_active=role_permission_is_active,
        )

        starts_at = assignment_starts_at or (timezone.now() - timedelta(minutes=5))
        if create_membership and scope == "organization":
            UserMembership.objects.create(
                user=user,
                organization=organization,
                facility=None,
                starts_at=starts_at,
            )
        if create_membership and scope == "facility":
            UserMembership.objects.create(
                user=user,
                organization=organization or facility.organization,
                facility=facility,
                starts_at=starts_at,
            )

        assignment = UserRoleAssignment.objects.create(
            user=user,
            role=role,
            starts_at=starts_at,
            ends_at=assignment_ends_at,
            is_active=assignment_is_active,
        )
        return {
            "permission": permission,
            "role": role,
            "role_permission": role_permission,
            "assignment": assignment,
        }

    return grant
