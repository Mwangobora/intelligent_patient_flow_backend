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
from apps.practitioners.models import Practitioner, PractitionerFacilityAssignment, PractitionerSpecialtyAssignment, PractitionerType
from apps.queueing.models import Queue, QueueEntry
from apps.scheduling.models import Appointment, AppointmentSlot, PractitionerShift


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_factory():
    sequence = count(1)

    def create_user(**overrides):
        index = next(sequence)
        defaults = {
            "email": f"intelligence-user-{index}@example.com",
            "phone_number": f"+255769000{index:03d}",
            "password": "Password123!",
            "first_name": "Intelligence",
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
            "name": f"Intelligence Role {index}",
            "code": f"INTELLIGENCE_ROLE_{index}",
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
    return Organization.objects.create(name="Intelligence Org", code="INTEL_ORG")


@pytest.fixture
def facility_type():
    return FacilityType.objects.create(name="Intelligence Hospital", code="INTEL_HOSP")


@pytest.fixture
def facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Intelligence Facility",
        code="INTEL_FAC",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def service_point_type():
    return ServicePointType.objects.create(name="Intelligence Desk", code="INTEL_DESK")


@pytest.fixture
def service_point(facility, service_point_type):
    return ServicePoint.objects.create(facility=facility, service_point_type=service_point_type, name="Desk", code="ID")


@pytest.fixture
def specialty():
    return Specialty.objects.create(name="Intelligence General", code="INTEL_GENERAL")


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
def queue(service_point, facility_specialty):
    return Queue.objects.create(
        service_point=service_point,
        facility_specialty=facility_specialty,
        queue_date=timezone.localdate(),
        status=Queue.Status.OPEN,
        opened_at=timezone.now(),
    )


@pytest.fixture
def practitioner_type():
    return PractitionerType.objects.create(name="Intelligence Doctor", code="INTEL_DOCTOR")


@pytest.fixture
def practitioner(organization, practitioner_type):
    return Practitioner.objects.create(
        organization=organization,
        practitioner_type=practitioner_type,
        practitioner_number="INTEL-PRAC-001",
        first_name="Ada",
        last_name="Doctor",
    )


@pytest.fixture
def practitioner_facility_assignment(practitioner, facility):
    return PractitionerFacilityAssignment.objects.create(
        practitioner=practitioner,
        facility=facility,
        starts_on=timezone.localdate() - timedelta(days=10),
    )


@pytest.fixture
def practitioner_specialty_assignment(practitioner_facility_assignment, facility_specialty):
    return PractitionerSpecialtyAssignment.objects.create(
        practitioner_facility_assignment=practitioner_facility_assignment,
        facility_specialty=facility_specialty,
        starts_on=timezone.localdate() - timedelta(days=10),
    )


@pytest.fixture
def practitioner_shift(practitioner_facility_assignment, service_point):
    starts_at = timezone.now() + timedelta(hours=1)
    return PractitionerShift.objects.create(
        practitioner_facility_assignment=practitioner_facility_assignment,
        service_point=service_point,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=4),
        accepts_appointments=True,
    )


@pytest.fixture
def patient_factory(organization, facility):
    sequence = count(1)

    def create_patient(**overrides):
        index = next(sequence)
        defaults = {
            "organization": organization,
            "registered_facility": facility,
            "patient_number": f"INTEL-PAT-{index:03d}",
            "first_name": f"Patient{index}",
            "last_name": "Intel",
        }
        defaults.update(overrides)
        return Patient.objects.create(**defaults)

    return create_patient


@pytest.fixture
def checkin_factory(facility, facility_specialty, patient_factory, user_factory):
    sequence = count(1)

    def create_checkin(*, checked_in_at=None, appointment_status=Appointment.Status.CHECKED_IN):
        index = next(sequence)
        patient = patient_factory()
        starts_at = timezone.now() + timedelta(hours=1, minutes=index)
        appointment = Appointment.objects.create(
            facility=facility,
            patient=patient,
            facility_specialty=facility_specialty,
            appointment_number=f"INTEL-APT-{index:03d}",
            scheduled_start=starts_at,
            scheduled_end=starts_at + timedelta(minutes=30),
            status=appointment_status,
            booking_channel=Appointment.BookingChannel.RECEPTION,
        )
        return PatientCheckin.objects.create(
            facility=facility,
            patient=patient,
            appointment=appointment,
            facility_specialty=facility_specialty,
            checkin_method=PatientCheckin.CheckinMethod.RECEPTION,
            checked_in_by=user_factory(),
            checked_in_at=checked_in_at or timezone.now(),
        )

    return create_checkin


@pytest.fixture
def queue_entry(queue, checkin_factory):
    return QueueEntry.objects.create(
        queue=queue,
        patient_checkin=checkin_factory(),
        sequence_number=1,
        joined_at=timezone.now(),
    )


@pytest.fixture
def completed_entry(queue, checkin_factory):
    joined_at = timezone.now() - timedelta(minutes=40)
    started_at = joined_at + timedelta(minutes=10)
    return QueueEntry.objects.create(
        queue=queue,
        patient_checkin=checkin_factory(),
        sequence_number=2,
        status=QueueEntry.Status.COMPLETED,
        joined_at=joined_at,
        called_at=started_at - timedelta(minutes=1),
        service_started_at=started_at,
        service_completed_at=started_at + timedelta(minutes=20),
    )


@pytest.fixture
def appointment_slot(practitioner_shift, facility_specialty, practitioner_specialty_assignment):
    starts_at = practitioner_shift.starts_at + timedelta(minutes=30)
    return AppointmentSlot.objects.create(
        practitioner_shift=practitioner_shift,
        facility_specialty=facility_specialty,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
        capacity=2,
        booked_count=0,
        status=AppointmentSlot.Status.AVAILABLE,
        is_online_bookable=True,
    )
