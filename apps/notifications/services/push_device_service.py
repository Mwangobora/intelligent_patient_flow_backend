from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.notifications.models import UserPushDevice
from common.exceptions import ConflictError, ValidationError

from ._crypto import build_value_hash, encrypt_sensitive_value
from ._shared import clean_optional_text, get_push_device, get_user, validate_user_is_active


@transaction.atomic
def register_push_device(
    *,
    user_id,
    platform: str,
    raw_token: str,
    device_name: str | None = None,
    app_version: str | None = None,
) -> UserPushDevice:
    if platform not in UserPushDevice.Platform.values:
        raise ValidationError("Invalid push device platform.")

    user = get_user(user_id)
    validate_user_is_active(user)
    token = clean_optional_text(raw_token)
    if token is None:
        raise ValidationError("Push token is required.")

    token_hash = build_value_hash(token)
    existing = UserPushDevice.objects.select_for_update().filter(token_hash=token_hash).first()
    now = timezone.now()
    if existing is not None:
        if existing.user_id != user.id:
            raise ConflictError("Push token is already registered to another user.")
        existing.platform = platform
        existing.token_encrypted = encrypt_sensitive_value(token)
        existing.device_name = clean_optional_text(device_name)
        existing.app_version = clean_optional_text(app_version)
        existing.last_seen_at = now
        existing.is_active = True
        existing.revoked_at = None
        existing.save(
            update_fields=[
                "platform",
                "token_encrypted",
                "device_name",
                "app_version",
                "last_seen_at",
                "is_active",
                "revoked_at",
                "updated_at",
            ]
        )
        return existing

    try:
        return UserPushDevice.objects.create(
            user=user,
            platform=platform,
            token_encrypted=encrypt_sensitive_value(token),
            token_hash=token_hash,
            device_name=clean_optional_text(device_name),
            app_version=clean_optional_text(app_version),
            last_seen_at=now,
        )
    except IntegrityError as exc:
        raise ConflictError("Push device conflicts with an existing record.") from exc


@transaction.atomic
def update_push_device_last_seen(*, device_id, last_seen_at=None) -> UserPushDevice:
    device = get_push_device(device_id, lock=True)
    if not device.is_active or device.revoked_at is not None:
        raise ValidationError("Inactive or revoked devices cannot be updated.")
    device.last_seen_at = last_seen_at or timezone.now()
    device.save(update_fields=["last_seen_at", "updated_at"])
    return device


@transaction.atomic
def revoke_push_device(*, device_id) -> UserPushDevice:
    device = get_push_device(device_id, lock=True)
    if device.revoked_at is None:
        device.revoked_at = timezone.now()
    device.is_active = False
    device.save(update_fields=["is_active", "revoked_at", "updated_at"])
    return device


@transaction.atomic
def deactivate_push_device(*, device_id) -> UserPushDevice:
    device = get_push_device(device_id, lock=True)
    device.is_active = False
    device.save(update_fields=["is_active", "updated_at"])
    return device


def get_active_devices_for_user(*, user_id):
    return UserPushDevice.objects.filter(user_id=user_id, is_active=True, revoked_at__isnull=True)
