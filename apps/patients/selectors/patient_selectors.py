from __future__ import annotations

from django.db.models import Prefetch, Q

from apps.patients.models import Patient, PatientAccessGrant, PatientAddress, PatientIdentifier, PatientRelatedPerson


def list_patients(
    *,
    organization_id=None,
    registered_facility_id=None,
    user_id=None,
    is_active: bool | None = None,
    search: str | None = None,
):
    queryset = Patient.objects.select_related("organization", "registered_facility", "user").prefetch_related(
        Prefetch("identifiers", queryset=PatientIdentifier.objects.select_related("identifier_type")),
        Prefetch("addresses", queryset=PatientAddress.objects.filter(is_active=True)),
        Prefetch("related_persons", queryset=PatientRelatedPerson.objects.select_related("relationship_type", "linked_user")),
        Prefetch("access_grants", queryset=PatientAccessGrant.objects.select_related("grantee_user", "role")),
    )
    if organization_id:
        queryset = queryset.filter(organization_id=organization_id)
    if registered_facility_id:
        queryset = queryset.filter(registered_facility_id=registered_facility_id)
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(
            Q(patient_number__icontains=search)
            | Q(first_name__icontains=search)
            | Q(middle_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(phone_number__icontains=search)
        )
    return queryset.order_by("last_name", "first_name", "patient_number")


def get_patient_by_id(patient_id):
    return (
        Patient.objects.select_related("organization", "registered_facility", "user")
        .prefetch_related(
            Prefetch("identifiers", queryset=PatientIdentifier.objects.select_related("identifier_type", "verified_by")),
            Prefetch("addresses", queryset=PatientAddress.objects.order_by("-is_primary", "created_at")),
            Prefetch(
                "related_persons",
                queryset=PatientRelatedPerson.objects.select_related("relationship_type", "linked_user").prefetch_related("contacts"),
            ),
            Prefetch(
                "access_grants",
                queryset=PatientAccessGrant.objects.select_related("grantee_user", "role", "related_person", "revoked_by"),
            ),
        )
        .filter(pk=patient_id)
        .first()
    )
