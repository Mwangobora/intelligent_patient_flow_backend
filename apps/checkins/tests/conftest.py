from __future__ import annotations

from datetime import timedelta
from itertools import count

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, RolePermission, User, UserMembership, UserRoleAssignment
from apps.facilities.models import Facility, FacilitySpecialty, FacilityType, Organization, Specialty
from apps.patients.models import Patient
from apps.scheduling.models import Appointment


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_factory():
    sequence = count(1)

    def create_user(**overrides):
        index = next(sequence)
        defaults = {
            "email": f"checkins-user-{index}@example.com",
            "phone_number": f"+255767000{index:03d}",
            "password": "Password123!",
            "first_name": "Checkin",
            "last_name": f"User{index}",
        }
        defaults.update(overrides)
        return User.objects.create_user(**defaults)

    return create_user


@pytest.fixture
def authenticated_client(api_client):
    def authenticate(user: User):
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return api_client

    return authenticate


@pytest.fixture
def permission_factory():
    def create_permission(code: str, **overrides):
        module, action = code.split(".", 1)
        defaults = {
            "name": code.replace(".", " ").replace("_", " ").title(),
            "module": module,
            "action": action,
            "is_active": True,
        }
        defaults.update(overrides)
        permission, _ = Permission.objects.get_or_create(code=code, defaults=defaults)
        for field, value in defaults.items():
            setattr(permission, field, value)
        permission.save()
        return permission

    return create_permission


@pytest.fixture
def role_factory():
    sequence = count(1)

    def create_role(**overrides):
        index = next(sequence)
        defaults = {
            "name": f"Checkins Role {index}",
            "code": f"CHECKINS_ROLE_{index}",
            "organization": None,
            "facility": None,
            "is_active": True,
        }
        defaults.update(overrides)
        return Role.objects.create(**defaults)

    return create_role


@pytest.fixture
def grant_system_permission(permission_factory, role_factory):
    sequence = count(1)

    def grant(
        *,
        user: User,
        permission_code: str,
        scope: str = "platform",
        organization: Organization | None = None,
        facility: Facility | None = None,
    ):
        permission = permission_factory(permission_code)
        role_kwargs = {"organization": None, "facility": None}
        if scope == "organization":
            role_kwargs["organization"] = organization
        elif scope == "facility":
            role_kwargs["organization"] = organization or facility.organization
            role_kwargs["facility"] = facility

        role = role_factory(
            name=f"{permission_code} role",
            code=f"{permission_code.replace('.', '_').upper()}_{next(sequence)}",
            **role_kwargs,
        )
        RolePermission.objects.create(role=role, permission=permission)

        if scope == "organization":
            UserMembership.objects.get_or_create(user=user, organization=organization, facility=None)
        elif scope == "facility":
            UserMembership.objects.get_or_create(
                user=user,
                organization=organization or facility.organization,
                facility=facility,
            )

        UserRoleAssignment.objects.create(user=user, role=role)
        return permission

    return grant


@pytest.fixture
def organization():
    return Organization.objects.create(name="Checkins Org", code="CHECKINS_ORG")


@pytest.fixture
def other_organization():
    return Organization.objects.create(name="Other Checkins Org", code="OTHER_CHECKINS_ORG")


@pytest.fixture
def facility_type():
    return FacilityType.objects.create(name="Checkins Hospital", code="CHECKINS_HOSP")


@pytest.fixture
def facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Checkins Main Facility",
        code="CHECKINS_MAIN",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def other_facility(other_organization, facility_type):
    return Facility.objects.create(
        organization=other_organization,
        facility_type=facility_type,
        name="Other Checkins Facility",
        code="OTHER_CHECKINS",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def specialty():
    return Specialty.objects.create(name="General Checkins", code="GENERAL_CHECKINS")


@pytest.fixture
def facility_specialty(facility, specialty):
    return FacilitySpecialty.objects.create(
        facility=facility,
        specialty=specialty,
        appointment_duration_minutes=30,
        accepts_appointments=True,
        accepts_walk_ins=True,
    )


@pytest.fixture
def non_walkin_specialty(facility):
    specialty = Specialty.objects.create(name="Referral Only", code="REFERRAL_ONLY")
    return FacilitySpecialty.objects.create(
        facility=facility,
        specialty=specialty,
        appointment_duration_minutes=30,
        accepts_appointments=True,
        accepts_walk_ins=False,
    )


@pytest.fixture
def other_facility_specialty(other_facility):
    specialty = Specialty.objects.create(name="Other General Checkins", code="OTHER_GENERAL_CHECKINS")
    return FacilitySpecialty.objects.create(
        facility=other_facility,
        specialty=specialty,
        appointment_duration_minutes=30,
        accepts_appointments=True,
        accepts_walk_ins=True,
    )


@pytest.fixture
def patient(organization, facility):
    return Patient.objects.create(
        organization=organization,
        registered_facility=facility,
        patient_number="CHECK-PAT-001",
        first_name="Asha",
        last_name="Patient",
    )


@pytest.fixture
def appointment(facility, patient, facility_specialty):
    starts_at = timezone.now() + timedelta(hours=1)
    return Appointment.objects.create(
        facility=facility,
        patient=patient,
        facility_specialty=facility_specialty,
        appointment_number="CHECK-APT-001",
        scheduled_start=starts_at,
        scheduled_end=starts_at + timedelta(minutes=30),
        booking_channel=Appointment.BookingChannel.RECEPTION,
    )
