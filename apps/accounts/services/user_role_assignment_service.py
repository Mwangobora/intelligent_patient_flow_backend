from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Role, User, UserMembership, UserRoleAssignment
from common.exceptions import ConflictError, NotFoundError, ValidationError


def _get_active_user(user_id) -> User:
    try:
        user = User.objects.select_for_update().get(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError("User not found.") from exc

    if not user.is_active:
        raise ValidationError("User must be active.")
    return user


def _get_active_role(role_id) -> Role:
    try:
        role = Role.objects.select_for_update().select_related("organization", "facility").get(pk=role_id)
    except Role.DoesNotExist as exc:
        raise NotFoundError("Role not found.") from exc

    if not role.is_active:
        raise ValidationError("Role must be active.")
    return role


def _get_assigning_user(user_id) -> User:
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError("Assigning user not found.") from exc


def _get_assignment_for_update(user_id, role_id) -> UserRoleAssignment:
    try:
        return UserRoleAssignment.objects.select_for_update().get(user_id=user_id, role_id=role_id)
    except UserRoleAssignment.DoesNotExist as exc:
        raise NotFoundError("User role assignment not found.") from exc


def _resolve_assignment_dates(*, starts_at, ends_at) -> tuple:
    resolved_starts_at = starts_at or timezone.now()
    if ends_at is not None and ends_at < resolved_starts_at:
        raise ValidationError("Role assignment ends_at must be greater than or equal to starts_at.")
    return resolved_starts_at, ends_at


def _has_active_membership(*, user: User, role: Role, effective_at) -> bool:
    queryset = UserMembership.objects.select_for_update().filter(
        user=user,
        is_active=True,
        starts_at__lte=effective_at,
    ).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gte=effective_at),
    )

    if role.facility_id is not None:
        return queryset.filter(
            organization_id=role.organization_id,
            facility_id=role.facility_id,
        ).exists()
    if role.organization_id is not None:
        return queryset.filter(
            organization_id=role.organization_id,
            facility__isnull=True,
        ).exists()
    return True


def _validate_assignment_scope(*, user: User, role: Role, effective_at) -> None:
    if role.facility_id is not None and not _has_active_membership(user=user, role=role, effective_at=effective_at):
        raise ValidationError("Facility-scoped roles require an active matching facility membership.")
    if (
        role.facility_id is None
        and role.organization_id is not None
        and not _has_active_membership(user=user, role=role, effective_at=effective_at)
    ):
        raise ValidationError("Organization-scoped roles require an active organization membership.")


@transaction.atomic
def assign_role_to_user(
    *,
    user_id,
    role_id,
    starts_at=None,
    ends_at=None,
    assigned_by_id=None,
) -> UserRoleAssignment:
    user = _get_active_user(user_id)
    role = _get_active_role(role_id)
    resolved_starts_at, resolved_ends_at = _resolve_assignment_dates(starts_at=starts_at, ends_at=ends_at)
    _validate_assignment_scope(user=user, role=role, effective_at=resolved_starts_at)

    assigned_by = _get_assigning_user(assigned_by_id) if assigned_by_id is not None else None
    existing = UserRoleAssignment.objects.select_for_update().filter(user=user, role=role).first()
    if existing:
        if existing.is_active:
            return existing

        existing.starts_at = resolved_starts_at
        existing.ends_at = resolved_ends_at
        existing.is_active = True
        update_fields = ["starts_at", "ends_at", "is_active", "updated_at"]
        if assigned_by_id is not None:
            existing.assigned_by = assigned_by
            update_fields.append("assigned_by")
        existing.save(update_fields=update_fields)
        return existing

    try:
        return UserRoleAssignment.objects.create(
            user=user,
            role=role,
            assigned_by=assigned_by,
            starts_at=resolved_starts_at,
            ends_at=resolved_ends_at,
        )
    except IntegrityError as exc:
        raise ConflictError("User role assignment could not be created because it already exists.") from exc


@transaction.atomic
def reactivate_role_assignment(
    *,
    user_id,
    role_id,
    starts_at=None,
    ends_at=None,
    assigned_by_id=None,
) -> UserRoleAssignment:
    user = _get_active_user(user_id)
    role = _get_active_role(role_id)
    role_assignment = _get_assignment_for_update(user_id, role_id)
    if role_assignment.is_active:
        return role_assignment

    resolved_starts_at, resolved_ends_at = _resolve_assignment_dates(starts_at=starts_at, ends_at=ends_at)
    _validate_assignment_scope(user=user, role=role, effective_at=resolved_starts_at)

    role_assignment.starts_at = resolved_starts_at
    role_assignment.ends_at = resolved_ends_at
    role_assignment.is_active = True
    update_fields = ["starts_at", "ends_at", "is_active", "updated_at"]
    if assigned_by_id is not None:
        role_assignment.assigned_by = _get_assigning_user(assigned_by_id)
        update_fields.append("assigned_by")
    role_assignment.save(update_fields=update_fields)
    return role_assignment


@transaction.atomic
def revoke_role_from_user(
    *,
    user_id,
    role_id,
    set_ends_at: bool = True,
) -> UserRoleAssignment:
    role_assignment = _get_assignment_for_update(user_id, role_id)
    if not role_assignment.is_active:
        return role_assignment

    role_assignment.is_active = False
    update_fields = ["is_active", "updated_at"]
    if set_ends_at:
        now = timezone.now()
        role_assignment.ends_at = now if now >= role_assignment.starts_at else role_assignment.starts_at
        update_fields.append("ends_at")

    role_assignment.save(update_fields=update_fields)
    return role_assignment
