from __future__ import annotations

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

import pytest

from apps.accounts.models import Permission, RolePermission, UserMembership, UserRoleAssignment
from apps.accounts.permissions import user_has_permission


@pytest.mark.django_db
def test_platform_role_can_be_assigned_without_membership(
    authenticated_client,
    grant_system_permission,
    role_factory,
    user_factory,
):
    actor = user_factory(email="assign-platform-actor@example.com")
    target = user_factory(email="assign-platform-target@example.com")
    role = role_factory(name="Platform Role", code="PLATFORM_ROLE")
    grant_system_permission(user=actor, permission_code="accounts_role_assignment.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-role-assignments-list"),
        {"user_id": str(target.id), "role_id": str(role.id)},
        format="json",
    )

    assert response.status_code == 201
    assert UserRoleAssignment.objects.filter(user=target, role=role, is_active=True).exists()


@pytest.mark.django_db
def test_organization_role_requires_active_organization_membership(
    authenticated_client,
    grant_system_permission,
    organization,
    role_factory,
    user_factory,
):
    actor = user_factory(email="assign-org-actor@example.com")
    target = user_factory(email="assign-org-target@example.com")
    role = role_factory(name="Org Role", code="ORG_ROLE", organization=organization)
    grant_system_permission(user=actor, permission_code="accounts_role_assignment.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-role-assignments-list"),
        {"user_id": str(target.id), "role_id": str(role.id)},
        format="json",
    )

    assert response.status_code == 400
    assert "Organization-scoped roles require an active organization membership." in str(response.data)


@pytest.mark.django_db
def test_facility_role_requires_active_facility_membership(
    authenticated_client,
    facility,
    grant_system_permission,
    organization,
    role_factory,
    user_factory,
):
    actor = user_factory(email="assign-facility-actor@example.com")
    target = user_factory(email="assign-facility-target@example.com")
    role = role_factory(name="Facility Role", code="FACILITY_ROLE", organization=organization, facility=facility)
    grant_system_permission(user=actor, permission_code="accounts_role_assignment.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-role-assignments-list"),
        {"user_id": str(target.id), "role_id": str(role.id)},
        format="json",
    )

    assert response.status_code == 400
    assert "Facility-scoped roles require an active matching facility membership." in str(response.data)


@pytest.mark.django_db
def test_cannot_assign_inactive_role(
    authenticated_client,
    grant_system_permission,
    role_factory,
    user_factory,
):
    actor = user_factory(email="assign-inactive-role-actor@example.com")
    target = user_factory(email="assign-inactive-role-target@example.com")
    role = role_factory(name="Inactive Role", code="INACTIVE_ROLE", is_active=False)
    grant_system_permission(user=actor, permission_code="accounts_role_assignment.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-role-assignments-list"),
        {"user_id": str(target.id), "role_id": str(role.id)},
        format="json",
    )

    assert response.status_code == 400
    assert "Role must be active." in str(response.data)


@pytest.mark.django_db
def test_cannot_assign_role_to_inactive_user(
    authenticated_client,
    grant_system_permission,
    role_factory,
    user_factory,
):
    actor = user_factory(email="assign-inactive-user-actor@example.com")
    target = user_factory(email="assign-inactive-user-target@example.com")
    target.is_active = False
    target.save(update_fields=["is_active", "updated_at"])
    role = role_factory(name="Platform Role", code="PLATFORM_ROLE")
    grant_system_permission(user=actor, permission_code="accounts_role_assignment.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-role-assignments-list"),
        {"user_id": str(target.id), "role_id": str(role.id)},
        format="json",
    )

    assert response.status_code == 400
    assert "User must be active." in str(response.data)


