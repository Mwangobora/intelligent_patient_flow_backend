from __future__ import annotations

from rest_framework import viewsets

from apps.accounts.permissions import HasSystemPermission

BILLING_DOCS_TAG = "Billing APIs"


def _bool_query_param(value):
    if value is None:
        return None
    return value.lower() == "true"


class BillingBaseViewSet(viewsets.GenericViewSet):
    permission_map: dict[str, str] = {}

    def get_permissions(self):
        self.required_permission = self.permission_map[self.action]
        return [HasSystemPermission()]
