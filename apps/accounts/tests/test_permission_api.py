from __future__ import annotations

from django.urls import reverse

import pytest

from apps.accounts.models import Permission


@pytest.mark.django_db
def test_permissions_are_not_seeded_automatically():
    assert Permission.objects.count() == 0


@pytest.mark.django_db
def test_unauthenticated_user_cannot_access_permission_endpoints(api_client):
    response = api_client.get(reverse("accounts-permissions-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_normal_user_without_permission_cannot_create_permission(authenticated_client, user_factory):
    user = user_factory(email="normal-permission@example.com")
    client = authenticated_client(user)

    response = client.post(
        reverse("accounts-permissions-list"),
        {"name": "Create Users", "module": "accounts_user", "action": "create"},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_user_with_permission_can_create_permission(authenticated_client, grant_system_permission, user_factory):
    actor = user_factory(email="permission-creator@example.com")
    grant_system_permission(user=actor, permission_code="accounts_permission.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-permissions-list"),
        {
            "name": "Create Appointments",
            "module": "appointments",
            "action": "create",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["code"] == "appointments.create"


@pytest.mark.django_db
def test_permission_code_must_follow_module_action_format(authenticated_client, grant_system_permission, user_factory):
    actor = user_factory(email="permission-format@example.com")
    grant_system_permission(user=actor, permission_code="accounts_permission.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-permissions-list"),
        {
            "name": "Bad Permission",
            "module": "appointments",
            "action": "create",
            "code": "BAD_FORMAT",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "module.action" in str(response.data)


@pytest.mark.django_db
def test_duplicate_permission_code_fails(authenticated_client, grant_system_permission, permission_factory, user_factory):
    actor = user_factory(email="permission-duplicate-code@example.com")
    grant_system_permission(user=actor, permission_code="accounts_permission.create")
    permission_factory("appointments.create", name="Existing Appointments Create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-permissions-list"),
        {
            "name": "Another Create Appointments",
            "module": "appointments",
            "action": "create",
            "code": "appointments.create",
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_duplicate_module_action_pair_fails(authenticated_client, grant_system_permission, permission_factory, user_factory):
    actor = user_factory(email="permission-duplicate-pair@example.com")
    grant_system_permission(user=actor, permission_code="accounts_permission.create")
    permission_factory("appointments.create", name="Existing Appointments Create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-permissions-list"),
        {
            "name": "Duplicate Pair",
            "module": "appointments",
            "action": "create",
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_deactivate_permission_works(authenticated_client, grant_system_permission, permission_factory, user_factory):
    actor = user_factory(email="permission-deactivate@example.com")
    permission = permission_factory("appointments.cancel", name="Cancel Appointments")
    grant_system_permission(user=actor, permission_code="accounts_permission.deactivate")
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-permissions-deactivate", kwargs={"pk": permission.id}), format="json")

    permission.refresh_from_db()
    assert response.status_code == 200
    assert permission.is_active is False
