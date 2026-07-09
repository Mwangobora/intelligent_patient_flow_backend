from __future__ import annotations

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, RolePermission, User, UserMembership
from apps.accounts.permissions import user_has_permission
from apps.accounts.serializers.user_serializers import UserDetailSerializer
from apps.accounts.services import assign_role_to_user
from apps.facilities.models import Facility, FacilityType, Organization
from common.exceptions import ValidationError


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def organization():
    return Organization.objects.create(name="Org", code="ORG")


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


def auth_headers(user: User):
    refresh = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


def create_user(**kwargs):
    defaults = {
        "email": "user@example.com",
        "password": "Password123!",
        "first_name": "Test",
        "last_name": "User",
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def create_permission_with_role(*, user: User, organization: Organization, permission_code: str):
    permission = Permission.objects.create(
        name=permission_code.replace(".", " ").title(),
        code=permission_code,
        module=permission_code.split(".")[0],
        action=permission_code.split(".")[1],
    )
    role = Role.objects.create(
        organization=organization,
        name=f"Role {permission_code}",
        code=permission_code.replace(".", "_").upper()[:80],
    )
    RolePermission.objects.create(role=role, permission=permission)
    UserMembership.objects.create(user=user, organization=organization)
    assign_role_to_user(user_id=user.id, role_id=role.id)
    return permission, role


@pytest.mark.django_db
def test_user_login_with_email(api_client):
    user = create_user(email="email-login@example.com")

    response = api_client.post(
        "/api/v1/auth/login/",
        {"email_or_phone": "email-login@example.com", "password": "Password123!"},
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data
    assert response.data["user"]["email"] == user.email


@pytest.mark.django_db
def test_user_login_with_phone(api_client):
    create_user(email="phone-login@example.com", phone_number="+255700000001")

    response = api_client.post(
        "/api/v1/auth/login/",
        {"email_or_phone": "+255700000001", "password": "Password123!"},
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data


@pytest.mark.django_db
def test_inactive_user_cannot_login(api_client):
    user = create_user(email="inactive@example.com")
    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])

    response = api_client.post(
        "/api/v1/auth/login/",
        {"email_or_phone": "inactive@example.com", "password": "Password123!"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_auth_me_requires_authentication(api_client):
    response = api_client.get("/api/v1/auth/me/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_normal_user_cannot_create_roles_without_permission(api_client, organization):
    user = create_user(email="normal@example.com")

    response = api_client.post(
        "/api/v1/accounts/roles/",
        {"name": "Scoped Role", "organization_id": str(organization.id)},
        format="json",
        **auth_headers(user),
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_superuser_can_create_role(api_client, organization):
    user = User.objects.create_superuser(
        email="admin@example.com",
        password="Password123!",
        first_name="Admin",
        last_name="User",
    )

    response = api_client.post(
        "/api/v1/accounts/roles/",
        {"name": "Org Admin", "organization_id": str(organization.id)},
        format="json",
        **auth_headers(user),
    )

    assert response.status_code == 201
    assert response.data["organization"] == organization.id


@pytest.mark.django_db
def test_role_creation_calls_service_and_respects_scope(api_client, organization, facility):
    user = User.objects.create_superuser(
        email="scope-admin@example.com",
        password="Password123!",
        first_name="Scope",
        last_name="Admin",
    )

    with patch(
        "apps.accounts.views.role_views.create_role",
        wraps=__import__("apps.accounts.services", fromlist=["create_role"]).create_role,
    ) as mocked_create_role:
        response = api_client.post(
            "/api/v1/accounts/roles/",
            {
                "name": "Facility Manager",
                "organization_id": str(organization.id),
                "facility_id": str(facility.id),
            },
            format="json",
            **auth_headers(user),
        )

    assert response.status_code == 201
    assert mocked_create_role.called
    assert response.data["organization"] == organization.id
    assert response.data["facility"] == facility.id


@pytest.mark.django_db
def test_permission_creation_enforces_module_action_format(api_client):
    user = User.objects.create_superuser(
        email="perm-admin@example.com",
        password="Password123!",
        first_name="Perm",
        last_name="Admin",
    )

    response = api_client.post(
        "/api/v1/accounts/permissions/",
        {
            "name": "Bad Permission",
            "module": "accounts",
            "action": "create",
            "code": "BAD_FORMAT",
        },
        format="json",
        **auth_headers(user),
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_role_permission_grant_works(api_client, organization):
    user = User.objects.create_superuser(
        email="grant-admin@example.com",
        password="Password123!",
        first_name="Grant",
        last_name="Admin",
    )
    role = Role.objects.create(organization=organization, name="Grant Role", code="GRANT_ROLE")
    permission = Permission.objects.create(
        name="Grant Perm",
        code="accounts_role_permission.grant",
        module="accounts_role_permission",
        action="grant",
    )

    response = api_client.post(
        f"/api/v1/accounts/roles/{role.id}/grant-permission/",
        {"permission_id": str(permission.id)},
        format="json",
        **auth_headers(user),
    )

    assert response.status_code == 201
    assert RolePermission.objects.filter(role=role, permission=permission, is_active=True).exists()


@pytest.mark.django_db
def test_user_role_assignment_requires_membership_for_scoped_roles(organization):
    user = create_user(email="memberless@example.com")
    role = Role.objects.create(organization=organization, name="Scoped Role", code="SCOPED_ROLE")

    with pytest.raises(ValidationError):
        assign_role_to_user(user_id=user.id, role_id=role.id)


@pytest.mark.django_db
def test_is_staff_and_is_superuser_not_exposed_in_normal_serializers():
    user = create_user(email="hidden@example.com")
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=["is_staff", "is_superuser", "updated_at"])

    data = UserDetailSerializer(user).data

    assert "is_staff" not in data
    assert "is_superuser" not in data


@pytest.mark.django_db
def test_user_has_permission_respects_granted_role(organization):
    user = create_user(email="hasperm@example.com")
    create_permission_with_role(user=user, organization=organization, permission_code="accounts_role.create")

    assert user_has_permission(user, "accounts_role.create", organization=organization.id) is True
