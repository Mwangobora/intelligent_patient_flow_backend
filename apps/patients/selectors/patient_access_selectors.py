from __future__ import annotations

from apps.patients.models import PatientAccessGrant


def list_patient_access_grants(
    *,
    patient_id=None,
    grantee_user_id=None,
    role_id=None,
    organization_id=None,
    is_active: bool | None = None,
):
    queryset = PatientAccessGrant.objects.select_related(
        "patient",
        "patient__organization",
        "patient__registered_facility",
        "related_person",
        "grantee_user",
        "role",
        "granted_by",
        "revoked_by",
    )
    if patient_id:
        queryset = queryset.filter(patient_id=patient_id)
    if grantee_user_id:
        queryset = queryset.filter(grantee_user_id=grantee_user_id)
    if role_id:
        queryset = queryset.filter(role_id=role_id)
    if organization_id:
        queryset = queryset.filter(patient__organization_id=organization_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("-is_active", "-created_at")


def get_patient_access_grant_by_id(grant_id):
    return (
        PatientAccessGrant.objects.select_related(
            "patient",
            "patient__organization",
            "patient__registered_facility",
            "patient__user",
            "related_person",
            "related_person__linked_user",
            "grantee_user",
            "role",
            "granted_by",
            "revoked_by",
        )
        .filter(pk=grant_id)
        .first()
    )
