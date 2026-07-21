from __future__ import annotations

import re

from django.urls import reverse

import pytest

from apps.accounts.models import RolePermission


@pytest.mark.django_db
def test_unauthenticated_user_cannot_access_role_endpoints(api_client):
    response = api_client.get(reverse("accounts-roles-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_normal_user_without_permission_cannot_create_role(authenticated_client, user_factory, organization):
    user = user_factory(email="normal-role@example.com")
    client = authenticated_client(user)

    response = client.post(
        reverse("accounts-roles-list"),
        {"name": "Scoped Role", "organization_id": str(organization.id)},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_user_with_permission_can_create_platform_role(authenticated_client, grant_system_permission, user_factory):
    actor = user_factory(email="platform-role-creator@example.com")
    grant_system_permission(user=actor, permission_code="accounts_role.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-roles-list"),
        {"name": "Platform Admin"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["organization"] is None
    assert response.data["facility"] is None


@pytest.mark.django_db
def test_user_with_permission_can_create_organization_role(
    authenticated_client,
    grant_system_permission,
    organization,
    user_factory,
):
    actor = user_factory(email="org-role-creator@example.com")
    grant_system_permission(user=actor, permission_code="accounts_role.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-roles-list"),
        {"name": "Organization Admin", "organization_id": str(organization.id)},
        format="json",
    )

    assert response.status_code == 201
    assert str(response.data["organization"]) == str(organization.id)
    assert response.data["facility"] is None


@pytest.mark.django_db
def test_user_with_permission_can_create_facility_role(
    authenticated_client,
    facility,
    grant_system_permission,
    organization,
    user_factory,
):
    actor = user_factory(email="facility-role-creator@example.com")
    grant_system_permission(user=actor, permission_code="accounts_role.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-roles-list"),
        {
            "name": "Facility Admin",
            "organization_id": str(organization.id),
            "facility_id": str(facility.id),
        },
        format="json",
    )

    assert response.status_code == 201
    assert str(response.data["organization"]) == str(organization.id)
    assert str(response.data["facility"]) == str(facility.id)


@pytest.mark.django_db
def test_facility_role_must_match_facility_organization(
    authenticated_client,
    grant_system_permission,
    organization,
    other_org_facility,
    user_factory,
):
    actor = user_factory(email="scope-mismatch@example.com")
    grant_system_permission(user=actor, permission_code="accounts_role.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-roles-list"),
        {
            "name": "Broken Facility Role",
            "organization_id": str(organization.id),
            "facility_id": str(other_org_facility.id),
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Facility must belong to the selected organization." in str(response.data)


@pytest.mark.django_db
def test_duplicate_role_code_or_name_in_same_scope_fails(
    authenticated_client,
    grant_system_permission,
    organization,
    role_factory,
    user_factory,
):
    actor = user_factory(email="duplicate-role@example.com")
    grant_system_permission(user=actor, permission_code="accounts_role.create")
    role_factory(name="Org Nurse", code="ORG_NURSE", organization=organization)
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-roles-list"),
        {
            "name": "Org Nurse",
            "code": "ORG_NURSE",
            "organization_id": str(organization.id),
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_same_role_name_and_code_in_different_valid_scope_is_allowed(
    authenticated_client,
    grant_system_permission,
    organization,
    second_organization,
    role_factory,
    user_factory,
):
    actor = user_factory(email="scope-allowed@example.com")
    grant_system_permission(user=actor, permission_code="accounts_role.create")
    role_factory(name="Shared Role", code="SHARED_ROLE", organization=organization)
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-roles-list"),
        {
            "name": "Shared Role",
            "code": "SHARED_ROLE",
            "organization_id": str(second_organization.id),
        },
        format="json",
    )

    assert response.status_code == 201
    assert str(response.data["organization"]) == str(second_organization.id)


@pytest.mark.django_db
def test_deactivate_role_works_with_permission(
    authenticated_client,
    grant_system_permission,
    organization,
    role_factory,
    user_factory,
):
    actor = user_factory(email="deactivate-role@example.com")
    role = role_factory(name="Active Role", code="ACTIVE_ROLE", organization=organization)
    grant_system_permission(user=actor, permission_code="accounts_role.deactivate")
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-roles-deactivate", kwargs={"pk": role.id}), format="json")

    role.refresh_from_db()
    assert response.status_code == 200
    assert role.is_active is False


@pytest.mark.django_db
def test_role_api_does_not_hardcode_behavior_by_role_code(
    authenticated_client,
    grant_system_permission,
    organization,
    user_factory,
):
    actor = user_factory(email="coded-role@example.com")
    grant_system_permission(user=actor, permission_code="accounts_role.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-roles-list"),
        {
            "name": "Custom Admin",
            "code": "ADMIN",
            "organization_id": str(organization.id),
        },
        format="json",
    )

    assert response.status_code == 201
    assert re.fullmatch(r"ROLE\d{4}", response.data["code"])
    assert str(response.data["organization"]) == str(organization.id)


@pytest.mark.django_db
def test_user_with_correct_permission_can_grant_permission_to_role(
    authenticated_client,
    grant_system_permission,
    organization,
    permission_factory,
    role_factory,
    user_factory,
):
    actor = user_factory(email="grant-role-perm@example.com")
    role = role_factory(name="Grant Role", code="GRANT_ROLE", organization=organization)
    permission = permission_factory("accounts_user.view")
    grant_system_permission(user=actor, permission_code="accounts_role_permission.grant")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-roles-grant-permission", kwargs={"pk": role.id}),
        {"permission_id": str(permission.id)},
        format="json",
    )

    assert response.status_code == 201
    assert RolePermission.objects.filter(role=role, permission=permission, is_active=True).exists()


@pytest.mark.django_db
def test_cannot_grant_inactive_permission(
    authenticated_client,
    grant_system_permission,
    organization,
    permission_factory,
    role_factory,
    user_factory,
):
    actor = user_factory(email="inactive-permission@example.com")
    role = role_factory(name="Grant Role", code="GRANT_ROLE", organization=organization)
    permission = permission_factory("accounts_user.view", is_active=False)
    grant_system_permission(user=actor, permission_code="accounts_role_permission.grant")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-roles-grant-permission", kwargs={"pk": role.id}),
        {"permission_id": str(permission.id)},
        format="json",
    )

    assert response.status_code == 400
    assert "Permission must be active." in str(response.data)


