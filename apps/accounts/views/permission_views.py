from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import HasSystemPermission
from apps.accounts.selectors import get_permission_by_id, list_permissions
from apps.accounts.serializers import (
    PermissionCreateSerializer,
    PermissionDetailSerializer,
    PermissionListSerializer,
    PermissionUpdateSerializer,
)
from apps.accounts.services import create_permission, deactivate_permission, update_permission

from ._helpers import translate_domain_error


@extend_schema(tags=["Authorization APIs"])
class PermissionViewSet(viewsets.GenericViewSet):
    lookup_url_kwarg = "pk"

    def get_permissions(self):
        permission_map = {
            "list": "accounts_permission.view",
            "retrieve": "accounts_permission.view",
            "create": "accounts_permission.create",
            "partial_update": "accounts_permission.update",
            "deactivate": "accounts_permission.deactivate",
        }
        self.required_permission = permission_map[self.action]
        return [HasSystemPermission()]

    def list(self, request):
        queryset = list_permissions(
            module=request.query_params.get("module"),
            is_active=None if request.query_params.get("is_active") is None else request.query_params.get("is_active") == "true",
            search=request.query_params.get("search"),
        )
        return Response(PermissionListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = PermissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            permission = create_permission(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PermissionDetailSerializer(permission).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        permission = get_permission_by_id(pk)
        if permission is None:
            return Response({"detail": "Permission not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PermissionDetailSerializer(permission).data)

    def partial_update(self, request, pk=None):
        serializer = PermissionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            permission = update_permission(permission_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PermissionDetailSerializer(permission).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            permission = deactivate_permission(permission_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PermissionDetailSerializer(permission).data)
