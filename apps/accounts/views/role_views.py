from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.accounts.models import UserMembership, UserRoleAssignment
from apps.accounts.permissions import HasSystemPermission, user_has_permission
from apps.accounts.selectors import get_permission_by_id, get_role_by_id, list_roles
from apps.accounts.serializers import (
    EndMembershipSerializer,
    FacilityMembershipCreateSerializer,
    MembershipSummarySerializer,
    OrganizationMembershipCreateSerializer,
    RoleAssignmentCreateSerializer,
    RoleAssignmentReactivateSerializer,
    RoleAssignmentSummarySerializer,
    RoleCreateSerializer,
    RoleDetailSerializer,
    RoleListSerializer,
    RolePermissionActionSerializer,
    RoleUpdateSerializer,
)
from apps.accounts.services import (
    assign_role_to_user,
    create_facility_membership,
    create_organization_membership,
    create_role,
    deactivate_membership,
    deactivate_role,
    end_membership,
    grant_permission_to_role,
    reactivate_membership,
    reactivate_role_assignment,
    revoke_permission_from_role,
    revoke_role_from_user,
    update_role,
)

from ._helpers import translate_domain_error


def _blank_to_none(value):
    return None if value == "" else value


def _active_memberships_for_user(user):
    now = timezone.now()
    return UserMembership.objects.filter(
        user=user,
        is_active=True,
        starts_at__lte=now,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))


def _default_role_scope(user):
    membership = _active_memberships_for_user(user).filter(facility__isnull=False).order_by("-starts_at").first()
    if membership is None:
        membership = _active_memberships_for_user(user).order_by("-starts_at").first()
    if membership is None:
        return None, None
    return membership.organization_id, membership.facility_id


def _request_role_scope(request, source):
    organization_id = _blank_to_none(source.get("organization_id"))
    facility_id = _blank_to_none(source.get("facility_id"))
    if request.user.is_superuser or organization_id or facility_id:
        return organization_id, facility_id
    return _default_role_scope(request.user)


