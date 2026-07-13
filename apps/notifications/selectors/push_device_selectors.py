from __future__ import annotations

from apps.notifications.models import UserPushDevice


def push_device_queryset():
    return UserPushDevice.objects.select_related("user").order_by("-created_at")


def list_push_devices(*, user_id=None, is_active: bool | None = None, revoked: bool | None = None):
    queryset = push_device_queryset()
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if revoked is True:
        queryset = queryset.filter(revoked_at__isnull=False)
    elif revoked is False:
        queryset = queryset.filter(revoked_at__isnull=True)
    return queryset


def get_push_device_by_id(device_id):
    return push_device_queryset().filter(pk=device_id).first()


def list_active_push_devices_by_user(*, user_id):
    return list_push_devices(user_id=user_id, is_active=True, revoked=False)


def list_revoked_push_devices_by_user(*, user_id):
    return list_push_devices(user_id=user_id, revoked=True)
