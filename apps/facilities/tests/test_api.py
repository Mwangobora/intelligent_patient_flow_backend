from __future__ import annotations

import re

from django.urls import reverse

import pytest

from apps.facilities.models import Department, Facility, FacilityFlowSetting, FacilitySpecialty, Organization, ServicePoint


@pytest.mark.django_db
def test_unauthenticated_users_cannot_access_protected_endpoints(api_client):
    response = api_client.get(reverse("facilities-organizations-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_unauthorized_users_cannot_create_update_or_deactivate(api_client, authenticated_client, organization, user_factory):
    user = user_factory()
    client = authenticated_client(user)

    create_response = client.post(reverse("facilities-organizations-list"), {"name": "Denied Org"}, format="json")
    update_response = client.patch(
        reverse("facilities-organizations-detail", kwargs={"pk": organization.id}),
        {"name": "Denied Update"},
        format="json",
    )
    deactivate_response = client.post(reverse("facilities-organizations-deactivate", kwargs={"pk": organization.id}), format="json")

    assert create_response.status_code == 403
    assert update_response.status_code == 403
    assert deactivate_response.status_code == 403


@pytest.mark.django_db
def test_authorized_user_can_create_organization_and_code_is_generated(
    authenticated_client,
    grant_system_permission,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_organization.create")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-organizations-list"),
        {"name": "New Health Network"},
        format="json",
    )

    assert response.status_code == 201
    assert re.fullmatch(r"ORG\d{4}", response.data["code"])


@pytest.mark.django_db
def test_client_provided_organization_code_is_ignored(
    authenticated_client,
    grant_system_permission,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_organization.create")
    Organization.objects.create(name="Existing Org", code="EXISTING_ORG")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-organizations-list"),
        {"name": "Another Org", "code": "EXISTING_ORG"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["code"] != "EXISTING_ORG"
    assert re.fullmatch(r"ORG\d{4}", response.data["code"])


@pytest.mark.django_db
def test_create_facility_type(authenticated_client, grant_system_permission, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_facility_type.create")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-facility-types-list"),
        {"name": "Dispensary"},
        format="json",
    )

    assert response.status_code == 201
    assert re.fullmatch(r"FTY\d{4}", response.data["code"])


@pytest.mark.django_db
def test_create_facility_under_active_organization_and_active_facility_type(
    authenticated_client,
    facility_type,
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_facility.create")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-facilities-list"),
        {
            "organization_id": str(organization.id),
            "facility_type_id": str(facility_type.id),
            "name": "District Hospital",
            "timezone": "Africa/Dar_es_Salaam",
        },
        format="json",
    )

    assert response.status_code == 201
    assert re.fullmatch(r"FAC\d{4}", response.data["code"])


@pytest.mark.django_db
def test_cannot_create_facility_under_inactive_organization(
    authenticated_client,
    facility_type,
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory()
    organization.is_active = False
    organization.save(update_fields=["is_active", "updated_at"])
    grant_system_permission(user=user, permission_code="facilities_facility.create")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-facilities-list"),
        {
            "organization_id": str(organization.id),
            "facility_type_id": str(facility_type.id),
            "name": "Inactive Org Facility",
            "timezone": "Africa/Dar_es_Salaam",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Organization must be active." in str(response.data)


@pytest.mark.django_db
def test_cannot_create_facility_with_inactive_facility_type(
    authenticated_client,
    facility_type,
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory()
    facility_type.is_active = False
    facility_type.save(update_fields=["is_active", "updated_at"])
    grant_system_permission(user=user, permission_code="facilities_facility.create")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-facilities-list"),
        {
            "organization_id": str(organization.id),
            "facility_type_id": str(facility_type.id),
            "name": "Inactive Type Facility",
            "timezone": "Africa/Dar_es_Salaam",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Facility type must be active." in str(response.data)


@pytest.mark.django_db
def test_only_one_active_primary_facility_per_organization(
    authenticated_client,
    facility_type,
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory()
    Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Primary One",
        code="PRIMARY_ONE",
        timezone="Africa/Dar_es_Salaam",
        is_primary=True,
    )
    grant_system_permission(user=user, permission_code="facilities_facility.create")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-facilities-list"),
        {
            "organization_id": str(organization.id),
            "facility_type_id": str(facility_type.id),
            "name": "Primary Two",
            "timezone": "Africa/Dar_es_Salaam",
            "is_primary": True,
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_create_department(authenticated_client, facility, grant_system_permission, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_department.manage")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-departments-list"),
        {"facility_id": str(facility.id), "name": "Laboratory"},
        format="json",
    )

    assert response.status_code == 201
    assert re.fullmatch(r"DEP\d{4}", response.data["code"])


@pytest.mark.django_db
def test_parent_department_must_belong_to_same_facility(
    authenticated_client,
    facility,
    grant_system_permission,
    other_facility,
    user_factory,
):
    user = user_factory()
    parent = Department.objects.create(facility=other_facility, name="External Parent", code="EXTERNAL_PARENT")
    grant_system_permission(user=user, permission_code="facilities_department.manage")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-departments-list"),
        {
            "facility_id": str(facility.id),
            "parent_department_id": str(parent.id),
            "name": "Child Department",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "Parent department must belong to the same facility." in str(response.data)


@pytest.mark.django_db
def test_create_specialty(authenticated_client, grant_system_permission, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_specialty.manage")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-specialties-list"),
        {"name": "Oncology"},
        format="json",
    )

    assert response.status_code == 201
    assert re.fullmatch(r"SPC\d{4}", response.data["code"])


@pytest.mark.django_db
def test_specialty_cannot_be_its_own_parent(authenticated_client, grant_system_permission, specialty, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_specialty.manage")
    client = authenticated_client(user)

    response = client.patch(
        reverse("facilities-specialties-detail", kwargs={"pk": specialty.id}),
        {"parent_specialty_id": str(specialty.id)},
        format="json",
    )

    assert response.status_code == 400
    assert "Specialty cannot be its own parent." in str(response.data)


@pytest.mark.django_db
def test_create_facility_specialty(
    authenticated_client,
    department,
    facility,
    grant_system_permission,
    specialty,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_specialty.manage")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-facility-specialties-list"),
        {
            "facility_id": str(facility.id),
            "specialty_id": str(specialty.id),
            "department_id": str(department.id),
            "appointment_duration_minutes": 20,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["appointment_duration_minutes"] == 20


@pytest.mark.django_db
def test_facility_specialty_department_must_match_facility(
    authenticated_client,
    facility,
    grant_system_permission,
    other_facility,
    specialty,
    user_factory,
):
    user = user_factory()
    foreign_department = Department.objects.create(facility=other_facility, name="Foreign", code="FOREIGN")
    grant_system_permission(user=user, permission_code="facilities_specialty.manage")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-facility-specialties-list"),
        {
            "facility_id": str(facility.id),
            "specialty_id": str(specialty.id),
            "department_id": str(foreign_department.id),
            "appointment_duration_minutes": 20,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "same facility" in str(response.data)


@pytest.mark.django_db
def test_create_service_point(
    authenticated_client,
    department,
    facility,
    grant_system_permission,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_service_point.manage")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-service-point-types-list"),
        {"name": "Reception Desk"},
        format="json",
    )
    service_point_type_id = response.data["id"]

    create_response = client.post(
        reverse("facilities-service-points-list"),
        {
            "facility_id": str(facility.id),
            "department_id": str(department.id),
            "service_point_type_id": str(service_point_type_id),
            "name": "Front Desk",
            "display_order": 1,
        },
        format="json",
    )

    assert create_response.status_code == 201
    assert re.fullmatch(r"SVP\d{4}", create_response.data["code"])


@pytest.mark.django_db
def test_service_point_department_must_match_facility(
    authenticated_client,
    facility,
    grant_system_permission,
    other_facility,
    user_factory,
):
    user = user_factory()
    foreign_department = Department.objects.create(facility=other_facility, name="Foreign", code="FOREIGN")
    grant_system_permission(user=user, permission_code="facilities_service_point.manage")
    client = authenticated_client(user)

    type_response = client.post(
        reverse("facilities-service-point-types-list"),
        {"name": "Queue Desk"},
        format="json",
    )

    response = client.post(
        reverse("facilities-service-points-list"),
        {
            "facility_id": str(facility.id),
            "department_id": str(foreign_department.id),
            "service_point_type_id": str(type_response.data["id"]),
            "name": "Bad Desk",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "same facility" in str(response.data)


@pytest.mark.django_db
def test_create_consultation_room(authenticated_client, department, facility, grant_system_permission, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_room.manage")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-consultation-rooms-list"),
        {
            "facility_id": str(facility.id),
            "department_id": str(department.id),
            "name": "Room 1",
            "capacity": 2,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["capacity"] == 2


@pytest.mark.django_db
def test_room_department_must_match_facility(
    authenticated_client,
    facility,
    grant_system_permission,
    other_facility,
    user_factory,
):
    user = user_factory()
    foreign_department = Department.objects.create(facility=other_facility, name="Foreign", code="FOREIGN")
    grant_system_permission(user=user, permission_code="facilities_room.manage")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-consultation-rooms-list"),
        {
            "facility_id": str(facility.id),
            "department_id": str(foreign_department.id),
            "name": "Bad Room",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "same facility" in str(response.data)


@pytest.mark.django_db
def test_operating_hours_reject_overlapping_periods(authenticated_client, facility, grant_system_permission, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_schedule.manage")
    client = authenticated_client(user)

    first_response = client.post(
        reverse("facilities-operating-hours-list"),
        {
            "facility_id": str(facility.id),
            "day_of_week": 1,
            "period_order": 1,
            "opens_at": "08:00:00",
            "closes_at": "12:00:00",
        },
        format="json",
    )
    second_response = client.post(
        reverse("facilities-operating-hours-list"),
        {
            "facility_id": str(facility.id),
            "day_of_week": 1,
            "period_order": 2,
            "opens_at": "11:00:00",
            "closes_at": "15:00:00",
        },
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400


@pytest.mark.django_db
def test_schedule_exceptions_reject_invalid_closed_24_hour_combinations(
    authenticated_client,
    facility,
    grant_system_permission,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_schedule.manage")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-schedule-exceptions-list"),
        {
            "facility_id": str(facility.id),
            "exception_date": "2026-07-10",
            "is_closed": True,
            "opens_at": "08:00:00",
            "closes_at": "10:00:00",
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_flow_settings_one_row_per_facility(authenticated_client, facility, grant_system_permission, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_settings.manage")
    client = authenticated_client(user)

    first_response = client.post(
        reverse("facilities-flow-settings-list"),
        {"facility_id": str(facility.id), "queue_number_padding": 3},
        format="json",
    )
    second_response = client.post(
        reverse("facilities-flow-settings-list"),
        {"facility_id": str(facility.id), "queue_number_padding": 4},
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400
    assert FacilityFlowSetting.objects.filter(facility=facility).count() == 1


@pytest.mark.django_db
def test_queue_number_padding_validation_works(authenticated_client, facility, grant_system_permission, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_settings.manage")
    client = authenticated_client(user)

    response = client.post(
        reverse("facilities-flow-settings-list"),
        {"facility_id": str(facility.id), "queue_number_padding": 0},
        format="json",
    )

    assert response.status_code == 400
    assert "Queue number padding must be between 1 and 6." in str(response.data)


@pytest.mark.django_db
def test_deactivation_uses_is_active_false_and_does_not_delete_records(
    authenticated_client,
    grant_system_permission,
    organization,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="facilities_organization.deactivate")
    client = authenticated_client(user)
    before_count = Organization.objects.count()

    response = client.post(reverse("facilities-organizations-deactivate", kwargs={"pk": organization.id}), format="json")

    organization.refresh_from_db()
    assert response.status_code == 200
    assert organization.is_active is False
    assert Organization.objects.count() == before_count
