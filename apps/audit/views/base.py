from __future__ import annotations

from rest_framework import viewsets

from apps.accounts.permissions import HasSystemPermission

AUDIT_DOCS_TAG = "Audit APIs"


class AuditBaseViewSet(viewsets.GenericViewSet):
    permission_map: dict[str, str] = {}

    def get_permissions(self):
        if self.action is None:
            return []
        self.required_permission = self.permission_map[self.action]
        return [HasSystemPermission()]
