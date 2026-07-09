from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.practitioners._helpers import translate_domain_error
from apps.practitioners.models import PractitionerCredentialType, PractitionerType
from apps.practitioners.selectors import (
    get_practitioner_credential_type_by_id,
    get_practitioner_type_by_id,
    list_practitioner_credential_types,
    list_practitioner_types,
)
from apps.practitioners.serializers import (
    PractitionerCredentialTypeCreateSerializer,
    PractitionerCredentialTypeDetailSerializer,
    PractitionerCredentialTypeListSerializer,
    PractitionerCredentialTypeUpdateSerializer,
    PractitionerTypeCreateSerializer,
    PractitionerTypeDetailSerializer,
    PractitionerTypeListSerializer,
    PractitionerTypeUpdateSerializer,
)
from apps.practitioners.services import (
    create_practitioner_credential_type,
    create_practitioner_type,
    deactivate_practitioner_credential_type,
    deactivate_practitioner_type,
    update_practitioner_credential_type,
    update_practitioner_type,
)

from .base import PRACTITIONER_DOCS_TAG, PractitionersBaseViewSet, _bool_query_param


@extend_schema(tags=[PRACTITIONER_DOCS_TAG])
class PractitionerTypeViewSet(PractitionersBaseViewSet):
    queryset = PractitionerType.objects.all()
    serializer_class = PractitionerTypeDetailSerializer
    permission_map = {
        "list": "practitioners_type.view",
        "retrieve": "practitioners_type.view",
        "create": "practitioners_type.manage",
        "partial_update": "practitioners_type.manage",
        "deactivate": "practitioners_type.manage",
    }

    def get_serializer_class(self):
        return {
            "list": PractitionerTypeListSerializer,
            "retrieve": PractitionerTypeDetailSerializer,
            "create": PractitionerTypeCreateSerializer,
            "partial_update": PractitionerTypeUpdateSerializer,
        }.get(self.action, PractitionerTypeDetailSerializer)

    def list(self, request):
        queryset = list_practitioner_types(
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(PractitionerTypeListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = PractitionerTypeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            practitioner_type = create_practitioner_type(**serializer.validated_data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerTypeDetailSerializer(practitioner_type).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        practitioner_type = get_practitioner_type_by_id(pk)
        if practitioner_type is None:
            return Response({"detail": "Practitioner type not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PractitionerTypeDetailSerializer(practitioner_type).data)

    def partial_update(self, request, pk=None):
        serializer = PractitionerTypeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        regenerate_code = data.pop("regenerate_code", False)
        try:
            practitioner_type = update_practitioner_type(practitioner_type_id=pk, regenerate_code=regenerate_code, **data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerTypeDetailSerializer(practitioner_type).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            practitioner_type = deactivate_practitioner_type(practitioner_type_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerTypeDetailSerializer(practitioner_type).data)


@extend_schema(tags=[PRACTITIONER_DOCS_TAG])
class PractitionerCredentialTypeViewSet(PractitionersBaseViewSet):
    queryset = PractitionerCredentialType.objects.all()
    serializer_class = PractitionerCredentialTypeDetailSerializer
    permission_map = {action: "practitioners_credential_type.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {
            "list": PractitionerCredentialTypeListSerializer,
            "retrieve": PractitionerCredentialTypeDetailSerializer,
            "create": PractitionerCredentialTypeCreateSerializer,
            "partial_update": PractitionerCredentialTypeUpdateSerializer,
        }.get(self.action, PractitionerCredentialTypeDetailSerializer)

    def get_permission_scope(self, request):
        if self.action in {"create", "list"}:
            return request.data.get("organization_id") if self.action == "create" else request.query_params.get("organization_id"), None
        credential_type = get_practitioner_credential_type_by_id(self.kwargs.get("pk"))
        if credential_type is None:
            return None, None
        return credential_type.organization_id, None

    def list(self, request):
        include_global = request.query_params.get("include_global", "true").lower() != "false"
        queryset = list_practitioner_credential_types(
            organization_id=request.query_params.get("organization_id"),
            include_global=include_global,
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(PractitionerCredentialTypeListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = PractitionerCredentialTypeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            credential_type = create_practitioner_credential_type(**serializer.validated_data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerCredentialTypeDetailSerializer(credential_type).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        credential_type = get_practitioner_credential_type_by_id(pk)
        if credential_type is None:
            return Response({"detail": "Practitioner credential type not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PractitionerCredentialTypeDetailSerializer(credential_type).data)

    def partial_update(self, request, pk=None):
        serializer = PractitionerCredentialTypeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        regenerate_code = data.pop("regenerate_code", False)
        try:
            credential_type = update_practitioner_credential_type(credential_type_id=pk, regenerate_code=regenerate_code, **data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerCredentialTypeDetailSerializer(credential_type).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            credential_type = deactivate_practitioner_credential_type(credential_type_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerCredentialTypeDetailSerializer(credential_type).data)
