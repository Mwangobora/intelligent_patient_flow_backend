from __future__ import annotations

from datetime import datetime, time, timedelta
from itertools import count
from zoneinfo import ZoneInfo

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Permission, Role, RolePermission, User, UserMembership, UserRoleAssignment
from apps.facilities.models import (
    ConsultationRoom,
    Department,
    Facility,
    FacilityFlowSetting,
    FacilityOperatingHour,
    FacilitySpecialty,
    FacilityType,
    Organization,
    ServicePoint,
    ServicePointType,
    Specialty,
)
from apps.patients.models import Patient
from apps.practitioners.models import (
    Practitioner,
    PractitionerDepartmentAssignment,
    PractitionerFacilityAssignment,
    PractitionerSpecialtyAssignment,
    PractitionerType,
)
from apps.scheduling.models import Appointment, AppointmentSlot, PractitionerAvailabilityPeriod, PractitionerShift


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_factory():
    sequence = count(1)

    def create_user(**overrides):
        index = next(sequence)
        defaults = {
            "email": f"scheduling-user-{index}@example.com",
            "phone_number": f"+255766000{index:03d}",
            "password": "Password123!",
            "first_name": "Scheduling",
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
            "name": f"Scheduling Role {index}",
            "code": f"SCHEDULING_ROLE_{index}",
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
            UserMembership.objects.get_or_create(
                user=user,
                organization=organization,
                facility=None,
            )
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
    return Organization.objects.create(name="Scheduling Org", code="SCHEDULING_ORG")


@pytest.fixture
def facility_type():
    return FacilityType.objects.create(name="Hospital", code="HOSPITAL")


@pytest.fixture
def facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Scheduling Main Facility",
        code="SCHED_MAIN_FAC",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def second_facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Scheduling Second Facility",
        code="SCHED_SECOND_FAC",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def third_facility(organization, facility_type):
    return Facility.objects.create(
        organization=organization,
        facility_type=facility_type,
        name="Scheduling Third Facility",
        code="SCHED_THIRD_FAC",
        timezone="Africa/Dar_es_Salaam",
    )


@pytest.fixture
def flow_settings(facility):
    return FacilityFlowSetting.objects.create(
        facility=facility,
        max_advance_booking_days=365,
        minimum_booking_notice_minutes=0,
        cancellation_cutoff_minutes=0,
        reschedule_cutoff_minutes=0,
    )


@pytest.fixture
def second_flow_settings(second_facility):
    return FacilityFlowSetting.objects.create(
        facility=second_facility,
        max_advance_booking_days=365,
        minimum_booking_notice_minutes=0,
        cancellation_cutoff_minutes=0,
        reschedule_cutoff_minutes=0,
    )


@pytest.fixture
def create_operating_hours():
    def create(facility: Facility):
        rows = []
        for day in range(1, 8):
            rows.append(
                FacilityOperatingHour.objects.create(
                    facility=facility,
                    day_of_week=day,
                    period_order=1,
                    opens_at=time(8, 0),
                    closes_at=time(17, 0),
                )
            )
        return rows

    return create


@pytest.fixture
def operating_hours(facility, create_operating_hours):
    return create_operating_hours(facility)


@pytest.fixture
def second_operating_hours(second_facility, create_operating_hours):
    return create_operating_hours(second_facility)


@pytest.fixture
def third_operating_hours(third_facility, create_operating_hours):
    return create_operating_hours(third_facility)


@pytest.fixture
def department(facility):
    return Department.objects.create(facility=facility, name="Outpatient", code="OUTPATIENT")


@pytest.fixture
def second_department(second_facility):
    return Department.objects.create(facility=second_facility, name="Second OPD", code="SECOND_OPD")


@pytest.fixture
def specialty():
    return Specialty.objects.create(name="General Medicine", code="GEN_MED")


@pytest.fixture
def other_specialty():
    return Specialty.objects.create(name="Dermatology", code="DERMATOLOGY")


@pytest.fixture
def facility_specialty(facility, specialty):
    return FacilitySpecialty.objects.create(
        facility=facility,
        specialty=specialty,
        appointment_duration_minutes=30,
    )


@pytest.fixture
def second_facility_specialty(second_facility, specialty):
    return FacilitySpecialty.objects.create(
        facility=second_facility,
        specialty=specialty,
        appointment_duration_minutes=30,
    )


@pytest.fixture
def other_facility_specialty(facility, other_specialty):
    return FacilitySpecialty.objects.create(
        facility=facility,
        specialty=other_specialty,
        appointment_duration_minutes=30,
    )


@pytest.fixture
def practitioner_type():
    return PractitionerType.objects.create(name="Doctor", code="DOCTOR")


@pytest.fixture
def practitioner(organization, practitioner_type):
    return Practitioner.objects.create(
        organization=organization,
        practitioner_type=practitioner_type,
        practitioner_number="PRAC-100001",
        first_name="Amina",
        last_name="Care",
        email="amina@example.com",
    )


@pytest.fixture
def second_practitioner(organization, practitioner_type):
    return Practitioner.objects.create(
        organization=organization,
        practitioner_type=practitioner_type,
        practitioner_number="PRAC-100002",
        first_name="Biko",
        last_name="Care",
        email="biko@example.com",
    )


@pytest.fixture
def practitioner_facility_assignment(practitioner, facility):
    return PractitionerFacilityAssignment.objects.create(
        practitioner=practitioner,
        facility=facility,
        starts_on=datetime.now().date() - timedelta(days=30),
        is_primary=True,
    )


@pytest.fixture
def practitioner_second_facility_assignment(practitioner, second_facility):
    return PractitionerFacilityAssignment.objects.create(
        practitioner=practitioner,
        facility=second_facility,
        starts_on=datetime.now().date() - timedelta(days=30),
    )


@pytest.fixture
def second_practitioner_facility_assignment(second_practitioner, facility):
    return PractitionerFacilityAssignment.objects.create(
        practitioner=second_practitioner,
        facility=facility,
        starts_on=datetime.now().date() - timedelta(days=30),
        is_primary=True,
    )


@pytest.fixture
def practitioner_department_assignment(practitioner_facility_assignment, department):
    return PractitionerDepartmentAssignment.objects.create(
        practitioner_facility_assignment=practitioner_facility_assignment,
        department=department,
        starts_on=datetime.now().date() - timedelta(days=30),
        is_primary=True,
    )


@pytest.fixture
def practitioner_specialty_assignment(practitioner_facility_assignment, facility_specialty):
    return PractitionerSpecialtyAssignment.objects.create(
        practitioner_facility_assignment=practitioner_facility_assignment,
        facility_specialty=facility_specialty,
        starts_on=datetime.now().date() - timedelta(days=30),
        is_primary=True,
    )


@pytest.fixture
def practitioner_second_specialty_assignment(practitioner_second_facility_assignment, second_facility_specialty):
    return PractitionerSpecialtyAssignment.objects.create(
        practitioner_facility_assignment=practitioner_second_facility_assignment,
        facility_specialty=second_facility_specialty,
        starts_on=datetime.now().date() - timedelta(days=30),
        is_primary=True,
    )


@pytest.fixture
def service_point_type():
    return ServicePointType.objects.create(name="Desk", code="DESK")


@pytest.fixture
def service_point(facility, department, service_point_type):
    return ServicePoint.objects.create(
        facility=facility,
        department=department,
        service_point_type=service_point_type,
        name="Desk 1",
        code="DESK_1",
    )


@pytest.fixture
def consultation_room(facility, department):
    return ConsultationRoom.objects.create(
        facility=facility,
        department=department,
        name="Room 1",
        code="ROOM_1",
    )


@pytest.fixture
def patient(organization, facility):
    return Patient.objects.create(
        organization=organization,
        registered_facility=facility,
        patient_number="PAT-100001",
        first_name="John",
        last_name="Citizen",
    )


@pytest.fixture
def second_patient(organization, facility):
    return Patient.objects.create(
        organization=organization,
        registered_facility=facility,
        patient_number="PAT-100002",
        first_name="Jane",
        last_name="Citizen",
    )


@pytest.fixture
def third_patient(organization, second_facility):
    return Patient.objects.create(
        organization=organization,
        registered_facility=second_facility,
        patient_number="PAT-100003",
        first_name="Sam",
        last_name="Citizen",
    )


@pytest.fixture
def build_time_window():
    def build(*, facility: Facility, days_offset: int = 2, hour: int = 10, minute: int = 0, duration_minutes: int = 30):
        tz = ZoneInfo(facility.timezone)
        local_day = datetime.now(tz).date() + timedelta(days=days_offset)
        local_start = datetime.combine(local_day, time(hour, minute), tzinfo=tz)
        local_end = local_start + timedelta(minutes=duration_minutes)
        return local_start, local_end

    return build


@pytest.fixture
def create_matching_availability():
    def create(*, practitioner_facility_assignment: PractitionerFacilityAssignment, starts_at, ends_at):
        return PractitionerAvailabilityPeriod.objects.create(
            practitioner_facility_assignment=practitioner_facility_assignment,
            day_of_week=starts_at.isoweekday(),
            starts_at=starts_at.timetz().replace(tzinfo=None),
            ends_at=ends_at.timetz().replace(tzinfo=None),
            valid_from=starts_at.date(),
            valid_until=ends_at.date(),
        )

    return create


@pytest.fixture
def shift(practitioner_facility_assignment, practitioner_department_assignment, service_point, consultation_room, build_time_window):
    starts_at, ends_at = build_time_window(facility=practitioner_facility_assignment.facility, hour=9, minute=0, duration_minutes=240)
    return PractitionerShift.objects.create(
        practitioner_facility_assignment=practitioner_facility_assignment,
        practitioner_department_assignment=practitioner_department_assignment,
        service_point=service_point,
        consultation_room=consultation_room,
        starts_at=starts_at,
        ends_at=ends_at,
        accepts_appointments=True,
    )


@pytest.fixture
def slot(shift, facility_specialty, build_time_window):
    starts_at, ends_at = build_time_window(facility=shift.practitioner_facility_assignment.facility)
    return AppointmentSlot.objects.create(
        practitioner_shift=shift,
        facility_specialty=facility_specialty,
        starts_at=starts_at,
        ends_at=ends_at,
        capacity=2,
        booked_count=0,
    )


@pytest.fixture
def availability_period(practitioner_facility_assignment):
    return PractitionerAvailabilityPeriod.objects.create(
        practitioner_facility_assignment=practitioner_facility_assignment,
        day_of_week=1,
        starts_at=time(9, 0),
        ends_at=time(12, 0),
        valid_from=datetime.now().date() - timedelta(days=5),
    )


@pytest.fixture
def appointment(patient, facility, facility_specialty, build_time_window):
    starts_at, ends_at = build_time_window(facility=facility)
    appointment = Appointment.objects.create(
        facility=facility,
        patient=patient,
        facility_specialty=facility_specialty,
        appointment_number="APT-TEST-0001",
        scheduled_start=starts_at,
        scheduled_end=ends_at,
        booking_channel=Appointment.BookingChannel.API,
    )
    return appointment
