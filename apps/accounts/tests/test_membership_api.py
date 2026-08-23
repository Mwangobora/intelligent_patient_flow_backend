from __future__ import annotations

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

import pytest

from apps.accounts.models import UserMembership


@pytest.mark.django_db
def test_create_organization_membership_works(authenticated_client, grant_system_permission, organization, user_factory):
    actor = user_factory(email="membership-creator@example.com")
    target = user_factory(email="membership-target@example.com")
    grant_system_permission(user=actor, permission_code="accounts_membership.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-memberships-organization"),
        {
            "user_id": str(target.id),
            "organization_id": str(organization.id),
        },
        format="json",
    )

    assert response.status_code == 201
    assert UserMembership.objects.filter(user=target, organization=organization, facility__isnull=True).exists()


@pytest.mark.django_db
def test_create_facility_membership_works(
    authenticated_client,
    facility,
    grant_system_permission,
    organization,
    user_factory,
):
    actor = user_factory(email="facility-membership-creator@example.com")
    target = user_factory(email="facility-membership-target@example.com")
    grant_system_permission(user=actor, permission_code="accounts_membership.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-memberships-facility"),
        {
            "user_id": str(target.id),
            "organization_id": str(organization.id),
            "facility_id": str(facility.id),
        },
        format="json",
    )

    assert response.status_code == 201
    assert UserMembership.objects.filter(user=target, facility=facility).exists()


@pytest.mark.django_db
def test_facility_membership_must_match_organization(
    authenticated_client,
    grant_system_permission,
    organization,
    other_org_facility,
    user_factory,
):
    actor = user_factory(email="membership-mismatch@example.com")
    target = user_factory(email="membership-mismatch-target@example.com")
    grant_system_permission(user=actor, permission_code="accounts_membership.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-memberships-facility"),
        {
            "user_id": str(target.id),
            "organization_id": str(organization.id),
            "facility_id": str(other_org_facility.id),
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Facility must belong to the selected organization." in str(response.data)


@pytest.mark.django_db
def test_inactive_user_cannot_receive_membership(authenticated_client, grant_system_permission, organization, user_factory):
    actor = user_factory(email="inactive-membership-actor@example.com")
    target = user_factory(email="inactive-membership-target@example.com")
    target.is_active = False
    target.save(update_fields=["is_active", "updated_at"])
    grant_system_permission(user=actor, permission_code="accounts_membership.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-memberships-organization"),
        {"user_id": str(target.id), "organization_id": str(organization.id)},
        format="json",
    )

    assert response.status_code == 400
    assert "User must be active." in str(response.data)


@pytest.mark.django_db
def test_inactive_organization_cannot_be_used(authenticated_client, grant_system_permission, organization, user_factory):
    actor = user_factory(email="inactive-org-actor@example.com")
    target = user_factory(email="inactive-org-target@example.com")
    organization.is_active = False
    organization.save(update_fields=["is_active", "updated_at"])
    grant_system_permission(user=actor, permission_code="accounts_membership.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-memberships-organization"),
        {"user_id": str(target.id), "organization_id": str(organization.id)},
        format="json",
    )

    assert response.status_code == 400
    assert "Organization must be active." in str(response.data)


