from __future__ import annotations

from django.db.models import Q

from apps.patients.models import PatientIdentifier, PatientIdentifierType


def list_identifier_types(
    *,
    organization_id=None,
    include_global: bool = True,
    is_active: bool | None = None,
    search: str | None = None,
):
    queryset = PatientIdentifierType.objects.select_related("organization", "created_by")
    if organization_id:
        scope_filter = Q(organization_id=organization_id)
        if include_global:
            scope_filter |= Q(organization__isnull=True)
        queryset = queryset.filter(scope_filter)
    elif include_global:
        queryset = queryset.all()
    else:
        queryset = queryset.filter(organization__isnull=False)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
    return queryset.order_by("organization_id", "name")


def get_identifier_type_by_id(identifier_type_id):
    return PatientIdentifierType.objects.select_related("organization", "created_by").filter(pk=identifier_type_id).first()


def list_patient_identifiers(
    *,
    patient_id=None,
    identifier_type_id=None,
    organization_id=None,
    is_active: bool | None = None,
):
    queryset = PatientIdentifier.objects.select_related(
        "patient",
        "patient__organization",
        "identifier_type",
        "verified_by",
    )
    if patient_id:
        queryset = queryset.filter(patient_id=patient_id)
    if identifier_type_id:
        queryset = queryset.filter(identifier_type_id=identifier_type_id)
    if organization_id:
        queryset = queryset.filter(patient__organization_id=organization_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("-is_primary", "identifier_type__name", "created_at")


def get_patient_identifier_by_id(identifier_id):
    return (
        PatientIdentifier.objects.select_related(
            "patient",
            "patient__organization",
            "patient__registered_facility",
            "identifier_type",
            "verified_by",
        )
        .filter(pk=identifier_id)
        .first()
    )
