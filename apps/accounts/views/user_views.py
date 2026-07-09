from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import HasSystemPermission
from apps.accounts.selectors import get_user_by_id, get_user_memberships, get_user_role_assignments, list_users
from apps.accounts.serializers import (
    MembershipSummarySerializer,
    RoleAssignmentSummarySerializer,
    UserCreateSerializer,
    UserDetailSerializer,
    UserListSerializer,
    UserUpdateSerializer,
)
from apps.accounts.services import activate_user, create_user, deactivate_user, update_user, verify_email, verify_phone

from ._helpers import translate_domain_error


@extend_schema(tags=["User Management APIs"])
class UserViewSet(viewsets.GenericViewSet):
    lookup_url_kwarg = "pk"
    serializer_class = UserDetailSerializer

    def get_permissions(self):
        permission_map = {
            "list": "accounts_user.view",
            "retrieve": "accounts_user.view",
            "create": "accounts_user.create",
            "partial_update": "accounts_user.update",
            "activate": "accounts_user.activate",
            "deactivate": "accounts_user.deactivate",
            "verify_email": "accounts_user.verify_email",
            "verify_phone": "accounts_user.verify_phone",
        }
        self.required_permission = permission_map[self.action]
        return [HasSystemPermission()]

    def list(self, request):
        queryset = list_users(
            organization_id=request.query_params.get("organization_id"),
            facility_id=request.query_params.get("facility_id"),
            is_active=None if request.query_params.get("is_active") is None else request.query_params.get("is_active") == "true",
            search=request.query_params.get("search"),
        )
        return Response(UserListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = create_user(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(UserDetailSerializer(user).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        user = get_user_by_id(pk)
        if user is None:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserDetailSerializer(user).data)

    def partial_update(self, request, pk=None):
        serializer = UserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            user = update_user(user_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(UserDetailSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        try:
            user = activate_user(user_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(UserDetailSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            user = deactivate_user(user_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(UserDetailSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="verify-email")
    def verify_email(self, request, pk=None):
        try:
            user = verify_email(user_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(UserDetailSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="verify-phone")
    def verify_phone(self, request, pk=None):
        try:
            user = verify_phone(user_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(UserDetailSerializer(user).data)


@extend_schema(tags=["User Management APIs"])
class UserMembershipReadOnlyViewSet(viewsets.ViewSet):
    serializer_class = MembershipSummarySerializer

    def get_permissions(self):
        self.required_permission = "accounts_user.view"
        return [HasSystemPermission()]

    def list(self, request, user_pk=None):
        memberships = get_user_memberships(
            user_id=user_pk,
            organization_id=request.query_params.get("organization_id"),
            facility_id=request.query_params.get("facility_id"),
            is_active=None if request.query_params.get("is_active") is None else request.query_params.get("is_active") == "true",
        )
        return Response(MembershipSummarySerializer(memberships, many=True).data)


@extend_schema(tags=["User Management APIs"])
class UserRoleAssignmentReadOnlyViewSet(viewsets.ViewSet):
    serializer_class = RoleAssignmentSummarySerializer

    def get_permissions(self):
        self.required_permission = "accounts_user.view"
        return [HasSystemPermission()]

    def list(self, request, user_pk=None):
        assignments = get_user_role_assignments(
            user_id=user_pk,
            organization_id=request.query_params.get("organization_id"),
            facility_id=request.query_params.get("facility_id"),
            is_active=None if request.query_params.get("is_active") is None else request.query_params.get("is_active") == "true",
        )
        return Response(RoleAssignmentSummarySerializer(assignments, many=True).data)
