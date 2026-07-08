from __future__ import annotations

import re

from django.db import IntegrityError, transaction

from apps.accounts.models import Permission, User
from common.exceptions import ConflictError, NotFoundError, ValidationError

PERMISSION_SEGMENT_RE = re.compile(r"[^a-z0-9_]+")
PERMISSION_CODE_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
UNDERSCORE_RE = re.compile(r"_+")


def _normalize_permission_segment(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    normalized = PERMISSION_SEGMENT_RE.sub("_", normalized)
    normalized = UNDERSCORE_RE.sub("_", normalized).strip("_")
    return normalized


def _normalize_module_and_action(*, module: str, action: str) -> tuple[str, str]:
    if not module or not module.strip():
        raise ValidationError("Permission module is required.")
    if not action or not action.strip():
        raise ValidationError("Permission action is required.")

    normalized_module = _normalize_permission_segment(module)
    normalized_action = _normalize_permission_segment(action)
    if not normalized_module:
        raise ValidationError("Permission module cannot be empty after normalization.")
    if not normalized_action:
        raise ValidationError("Permission action cannot be empty after normalization.")
    return normalized_module, normalized_action


def _build_permission_code(*, module: str, action: str) -> str:
    return f"{module}.{action}"


def _normalize_supplied_code(code: str) -> str:
    normalized_code = code.strip().lower()
    if not normalized_code or not PERMISSION_CODE_RE.fullmatch(normalized_code):
        raise ValidationError("Permission code must use lowercase module.action format.")
    return normalized_code


def _get_permission_for_update(permission_id) -> Permission:
    try:
        return Permission.objects.select_for_update().get(pk=permission_id)
    except Permission.DoesNotExist as exc:
        raise NotFoundError("Permission not found.") from exc


def _get_user(user_id, *, field_label: str) -> User:
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} user not found.") from exc


def _ensure_permission_uniqueness(
    *,
    name: str,
    code: str,
    module: str,
    action: str,
    exclude_id=None,
) -> None:
    queryset = Permission.objects.select_for_update()
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    if queryset.filter(name__iexact=name).exists():
        raise ConflictError("Permission name already exists.")
    if queryset.filter(code=code).exists():
        raise ConflictError("Permission code already exists.")
    if queryset.filter(module=module, action=action).exists():
        raise ConflictError("Permission module/action pair already exists.")


@transaction.atomic
def create_permission(
    *,
    name: str,
    module: str,
    action: str,
    description: str | None = None,
    code: str | None = None,
    created_by_id=None,
) -> Permission:
    if not name or not name.strip():
        raise ValidationError("Permission name is required.")

    cleaned_name = name.strip()
    normalized_module, normalized_action = _normalize_module_and_action(module=module, action=action)
    expected_code = _build_permission_code(module=normalized_module, action=normalized_action)

    if code is not None:
        normalized_code = _normalize_supplied_code(code)
        if normalized_code != expected_code:
            raise ValidationError("Permission code must match the normalized module.action value.")
    else:
        normalized_code = expected_code

    _ensure_permission_uniqueness(
        name=cleaned_name,
        code=normalized_code,
        module=normalized_module,
        action=normalized_action,
    )

    created_by = _get_user(created_by_id, field_label="Creator") if created_by_id is not None else None

    try:
        return Permission.objects.create(
            name=cleaned_name,
            code=normalized_code,
            module=normalized_module,
            action=normalized_action,
            description=description.strip() if description else None,
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Permission could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_permission(
    *,
    permission_id,
    regenerate_code: bool = False,
    **updates,
) -> Permission:
    permission = _get_permission_for_update(permission_id)

    allowed_fields = {"name", "code", "module", "action", "description"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported permission update fields: {unexpected}.")

    next_name = permission.name
    if "name" in updates:
        if not updates["name"] or not updates["name"].strip():
            raise ValidationError("Permission name is required.")
        next_name = updates["name"].strip()

    next_module = permission.module
    next_action = permission.action
    if "module" in updates or "action" in updates:
        module_value = updates["module"] if "module" in updates else permission.module
        action_value = updates["action"] if "action" in updates else permission.action
        next_module, next_action = _normalize_module_and_action(module=module_value, action=action_value)

    expected_code = _build_permission_code(module=next_module, action=next_action)
    if "code" in updates and updates["code"] is not None:
        next_code = _normalize_supplied_code(updates["code"])
        if next_code != expected_code:
            raise ValidationError("Permission code must match the normalized module.action value.")
    elif regenerate_code or "module" in updates or "action" in updates:
        next_code = expected_code
    else:
        next_code = permission.code

    _ensure_permission_uniqueness(
        name=next_name,
        code=next_code,
        module=next_module,
        action=next_action,
        exclude_id=permission.pk,
    )

    permission.name = next_name
    permission.module = next_module
    permission.action = next_action
    permission.code = next_code

    if "description" in updates:
        permission.description = updates["description"].strip() if updates["description"] else None

    try:
        permission.save()
    except IntegrityError as exc:
        raise ConflictError("Permission could not be updated because a unique value already exists.") from exc
    return permission


@transaction.atomic
def deactivate_permission(*, permission_id) -> Permission:
    permission = _get_permission_for_update(permission_id)
    if not permission.is_active:
        return permission

    permission.is_active = False
    permission.save(update_fields=["is_active", "updated_at"])
    return permission