@pytest.mark.django_db
def test_inactive_facility_cannot_be_used(
    authenticated_client,
    facility,
    grant_system_permission,
    organization,
    user_factory,
):
    actor = user_factory(email="inactive-facility-actor@example.com")
    target = user_factory(email="inactive-facility-target@example.com")
    facility.is_active = False
    facility.save(update_fields=["is_active", "updated_at"])
    grant_system_permission(user=actor, permission_code="accounts_membership.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-memberships-facility"),
        {
            "user_id": str(target.id),
            "organization_id": str(organization.id),
            "facility_id": str(facility.id),
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Facility must be active." in str(response.data)


@pytest.mark.django_db
def test_duplicate_membership_fails_cleanly(authenticated_client, grant_system_permission, organization, user_factory):
    actor = user_factory(email="duplicate-membership-actor@example.com")
    target = user_factory(email="duplicate-membership-target@example.com")
    membership = UserMembership.objects.create(user=target, organization=organization)
    grant_system_permission(user=actor, permission_code="accounts_membership.create")
    client = authenticated_client(actor)

    response = client.post(
        reverse("accounts-memberships-organization"),
        {"user_id": str(target.id), "organization_id": str(organization.id)},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["id"] == str(membership.id)
    assert UserMembership.objects.filter(user=target, organization=organization, facility__isnull=True).count() == 1


@pytest.mark.django_db
def test_existing_future_facility_membership_is_refreshed_for_today(
    authenticated_client,
    facility,
    grant_system_permission,
    organization,
    user_factory,
):
    actor = user_factory(email="refresh-future-membership-actor@example.com")
    target = user_factory(email="refresh-future-membership-target@example.com")
    future_start = timezone.now() + timedelta(days=30)
    membership = UserMembership.objects.create(
        user=target,
        organization=organization,
        facility=facility,
        starts_at=future_start,
    )
    grant_system_permission(user=actor, permission_code="accounts_membership.create")
    client = authenticated_client(actor)
    starts_at = timezone.now()

    response = client.post(
        reverse("accounts-memberships-facility"),
        {
            "user_id": str(target.id),
            "organization_id": str(organization.id),
            "facility_id": str(facility.id),
            "starts_at": starts_at.isoformat(),
        },
        format="json",
    )

    membership.refresh_from_db()
    assert response.status_code == 201
    assert response.data["id"] == str(membership.id)
    assert membership.starts_at <= timezone.now()
    assert membership.is_active is True
    assert UserMembership.objects.filter(user=target, facility=facility).count() == 1


@pytest.mark.django_db
def test_deactivate_membership_works(authenticated_client, grant_system_permission, organization, user_factory):
    actor = user_factory(email="deactivate-membership-actor@example.com")
    target = user_factory(email="deactivate-membership-target@example.com")
    membership = UserMembership.objects.create(user=target, organization=organization)
    grant_system_permission(user=actor, permission_code="accounts_membership.deactivate")
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-memberships-deactivate", kwargs={"pk": membership.id}), format="json")

    membership.refresh_from_db()
    assert response.status_code == 200
    assert membership.is_active is False


@pytest.mark.django_db
def test_reactivate_membership_works(authenticated_client, grant_system_permission, organization, user_factory):
    actor = user_factory(email="reactivate-membership-actor@example.com")
    target = user_factory(email="reactivate-membership-target@example.com")
    membership = UserMembership.objects.create(user=target, organization=organization, is_active=False)
    grant_system_permission(user=actor, permission_code="accounts_membership.reactivate")
    client = authenticated_client(actor)

    response = client.post(reverse("accounts-memberships-reactivate", kwargs={"pk": membership.id}), format="json")

    membership.refresh_from_db()
    assert response.status_code == 200
    assert membership.is_active is True


@pytest.mark.django_db
def test_end_membership_sets_ends_at_correctly(authenticated_client, grant_system_permission, organization, user_factory):
    actor = user_factory(email="end-membership-actor@example.com")
    target = user_factory(email="end-membership-target@example.com")
    membership = UserMembership.objects.create(user=target, organization=organization)
    grant_system_permission(user=actor, permission_code="accounts_membership.end")
    client = authenticated_client(actor)
    target_end = timezone.now() + timedelta(days=1)

    response = client.post(
        reverse("accounts-memberships-end", kwargs={"pk": membership.id}),
        {"ends_at": target_end.isoformat()},
        format="json",
    )

    membership.refresh_from_db()
    assert response.status_code == 200
    assert membership.ends_at is not None
    assert membership.ends_at.isoformat().startswith(target_end.replace(microsecond=0).isoformat()[:19])


@pytest.mark.django_db
def test_membership_ends_at_cannot_be_before_starts_at(
    authenticated_client,
    grant_system_permission,
    organization,
    user_factory,
):
    actor = user_factory(email="membership-date-actor@example.com")
    target = user_factory(email="membership-date-target@example.com")
    grant_system_permission(user=actor, permission_code="accounts_membership.create")
    client = authenticated_client(actor)
    starts_at = timezone.now()
    ends_at = starts_at - timedelta(hours=1)

    response = client.post(
        reverse("accounts-memberships-organization"),
        {
            "user_id": str(target.id),
            "organization_id": str(organization.id),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400
    assert "ends_at" in str(response.data)
