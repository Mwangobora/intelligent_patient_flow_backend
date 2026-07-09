from __future__ import annotations

from django.db.models import Q

from apps.facilities.models import Organization


def list_organizations(*, is_active: bool | None = None, search: str | None = None):
    queryset = Organization.objects.all()
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(code__icontains=search) | Q(legal_name__icontains=search)
        )
    return queryset.order_by("name")


def get_organization_by_id(organization_id):
    return Organization.objects.filter(pk=organization_id).first()
