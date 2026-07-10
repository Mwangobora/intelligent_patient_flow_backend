from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.scheduling.models import Appointment, PractitionerLeaveRequest
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    ACTIVE_APPOINTMENT_STATUSES,
    datetime_overlap,
    ensure_within_assignment_dates,
    get_leave_request,
    get_practitioner_facility_assignment,
    get_user,
    normalize_optional_text,
    validate_datetime_range,
)


def _validate_overlap(*, practitioner_facility_assignment, starts_at, ends_at, exclude_id=None) -> None:
    queryset = PractitionerLeaveRequest.objects.select_for_update().filter(
        practitioner_facility_assignment=practitioner_facility_assignment,
        status__in=[PractitionerLeaveRequest.Status.PENDING, PractitionerLeaveRequest.Status.APPROVED],
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.filter(starts_at__lt=ends_at, ends_at__gt=starts_at).exists():
        raise ConflictError("Leave overlaps another pending or approved request.")


def _affected_appointments(leave_request: PractitionerLeaveRequest):
    return list(
        Appointment.objects.filter(
            practitioner_facility_assignment=leave_request.practitioner_facility_assignment,
            status__in=ACTIVE_APPOINTMENT_STATUSES,
            scheduled_start__lt=leave_request.ends_at,
            scheduled_end__gt=leave_request.starts_at,
        ).order_by("scheduled_start")
    )


@transaction.atomic
def request_leave(
    *,
    practitioner_facility_assignment_id,
    starts_at,
    ends_at,
    reason: str | None = None,
    requested_by_id=None,
) -> PractitionerLeaveRequest:
    practitioner_facility_assignment = get_practitioner_facility_assignment(
        practitioner_facility_assignment_id,
        active_only=True,
        for_update=True,
    )
    requested_by = get_user(requested_by_id, field_label="Requesting user", active_only=True) if requested_by_id is not None else None
    validate_datetime_range(starts_at=starts_at, ends_at=ends_at, label="Leave request")
    ensure_within_assignment_dates(
        facility=practitioner_facility_assignment.facility,
        starts_at=starts_at,
        ends_at=ends_at,
        assignment=practitioner_facility_assignment,
        label="Leave request",
    )
    _validate_overlap(
        practitioner_facility_assignment=practitioner_facility_assignment,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    try:
        return PractitionerLeaveRequest.objects.create(
            practitioner_facility_assignment=practitioner_facility_assignment,
            starts_at=starts_at,
            ends_at=ends_at,
            reason=normalize_optional_text(reason),
            requested_by=requested_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Leave request could not be created because a conflicting record already exists.") from exc


@transaction.atomic
def approve_leave(*, leave_request_id, decided_by_id, decided_at=None, decision_note: str | None = None):
    leave_request = get_leave_request(leave_request_id, for_update=True)
    if leave_request.status != PractitionerLeaveRequest.Status.PENDING:
        raise ValidationError("Only pending leave requests can be approved.")
    _validate_overlap(
        practitioner_facility_assignment=leave_request.practitioner_facility_assignment,
        starts_at=leave_request.starts_at,
        ends_at=leave_request.ends_at,
        exclude_id=leave_request.pk,
    )
    leave_request.status = PractitionerLeaveRequest.Status.APPROVED
    leave_request.decided_by = get_user(decided_by_id, field_label="Deciding user", active_only=True)
    leave_request.decided_at = decided_at or timezone.now()
    leave_request.decision_note = normalize_optional_text(decision_note)
    leave_request.cancelled_by = None
    leave_request.cancelled_at = None
    leave_request.cancellation_reason = None
    leave_request.save()
    return leave_request, _affected_appointments(leave_request)


@transaction.atomic
def reject_leave(*, leave_request_id, decided_by_id, decided_at=None, decision_note: str | None = None) -> PractitionerLeaveRequest:
    leave_request = get_leave_request(leave_request_id, for_update=True)
    if leave_request.status != PractitionerLeaveRequest.Status.PENDING:
        raise ValidationError("Only pending leave requests can be rejected.")
    leave_request.status = PractitionerLeaveRequest.Status.REJECTED
    leave_request.decided_by = get_user(decided_by_id, field_label="Deciding user", active_only=True)
    leave_request.decided_at = decided_at or timezone.now()
    leave_request.decision_note = normalize_optional_text(decision_note)
    leave_request.cancelled_by = None
    leave_request.cancelled_at = None
    leave_request.cancellation_reason = None
    leave_request.save()
    return leave_request


@transaction.atomic
def cancel_leave(*, leave_request_id, cancelled_by_id, cancellation_reason: str, cancelled_at=None) -> PractitionerLeaveRequest:
    leave_request = get_leave_request(leave_request_id, for_update=True)
    if leave_request.status == PractitionerLeaveRequest.Status.CANCELLED:
        return leave_request
    if leave_request.status == PractitionerLeaveRequest.Status.REJECTED:
        raise ValidationError("Rejected leave requests cannot be cancelled.")
    reason = normalize_optional_text(cancellation_reason)
    if reason is None:
        raise ValidationError("cancellation_reason is required.")
    leave_request.status = PractitionerLeaveRequest.Status.CANCELLED
    leave_request.cancelled_by = get_user(cancelled_by_id, field_label="Cancelling user", active_only=True)
    leave_request.cancelled_at = cancelled_at or timezone.now()
    leave_request.cancellation_reason = reason
    leave_request.decided_by = None
    leave_request.decided_at = None
    leave_request.decision_note = None
    leave_request.save()
    return leave_request
