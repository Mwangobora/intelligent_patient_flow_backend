from __future__ import annotations

from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import timezone

from apps.accounts.models import Permission, RolePermission, UserMembership, UserRoleAssignment
from apps.facilities.models import Facility, Organization


def list_permissions(
    *,
    module: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
):
    queryset = Permission.objects.all().prefetch_related(
        Prefetch(
            "role_permissions",
            queryset=RolePermission.objects.select_related("role").filter(is_active=True),
        )
    )
    if module:
        queryset = queryset.filter(module=module)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(code__icontains=search) | Q(module__icontains=search) | Q(action__icontains=search)
        )
    return queryset.order_by("module", "action")


def get_permission_by_id(permission_id):
    return Permission.objects.prefetch_related(
        Prefetch(
            "role_permissions",
            queryset=RolePermission.objects.select_related("role", "role__organization", "role__facility"),
        )
    ).filter(pk=permission_id).first()


def _resolve_scope_ids(*, organization=None, facility=None) -> tuple[str | None, str | None]:
    organization_id = None
    facility_id = None

    if isinstance(organization, Organization):
        organization_id = organization.id
    elif organization is not None:
        organization_id = organization

    if isinstance(facility, Facility):
        facility_id = facility.id
        if organization_id is None:
            organization_id = facility.organization_id
    elif facility is not None:
        facility_record = Facility.objects.select_related("organization").filter(pk=facility).first()
        if facility_record:
            facility_id = facility_record.id
            if organization_id is None:
                organization_id = facility_record.organization_id

    return organization_id, facility_id


def get_user_effective_permissions(
    *,
    user,
    organization=None,
    facility=None,
    effective_at=None,
):
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return Permission.objects.none()
    if user.is_superuser:
        return Permission.objects.filter(is_active=True).order_by("module", "action")

    effective_at = effective_at or timezone.now()
    organization_id, facility_id = _resolve_scope_ids(organization=organization, facility=facility)

    membership_base = UserMembership.objects.filter(
        user_id=user.id,
        is_active=True,
        starts_at__lte=effective_at,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gte=effective_at))

    assignments = UserRoleAssignment.objects.filter(
        user_id=user.id,
        is_active=True,
        role__is_active=True,
        starts_at__lte=effective_at,
    ).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gte=effective_at)
    ).annotate(
        has_org_membership=Exists(
            membership_base.filter(
                organization_id=OuterRef("role__organization_id"),
                facility__isnull=True,
            )
        ),
        has_facility_membership=Exists(
            membership_base.filter(
                organization_id=OuterRef("role__organization_id"),
                facility_id=OuterRef("role__facility_id"),
            )
        ),
    ).filter(
        Q(role__organization__isnull=True, role__facility__isnull=True)
        | Q(role__organization__isnull=False, role__facility__isnull=True, has_org_membership=True)
        | Q(role__facility__isnull=False, has_facility_membership=True)
    )

    if facility_id is not None:
        assignments = assignments.filter(
            Q(role__organization__isnull=True, role__facility__isnull=True)
            | Q(role__organization_id=organization_id, role__facility__isnull=True)
            | Q(role__facility_id=facility_id)
        )
    elif organization_id is not None:
        assignments = assignments.filter(
            Q(role__organization__isnull=True, role__facility__isnull=True)
            | Q(role__organization_id=organization_id, role__facility__isnull=True)
        )

    return Permission.objects.filter(
        is_active=True,
        role_permissions__is_active=True,
        role_permissions__role_id__in=assignments.values("role_id"),
    ).distinct().order_by("module", "action")
