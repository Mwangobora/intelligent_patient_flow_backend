from __future__ import annotations

from apps.practitioners.models import (
    PractitionerDepartmentAssignment,
    PractitionerFacilityAssignment,
    PractitionerSpecialtyAssignment,
)


def list_practitioner_facility_assignments(*, practitioner_id=None, facility_id=None, organization_id=None, is_active: bool | None = None):
    queryset = PractitionerFacilityAssignment.objects.select_related(
        "practitioner",
        "practitioner__organization",
        "facility",
    )
    if practitioner_id:
        queryset = queryset.filter(practitioner_id=practitioner_id)
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if organization_id:
        queryset = queryset.filter(practitioner__organization_id=organization_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("-is_primary", "-created_at")


def get_practitioner_facility_assignment_by_id(assignment_id):
    return (
        PractitionerFacilityAssignment.objects.select_related(
            "practitioner",
            "practitioner__organization",
            "facility",
        )
        .prefetch_related("department_assignments__department", "specialty_assignments__facility_specialty__specialty")
        .filter(pk=assignment_id)
        .first()
    )


def list_practitioner_department_assignments(
    *,
    practitioner_facility_assignment_id=None,
    department_id=None,
    facility_id=None,
    organization_id=None,
    is_active: bool | None = None,
):
    queryset = PractitionerDepartmentAssignment.objects.select_related(
        "practitioner_facility_assignment",
        "practitioner_facility_assignment__practitioner",
        "practitioner_facility_assignment__facility",
        "department",
        "department__facility",
    )
    if practitioner_facility_assignment_id:
        queryset = queryset.filter(practitioner_facility_assignment_id=practitioner_facility_assignment_id)
    if department_id:
        queryset = queryset.filter(department_id=department_id)
    if facility_id:
        queryset = queryset.filter(practitioner_facility_assignment__facility_id=facility_id)
    if organization_id:
        queryset = queryset.filter(practitioner_facility_assignment__practitioner__organization_id=organization_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("-is_primary", "-created_at")


def get_practitioner_department_assignment_by_id(assignment_id):
    return (
        PractitionerDepartmentAssignment.objects.select_related(
            "practitioner_facility_assignment",
            "practitioner_facility_assignment__practitioner",
            "practitioner_facility_assignment__facility",
            "department",
            "department__facility",
        )
        .filter(pk=assignment_id)
        .first()
    )


def list_practitioner_specialty_assignments(
    *,
    practitioner_facility_assignment_id=None,
    facility_specialty_id=None,
    facility_id=None,
    specialty_id=None,
    department_id=None,
    organization_id=None,
    is_active: bool | None = None,
):
    queryset = PractitionerSpecialtyAssignment.objects.select_related(
        "practitioner_facility_assignment",
        "practitioner_facility_assignment__practitioner",
        "practitioner_facility_assignment__facility",
        "facility_specialty",
        "facility_specialty__facility",
        "facility_specialty__specialty",
        "facility_specialty__department",
    )
    if practitioner_facility_assignment_id:
        queryset = queryset.filter(practitioner_facility_assignment_id=practitioner_facility_assignment_id)
    if facility_specialty_id:
        queryset = queryset.filter(facility_specialty_id=facility_specialty_id)
    if facility_id:
        queryset = queryset.filter(practitioner_facility_assignment__facility_id=facility_id)
    if specialty_id:
        queryset = queryset.filter(facility_specialty__specialty_id=specialty_id)
    if department_id:
        queryset = queryset.filter(facility_specialty__department_id=department_id)
    if organization_id:
        queryset = queryset.filter(practitioner_facility_assignment__practitioner__organization_id=organization_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("-is_primary", "-created_at")


def get_practitioner_specialty_assignment_by_id(assignment_id):
    return (
        PractitionerSpecialtyAssignment.objects.select_related(
            "practitioner_facility_assignment",
            "practitioner_facility_assignment__practitioner",
            "practitioner_facility_assignment__facility",
            "facility_specialty",
            "facility_specialty__facility",
            "facility_specialty__specialty",
            "facility_specialty__department",
        )
        .filter(pk=assignment_id)
        .first()
    )
