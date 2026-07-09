from __future__ import annotations

from apps.practitioners.models import PractitionerCredential


def list_practitioner_credentials(
    *,
    practitioner_id=None,
    credential_type_id=None,
    organization_id=None,
    is_active: bool | None = None,
):
    queryset = PractitionerCredential.objects.select_related(
        "practitioner",
        "practitioner__organization",
        "credential_type",
        "verified_by",
    )
    if practitioner_id:
        queryset = queryset.filter(practitioner_id=practitioner_id)
    if credential_type_id:
        queryset = queryset.filter(credential_type_id=credential_type_id)
    if organization_id:
        queryset = queryset.filter(practitioner__organization_id=organization_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("-created_at")


def get_practitioner_credential_by_id(credential_id):
    return (
        PractitionerCredential.objects.select_related(
            "practitioner",
            "practitioner__organization",
            "credential_type",
            "verified_by",
        )
        .filter(pk=credential_id)
        .first()
    )
