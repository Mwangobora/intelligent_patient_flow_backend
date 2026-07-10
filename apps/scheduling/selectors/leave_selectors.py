from __future__ import annotations

from apps.scheduling.models import PractitionerLeaveRequest


def list_leave_requests(
    *,
    practitioner_facility_assignment_id=None,
    practitioner_id=None,
    facility_id=None,
    status=None,
    starts_from=None,
    ends_to=None,
):
    queryset = PractitionerLeaveRequest.objects.select_related(
        "practitioner_facility_assignment",
        "practitioner_facility_assignment__practitioner",
        "practitioner_facility_assignment__facility",
        "requested_by",
        "decided_by",
        "cancelled_by",
    )
    if practitioner_facility_assignment_id:
        queryset = queryset.filter(practitioner_facility_assignment_id=practitioner_facility_assignment_id)
    if practitioner_id:
        queryset = queryset.filter(practitioner_facility_assignment__practitioner_id=practitioner_id)
    if facility_id:
        queryset = queryset.filter(practitioner_facility_assignment__facility_id=facility_id)
    if status:
        queryset = queryset.filter(status=status)
    if starts_from:
        queryset = queryset.filter(starts_at__gte=starts_from)
    if ends_to:
        queryset = queryset.filter(ends_at__lte=ends_to)
    return queryset.order_by("-starts_at")


def get_leave_request_by_id(leave_request_id):
    return list_leave_requests().filter(pk=leave_request_id).first()
