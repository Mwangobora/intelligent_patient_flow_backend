from __future__ import annotations

from rest_framework import viewsets

from apps.accounts.permissions import HasSystemPermission

INTELLIGENCE_DOCS_TAG = "Intelligence APIs"


class IntelligenceBaseViewSet(viewsets.GenericViewSet):
    permission_map: dict[str, str] = {}

    def get_permissions(self):
        self.required_permission = self.permission_map[self.action]
        return [HasSystemPermission()]
