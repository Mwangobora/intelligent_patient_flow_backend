from __future__ import annotations

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

import pytest

from apps.accounts.models import User
from apps.patients.models import Patient, PatientAccessGrant, PatientAddress, PatientIdentifier, RelatedPersonContact


@pytest.mark.django_db
def test_unauthenticated_users_cannot_access_protected_endpoints(api_client):
    response = api_client.get(reverse("patients-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_unauthorized_users_cannot_create_update_or_deactivate(authenticated_client, organization, patient, user_factory):
    user = user_factory()
    client = authenticated_client(user)

    create_response = client.post(
        reverse("patients-list"),
        {
            "organization_id": str(organization.id),
            "first_name": "Unauth",
            "last_name": "Denied",
        },
        format="json",
    )
    update_response = client.patch(
        reverse("patients-detail", kwargs={"pk": patient.id}),
        {"first_name": "Denied"},
        format="json",
    )
    deactivate_response = client.post(reverse("patients-deactivate", kwargs={"pk": patient.id}), format="json")

    assert create_response.status_code == 403
    assert update_response.status_code == 403
    assert deactivate_response.status_code == 403


@pytest.mark.django_db
def test_authorized_user_can_create_patient_and_number_email_phone_are_normalized(
    authenticated_client,
    facility,
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_patient.create",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("patients-list"),
        {
            "organization_id": str(organization.id),
            "registered_facility_id": str(facility.id),
            "first_name": "John",
            "last_name": "Citizen",
            "email": "PATIENT@EXAMPLE.COM",
            "phone_number": "+255 712-345-678",
        },
        format="json",
    )

    created = Patient.objects.get(id=response.data["id"])

    assert response.status_code == 201
    assert response.data["patient_number"].startswith("PAT-")
    assert created.email == "patient@example.com"
    assert created.phone_number == "+255712345678"


@pytest.mark.django_db
def test_cannot_create_patient_under_inactive_organization(
    authenticated_client,
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory()
    organization.is_active = False
    organization.save(update_fields=["is_active", "updated_at"])
    grant_system_permission(
        user=user,
        permission_code="patients_patient.create",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("patients-list"),
        {
            "organization_id": str(organization.id),
            "first_name": "John",
            "last_name": "Citizen",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Organization must be active." in str(response.data)


@pytest.mark.django_db
def test_registered_facility_must_belong_to_same_organization(
    authenticated_client,
    grant_system_permission,
    organization,
    other_org_facility,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_patient.create",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("patients-list"),
        {
            "organization_id": str(organization.id),
            "registered_facility_id": str(other_org_facility.id),
            "first_name": "John",
            "last_name": "Citizen",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Registered facility must belong to the same organization" in str(response.data)


@pytest.mark.django_db
def test_date_of_birth_cannot_be_in_future(authenticated_client, grant_system_permission, organization, user_factory):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_patient.create",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("patients-list"),
        {
            "organization_id": str(organization.id),
            "first_name": "Baby",
            "last_name": "Future",
            "date_of_birth": (timezone.localdate() + timedelta(days=1)).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Date of birth cannot be in the future." in str(response.data)


@pytest.mark.django_db
def test_same_user_cannot_have_two_patient_profiles_in_same_organization(
    authenticated_client,
    grant_system_permission,
    organization,
    patient_user,
    patient_with_user,
):
    user = User.objects.create_user(
        email="creator@example.com",
        phone_number="+255788111222",
        password="Password123!",
        first_name="Creator",
        last_name="User",
    )
    grant_system_permission(
        user=user,
        permission_code="patients_patient.create",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("patients-list"),
        {
            "organization_id": str(organization.id),
            "user_id": str(patient_user.id),
            "first_name": "Second",
            "last_name": "Profile",
        },
        format="json",
    )

    assert patient_with_user.user_id == patient_user.id
    assert response.status_code == 400
    assert "already has a patient profile" in str(response.data)


@pytest.mark.django_db
def test_patient_deactivate_uses_is_active_false_and_does_not_delete(
    authenticated_client,
    grant_system_permission,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_patient.deactivate",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(reverse("patients-deactivate", kwargs={"pk": patient.id}), format="json")
    patient.refresh_from_db()

    assert response.status_code == 200
    assert patient.is_active is False
    assert Patient.objects.filter(pk=patient.id).exists()


@pytest.mark.django_db
def test_create_global_identifier_type(authenticated_client, grant_system_permission, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="patients_identifier_type.manage")
    client = authenticated_client(user)

    response = client.post(
        reverse("patients-identifier-types-list"),
        {"name": "Passport"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["code"] == "PASSPORT"
    assert response.data["organization"] is None


@pytest.mark.django_db
def test_create_organization_specific_identifier_type(
    authenticated_client,
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_identifier_type.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("patients-identifier-types-list"),
        {"organization_id": str(organization.id), "name": "Clinic Number"},
        format="json",
    )

    assert response.status_code == 201
    assert str(response.data["organization"]) == str(organization.id)


@pytest.mark.django_db
def test_duplicate_identifier_type_code_or_name_in_same_scope_fails(
    authenticated_client,
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_identifier_type.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)
    first_response = client.post(
        reverse("patients-identifier-types-list"),
        {"organization_id": str(organization.id), "name": "Member ID", "code": "MEMBER_ID"},
        format="json",
    )
    second_response = client.post(
        reverse("patients-identifier-types-list"),
        {"organization_id": str(organization.id), "name": "Member ID", "code": "MEMBER_ID"},
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400


@pytest.mark.django_db
def test_add_patient_identifier_stores_encrypted_and_hash_fields_not_plaintext(
    authenticated_client,
    grant_system_permission,
    identifier_type_global,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_identifier.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)
    raw_value = "A123456789"

    response = client.post(
        reverse("patients-patient-identifiers-list", kwargs={"patient_pk": patient.id}),
        {"identifier_type_id": str(identifier_type_global.id), "value": raw_value, "is_primary": True},
        format="json",
    )

    identifier = PatientIdentifier.objects.get(id=response.data["id"])

    assert response.status_code == 201
    assert identifier.value_encrypted != raw_value
    assert identifier.value_hash != raw_value
    assert len(identifier.value_hash) == 64
    assert "value_encrypted" not in response.data
    assert "value_hash" not in response.data


@pytest.mark.django_db
def test_duplicate_identifier_by_type_hash_fails(
    authenticated_client,
    grant_system_permission,
    identifier_type_global,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    another_patient = Patient.objects.create(
        organization=organization,
        patient_number="PAT-009999",
        first_name="Another",
        last_name="Patient",
    )
    grant_system_permission(
        user=user,
        permission_code="patients_identifier.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    first_response = client.post(
        reverse("patients-patient-identifiers-list", kwargs={"patient_pk": patient.id}),
        {"identifier_type_id": str(identifier_type_global.id), "value": "SHARED-001"},
        format="json",
    )
    second_response = client.post(
        reverse("patients-patient-identifiers-list", kwargs={"patient_pk": another_patient.id}),
        {"identifier_type_id": str(identifier_type_global.id), "value": "SHARED-001"},
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400


@pytest.mark.django_db
def test_only_one_active_primary_identifier_per_patient_type(
    authenticated_client,
    grant_system_permission,
    identifier_type_global,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_identifier.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    first = client.post(
        reverse("patients-patient-identifiers-list", kwargs={"patient_pk": patient.id}),
        {"identifier_type_id": str(identifier_type_global.id), "value": "PRIMARY-1", "is_primary": True},
        format="json",
    )
    second = client.post(
        reverse("patients-patient-identifiers-list", kwargs={"patient_pk": patient.id}),
        {"identifier_type_id": str(identifier_type_global.id), "value": "PRIMARY-2", "is_primary": True},
        format="json",
    )

    first_identifier = PatientIdentifier.objects.get(id=first.data["id"])
    second_identifier = PatientIdentifier.objects.get(id=second.data["id"])

    assert second.status_code == 201
    first_identifier.refresh_from_db()
    second_identifier.refresh_from_db()
    assert first_identifier.is_primary is False
    assert second_identifier.is_primary is True


@pytest.mark.django_db
def test_verify_identifier_works(
    authenticated_client,
    grant_system_permission,
    identifier_type_global,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_identifier.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)
    create_response = client.post(
        reverse("patients-patient-identifiers-list", kwargs={"patient_pk": patient.id}),
        {"identifier_type_id": str(identifier_type_global.id), "value": "VERIFY-001"},
        format="json",
    )

    verify_response = client.post(
        reverse("patients-identifiers-verify", kwargs={"pk": create_response.data["id"]}),
        format="json",
    )

    assert verify_response.status_code == 200
    assert verify_response.data["verified_at"] is not None


@pytest.mark.django_db
def test_add_address_validates_lat_long_pair_and_ranges(
    authenticated_client,
    grant_system_permission,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_address.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    pair_response = client.post(
        reverse("patients-patient-addresses-list", kwargs={"patient_pk": patient.id}),
        {"region": "Dar es Salaam", "latitude": "-6.8"},
        format="json",
    )
    range_response = client.post(
        reverse("patients-patient-addresses-list", kwargs={"patient_pk": patient.id}),
        {"region": "Dar es Salaam", "latitude": "100.0", "longitude": "39.0"},
        format="json",
    )

    assert pair_response.status_code == 400
    assert range_response.status_code == 400


@pytest.mark.django_db
def test_only_one_active_primary_address_per_patient(
    authenticated_client,
    grant_system_permission,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_address.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    first = client.post(
        reverse("patients-patient-addresses-list", kwargs={"patient_pk": patient.id}),
        {"region": "Dar es Salaam", "is_primary": True},
        format="json",
    )
    second = client.post(
        reverse("patients-patient-addresses-list", kwargs={"patient_pk": patient.id}),
        {"district": "Ilala", "is_primary": True},
        format="json",
    )

    first_address = PatientAddress.objects.get(id=first.data["id"])
    second_address = PatientAddress.objects.get(id=second.data["id"])

    first_address.refresh_from_db()
    second_address.refresh_from_db()
    assert first_address.is_primary is False
    assert second_address.is_primary is True


@pytest.mark.django_db
def test_create_relationship_type(authenticated_client, grant_system_permission, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="patients_relationship_type.manage")
    client = authenticated_client(user)

    response = client.post(
        reverse("patients-relationship-types-list"),
        {"name": "Caregiver"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["code"] == "CAREGIVER"


@pytest.mark.django_db
def test_add_related_person(
    authenticated_client,
    grant_system_permission,
    organization,
    patient,
    relationship_type,
    user_factory,
):
    user = user_factory()
    linked_user = user_factory(email="new.related@example.com", phone_number="+255722222333")
    grant_system_permission(
        user=user,
        permission_code="patients_related_person.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("patients-patient-related-persons-list", kwargs={"patient_pk": patient.id}),
        {
            "relationship_type_id": str(relationship_type.id),
            "linked_user_id": str(linked_user.id),
            "first_name": "Mary",
            "last_name": "Support",
            "priority_order": 1,
        },
        format="json",
    )

    assert response.status_code == 201
    assert str(response.data["linked_user"]) == str(linked_user.id)


@pytest.mark.django_db
def test_linked_user_cannot_be_same_as_patient_user(
    authenticated_client,
    grant_system_permission,
    organization,
    patient_with_user,
    relationship_type,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_related_person.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("patients-patient-related-persons-list", kwargs={"patient_pk": patient_with_user.id}),
        {
            "relationship_type_id": str(relationship_type.id),
            "linked_user_id": str(patient_with_user.user_id),
            "first_name": "Same",
            "last_name": "User",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Linked user cannot be the same as the patient user." in str(response.data)


@pytest.mark.django_db
def test_related_person_contact_stores_encrypted_hash_and_only_one_primary_per_channel(
    authenticated_client,
    grant_system_permission,
    organization,
    related_person,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_related_person_contact.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    first = client.post(
        reverse("patients-related-person-contacts-nested-list", kwargs={"related_person_pk": related_person.id}),
        {"channel": "phone", "value": "+255 700 222 111", "is_primary": True},
        format="json",
    )
    second = client.post(
        reverse("patients-related-person-contacts-nested-list", kwargs={"related_person_pk": related_person.id}),
        {"channel": "phone", "value": "+255700333444", "is_primary": True},
        format="json",
    )

    first_contact = RelatedPersonContact.objects.get(id=first.data["id"])
    second_contact = RelatedPersonContact.objects.get(id=second.data["id"])

    first_contact.refresh_from_db()
    second_contact.refresh_from_db()
    assert first_contact.value_encrypted != "+255700222111"
    assert len(first_contact.value_hash) == 64
    assert first_contact.is_primary is False
    assert second_contact.is_primary is True
    assert "value_encrypted" not in first.data
    assert "value_hash" not in first.data


@pytest.mark.django_db
def test_grant_patient_access_validates_related_person_belongs_to_patient(
    authenticated_client,
    access_role,
    grant_system_permission,
    organization,
    patient,
    relationship_type,
    user_factory,
):
    user = user_factory()
    other_patient = Patient.objects.create(
        organization=organization,
        patient_number="PAT-000777",
        first_name="Other",
        last_name="Patient",
    )
    outsider = user_factory(email="outsider@example.com", phone_number="+255744555666")
    related_person = other_patient.related_persons.create(
        relationship_type=relationship_type,
        linked_user=outsider,
        first_name="Other",
        last_name="Helper",
        priority_order=1,
    )
    grant_system_permission(
        user=user,
        permission_code="patients_access_grant.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("patients-patient-access-grants-list", kwargs={"patient_pk": patient.id}),
        {
            "related_person_id": str(related_person.id),
            "grantee_user_id": str(outsider.id),
            "role_id": str(access_role.id),
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Related person must belong to the selected patient." in str(response.data)


@pytest.mark.django_db
def test_grant_patient_access_validates_linked_user_equals_grantee_user(
    authenticated_client,
    access_role,
    grant_system_permission,
    organization,
    patient,
    related_person,
    user_factory,
):
    user = user_factory()
    other_user = user_factory(email="different.grantee@example.com", phone_number="+255788999000")
    grant_system_permission(
        user=user,
        permission_code="patients_access_grant.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("patients-patient-access-grants-list", kwargs={"patient_pk": patient.id}),
        {
            "related_person_id": str(related_person.id),
            "grantee_user_id": str(other_user.id),
            "role_id": str(access_role.id),
        },
        format="json",
    )

    assert response.status_code == 400
    assert "linked user must match the grantee user" in str(response.data)


@pytest.mark.django_db
def test_cannot_grant_access_to_patients_own_user(
    authenticated_client,
    access_role,
    grant_system_permission,
    organization,
    patient_with_user,
    relationship_type,
    user_factory,
):
    user = user_factory()
    related_person = patient_with_user.related_persons.create(
        relationship_type=relationship_type,
        linked_user=patient_with_user.user,
        first_name="Self",
        last_name="Link",
        priority_order=1,
    )
    grant_system_permission(
        user=user,
        permission_code="patients_access_grant.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)

    response = client.post(
        reverse("patients-patient-access-grants-list", kwargs={"patient_pk": patient_with_user.id}),
        {
            "related_person_id": str(related_person.id),
            "grantee_user_id": str(patient_with_user.user_id),
            "role_id": str(access_role.id),
        },
        format="json",
    )

    assert response.status_code == 400
    assert "own record" in str(response.data)


@pytest.mark.django_db
def test_revoke_patient_access_sets_revoked_at_and_is_active_false(
    authenticated_client,
    access_role,
    grant_system_permission,
    organization,
    patient,
    related_person,
    user_factory,
):
    user = user_factory()
    grant_system_permission(
        user=user,
        permission_code="patients_access_grant.manage",
        scope="organization",
        organization=organization,
    )
    client = authenticated_client(user)
    create_response = client.post(
        reverse("patients-patient-access-grants-list", kwargs={"patient_pk": patient.id}),
        {
            "related_person_id": str(related_person.id),
            "grantee_user_id": str(related_person.linked_user_id),
            "role_id": str(access_role.id),
        },
        format="json",
    )

    revoke_response = client.post(
        reverse("patients-access-grants-revoke", kwargs={"pk": create_response.data["id"]}),
        {"revoked_reason": "Access no longer needed"},
        format="json",
    )

    grant = PatientAccessGrant.objects.get(id=create_response.data["id"])
    assert revoke_response.status_code == 200
    assert grant.revoked_at is not None
    assert grant.is_active is False


@pytest.mark.django_db
def test_sensitive_encrypted_and_hash_fields_are_not_exposed_in_api_responses(
    authenticated_client,
    grant_system_permission,
    identifier_type_global,
    organization,
    patient,
    related_person,
    user_factory,
):
    user = user_factory()
    for code in [
        "patients_identifier.manage",
        "patients_address.manage",
        "patients_related_person_contact.manage",
        "patients_patient.view",
    ]:
        grant_system_permission(user=user, permission_code=code, scope="organization", organization=organization)
    client = authenticated_client(user)

    identifier_response = client.post(
        reverse("patients-patient-identifiers-list", kwargs={"patient_pk": patient.id}),
        {"identifier_type_id": str(identifier_type_global.id), "value": "SAFE-001"},
        format="json",
    )
    address_response = client.post(
        reverse("patients-patient-addresses-list", kwargs={"patient_pk": patient.id}),
        {"address_line1": "Plot 5", "region": "Dar es Salaam"},
        format="json",
    )
    contact_response = client.post(
        reverse("patients-related-person-contacts-nested-list", kwargs={"related_person_pk": related_person.id}),
        {"channel": "email", "value": "care@example.com"},
        format="json",
    )
    patient_detail = client.get(reverse("patients-detail", kwargs={"pk": patient.id}))

    for payload in [identifier_response.data, address_response.data, contact_response.data, patient_detail.data]:
        assert "value_encrypted" not in payload
        assert "value_hash" not in payload
        assert "address_line1_encrypted" not in payload
        assert "address_line2_encrypted" not in payload
