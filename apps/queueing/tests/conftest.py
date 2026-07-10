from __future__ import annotations

from datetime import timedelta
from itertools import count

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, RolePermission, User, UserMembership, UserRoleAssignment
from apps.checkins.models import PatientCheckin
from apps.facilities.models import Facility, FacilityFlowSetting, FacilitySpecialty, FacilityType, Organization, ServicePoint, ServicePointType, Specialty
from apps.patients.models import Patient
from apps.queueing.models import Queue
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
            "email": f"queueing-user-{index}@example.com",
            "phone_number": f"+255768000{index:03d}",
            "password": "Password123!",
            "first_name": "Queueing",
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
            "name": f"Queueing Role {index}",
            "code": f"QUEUEING_ROLE_{index}",
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
    return Organization.objects.create(name="Queueing Org", code="QUEUEING_ORG")


@pytest.fixture
def other_organization():
    return Organization.objects.create(name="Other Queueing Org", code="OTHER_QUEUEING_ORG")


@pytest.fixture
def facility_type():
    return FacilityType.objects.create(name="Queueing Hospital", code="QUEUEING_HOSP")


@pytest.fixture
def facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Queueing Main Facility",
        code="QUEUEING_MAIN",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def other_facility(other_organization, facility_type):
    return Facility.objects.create(
        organization=other_organization,
        facility_type=facility_type,
        name="Other Queueing Facility",
        code="OTHER_QUEUEING",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def flow_settings(facility):
    return FacilityFlowSetting.objects.create(facility=facility, queue_number_padding=4)


@pytest.fixture
def service_point_type():
    return ServicePointType.objects.create(name="Queue Desk", code="QUEUE_DESK")


@pytest.fixture
def service_point(facility, service_point_type):
    return ServicePoint.objects.create(
        facility=facility,
        service_point_type=service_point_type,
        name="Front Desk",
        code="FD",
    )


@pytest.fixture
def second_service_point(facility, service_point_type):
    return ServicePoint.objects.create(
        facility=facility,
        service_point_type=service_point_type,
        name="Second Desk",
        code="SD",
    )


@pytest.fixture
def other_service_point(other_facility, service_point_type):
    return ServicePoint.objects.create(
        facility=other_facility,
        service_point_type=service_point_type,
        name="Other Desk",
        code="OD",
    )


@pytest.fixture
def specialty():
    return Specialty.objects.create(name="Queue General", code="QUEUE_GENERAL")


@pytest.fixture
def other_specialty():
    return Specialty.objects.create(name="Queue Other", code="QUEUE_OTHER")


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
def other_facility_specialty(facility, other_specialty):
    return FacilitySpecialty.objects.create(
        facility=facility,
        specialty=other_specialty,
        appointment_duration_minutes=30,
        accepts_appointments=True,
        accepts_walk_ins=True,
    )


@pytest.fixture
def patient(organization, facility):
    return Patient.objects.create(
        organization=organization,
        registered_facility=facility,
        patient_number="QUEUE-PAT-001",
        first_name="Musa",
        last_name="Patient",
    )


@pytest.fixture
def patient_factory(organization, facility):
    sequence = count(2)

    def create_patient(**overrides):
        index = next(sequence)
        defaults = {
            "organization": organization,
            "registered_facility": facility,
            "patient_number": f"QUEUE-PAT-{index:03d}",
            "first_name": f"Patient{index}",
            "last_name": "Queue",
        }
        defaults.update(overrides)
        return Patient.objects.create(**defaults)

    return create_patient


@pytest.fixture
def appointment(facility, patient, facility_specialty):
    starts_at = timezone.now() + timedelta(hours=1)
    return Appointment.objects.create(
        facility=facility,
        patient=patient,
        facility_specialty=facility_specialty,
        appointment_number="QUEUE-APT-001",
        scheduled_start=starts_at,
        scheduled_end=starts_at + timedelta(minutes=30),
        status=Appointment.Status.CHECKED_IN,
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
def checkin_factory(facility, facility_specialty, patient_factory, user_factory):
    sequence = count(1)

    def create_checkin(*, specialty=None, appointment=None, patient=None, checked_in_at=None, voided: bool = False):
        index = next(sequence)
        selected_patient = patient or patient_factory()
        selected_specialty = specialty or facility_specialty
        if appointment is None:
            starts_at = timezone.now() + timedelta(hours=1, minutes=index)
            appointment = Appointment.objects.create(
                facility=facility,
                patient=selected_patient,
                facility_specialty=selected_specialty,
                appointment_number=f"QUEUE-APT-{index + 1:03d}",
                scheduled_start=starts_at,
                scheduled_end=starts_at + timedelta(minutes=30),
                status=Appointment.Status.CHECKED_IN,
                booking_channel=Appointment.BookingChannel.RECEPTION,
            )
        checkin = PatientCheckin.objects.create(
            facility=facility,
            patient=selected_patient,
            appointment=appointment,
            facility_specialty=selected_specialty,
            checkin_method=PatientCheckin.CheckinMethod.RECEPTION,
            checked_in_by=user_factory(),
            checked_in_at=checked_in_at or timezone.now(),
        )
        if voided:
            checkin.voided_at = timezone.now()
            checkin.voided_by = user_factory()
            checkin.void_reason = "Voided fixture"
            checkin.save(update_fields=["voided_at", "voided_by", "void_reason", "updated_at"])
        return checkin

    return create_checkin


@pytest.fixture
def queue(service_point):
    return Queue.objects.create(service_point=service_point, queue_date=timezone.localdate())


@pytest.fixture
def open_queue(queue, user_factory):
    queue.status = Queue.Status.OPEN
    queue.opened_at = timezone.now()
    queue.opened_by = user_factory()
    queue.save(update_fields=["status", "opened_at", "opened_by", "updated_at"])
    return queue


@pytest.fixture
def second_open_queue(second_service_point, user_factory):
    return Queue.objects.create(
        service_point=second_service_point,
        queue_date=timezone.localdate(),
        status=Queue.Status.OPEN,
        opened_at=timezone.now(),
        opened_by=user_factory(),
    )
