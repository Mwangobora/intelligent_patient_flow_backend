from __future__ import annotations

from django.db.models import Prefetch, Q
from django.utils import timezone

from apps.accounts.models import User, UserMembership, UserRoleAssignment


def list_users(
    *,
    organization_id=None,
    facility_id=None,
    is_active: bool | None = None,
    search: str | None = None,
):
    queryset = User.objects.all().prefetch_related(
        Prefetch(
            "memberships",
            queryset=UserMembership.objects.select_related("organization", "facility").order_by("-starts_at"),
        ),
        Prefetch(
            "role_assignments",
            queryset=UserRoleAssignment.objects.select_related("role", "role__organization", "role__facility").order_by(
                "-starts_at"
            ),
        ),
    )

    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if organization_id is not None:
        queryset = queryset.filter(memberships__organization_id=organization_id)
    if facility_id is not None:
        queryset = queryset.filter(memberships__facility_id=facility_id)
    if search:
        queryset = queryset.filter(
            Q(email__icontains=search)
            | Q(phone_number__icontains=search)
            | Q(first_name__icontains=search)
            | Q(middle_name__icontains=search)
            | Q(last_name__icontains=search)
        )

    return queryset.distinct().order_by("first_name", "last_name", "email")


def get_user_by_id(user_id):
    return (
        User.objects.select_related()
        .prefetch_related(
            Prefetch(
                "memberships",
                queryset=UserMembership.objects.select_related("organization", "facility").order_by("-starts_at"),
            ),
            Prefetch(
                "role_assignments",
                queryset=UserRoleAssignment.objects.select_related("role", "role__organization", "role__facility").order_by(
                    "-starts_at"
                ),
            ),
        )
        .filter(pk=user_id)
        .first()
    )


def get_user_by_email_or_phone(email_or_phone: str):
    normalized_identifier = email_or_phone.strip()
    if not normalized_identifier:
        return None

    return User.objects.filter(
        Q(email__iexact=normalized_identifier) | Q(phone_number=normalized_identifier)
    ).first()


def get_user_memberships(
    *,
    user_id,
    organization_id=None,
    facility_id=None,
    is_active: bool | None = None,
):
    queryset = UserMembership.objects.select_related("organization", "facility").filter(user_id=user_id)
    if organization_id is not None:
        queryset = queryset.filter(organization_id=organization_id)
    if facility_id is not None:
        queryset = queryset.filter(facility_id=facility_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("-starts_at")


def get_user_role_assignments(
    *,
    user_id,
    organization_id=None,
    facility_id=None,
    is_active: bool | None = None,
    effective_at=None,
):
    queryset = UserRoleAssignment.objects.select_related("role", "role__organization", "role__facility").filter(user_id=user_id)
    if organization_id is not None:
        queryset = queryset.filter(role__organization_id=organization_id)
    if facility_id is not None:
        queryset = queryset.filter(role__facility_id=facility_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)

    effective_at = effective_at or timezone.now()
    return queryset.filter(
        starts_at__lte=effective_at,
    ).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gte=effective_at)
    ).order_by("-starts_at")
