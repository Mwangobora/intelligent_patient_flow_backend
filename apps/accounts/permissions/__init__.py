from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.accounts.selectors.permission_selectors import get_user_effective_permissions


def user_has_permission(user, permission_code: str, organization=None, facility=None) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if not user.is_active:
        return False
    if user.is_superuser:
        return True

    return get_user_effective_permissions(
        user=user,
        organization=organization,
        facility=facility,
    ).filter(code=permission_code).exists()


class IsAuthenticatedActive(BasePermission):
    message = "Authentication is required."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_active)


class HasSystemPermission(BasePermission):
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated or not request.user.is_active:
            return False
        if request.user.is_superuser:
            return True

        permission_codes = getattr(view, "required_permissions_any", None)
        permission_code = getattr(view, "required_permission", None)
        if not permission_code and not permission_codes:
            return False

        if hasattr(view, "get_permission_scope"):
            organization, facility = view.get_permission_scope(request)
        else:
            organization, facility = None, None

        if permission_codes:
            return any(
                user_has_permission(
                    request.user,
                    candidate_permission,
                    organization=organization,
                    facility=facility,
                )
                for candidate_permission in permission_codes
            )

        return user_has_permission(
            request.user,
            permission_code,
            organization=organization,
            facility=facility,
        )


__all__ = [
    "HasSystemPermission",
    "IsAuthenticatedActive",
    "user_has_permission",
]
