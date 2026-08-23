from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import UserMembership
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
from apps.accounts.services import (
    activate_user,
    create_facility_membership,
    create_organization_membership,
    create_user,
    deactivate_user,
    update_user,
    verify_email,
    verify_phone,
)

from ._helpers import translate_domain_error


def _bool_query_param(value):
    if value is None:
        return None
    return value == "true"


def _active_memberships_for_user(user):
    now = timezone.now()
    return UserMembership.objects.filter(
        user=user,
        is_active=True,
        starts_at__lte=now,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))


def _default_user_scope(user):
    membership = _active_memberships_for_user(user).filter(facility__isnull=False).order_by("-starts_at").first()
    if membership is None:
        membership = _active_memberships_for_user(user).order_by("-starts_at").first()
    if membership is None:
        return None, None
    return membership.organization_id, membership.facility_id


def _request_scope(request, source):
    organization_id = source.get("organization_id")
    facility_id = source.get("facility_id")
    if request.user.is_superuser or organization_id or facility_id:
        return organization_id, facility_id
    return _default_user_scope(request.user)


def _apply_scope_to_created_user(*, user, organization_id=None, facility_id=None, created_by_id=None):
    if not organization_id:
        return
    if facility_id:
        create_facility_membership(
            user_id=user.id,
            organization_id=organization_id,
            facility_id=facility_id,
            created_by_id=created_by_id,
        )
        return
    create_organization_membership(
        user_id=user.id,
        organization_id=organization_id,
        created_by_id=created_by_id,
    )


def _user_visible_in_scope(*, actor, target, organization_id=None, facility_id=None):
    if actor.is_superuser or actor.pk == target.pk:
        return True
    if not organization_id and not facility_id:
        return False

    memberships = _active_memberships_for_user(target)
    if facility_id:
        return memberships.filter(facility_id=facility_id).exists()
    return memberships.filter(organization_id=organization_id).exists()


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

    def get_permission_scope(self, request):
        if self.action in {"list", "retrieve"}:
            return _request_scope(request, request.query_params)
        return _request_scope(request, request.data)

    def list(self, request):
        organization_id, facility_id = _request_scope(request, request.query_params)
        queryset = list_users(
            organization_id=organization_id,
            facility_id=facility_id,
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(UserListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_data = dict(serializer.validated_data)
        organization_id = user_data.pop("organization_id", None)
        facility_id = user_data.pop("facility_id", None)
        if not request.user.is_superuser and not organization_id and not facility_id:
            organization_id, facility_id = _default_user_scope(request.user)
        try:
            with transaction.atomic():
                user = create_user(**user_data)
                _apply_scope_to_created_user(
                    user=user,
                    organization_id=organization_id,
                    facility_id=facility_id,
                    created_by_id=request.user.id,
                )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(UserDetailSerializer(get_user_by_id(user.id)).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        organization_id, facility_id = _request_scope(request, request.query_params)
        user = get_user_by_id(pk)
        if user is None:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _user_visible_in_scope(actor=request.user, target=user, organization_id=organization_id, facility_id=facility_id):
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserDetailSerializer(user).data)

    def partial_update(self, request, pk=None):
        organization_id, facility_id = _request_scope(request, request.data)
        user = get_user_by_id(pk)
        if user is None:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _user_visible_in_scope(actor=request.user, target=user, organization_id=organization_id, facility_id=facility_id):
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = UserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            user = update_user(user_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(UserDetailSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        organization_id, facility_id = _request_scope(request, request.data)
        user = get_user_by_id(pk)
        if user is None or not _user_visible_in_scope(actor=request.user, target=user, organization_id=organization_id, facility_id=facility_id):
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            user = activate_user(user_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(UserDetailSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        organization_id, facility_id = _request_scope(request, request.data)
        user = get_user_by_id(pk)
        if user is None or not _user_visible_in_scope(actor=request.user, target=user, organization_id=organization_id, facility_id=facility_id):
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            user = deactivate_user(user_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(UserDetailSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="verify-email")
    def verify_email(self, request, pk=None):
        organization_id, facility_id = _request_scope(request, request.data)
        user = get_user_by_id(pk)
        if user is None or not _user_visible_in_scope(actor=request.user, target=user, organization_id=organization_id, facility_id=facility_id):
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            user = verify_email(user_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(UserDetailSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="verify-phone")
    def verify_phone(self, request, pk=None):
        organization_id, facility_id = _request_scope(request, request.data)
        user = get_user_by_id(pk)
        if user is None or not _user_visible_in_scope(actor=request.user, target=user, organization_id=organization_id, facility_id=facility_id):
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
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

    def get_permission_scope(self, request):
        return _request_scope(request, request.query_params)

    def list(self, request, user_pk=None):
        organization_id, facility_id = _request_scope(request, request.query_params)
        user = get_user_by_id(user_pk)
        if user is None or not _user_visible_in_scope(actor=request.user, target=user, organization_id=organization_id, facility_id=facility_id):
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        memberships = get_user_memberships(
            user_id=user_pk,
            organization_id=organization_id,
            facility_id=facility_id,
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(MembershipSummarySerializer(memberships, many=True).data)


@extend_schema(tags=["User Management APIs"])
class UserRoleAssignmentReadOnlyViewSet(viewsets.ViewSet):
    serializer_class = RoleAssignmentSummarySerializer

    def get_permissions(self):
        self.required_permission = "accounts_user.view"
        return [HasSystemPermission()]

    def get_permission_scope(self, request):
        return _request_scope(request, request.query_params)

    def list(self, request, user_pk=None):
        organization_id, facility_id = _request_scope(request, request.query_params)
        user = get_user_by_id(user_pk)
        if user is None or not _user_visible_in_scope(actor=request.user, target=user, organization_id=organization_id, facility_id=facility_id):
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        assignments = get_user_role_assignments(
            user_id=user_pk,
            organization_id=organization_id,
            facility_id=facility_id,
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(RoleAssignmentSummarySerializer(assignments, many=True).data)
