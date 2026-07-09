from __future__ import annotations

from django.urls import reverse

import pytest

from apps.accounts.models import User


@pytest.mark.django_db
def test_unauthenticated_user_cannot_list_users(api_client):
    response = api_client.get(reverse("accounts-users-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_unauthorized_normal_user_cannot_create_users(api_client, authenticated_client, user_factory):
    user = user_factory(email="normal-create-user@example.com")
    client = authenticated_client(user)

    response = client.post(
        reverse("accounts-users-list"),
        {
            "email": "created@example.com",
            "phone_number": "+255711111111",
            "password": "Password123!",
            "first_name": "Created",
            "last_name": "User",
        },
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_user_with_correct_permission_can_create_user(
    authenticated_client,
    grant_system_permission,
    organization,
    user_factory,
):
    actor = user_factory(email="creator@example.com")
    grant_system_permission(user=actor, permission_code="accounts_user.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-users-list"),
        {
            "email": "created@example.com",
            "phone_number": "+255722222222",
            "password": "Password123!",
            "first_name": "Created",
            "last_name": "User",
        },
        format="json",
    )

    created_user = User.objects.get(email="created@example.com")

    assert response.status_code == 201
    assert response.data["email"] == "created@example.com"
    assert "password" not in response.data
    assert "is_staff" not in response.data
    assert "is_superuser" not in response.data
    assert created_user.is_staff is False
    assert created_user.is_superuser is False


@pytest.mark.django_db
def test_activate_user_works_with_permission(authenticated_client, grant_system_permission, user_factory):
    actor = user_factory(email="activate-actor@example.com")
    target = user_factory(email="inactive-target@example.com")
    target.is_active = False
    target.save(update_fields=["is_active", "updated_at"])
    grant_system_permission(user=actor, permission_code="accounts_user.activate")
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-users-activate", kwargs={"pk": target.id}), format="json")

    target.refresh_from_db()
    assert response.status_code == 200
    assert target.is_active is True


@pytest.mark.django_db
def test_deactivate_user_works_with_permission(authenticated_client, grant_system_permission, user_factory):
    actor = user_factory(email="deactivate-actor@example.com")
    target = user_factory(email="active-target@example.com")
    grant_system_permission(user=actor, permission_code="accounts_user.deactivate")
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-users-deactivate", kwargs={"pk": target.id}), format="json")

    target.refresh_from_db()
    assert response.status_code == 200
    assert target.is_active is False


@pytest.mark.django_db
def test_verify_email_works_with_permission(authenticated_client, grant_system_permission, user_factory):
    actor = user_factory(email="verify-email-actor@example.com")
    target = user_factory(email="verify-email-target@example.com")
    grant_system_permission(user=actor, permission_code="accounts_user.verify_email")
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-users-verify-email", kwargs={"pk": target.id}), format="json")

    target.refresh_from_db()
    assert response.status_code == 200
    assert target.email_verified_at is not None


@pytest.mark.django_db
def test_verify_phone_works_with_permission(authenticated_client, grant_system_permission, user_factory):
    actor = user_factory(email="verify-phone-actor@example.com")
    target = user_factory(email="verify-phone-target@example.com", phone_number="+255733333333")
    grant_system_permission(user=actor, permission_code="accounts_user.verify_phone")
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-users-verify-phone", kwargs={"pk": target.id}), format="json")

    target.refresh_from_db()
    assert response.status_code == 200
    assert target.phone_verified_at is not None
