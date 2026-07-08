from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.accounts.models import Permission, Role, RolePermission, User
from common.exceptions import ConflictError, NotFoundError, ValidationError


def _get_user(user_id, *, field_label: str) -> User:
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} user not found.") from exc


def _get_active_role(role_id) -> Role:
    try:
        role = Role.objects.select_for_update().get(pk=role_id)
    except Role.DoesNotExist as exc:
        raise NotFoundError("Role not found.") from exc

    if not role.is_active:
        raise ValidationError("Role must be active.")
    return role


def _get_active_permission(permission_id) -> Permission:
    try:
        permission = Permission.objects.select_for_update().get(pk=permission_id)
    except Permission.DoesNotExist as exc:
        raise NotFoundError("Permission not found.") from exc

    if not permission.is_active:
        raise ValidationError("Permission must be active.")
    return permission


def _get_role_permission(role_id, permission_id) -> RolePermission:
    try:
        return RolePermission.objects.select_for_update().get(role_id=role_id, permission_id=permission_id)
    except RolePermission.DoesNotExist as exc:
        raise NotFoundError("Role permission assignment not found.") from exc


@transaction.atomic
def grant_permission_to_role(
    *,
    role_id,
    permission_id,
    granted_by_id=None,
) -> RolePermission:
    role = _get_active_role(role_id)
    permission = _get_active_permission(permission_id)
    granted_by = _get_user(granted_by_id, field_label="Granting") if granted_by_id is not None else None

    existing = RolePermission.objects.select_for_update().filter(role=role, permission=permission).first()
    if existing:
        if existing.is_active:
            return existing

        existing.is_active = True
        update_fields = ["is_active", "updated_at"]
        if granted_by_id is not None:
            existing.granted_by = granted_by
            update_fields.append("granted_by")
        existing.save(update_fields=update_fields)
        return existing

    try:
        return RolePermission.objects.create(
            role=role,
            permission=permission,
            granted_by=granted_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Role permission could not be created because it already exists.") from exc


@transaction.atomic
def reactivate_role_permission(
    *,
    role_id,
    permission_id,
    granted_by_id=None,
) -> RolePermission:
    _get_active_role(role_id)
    _get_active_permission(permission_id)
    role_permission = _get_role_permission(role_id, permission_id)
    if role_permission.is_active:
        return role_permission

    granted_by = _get_user(granted_by_id, field_label="Granting") if granted_by_id is not None else None
    role_permission.is_active = True
    update_fields = ["is_active", "updated_at"]
    if granted_by_id is not None:
        role_permission.granted_by = granted_by
        update_fields.append("granted_by")
    role_permission.save(update_fields=update_fields)
    return role_permission


@transaction.atomic
def revoke_permission_from_role(
    *,
    role_id,
    permission_id,
) -> RolePermission:
    role_permission = _get_role_permission(role_id, permission_id)
    if not role_permission.is_active:
        return role_permission

    role_permission.is_active = False
    role_permission.save(update_fields=["is_active", "updated_at"])
    return role_permission