@extend_schema(tags=["Authorization APIs"])
class RoleViewSet(viewsets.GenericViewSet):
    lookup_url_kwarg = "pk"
    serializer_class = RoleDetailSerializer

    def get_permissions(self):
        permission_map = {
            "list": "accounts_role.view",
            "retrieve": "accounts_role.view",
            "create": "accounts_role.create",
            "partial_update": "accounts_role.update",
            "deactivate": "accounts_role.deactivate",
            "grant_permission": "accounts_role_permission.grant",
            "revoke_permission": "accounts_role_permission.revoke",
        }
        self.required_permission = permission_map[self.action]
        return [HasSystemPermission()]

    def get_permission_scope(self, request):
        if self.action == "list":
            return _request_role_scope(request, request.query_params)
        if self.action == "create":
            return _request_role_scope(request, request.data)

        role = get_role_by_id(self.kwargs.get("pk"))
        if role is None:
            return None, None
        return role.organization_id, role.facility_id

    def list(self, request):
        organization_id, facility_id = _request_role_scope(request, request.query_params)
        queryset = list_roles(
            organization_id=organization_id,
            facility_id=facility_id,
            is_active=None if request.query_params.get("is_active") is None else request.query_params.get("is_active") == "true",
            search=request.query_params.get("search"),
        )
        return Response(RoleListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = RoleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role_data = dict(serializer.validated_data)
        if not request.user.is_superuser and not role_data.get("organization_id") and not role_data.get("facility_id"):
            organization_id, facility_id = _default_role_scope(request.user)
            role_data["organization_id"] = organization_id
            role_data["facility_id"] = facility_id
        try:
            role = create_role(**role_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(RoleDetailSerializer(role).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        role = get_role_by_id(pk)
        if role is None:
            return Response({"detail": "Role not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(RoleDetailSerializer(role).data)

    def partial_update(self, request, pk=None):
        serializer = RoleUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            role = update_role(role_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(RoleDetailSerializer(role).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            role = deactivate_role(role_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(RoleDetailSerializer(role).data)

    @action(detail=True, methods=["post"], url_path="grant-permission")
    def grant_permission(self, request, pk=None):
        serializer = RolePermissionActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = get_role_by_id(pk)
        permission = get_permission_by_id(serializer.validated_data["permission_id"])
        if role is None or permission is None:
            return Response({"detail": "Role or permission not found."}, status=status.HTTP_404_NOT_FOUND)
        if not request.user.is_superuser and not user_has_permission(
            request.user,
            permission.code,
            organization=role.organization_id,
            facility=role.facility_id,
        ):
            raise PermissionDenied("You can only grant permissions you already have in this scope.")
        try:
            role_permission = grant_permission_to_role(
                role_id=pk,
                permission_id=serializer.validated_data["permission_id"],
                granted_by_id=request.user.id,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(
            {
                "id": str(role_permission.id),
                "role": str(role_permission.role_id),
                "permission": str(role_permission.permission_id),
                "is_active": role_permission.is_active,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="revoke-permission")
    def revoke_permission(self, request, pk=None):
        serializer = RolePermissionActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            role_permission = revoke_permission_from_role(
                role_id=pk,
                permission_id=serializer.validated_data["permission_id"],
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(
            {
                "id": str(role_permission.id),
                "role": str(role_permission.role_id),
                "permission": str(role_permission.permission_id),
                "is_active": role_permission.is_active,
            }
        )


@extend_schema(tags=["Authorization APIs"])
class MembershipViewSet(viewsets.GenericViewSet):
    serializer_class = MembershipSummarySerializer

    def get_permissions(self):
        permission_map = {
            "organization": "accounts_membership.create",
            "facility": "accounts_membership.create",
            "deactivate": "accounts_membership.deactivate",
            "reactivate": "accounts_membership.reactivate",
            "end": "accounts_membership.end",
        }
        self.required_permission = permission_map[self.action]
        return [HasSystemPermission()]

    def get_permission_scope(self, request):
        if self.action == "organization":
            return request.data.get("organization_id"), None
        if self.action == "facility":
            return request.data.get("organization_id"), request.data.get("facility_id")

        membership = UserMembership.objects.select_related("organization", "facility").filter(pk=self.kwargs.get("pk")).first()
        if membership is None:
            return None, None
        return membership.organization_id, membership.facility_id

    @action(detail=False, methods=["post"], url_path="organization")
    def organization(self, request):
        serializer = OrganizationMembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = create_organization_membership(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(MembershipSummarySerializer(membership).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="facility")
    def facility(self, request):
        serializer = FacilityMembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = create_facility_membership(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(MembershipSummarySerializer(membership).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            membership = deactivate_membership(membership_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(MembershipSummarySerializer(membership).data)

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        try:
            membership = reactivate_membership(membership_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(MembershipSummarySerializer(membership).data)

    @action(detail=True, methods=["post"], url_path="end")
    def end(self, request, pk=None):
        serializer = EndMembershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            membership = end_membership(membership_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(MembershipSummarySerializer(membership).data)


@extend_schema(tags=["Authorization APIs"])
class RoleAssignmentViewSet(viewsets.GenericViewSet):
    serializer_class = RoleAssignmentSummarySerializer

    def get_permissions(self):
        permission_map = {
            "create": "accounts_role_assignment.create",
            "revoke": "accounts_role_assignment.revoke",
            "reactivate": "accounts_role_assignment.reactivate",
        }
        self.required_permission = permission_map[self.action]
        return [HasSystemPermission()]

    def get_permission_scope(self, request):
        if self.action == "create":
            role = get_role_by_id(request.data.get("role_id"))
        else:
            assignment = UserRoleAssignment.objects.select_related("role").filter(pk=self.kwargs.get("pk")).first()
            role = assignment.role if assignment is not None else None

        if role is None:
            return None, None
        return role.organization_id, role.facility_id

    def create(self, request):
        serializer = RoleAssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = assign_role_to_user(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(RoleAssignmentSummarySerializer(assignment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        assignment = UserRoleAssignment.objects.filter(pk=pk).first()
        if assignment is None:
            return Response({"detail": "User role assignment not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            assignment = revoke_role_from_user(user_id=assignment.user_id, role_id=assignment.role_id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(RoleAssignmentSummarySerializer(assignment).data)

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        serializer = RoleAssignmentReactivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = UserRoleAssignment.objects.filter(pk=pk).first()
        if assignment is None:
            return Response({"detail": "User role assignment not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            assignment = reactivate_role_assignment(
                user_id=assignment.user_id,
                role_id=assignment.role_id,
                **serializer.validated_data,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(RoleAssignmentSummarySerializer(assignment).data)
