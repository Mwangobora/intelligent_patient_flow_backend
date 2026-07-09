from __future__ import annotations

from django.db.models import Prefetch, Q

from apps.practitioners.models import Practitioner, PractitionerCredential, PractitionerFacilityAssignment


def list_practitioners(
    *,
    organization_id=None,
    facility_id=None,
    practitioner_type_id=None,
    user_id=None,
    is_active: bool | None = None,
    search: str | None = None,
):
    queryset = Practitioner.objects.select_related("organization", "user", "practitioner_type").prefetch_related(
        Prefetch(
            "facility_assignments",
            queryset=PractitionerFacilityAssignment.objects.select_related("facility").filter(is_active=True),
        ),
        Prefetch(
            "credentials",
            queryset=PractitionerCredential.objects.select_related("credential_type").filter(is_active=True),
        ),
    )
    if organization_id:
        queryset = queryset.filter(organization_id=organization_id)
    if facility_id:
        queryset = queryset.filter(facility_assignments__facility_id=facility_id).distinct()
    if practitioner_type_id:
        queryset = queryset.filter(practitioner_type_id=practitioner_type_id)
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(
            Q(practitioner_number__icontains=search)
            | Q(first_name__icontains=search)
            | Q(middle_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(preferred_name__icontains=search)
            | Q(email__icontains=search)
            | Q(phone_number__icontains=search)
        )
    return queryset.order_by("last_name", "first_name", "practitioner_number")


def get_practitioner_by_id(practitioner_id):
    return (
        Practitioner.objects.select_related("organization", "user", "practitioner_type")
        .prefetch_related(
            "facility_assignments__facility",
            "facility_assignments__department_assignments__department",
            "facility_assignments__specialty_assignments__facility_specialty__specialty",
            "facility_assignments__specialty_assignments__facility_specialty__department",
            "credentials__credential_type",
            "credentials__verified_by",
        )
        .filter(pk=practitioner_id)
        .first()
    )
