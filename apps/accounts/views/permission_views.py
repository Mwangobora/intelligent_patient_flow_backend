from __future__ import annotations

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import HasSystemPermission, user_has_permission
from apps.accounts.selectors.permission_selectors import get_user_effective_permissions
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
        if self.action == "list":
            self.required_permissions_any = ["accounts_permission.view", "accounts_role_permission.grant"]
        else:
            self.required_permission = permission_map[self.action]
        return [HasSystemPermission()]

    def list(self, request):
        is_active = None if request.query_params.get("is_active") is None else request.query_params.get("is_active") == "true"
        if request.user.is_superuser or user_has_permission(request.user, "accounts_permission.view"):
            queryset = list_permissions(
                module=request.query_params.get("module"),
                is_active=is_active,
                search=request.query_params.get("search"),
            )
        else:
            queryset = get_user_effective_permissions(user=request.user)
            if request.query_params.get("module"):
                queryset = queryset.filter(module=request.query_params.get("module"))
            if is_active is not None:
                queryset = queryset.filter(is_active=is_active)
            if request.query_params.get("search"):
                search = request.query_params.get("search")
                queryset = queryset.filter(
                    Q(name__icontains=search)
                    | Q(code__icontains=search)
                    | Q(module__icontains=search)
                    | Q(action__icontains=search)
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
