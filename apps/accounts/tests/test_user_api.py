from __future__ import annotations

from django.urls import reverse

import pytest

from apps.accounts.models import User, UserMembership, UserRoleAssignment


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


def _add_user_to_organization(user, organization):
    return UserMembership.objects.create(user=user, organization=organization)


@pytest.mark.django_db
def test_user_list_includes_access_summary(
    authenticated_client,
    grant_system_permission,
    organization,
    role_factory,
    user_factory,
):
    actor = user_factory(email="list-summary-actor@example.com")
    target = user_factory(email="list-summary-target@example.com")
    membership = UserMembership.objects.create(user=target, organization=organization)
    role = role_factory(name="Receptionist", code="RECEPTIONIST", organization=organization)
    assignment = UserRoleAssignment.objects.create(user=target, role=role)
    grant_system_permission(user=actor, permission_code="accounts_user.view", scope="organization", organization=organization)
    client = authenticated_client(actor)

    response = client.get(reverse("accounts-users-list"), {"organization_id": str(organization.id)})

    row = next(item for item in response.data if item["id"] == str(target.id))
    assert response.status_code == 200
    assert row["memberships"][0]["id"] == str(membership.id)
    assert row["role_assignments"][0]["id"] == str(assignment.id)
    assert row["role_assignments"][0]["role_name"] == "Receptionist"


@pytest.mark.django_db
def test_activate_user_works_with_permission(authenticated_client, grant_system_permission, organization, user_factory):
    actor = user_factory(email="activate-actor@example.com")
    target = user_factory(email="inactive-target@example.com")
    _add_user_to_organization(target, organization)
    target.is_active = False
    target.save(update_fields=["is_active", "updated_at"])
    grant_system_permission(user=actor, permission_code="accounts_user.activate", scope="organization", organization=organization)
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-users-activate", kwargs={"pk": target.id}), {"organization_id": str(organization.id)}, format="json")

    target.refresh_from_db()
    assert response.status_code == 200
    assert target.is_active is True


@pytest.mark.django_db
def test_deactivate_user_works_with_permission(authenticated_client, grant_system_permission, organization, user_factory):
    actor = user_factory(email="deactivate-actor@example.com")
    target = user_factory(email="active-target@example.com")
    _add_user_to_organization(target, organization)
    grant_system_permission(user=actor, permission_code="accounts_user.deactivate", scope="organization", organization=organization)
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-users-deactivate", kwargs={"pk": target.id}), {"organization_id": str(organization.id)}, format="json")

    target.refresh_from_db()
    assert response.status_code == 200
    assert target.is_active is False


@pytest.mark.django_db
def test_verify_email_works_with_permission(authenticated_client, grant_system_permission, organization, user_factory):
    actor = user_factory(email="verify-email-actor@example.com")
    target = user_factory(email="verify-email-target@example.com")
    _add_user_to_organization(target, organization)
    grant_system_permission(user=actor, permission_code="accounts_user.verify_email", scope="organization", organization=organization)
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-users-verify-email", kwargs={"pk": target.id}), {"organization_id": str(organization.id)}, format="json")

    target.refresh_from_db()
    assert response.status_code == 200
    assert target.email_verified_at is not None


@pytest.mark.django_db
def test_verify_phone_works_with_permission(authenticated_client, grant_system_permission, organization, user_factory):
    actor = user_factory(email="verify-phone-actor@example.com")
    target = user_factory(email="verify-phone-target@example.com", phone_number="+255733333333")
    _add_user_to_organization(target, organization)
    grant_system_permission(user=actor, permission_code="accounts_user.verify_phone", scope="organization", organization=organization)
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-users-verify-phone", kwargs={"pk": target.id}), {"organization_id": str(organization.id)}, format="json")

    target.refresh_from_db()
    assert response.status_code == 200
    assert target.phone_verified_at is not None
