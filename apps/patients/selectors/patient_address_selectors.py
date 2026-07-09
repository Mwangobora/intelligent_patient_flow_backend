from __future__ import annotations

from apps.patients.models import PatientAddress


def list_patient_addresses(*, patient_id=None, organization_id=None, is_active: bool | None = None):
    queryset = PatientAddress.objects.select_related("patient", "patient__organization", "patient__registered_facility")
    if patient_id:
        queryset = queryset.filter(patient_id=patient_id)
    if organization_id:
        queryset = queryset.filter(patient__organization_id=organization_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("-is_primary", "-created_at")


def get_patient_address_by_id(address_id):
    return (
        PatientAddress.objects.select_related("patient", "patient__organization", "patient__registered_facility")
        .filter(pk=address_id)
        .first()
    )
