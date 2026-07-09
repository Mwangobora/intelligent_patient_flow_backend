from __future__ import annotations

from django.db.models import Prefetch, Q

from apps.accounts.models import Role, RolePermission, UserRoleAssignment


def list_roles(
    *,
    organization_id=None,
    facility_id=None,
    is_active: bool | None = None,
    search: str | None = None,
):
    queryset = Role.objects.select_related("organization", "facility", "created_by").prefetch_related(
        Prefetch(
            "role_permissions",
            queryset=RolePermission.objects.select_related("permission").order_by("permission__module", "permission__action"),
        ),
        Prefetch(
            "user_assignments",
            queryset=UserRoleAssignment.objects.select_related("user").order_by("-starts_at"),
        ),
    )
    if organization_id is not None:
        queryset = queryset.filter(organization_id=organization_id)
    if facility_id is not None:
        queryset = queryset.filter(facility_id=facility_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search) | Q(description__icontains=search))
    return queryset.order_by("name")


def get_role_by_id(role_id):
    return Role.objects.select_related("organization", "facility", "created_by").prefetch_related(
        Prefetch(
            "role_permissions",
            queryset=RolePermission.objects.select_related("permission").order_by("permission__module", "permission__action"),
        ),
        Prefetch(
            "user_assignments",
            queryset=UserRoleAssignment.objects.select_related("user").order_by("-starts_at"),
        ),
    ).filter(pk=role_id).first()
