from __future__ import annotations

from datetime import date
import re

from django.urls import reverse

import pytest

from apps.practitioners.models import (
    Practitioner,
    PractitionerCredential,
    PractitionerFacilityAssignment,
)


@pytest.mark.django_db
def test_unauthenticated_users_cannot_access_protected_endpoints(api_client):
    response = api_client.get(reverse("practitioners-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_unauthorized_users_cannot_create_update_or_deactivate(authenticated_client, organization, practitioner, practitioner_type, user_factory):
    user = user_factory()
    client = authenticated_client(user)

    create_response = client.post(
        reverse("practitioners-list"),
        {
            "organization_id": str(organization.id),
            "practitioner_type_id": str(practitioner_type.id),
            "first_name": "No",
            "last_name": "Access",
        },
        format="json",
    )
    update_response = client.patch(
        reverse("practitioners-detail", kwargs={"pk": practitioner.id}),
        {"first_name": "Blocked"},
        format="json",
    )
    deactivate_response = client.post(reverse("practitioners-deactivate", kwargs={"pk": practitioner.id}), format="json")

    assert create_response.status_code == 403
    assert update_response.status_code == 403
    assert deactivate_response.status_code == 403


@pytest.mark.django_db
def test_authorized_user_can_create_practitioner_type_and_code_is_generated(authenticated_client, grant_system_permission, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="practitioners_type.manage")
    client = authenticated_client(user)

    response = client.post(reverse("practitioners-types-list"), {"name": "Clinical Officer"}, format="json")

    assert response.status_code == 201
    assert re.fullmatch(r"PRT\d{4}", response.data["code"])


@pytest.mark.django_db
def test_duplicate_practitioner_type_name_fails_and_supplied_code_is_ignored(authenticated_client, grant_system_permission, practitioner_type, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="practitioners_type.manage")
    client = authenticated_client(user)

    name_response = client.post(
        reverse("practitioners-types-list"),
        {"name": practitioner_type.name},
        format="json",
    )
    code_response = client.post(
        reverse("practitioners-types-list"),
        {"name": "Different Type", "code": practitioner_type.code},
        format="json",
    )

    assert name_response.status_code == 400
    assert code_response.status_code == 201
    assert code_response.data["code"] != practitioner_type.code
    assert re.fullmatch(r"PRT\d{4}", code_response.data["code"])


@pytest.mark.django_db
def test_authorized_user_can_create_practitioner_and_values_are_normalized(
    authenticated_client,
    grant_system_permission,
    organization,
    practitioner_type,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_practitioner.create",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("practitioners-list"),
        {
            "organization_id": str(organization.id),
            "practitioner_type_id": str(practitioner_type.id),
            "first_name": "Mariam",
            "last_name": "Daktari",
            "email": "MARIAM@EXAMPLE.COM",
            "phone_number": "+255 712-345-678",
        },
        format="json",
    )

    created = Practitioner.objects.get(id=response.data["id"])

    assert response.status_code == 201
    assert response.data["practitioner_number"].startswith("PRAC-")
    assert created.email == "mariam@example.com"
    assert created.phone_number == "+255712345678"


@pytest.mark.django_db
def test_cannot_create_practitioner_under_inactive_organization(
    authenticated_client,
    grant_system_permission,
    organization,
    practitioner_type,
    user_factory,
):
    user = user_factory()
    organization.is_active = False
    organization.save(update_fields=["is_active", "updated_at"])
    grant_system_permission(
        user=user,
        permission_code="practitioners_practitioner.create",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("practitioners-list"),
        {
            "organization_id": str(organization.id),
            "practitioner_type_id": str(practitioner_type.id),
            "first_name": "John",
            "last_name": "InactiveOrg",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Organization must be active." in str(response.data)


@pytest.mark.django_db
def test_cannot_create_practitioner_with_inactive_practitioner_type(
    authenticated_client,
    grant_system_permission,
    inactive_practitioner_type,
    organization,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_practitioner.create",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("practitioners-list"),
        {
            "organization_id": str(organization.id),
            "practitioner_type_id": str(inactive_practitioner_type.id),
            "first_name": "John",
            "last_name": "InactiveType",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Practitioner type must be active." in str(response.data)


@pytest.mark.django_db
def test_same_user_cannot_have_two_practitioner_profiles_in_same_organization(
    authenticated_client,
    grant_system_permission,
    organization,
    practitioner_type,
    practitioner_user,
    practitioner_with_user,
    user_factory,
):
    actor = user_factory()
    grant_system_permission(
        user=actor,
        permission_code="practitioners_practitioner.create",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(actor)

    response = client.post(
        reverse("practitioners-list"),
        {
            "organization_id": str(organization.id),
            "practitioner_type_id": str(practitioner_type.id),
            "user_id": str(practitioner_user.id),
            "first_name": "Second",
            "last_name": "Profile",
        },
        format="json",
    )

    assert practitioner_with_user.user_id == practitioner_user.id
    assert response.status_code == 400
    assert "already has a practitioner profile" in str(response.data)


@pytest.mark.django_db
def test_practitioner_deactivate_uses_is_active_false_and_does_not_delete(
    authenticated_client,
    grant_system_permission,
    organization,
    practitioner,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_practitioner.deactivate",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(reverse("practitioners-deactivate", kwargs={"pk": practitioner.id}), format="json")
    practitioner.refresh_from_db()

    assert response.status_code == 200
    assert practitioner.is_active is False
    assert Practitioner.objects.filter(pk=practitioner.id).exists()


@pytest.mark.django_db
def test_assign_practitioner_to_facility(
    authenticated_client,
    facility,
    grant_system_permission,
    organization,
    practitioner,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_assignment.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("practitioners-practitioner-facility-assignments-list", kwargs={"practitioner_pk": practitioner.id}),
        {
            "facility_id": str(facility.id),
            "starts_on": "2026-01-01",
            "is_primary": True,
        },
        format="json",
    )

    assert response.status_code == 201
    assert str(response.data["facility"]) == str(facility.id)


@pytest.mark.django_db
def test_facility_must_belong_to_practitioner_organization(
    authenticated_client,
    grant_system_permission,
    organization,
    other_org_facility,
    practitioner,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_assignment.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("practitioners-practitioner-facility-assignments-list", kwargs={"practitioner_pk": practitioner.id}),
        {
            "facility_id": str(other_org_facility.id),
            "starts_on": "2026-01-01",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "same organization" in str(response.data)


@pytest.mark.django_db
def test_only_one_active_primary_facility_assignment_per_practitioner(
    authenticated_client,
    facility,
    grant_system_permission,
    organization,
    practitioner,
    second_facility,
    user_factory,
):
    existing = PractitionerFacilityAssignment.objects.create(
        practitioner=practitioner,
        facility=facility,
        starts_on=date(2026, 1, 1),
        is_primary=True,
    )
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_assignment.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("practitioners-practitioner-facility-assignments-list", kwargs={"practitioner_pk": practitioner.id}),
        {
            "facility_id": str(second_facility.id),
            "starts_on": "2026-02-01",
            "is_primary": True,
        },
        format="json",
    )

    created = PractitionerFacilityAssignment.objects.get(id=response.data["id"])
    existing.refresh_from_db()

    assert response.status_code == 201
    assert existing.is_primary is False
    assert created.is_primary is True


@pytest.mark.django_db
def test_department_assignment_department_must_belong_to_same_facility(
    authenticated_client,
    facility_assignment,
    grant_system_permission,
    organization,
    other_facility_department,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_assignment.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse(
            "practitioners-facility-department-assignments-list",
            kwargs={"practitioner_facility_assignment_pk": facility_assignment.id},
        ),
        {
            "department_id": str(other_facility_department.id),
            "starts_on": "2026-01-05",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "same facility" in str(response.data)


@pytest.mark.django_db
def test_specialty_assignment_facility_specialty_must_belong_to_same_facility(
    authenticated_client,
    facility_assignment,
    grant_system_permission,
    organization,
    other_facility_specialty,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_assignment.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse(
            "practitioners-facility-specialty-assignments-list",
            kwargs={"practitioner_facility_assignment_pk": facility_assignment.id},
        ),
        {
            "facility_specialty_id": str(other_facility_specialty.id),
            "starts_on": "2026-01-05",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "same facility" in str(response.data)


@pytest.mark.django_db
def test_specialty_assignment_requiring_department_validates_department_assignment_exists(
    authenticated_client,
    department_facility_specialty,
    facility_assignment,
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_assignment.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse(
            "practitioners-facility-specialty-assignments-list",
            kwargs={"practitioner_facility_assignment_pk": facility_assignment.id},
        ),
        {
            "facility_specialty_id": str(department_facility_specialty.id),
            "starts_on": "2026-01-05",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Department assignment must cover the full specialty-assignment period." in str(response.data)


@pytest.mark.django_db
def test_credential_type_can_be_global_or_organization_specific(
    authenticated_client,
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="practitioners_credential_type.manage")
    client = authenticated_client(user)

    global_response = client.post(
        reverse("practitioners-credential-types-list"),
        {"name": "Board Certificate"},
        format="json",
    )
    grant_system_permission(
        user=user,
        permission_code="practitioners_credential_type.manage",
        scope="organization",
        organization=organization,
    )
    org_response = client.post(
        reverse("practitioners-credential-types-list"),
        {"organization_id": str(organization.id), "name": "Hospital Badge"},
        format="json",
    )

    assert global_response.status_code == 201
    assert global_response.data["organization"] is None
    assert org_response.status_code == 201
    assert str(org_response.data["organization"]) == str(organization.id)


@pytest.mark.django_db
def test_duplicate_credential_type_name_fails_and_supplied_code_is_ignored(
    authenticated_client,
    credential_type_org,
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_credential_type.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    name_response = client.post(
        reverse("practitioners-credential-types-list"),
        {"organization_id": str(organization.id), "name": credential_type_org.name},
        format="json",
    )
    code_response = client.post(
        reverse("practitioners-credential-types-list"),
        {"organization_id": str(organization.id), "name": "Different Name", "code": credential_type_org.code},
        format="json",
    )

    assert name_response.status_code == 400
    assert code_response.status_code == 201
    assert code_response.data["code"] != credential_type_org.code
    assert re.fullmatch(r"PCT\d{4}", code_response.data["code"])


@pytest.mark.django_db
def test_add_credential_stores_encrypted_and_hash_fields_not_plaintext(
    authenticated_client,
    credential_type_org,
    grant_system_permission,
    organization,
    practitioner,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_credential.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)
    raw_number = "LIC-12345-XYZ"

    response = client.post(
        reverse("practitioners-practitioner-credentials-list", kwargs={"practitioner_pk": practitioner.id}),
        {
            "credential_type_id": str(credential_type_org.id),
            "credential_number": raw_number,
            "issued_on": "2026-01-01",
        },
        format="json",
    )

    credential = PractitionerCredential.objects.get(id=response.data["id"])

    assert response.status_code == 201
    assert credential.credential_number_encrypted != raw_number
    assert credential.credential_number_hash != raw_number
    assert len(credential.credential_number_hash) == 64
    assert "credential_number_encrypted" not in response.data
    assert "credential_number_hash" not in response.data


@pytest.mark.django_db
def test_duplicate_credential_by_type_hash_fails(
    authenticated_client,
    credential_type_org,
    grant_system_permission,
    organization,
    practitioner,
    practitioner_type,
    user_factory,
):
    second_practitioner = Practitioner.objects.create(
        organization=organization,
        practitioner_type=practitioner_type,
        practitioner_number="PRAC-000202",
        first_name="Second",
        last_name="Doctor",
    )
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_credential.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    first_response = client.post(
        reverse("practitioners-practitioner-credentials-list", kwargs={"practitioner_pk": practitioner.id}),
        {"credential_type_id": str(credential_type_org.id), "credential_number": "SAME-CRED-001"},
        format="json",
    )
    second_response = client.post(
        reverse("practitioners-practitioner-credentials-list", kwargs={"practitioner_pk": second_practitioner.id}),
        {"credential_type_id": str(credential_type_org.id), "credential_number": "SAME-CRED-001"},
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400


@pytest.mark.django_db
def test_credential_requiring_expiry_rejects_missing_expires_on(
    authenticated_client,
    credential_type_global,
    grant_system_permission,
    organization,
    practitioner,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_credential.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("practitioners-practitioner-credentials-list", kwargs={"practitioner_pk": practitioner.id}),
        {"credential_type_id": str(credential_type_global.id), "credential_number": "REQ-EXP-001"},
        format="json",
    )

    assert response.status_code == 400
    assert "requires an expiry date" in str(response.data)


@pytest.mark.django_db
def test_verify_credential_works_and_sets_verified_fields(
    authenticated_client,
    credential_type_org,
    grant_system_permission,
    organization,
    practitioner,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_credential.manage",
        scope="organization",
        organization=organization,
    )
    grant_system_permission(
        user=user,
        permission_code="practitioners_credential.verify",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    create_response = client.post(
        reverse("practitioners-practitioner-credentials-list", kwargs={"practitioner_pk": practitioner.id}),
        {
            "credential_type_id": str(credential_type_org.id),
            "credential_number": "VERIFY-100",
        },
        format="json",
    )
    verify_response = client.post(
        reverse("practitioners-credentials-verify", kwargs={"pk": create_response.data["id"]}),
        format="json",
    )

    assert verify_response.status_code == 200
    assert verify_response.data["verification_status"] == PractitionerCredential.VerificationStatus.VERIFIED
    assert verify_response.data["verified_at"] is not None
    assert str(verify_response.data["verified_by"]) == str(user.id)


@pytest.mark.django_db
def test_reject_credential_works_according_to_status_rules(
    authenticated_client,
    credential_type_org,
    grant_system_permission,
    organization,
    practitioner,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_credential.manage",
        scope="organization",
        organization=organization,
    )
    grant_system_permission(
        user=user,
        permission_code="practitioners_credential.verify",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    create_response = client.post(
        reverse("practitioners-practitioner-credentials-list", kwargs={"practitioner_pk": practitioner.id}),
        {
            "credential_type_id": str(credential_type_org.id),
            "credential_number": "REJECT-100",
        },
        format="json",
    )
    reject_response = client.post(
        reverse("practitioners-credentials-reject", kwargs={"pk": create_response.data["id"]}),
        format="json",
    )

    assert reject_response.status_code == 200
    assert reject_response.data["verification_status"] == PractitionerCredential.VerificationStatus.REJECTED
    assert reject_response.data["verified_at"] is not None
    assert str(reject_response.data["verified_by"]) == str(user.id)


@pytest.mark.django_db
def test_encrypted_and_hash_fields_are_not_exposed_in_api_responses(
    authenticated_client,
    credential_type_org,
    grant_system_permission,
    organization,
    practitioner,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="practitioners_credential.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    create_response = client.post(
        reverse("practitioners-practitioner-credentials-list", kwargs={"practitioner_pk": practitioner.id}),
        {
            "credential_type_id": str(credential_type_org.id),
            "credential_number": "MASK-100",
        },
        format="json",
    )
    detail_response = client.get(reverse("practitioners-credentials-detail", kwargs={"pk": create_response.data["id"]}))
    list_response = client.get(
        reverse("practitioners-practitioner-credentials-list", kwargs={"practitioner_pk": practitioner.id})
    )

    assert detail_response.status_code == 200
    assert list_response.status_code == 200
    for payload in [create_response.data, detail_response.data, list_response.data[0]]:
        assert "credential_number_encrypted" not in payload
        assert "credential_number_hash" not in payload
        assert "credential_number" not in payload