@pytest.mark.django_db
def test_cannot_grant_permission_to_inactive_role(
    authenticated_client,
    grant_system_permission,
    organization,
    permission_factory,
    role_factory,
    user_factory,
):
    actor = user_factory(email="inactive-role@example.com")
    role = role_factory(name="Grant Role", code="GRANT_ROLE", organization=organization, is_active=False)
    permission = permission_factory("accounts_user.view")
    grant_system_permission(user=actor, permission_code="accounts_role_permission.grant")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-roles-grant-permission", kwargs={"pk": role.id}),
        {"permission_id": str(permission.id)},
        format="json",
    )

    assert response.status_code == 400
    assert "Role must be active." in str(response.data)


@pytest.mark.django_db
def test_duplicate_active_role_permission_grant_is_handled_cleanly(
    authenticated_client,
    grant_system_permission,
    organization,
    permission_factory,
    role_factory,
    user_factory,
):
    actor = user_factory(email="duplicate-role-permission@example.com")
    role = role_factory(name="Grant Role", code="GRANT_ROLE", organization=organization)
    permission = permission_factory("accounts_user.view")
    grant_system_permission(user=actor, permission_code="accounts_role_permission.grant")
    client = authenticated_client(actor)

    first_response = client.post(
        reverse("accounts-roles-grant-permission", kwargs={"pk": role.id}),
        {"permission_id": str(permission.id)},
        format="json",
    )
    second_response = client.post(
        reverse("accounts-roles-grant-permission", kwargs={"pk": role.id}),
        {"permission_id": str(permission.id)},
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.data["id"] == second_response.data["id"]
    assert RolePermission.objects.filter(role=role, permission=permission).count() == 1


@pytest.mark.django_db
def test_inactive_role_permission_can_be_reactivated_via_grant(
    authenticated_client,
    grant_system_permission,
    organization,
    permission_factory,
    role_factory,
    user_factory,
):
    actor = user_factory(email="reactivate-role-permission@example.com")
    role = role_factory(name="Grant Role", code="GRANT_ROLE", organization=organization)
    permission = permission_factory("accounts_user.view")
    role_permission = RolePermission.objects.create(role=role, permission=permission, is_active=False)
    grant_system_permission(user=actor, permission_code="accounts_role_permission.grant")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-roles-grant-permission", kwargs={"pk": role.id}),
        {"permission_id": str(permission.id)},
        format="json",
    )

    role_permission.refresh_from_db()
    assert response.status_code == 201
    assert response.data["id"] == str(role_permission.id)
    assert role_permission.is_active is True


@pytest.mark.django_db
def test_revoke_permission_from_role_sets_is_active_false_and_does_not_delete_row(
    authenticated_client,
    grant_system_permission,
    organization,
    permission_factory,
    role_factory,
    user_factory,
):
    actor = user_factory(email="revoke-role-permission@example.com")
    role = role_factory(name="Grant Role", code="GRANT_ROLE", organization=organization)
    permission = permission_factory("accounts_user.view")
    role_permission = RolePermission.objects.create(role=role, permission=permission)
    grant_system_permission(user=actor, permission_code="accounts_role_permission.revoke")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-roles-revoke-permission", kwargs={"pk": role.id}),
        {"permission_id": str(permission.id)},
        format="json",
    )

    role_permission.refresh_from_db()
    assert response.status_code == 200
    assert role_permission.is_active is False
    assert RolePermission.objects.filter(role=role, permission=permission).count() == 1
