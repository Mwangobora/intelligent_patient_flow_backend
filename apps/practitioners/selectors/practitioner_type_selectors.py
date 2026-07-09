from __future__ import annotations

from django.db.models import Q

from apps.practitioners.models import PractitionerCredentialType, PractitionerType


def list_practitioner_types(*, is_active: bool | None = None, search: str | None = None):
    queryset = PractitionerType.objects.all()
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
    return queryset.order_by("name")


def get_practitioner_type_by_id(practitioner_type_id):
    return PractitionerType.objects.filter(pk=practitioner_type_id).first()


def list_practitioner_credential_types(
    *,
    organization_id=None,
    include_global: bool = True,
    is_active: bool | None = None,
    search: str | None = None,
):
    queryset = PractitionerCredentialType.objects.select_related("organization", "created_by")
    if organization_id:
        scope_filter = Q(organization_id=organization_id)
        if include_global:
            scope_filter |= Q(organization__isnull=True)
        queryset = queryset.filter(scope_filter)
    elif not include_global:
        queryset = queryset.filter(organization__isnull=False)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
    return queryset.order_by("organization_id", "name")


def get_practitioner_credential_type_by_id(credential_type_id):
    return PractitionerCredentialType.objects.select_related("organization", "created_by").filter(pk=credential_type_id).first()
