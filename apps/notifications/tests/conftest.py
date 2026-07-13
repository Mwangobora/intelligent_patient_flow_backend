from __future__ import annotations

from datetime import timedelta
from itertools import count

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, RolePermission, User, UserMembership, UserRoleAssignment
from apps.checkins.models import PatientCheckin
from apps.facilities.models import Facility, FacilitySpecialty, FacilityType, Organization, ServicePoint, ServicePointType, Specialty
from apps.patients.models import Patient
from apps.queueing.models import Queue, QueueEntry
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
            "email": f"notifications-user-{index}@example.com",
            "phone_number": f"+255769000{index:03d}",
            "password": "Password123!",
            "first_name": "Notify",
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
            "name": f"Notifications Role {index}",
            "code": f"NOTIFICATIONS_ROLE_{index}",
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

    def grant(*, user: User, permission_code: str, scope: str = "platform", organization: Organization | None = None, facility: Facility | None = None):
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
            UserMembership.objects.get_or_create(user=user, organization=organization or facility.organization, facility=facility)

        UserRoleAssignment.objects.create(user=user, role=role)
        return permission

    return grant


@pytest.fixture
def organization():
    return Organization.objects.create(name="Notifications Org", code="NOTIFY_ORG")


@pytest.fixture
def other_organization():
    return Organization.objects.create(name="Other Notifications Org", code="OTHER_NOTIFY_ORG")


@pytest.fixture
def facility_type():
    return FacilityType.objects.create(name="Notifications Hospital", code="NOTIFY_HOSP")


@pytest.fixture
def facility(organization, facility_type):
    return Facility.objects.create(organization=organization, facility_type=facility_type, name="Notify Facility", code="NOTIFY_FAC", timezone="Africa/Dar_es_Salaam")


@pytest.fixture
def other_facility(other_organization, facility_type):
    return Facility.objects.create(organization=other_organization, facility_type=facility_type, name="Other Notify Facility", code="OTHER_NOTIFY", timezone="Africa/Dar_es_Salaam")


@pytest.fixture
def service_point_type():
    return ServicePointType.objects.create(name="Notify Desk", code="NOTIFY_DESK")


@pytest.fixture
def service_point(facility, service_point_type):
    return ServicePoint.objects.create(facility=facility, service_point_type=service_point_type, name="Reception", code="REC")


@pytest.fixture
def specialty():
    return Specialty.objects.create(name="Notify General", code="NOTIFY_GENERAL")


@pytest.fixture
def facility_specialty(facility, specialty):
    return FacilitySpecialty.objects.create(facility=facility, specialty=specialty, appointment_duration_minutes=30, accepts_appointments=True, accepts_walk_ins=True)


@pytest.fixture
def patient_user(user_factory):
    return user_factory(email="patient.notifications@example.com", phone_number="+255769111111")


@pytest.fixture
def patient(organization, facility, patient_user):
    return Patient.objects.create(
        organization=organization,
        registered_facility=facility,
        user=patient_user,
        patient_number="NOTIFY-PAT-001",
        first_name="Patient",
        last_name="Notify",
        email="patient.notifications@example.com",
        phone_number="+255769111111",
    )


@pytest.fixture
def other_patient(organization, facility, user_factory):
    return Patient.objects.create(
        organization=organization,
        registered_facility=facility,
        user=user_factory(email="other.patient.notifications@example.com", phone_number="+255769222222"),
        patient_number="OTHER-NOTIFY-PAT-001",
        first_name="Other",
        last_name="Patient",
    )


@pytest.fixture
def appointment(facility, patient, facility_specialty):
    starts_at = timezone.now() + timedelta(hours=2)
    return Appointment.objects.create(
        facility=facility,
        patient=patient,
        facility_specialty=facility_specialty,
        appointment_number="NOTIFY-APT-001",
        scheduled_start=starts_at,
        scheduled_end=starts_at + timedelta(minutes=30),
        status=Appointment.Status.CONFIRMED,
        booking_channel=Appointment.BookingChannel.RECEPTION,
    )


@pytest.fixture
def other_patient_appointment(facility, other_patient, facility_specialty):
    starts_at = timezone.now() + timedelta(hours=3)
    return Appointment.objects.create(
        facility=facility,
        patient=other_patient,
        facility_specialty=facility_specialty,
        appointment_number="NOTIFY-APT-OTHER",
        scheduled_start=starts_at,
        scheduled_end=starts_at + timedelta(minutes=30),
        status=Appointment.Status.CONFIRMED,
        booking_channel=Appointment.BookingChannel.RECEPTION,
    )


@pytest.fixture
def patient_checkin(facility, patient, appointment, facility_specialty, user_factory):
    return PatientCheckin.objects.create(
        facility=facility,
        patient=patient,
        appointment=appointment,
        facility_specialty=facility_specialty,
        checkin_method=PatientCheckin.CheckinMethod.RECEPTION,
        checked_in_by=user_factory(),
    )


@pytest.fixture
def other_patient_checkin(facility, other_patient, other_patient_appointment, facility_specialty, user_factory):
    return PatientCheckin.objects.create(
        facility=facility,
        patient=other_patient,
        appointment=other_patient_appointment,
        facility_specialty=facility_specialty,
        checkin_method=PatientCheckin.CheckinMethod.RECEPTION,
        checked_in_by=user_factory(),
    )


@pytest.fixture
def open_queue(service_point, user_factory):
    return Queue.objects.create(
        service_point=service_point,
        queue_date=timezone.localdate(),
        status=Queue.Status.OPEN,
        opened_at=timezone.now(),
        opened_by=user_factory(),
    )


@pytest.fixture
def queue_entry(open_queue, patient_checkin):
    return QueueEntry.objects.create(queue=open_queue, patient_checkin=patient_checkin, sequence_number=1)


@pytest.fixture
def other_patient_queue_entry(open_queue, other_patient_checkin):
    return QueueEntry.objects.create(queue=open_queue, patient_checkin=other_patient_checkin, sequence_number=2)