@pytest.mark.django_db
def test_duplicate_active_role_assignment_is_handled_cleanly(
    authenticated_client,
    grant_system_permission,
    role_factory,
    user_factory,
):
    actor = user_factory(email="duplicate-assignment-actor@example.com")
    target = user_factory(email="duplicate-assignment-target@example.com")
    role = role_factory(name="Platform Role", code="PLATFORM_ROLE")
    grant_system_permission(user=actor, permission_code="accounts_role_assignment.create")
    client = authenticated_client(actor)

    first_response = client.post(
        reverse("accounts-role-assignments-list"),
        {"user_id": str(target.id), "role_id": str(role.id)},
        format="json",
    )
    second_response = client.post(
        reverse("accounts-role-assignments-list"),
        {"user_id": str(target.id), "role_id": str(role.id)},
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.data["id"] == second_response.data["id"]
    assert UserRoleAssignment.objects.filter(user=target, role=role).count() == 1


@pytest.mark.django_db
def test_inactive_role_assignment_can_be_reactivated(
    authenticated_client,
    grant_system_permission,
    role_factory,
    user_factory,
):
    actor = user_factory(email="reactivate-assignment-actor@example.com")
    target = user_factory(email="reactivate-assignment-target@example.com")
    role = role_factory(name="Platform Role", code="PLATFORM_ROLE")
    assignment = UserRoleAssignment.objects.create(user=target, role=role, is_active=False)
    grant_system_permission(user=actor, permission_code="accounts_role_assignment.reactivate")
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-role-assignments-reactivate", kwargs={"pk": assignment.id}), format="json")

    assignment.refresh_from_db()
    assert response.status_code == 200
    assert assignment.is_active is True


@pytest.mark.django_db
def test_revoke_role_assignment_sets_is_active_false_and_does_not_delete_row(
    authenticated_client,
    grant_system_permission,
    role_factory,
    user_factory,
):
    actor = user_factory(email="revoke-assignment-actor@example.com")
    target = user_factory(email="revoke-assignment-target@example.com")
    role = role_factory(name="Platform Role", code="PLATFORM_ROLE")
    assignment = UserRoleAssignment.objects.create(user=target, role=role)
    grant_system_permission(user=actor, permission_code="accounts_role_assignment.revoke")
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-role-assignments-revoke", kwargs={"pk": assignment.id}), format="json")

    assignment.refresh_from_db()
    assert response.status_code == 200
    assert assignment.is_active is False
    assert UserRoleAssignment.objects.filter(user=target, role=role).count() == 1


@pytest.mark.django_db
def test_permissions_are_never_assigned_directly_to_users(user_factory, role_factory):
    user = user_factory(email="no-direct-perms@example.com")
    role = role_factory(name="Plain Role", code="PLAIN_ROLE")
    UserRoleAssignment.objects.create(user=user, role=role)

    assert user_has_permission(user, "accounts_user.view") is False


@pytest.mark.django_db
def test_superuser_passes_permission_checks(user_factory):
    user = user_factory(email="super-check@example.com")
    user.is_superuser = True
    user.save(update_fields=["is_superuser", "updated_at"])

    assert user_has_permission(user, "any.permission") is True


@pytest.mark.django_db
def test_inactive_user_fails_permission_checks(user_factory):
    user = user_factory(email="inactive-check@example.com")
    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])

    assert user_has_permission(user, "accounts_user.view") is False


@pytest.mark.django_db
def test_active_user_with_active_role_permission_and_permission_passes_permission_checks(
    grant_system_permission,
    user_factory,
):
    user = user_factory(email="effective-permission@example.com")
    grant_system_permission(user=user, permission_code="accounts_user.view")

    assert user_has_permission(user, "accounts_user.view") is True


@pytest.mark.django_db
def test_inactive_role_assignment_fails_permission_checks(grant_system_permission, user_factory):
    user = user_factory(email="inactive-assignment-check@example.com")
    grant_system_permission(
        user=user,
        permission_code="accounts_user.view",
        assignment_is_active=False,
    )

    assert user_has_permission(user, "accounts_user.view") is False


@pytest.mark.django_db
def test_inactive_role_fails_permission_checks(grant_system_permission, user_factory):
    user = user_factory(email="inactive-role-check@example.com")
    grant_system_permission(
        user=user,
        permission_code="accounts_user.view",
        role_is_active=False,
    )

    assert user_has_permission(user, "accounts_user.view") is False


@pytest.mark.django_db
def test_inactive_role_permission_fails_permission_checks(grant_system_permission, user_factory):
    user = user_factory(email="inactive-role-permission-check@example.com")
    grant_system_permission(
        user=user,
        permission_code="accounts_user.view",
        role_permission_is_active=False,
    )

    assert user_has_permission(user, "accounts_user.view") is False


@pytest.mark.django_db
def test_inactive_permission_fails_permission_checks(grant_system_permission, user_factory):
    user = user_factory(email="inactive-permission-check@example.com")
    grant_system_permission(
        user=user,
        permission_code="accounts_user.view",
        permission_is_active=False,
    )

    assert user_has_permission(user, "accounts_user.view") is False


@pytest.mark.django_db
def test_expired_role_assignment_fails_permission_checks(grant_system_permission, user_factory):
    user = user_factory(email="expired-assignment-check@example.com")
    grant_system_permission(
        user=user,
        permission_code="accounts_user.view",
        assignment_ends_at=timezone.now() - timedelta(minutes=1),
    )

    assert user_has_permission(user, "accounts_user.view") is False


@pytest.mark.django_db
def test_organization_scoped_permission_requires_organization_membership(
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory(email="org-scope-check@example.com")
    grant_system_permission(
        user=user,
        permission_code="accounts_role.create",
        scope="organization",
        organization=organization,
        create_membership=False,
    )

    assert user_has_permission(user, "accounts_role.create", organization=organization.id) is False


@pytest.mark.django_db
def test_facility_scoped_permission_requires_facility_membership(
    facility,
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory(email="facility-scope-check@example.com")
    grant_system_permission(
        user=user,
        permission_code="accounts_role.create",
        scope="facility",
        organization=organization,
        facility=facility,
        create_membership=False,
    )

    assert user_has_permission(user, "accounts_role.create", organization=organization.id, facility=facility.id) is False
