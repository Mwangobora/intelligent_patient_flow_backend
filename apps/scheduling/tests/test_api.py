from __future__ import annotations

from datetime import time, timedelta

from django.urls import reverse
from django.utils import timezone

import pytest

from apps.scheduling.models import Appointment, AppointmentSlot, AppointmentStatusHistory, PractitionerLeaveRequest, PractitionerShift
from apps.scheduling.services import change_appointment_status, create_initial_appointment_status_history, mark_checked_in, mark_completed, mark_in_service


@pytest.mark.django_db
def test_unauthenticated_users_cannot_access_protected_endpoints(api_client):
    response = api_client.get(reverse("scheduling-appointments-list"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_unauthorized_users_cannot_create_update_or_cancel(authenticated_client, appointment, build_time_window, practitioner_facility_assignment, user_factory):
    user = user_factory()
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=practitioner_facility_assignment.facility)

    create_response = client.post(
        reverse("scheduling-availability-list"),
        {
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "day_of_week": starts_at.isoweekday(),
            "starts_at": "09:00:00",
            "ends_at": "12:00:00",
            "valid_from": starts_at.date().isoformat(),
        },
        format="json",
    )
    update_response = client.patch(
        reverse("scheduling-appointments-detail", kwargs={"pk": appointment.id}),
        {"booking_channel": Appointment.BookingChannel.WEB},
        format="json",
    )
    cancel_response = client.post(
        reverse("scheduling-appointments-cancel", kwargs={"pk": appointment.id}),
        {"cancellation_reason": "No access"},
        format="json",
    )

    assert create_response.status_code == 403
    assert update_response.status_code == 403
    assert cancel_response.status_code == 403


@pytest.mark.django_db
def test_authorized_user_can_create_availability_period(
    authenticated_client,
    build_time_window,
    grant_system_permission,
    organization,
    practitioner_facility_assignment,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_availability.manage", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, _ = build_time_window(facility=practitioner_facility_assignment.facility)

    response = client.post(
        reverse("scheduling-availability-list"),
        {
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "day_of_week": starts_at.isoweekday(),
            "starts_at": "09:00:00",
            "ends_at": "12:00:00",
            "valid_from": starts_at.date().isoformat(),
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["is_available_for_appointments"] is True


@pytest.mark.django_db
def test_availability_rejects_overlapping_active_periods(
    authenticated_client,
    build_time_window,
    grant_system_permission,
    organization,
    practitioner_facility_assignment,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_availability.manage", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, _ = build_time_window(facility=practitioner_facility_assignment.facility)
    payload = {
        "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
        "day_of_week": starts_at.isoweekday(),
        "starts_at": "09:00:00",
        "ends_at": "12:00:00",
        "valid_from": starts_at.date().isoformat(),
    }

    first_response = client.post(reverse("scheduling-availability-list"), payload, format="json")
    second_response = client.post(
        reverse("scheduling-availability-list"),
        {
            **payload,
            "starts_at": "11:00:00",
            "ends_at": "13:00:00",
        },
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400


@pytest.mark.django_db
def test_leave_request_can_be_created(authenticated_client, build_time_window, grant_system_permission, organization, practitioner_facility_assignment, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_leave.manage", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=practitioner_facility_assignment.facility, hour=8, minute=0, duration_minutes=120)

    response = client.post(
        reverse("scheduling-leave-requests-list"),
        {
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "reason": "Family event",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["status"] == PractitionerLeaveRequest.Status.PENDING


@pytest.mark.django_db
def test_leave_approval_blocks_overlapping_shift_creation(
    authenticated_client,
    build_time_window,
    grant_system_permission,
    organization,
    practitioner_facility_assignment,
    service_point,
    consultation_room,
    practitioner_department_assignment,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_leave.manage", scope="organization", organization=organization)
    grant_system_permission(user=user, permission_code="scheduling_shift.manage", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=practitioner_facility_assignment.facility, hour=9, minute=0, duration_minutes=180)
    create_leave = client.post(
        reverse("scheduling-leave-requests-list"),
        {
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
        format="json",
    )
    approve_leave = client.post(
        reverse("scheduling-leave-requests-approve", kwargs={"pk": create_leave.data["id"]}),
        format="json",
    )
    shift_response = client.post(
        reverse("scheduling-shifts-list"),
        {
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "practitioner_department_assignment_id": str(practitioner_department_assignment.id),
            "service_point_id": str(service_point.id),
            "consultation_room_id": str(consultation_room.id),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
        format="json",
    )

    assert approve_leave.status_code == 200
    assert shift_response.status_code == 400


@pytest.mark.django_db
def test_leave_rejects_overlapping_pending_or_approved_leave(
    authenticated_client,
    build_time_window,
    grant_system_permission,
    organization,
    practitioner_facility_assignment,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_leave.manage", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=practitioner_facility_assignment.facility, hour=8, minute=0, duration_minutes=120)

    first_response = client.post(
        reverse("scheduling-leave-requests-list"),
        {
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
        format="json",
    )
    second_response = client.post(
        reverse("scheduling-leave-requests-list"),
        {
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "starts_at": (starts_at + timedelta(minutes=30)).isoformat(),
            "ends_at": (ends_at + timedelta(minutes=30)).isoformat(),
        },
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400


@pytest.mark.django_db
def test_authorized_user_can_create_practitioner_shift(
    authenticated_client,
    build_time_window,
    consultation_room,
    grant_system_permission,
    organization,
    practitioner_department_assignment,
    practitioner_facility_assignment,
    service_point,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_shift.manage", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=practitioner_facility_assignment.facility, hour=9, minute=0, duration_minutes=180)

    response = client.post(
        reverse("scheduling-shifts-list"),
        {
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "practitioner_department_assignment_id": str(practitioner_department_assignment.id),
            "service_point_id": str(service_point.id),
            "consultation_room_id": str(consultation_room.id),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["status"] == PractitionerShift.Status.SCHEDULED


@pytest.mark.django_db
def test_shift_rejects_approved_leave_overlap(
    authenticated_client,
    build_time_window,
    consultation_room,
    grant_system_permission,
    organization,
    practitioner_department_assignment,
    practitioner_facility_assignment,
    service_point,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_leave.manage", scope="organization", organization=organization)
    grant_system_permission(user=user, permission_code="scheduling_shift.manage", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=practitioner_facility_assignment.facility, hour=9, minute=0, duration_minutes=180)
    leave = client.post(
        reverse("scheduling-leave-requests-list"),
        {
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
        format="json",
    )
    client.post(reverse("scheduling-leave-requests-approve", kwargs={"pk": leave.data["id"]}), format="json")

    response = client.post(
        reverse("scheduling-shifts-list"),
        {
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "practitioner_department_assignment_id": str(practitioner_department_assignment.id),
            "service_point_id": str(service_point.id),
            "consultation_room_id": str(consultation_room.id),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_shift_rejects_overlapping_practitioner_shift(
    authenticated_client,
    build_time_window,
    consultation_room,
    grant_system_permission,
    organization,
    practitioner_department_assignment,
    practitioner_facility_assignment,
    service_point,
    shift,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_shift.manage", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(
        reverse("scheduling-shifts-list"),
        {
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "practitioner_department_assignment_id": str(practitioner_department_assignment.id),
            "service_point_id": str(service_point.id),
            "consultation_room_id": str(consultation_room.id),
            "starts_at": shift.starts_at.isoformat(),
            "ends_at": shift.ends_at.isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_shift_rejects_overlapping_consultation_room_allocation(
    authenticated_client,
    consultation_room,
    grant_system_permission,
    organization,
    second_practitioner_facility_assignment,
    shift,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_shift.manage", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(
        reverse("scheduling-shifts-list"),
        {
            "practitioner_facility_assignment_id": str(second_practitioner_facility_assignment.id),
            "consultation_room_id": str(consultation_room.id),
            "starts_at": shift.starts_at.isoformat(),
            "ends_at": shift.ends_at.isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_shift_status_transitions_work(authenticated_client, grant_system_permission, organization, shift, user_factory):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_shift.manage", scope="organization", organization=organization)
    client = authenticated_client(user)

    start_response = client.post(reverse("scheduling-shifts-start", kwargs={"pk": shift.id}), format="json")
    complete_response = client.post(reverse("scheduling-shifts-complete", kwargs={"pk": shift.id}), format="json")

    assert start_response.status_code == 200
    assert complete_response.status_code == 200
    assert complete_response.data["status"] == PractitionerShift.Status.COMPLETED


@pytest.mark.django_db
def test_create_appointment_without_practitioner_for_specialty_works(
    authenticated_client,
    build_time_window,
    facility,
    facility_specialty,
    flow_settings,
    grant_system_permission,
    operating_hours,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_appointment.create", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=facility)

    response = client.post(
        reverse("scheduling-appointments-list"),
        {
            "facility_id": str(facility.id),
            "patient_id": str(patient.id),
            "facility_specialty_id": str(facility_specialty.id),
            "scheduled_start": starts_at.isoformat(),
            "scheduled_end": ends_at.isoformat(),
            "booking_channel": Appointment.BookingChannel.API,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["appointment_number"].startswith("APT-")


@pytest.mark.django_db
def test_create_appointment_with_practitioner_validates_specialty_assignment(
    authenticated_client,
    build_time_window,
    facility,
    flow_settings,
    grant_system_permission,
    operating_hours,
    organization,
    other_facility_specialty,
    patient,
    practitioner_facility_assignment,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_appointment.create", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=facility)

    response = client.post(
        reverse("scheduling-appointments-list"),
        {
            "facility_id": str(facility.id),
            "patient_id": str(patient.id),
            "facility_specialty_id": str(other_facility_specialty.id),
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "scheduled_start": starts_at.isoformat(),
            "scheduled_end": ends_at.isoformat(),
            "booking_channel": Appointment.BookingChannel.API,
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_create_appointment_with_shift_validates_time_inside_shift(
    authenticated_client,
    build_time_window,
    facility,
    facility_specialty,
    flow_settings,
    grant_system_permission,
    operating_hours,
    organization,
    patient,
    practitioner_facility_assignment,
    practitioner_specialty_assignment,
    shift,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_appointment.create", scope="organization", organization=organization)
    client = authenticated_client(user)
    invalid_start = shift.ends_at + timedelta(minutes=15)
    invalid_end = invalid_start + timedelta(minutes=30)

    response = client.post(
        reverse("scheduling-appointments-list"),
        {
            "facility_id": str(facility.id),
            "patient_id": str(patient.id),
            "facility_specialty_id": str(facility_specialty.id),
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "practitioner_specialty_assignment_id": str(practitioner_specialty_assignment.id),
            "practitioner_shift_id": str(shift.id),
            "scheduled_start": invalid_start.isoformat(),
            "scheduled_end": invalid_end.isoformat(),
            "booking_channel": Appointment.BookingChannel.API,
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_create_appointment_with_slot_increments_booked_count(
    authenticated_client,
    facility,
    facility_specialty,
    flow_settings,
    grant_system_permission,
    operating_hours,
    organization,
    patient,
    practitioner_facility_assignment,
    practitioner_specialty_assignment,
    slot,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_appointment.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(
        reverse("scheduling-appointments-list"),
        {
            "facility_id": str(facility.id),
            "patient_id": str(patient.id),
            "facility_specialty_id": str(facility_specialty.id),
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "practitioner_specialty_assignment_id": str(practitioner_specialty_assignment.id),
            "practitioner_shift_id": str(slot.practitioner_shift_id),
            "appointment_slot_id": str(slot.id),
            "scheduled_start": slot.starts_at.isoformat(),
            "scheduled_end": slot.ends_at.isoformat(),
            "booking_channel": Appointment.BookingChannel.API,
        },
        format="json",
    )

    slot.refresh_from_db()
    assert response.status_code == 201
    assert slot.booked_count == 1


@pytest.mark.django_db
def test_booking_full_slot_fails(
    authenticated_client,
    facility,
    facility_specialty,
    flow_settings,
    grant_system_permission,
    operating_hours,
    organization,
    patient,
    practitioner_facility_assignment,
    practitioner_specialty_assignment,
    second_patient,
    slot,
    user_factory,
):
    slot.capacity = 1
    slot.save(update_fields=["capacity", "updated_at"])
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_appointment.create", scope="organization", organization=organization)
    client = authenticated_client(user)
    payload = {
        "facility_id": str(facility.id),
        "facility_specialty_id": str(facility_specialty.id),
        "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
        "practitioner_specialty_assignment_id": str(practitioner_specialty_assignment.id),
        "practitioner_shift_id": str(slot.practitioner_shift_id),
        "appointment_slot_id": str(slot.id),
        "scheduled_start": slot.starts_at.isoformat(),
        "scheduled_end": slot.ends_at.isoformat(),
        "booking_channel": Appointment.BookingChannel.API,
    }

    first_response = client.post(reverse("scheduling-appointments-list"), {**payload, "patient_id": str(patient.id)}, format="json")
    second_response = client.post(reverse("scheduling-appointments-list"), {**payload, "patient_id": str(second_patient.id)}, format="json")

    assert first_response.status_code == 201
    assert second_response.status_code == 400


@pytest.mark.django_db
def test_patient_double_booking_fails(
    authenticated_client,
    build_time_window,
    facility,
    facility_specialty,
    flow_settings,
    grant_system_permission,
    operating_hours,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_appointment.create", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=facility)
    payload = {
        "facility_id": str(facility.id),
        "patient_id": str(patient.id),
        "facility_specialty_id": str(facility_specialty.id),
        "scheduled_start": starts_at.isoformat(),
        "scheduled_end": ends_at.isoformat(),
        "booking_channel": Appointment.BookingChannel.API,
    }

    first_response = client.post(reverse("scheduling-appointments-list"), payload, format="json")
    second_response = client.post(reverse("scheduling-appointments-list"), payload, format="json")

    assert first_response.status_code == 201
    assert second_response.status_code == 400


@pytest.mark.django_db
def test_practitioner_double_booking_fails(
    authenticated_client,
    build_time_window,
    create_matching_availability,
    facility,
    facility_specialty,
    flow_settings,
    grant_system_permission,
    operating_hours,
    organization,
    patient,
    practitioner_facility_assignment,
    practitioner_specialty_assignment,
    second_facility,
    second_facility_specialty,
    second_flow_settings,
    second_operating_hours,
    practitioner_second_facility_assignment,
    practitioner_second_specialty_assignment,
    third_patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_appointment.create", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=facility)
    create_matching_availability(
        practitioner_facility_assignment=practitioner_facility_assignment,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    create_matching_availability(
        practitioner_facility_assignment=practitioner_second_facility_assignment,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    first_response = client.post(
        reverse("scheduling-appointments-list"),
        {
            "facility_id": str(facility.id),
            "patient_id": str(patient.id),
            "facility_specialty_id": str(facility_specialty.id),
            "practitioner_facility_assignment_id": str(practitioner_facility_assignment.id),
            "practitioner_specialty_assignment_id": str(practitioner_specialty_assignment.id),
            "scheduled_start": starts_at.isoformat(),
            "scheduled_end": ends_at.isoformat(),
            "booking_channel": Appointment.BookingChannel.API,
        },
        format="json",
    )
    second_response = client.post(
        reverse("scheduling-appointments-list"),
        {
            "facility_id": str(second_facility.id),
            "patient_id": str(third_patient.id),
            "facility_specialty_id": str(second_facility_specialty.id),
            "practitioner_facility_assignment_id": str(practitioner_second_facility_assignment.id),
            "practitioner_specialty_assignment_id": str(practitioner_second_specialty_assignment.id),
            "scheduled_start": starts_at.isoformat(),
            "scheduled_end": ends_at.isoformat(),
            "booking_channel": Appointment.BookingChannel.API,
        },
        format="json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400


@pytest.mark.django_db
def test_appointment_cancellation_writes_status_history(
    authenticated_client,
    build_time_window,
    facility,
    facility_specialty,
    flow_settings,
    grant_system_permission,
    operating_hours,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_appointment.create", scope="organization", organization=organization)
    grant_system_permission(user=user, permission_code="scheduling_appointment.cancel", scope="organization", organization=organization)
    grant_system_permission(user=user, permission_code="scheduling_appointment.view", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=facility)
    create_response = client.post(
        reverse("scheduling-appointments-list"),
        {
            "facility_id": str(facility.id),
            "patient_id": str(patient.id),
            "facility_specialty_id": str(facility_specialty.id),
            "scheduled_start": starts_at.isoformat(),
            "scheduled_end": ends_at.isoformat(),
            "booking_channel": Appointment.BookingChannel.API,
        },
        format="json",
    )
    cancel_response = client.post(
        reverse("scheduling-appointments-cancel", kwargs={"pk": create_response.data["id"]}),
        {"cancellation_reason": "Patient requested"},
        format="json",
    )
    history_response = client.get(reverse("scheduling-appointments-status-history", kwargs={"pk": create_response.data["id"]}))

    assert cancel_response.status_code == 200
    assert history_response.status_code == 200
    assert [row["to_status"] for row in history_response.data] == [Appointment.Status.PENDING, Appointment.Status.CANCELLED]


@pytest.mark.django_db
def test_rescheduling_creates_new_appointment_and_marks_old_rescheduled(
    authenticated_client,
    build_time_window,
    facility,
    facility_specialty,
    flow_settings,
    grant_system_permission,
    operating_hours,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_appointment.create", scope="organization", organization=organization)
    grant_system_permission(user=user, permission_code="scheduling_appointment.reschedule", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=facility, hour=10, minute=0)
    create_response = client.post(
        reverse("scheduling-appointments-list"),
        {
            "facility_id": str(facility.id),
            "patient_id": str(patient.id),
            "facility_specialty_id": str(facility_specialty.id),
            "scheduled_start": starts_at.isoformat(),
            "scheduled_end": ends_at.isoformat(),
            "booking_channel": Appointment.BookingChannel.API,
        },
        format="json",
    )
    new_start, new_end = build_time_window(facility=facility, hour=11, minute=0)
    reschedule_response = client.post(
        reverse("scheduling-appointments-reschedule", kwargs={"pk": create_response.data["id"]}),
        {
            "scheduled_start": new_start.isoformat(),
            "scheduled_end": new_end.isoformat(),
        },
        format="json",
    )

    original = Appointment.objects.get(pk=create_response.data["id"])
    assert reschedule_response.status_code == 201
    original.refresh_from_db()
    assert original.status == Appointment.Status.RESCHEDULED
    assert str(reschedule_response.data["rescheduled_from"]) == str(original.id)


@pytest.mark.django_db
def test_completed_appointment_cannot_be_cancelled_normally(
    authenticated_client,
    appointment,
    grant_system_permission,
    organization,
    user_factory,
):
    create_initial_appointment_status_history(
        appointment=appointment,
        change_source=AppointmentStatusHistory.ChangeSource.SYSTEM,
    )
    change_appointment_status(
        appointment_id=appointment.id,
        to_status=Appointment.Status.CONFIRMED,
        change_source=AppointmentStatusHistory.ChangeSource.SYSTEM,
    )
    mark_checked_in(appointment_id=appointment.id, change_source=AppointmentStatusHistory.ChangeSource.SYSTEM)
    mark_in_service(appointment_id=appointment.id, change_source=AppointmentStatusHistory.ChangeSource.SYSTEM)
    mark_completed(appointment_id=appointment.id, change_source=AppointmentStatusHistory.ChangeSource.SYSTEM)
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_appointment.cancel", scope="organization", organization=organization)
    client = authenticated_client(user)

    response = client.post(
        reverse("scheduling-appointments-cancel", kwargs={"pk": appointment.id}),
        {"cancellation_reason": "Too late"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_appointment_reason_for_visit_encrypted_is_not_exposed_in_normal_response(
    authenticated_client,
    build_time_window,
    facility,
    facility_specialty,
    flow_settings,
    grant_system_permission,
    operating_hours,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_appointment.create", scope="organization", organization=organization)
    grant_system_permission(user=user, permission_code="scheduling_appointment.view", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=facility)

    create_response = client.post(
        reverse("scheduling-appointments-list"),
        {
            "facility_id": str(facility.id),
            "patient_id": str(patient.id),
            "facility_specialty_id": str(facility_specialty.id),
            "scheduled_start": starts_at.isoformat(),
            "scheduled_end": ends_at.isoformat(),
            "booking_channel": Appointment.BookingChannel.API,
            "reason_for_visit": "Severe headache",
        },
        format="json",
    )
    detail_response = client.get(reverse("scheduling-appointments-detail", kwargs={"pk": create_response.data["id"]}))

    assert create_response.status_code == 201
    assert detail_response.status_code == 200
    assert "reason_for_visit_encrypted" not in create_response.data
    assert "reason_for_visit_encrypted" not in detail_response.data


@pytest.mark.django_db
def test_appointment_number_is_generated_automatically(
    authenticated_client,
    build_time_window,
    facility,
    facility_specialty,
    flow_settings,
    grant_system_permission,
    operating_hours,
    organization,
    patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_appointment.create", scope="organization", organization=organization)
    client = authenticated_client(user)
    starts_at, ends_at = build_time_window(facility=facility)

    response = client.post(
        reverse("scheduling-appointments-list"),
        {
            "facility_id": str(facility.id),
            "patient_id": str(patient.id),
            "facility_specialty_id": str(facility_specialty.id),
            "scheduled_start": starts_at.isoformat(),
            "scheduled_end": ends_at.isoformat(),
            "booking_channel": Appointment.BookingChannel.API,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["appointment_number"].startswith("APT-")


@pytest.mark.django_db
def test_available_slots_endpoint_returns_only_available_slots(
    authenticated_client,
    facility_specialty,
    grant_system_permission,
    organization,
    practitioner_specialty_assignment,
    shift,
    slot,
    second_patient,
    user_factory,
):
    user = user_factory()
    grant_system_permission(user=user, permission_code="scheduling_slot.manage", scope="organization", organization=organization)
    grant_system_permission(user=user, permission_code="scheduling_appointment.create", scope="organization", organization=organization)
    client = authenticated_client(user)

    blocked_slot = AppointmentSlot.objects.create(
        practitioner_shift=shift,
        facility_specialty=facility_specialty,
        starts_at=slot.ends_at,
        ends_at=slot.ends_at + timedelta(minutes=30),
        capacity=1,
        booked_count=0,
    )
    client.post(reverse("scheduling-slots-block", kwargs={"pk": blocked_slot.id}), format="json")

    full_slot = AppointmentSlot.objects.create(
        practitioner_shift=shift,
        facility_specialty=facility_specialty,
        starts_at=blocked_slot.ends_at,
        ends_at=blocked_slot.ends_at + timedelta(minutes=30),
        capacity=1,
        booked_count=0,
    )
    Appointment.objects.create(
        facility=shift.practitioner_facility_assignment.facility,
        patient=second_patient,
        facility_specialty=facility_specialty,
        practitioner_facility_assignment=shift.practitioner_facility_assignment,
        practitioner_specialty_assignment=practitioner_specialty_assignment,
        practitioner_shift=shift,
        appointment_slot=full_slot,
        appointment_number="APT-FULL-0001",
        scheduled_start=full_slot.starts_at,
        scheduled_end=full_slot.ends_at,
        booking_channel=Appointment.BookingChannel.API,
    )
    full_slot.booked_count = 1
    full_slot.status = AppointmentSlot.Status.FULL
    full_slot.save(update_fields=["booked_count", "status", "updated_at"])

    response = client.get(reverse("scheduling-slots-list"))

    slot_ids = {str(row["id"]) for row in response.data}
    assert response.status_code == 200
    assert str(slot.id) in slot_ids
    assert str(blocked_slot.id) not in slot_ids
    assert str(full_slot.id) not in slot_ids
