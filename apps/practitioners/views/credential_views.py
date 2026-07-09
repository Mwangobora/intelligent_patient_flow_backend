from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.practitioners._helpers import translate_domain_error
from apps.practitioners.models import PractitionerCredential
from apps.practitioners.selectors import (
    get_practitioner_by_id,
    get_practitioner_credential_by_id,
    list_practitioner_credentials,
)
from apps.practitioners.serializers import (
    PractitionerCredentialCreateSerializer,
    PractitionerCredentialDetailSerializer,
    PractitionerCredentialUpdateSerializer,
)
from apps.practitioners.services import (
    add_practitioner_credential,
    deactivate_practitioner_credential,
    reject_practitioner_credential,
    update_practitioner_credential,
    verify_practitioner_credential,
)

from .base import PRACTITIONER_DOCS_TAG, PractitionersBaseViewSet, _bool_query_param


@extend_schema(tags=[PRACTITIONER_DOCS_TAG])
class PractitionerCredentialViewSet(PractitionersBaseViewSet):
    queryset = PractitionerCredential.objects.all()
    serializer_class = PractitionerCredentialDetailSerializer
    permission_map = {
        "list": "practitioners_credential.manage",
        "retrieve": "practitioners_credential.manage",
        "create": "practitioners_credential.manage",
        "partial_update": "practitioners_credential.manage",
        "deactivate": "practitioners_credential.manage",
        "verify": "practitioners_credential.verify",
        "reject": "practitioners_credential.verify",
    }

    def get_serializer_class(self):
        return {
            "create": PractitionerCredentialCreateSerializer,
            "partial_update": PractitionerCredentialUpdateSerializer,
        }.get(self.action, PractitionerCredentialDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            practitioner = get_practitioner_by_id(self.kwargs.get("practitioner_pk") or request.data.get("practitioner_id"))
            if practitioner is None:
                return None, None
            return practitioner.organization_id, None
        if self.action in {"retrieve", "partial_update", "deactivate", "verify", "reject"}:
            credential = get_practitioner_credential_by_id(self.kwargs.get("pk"))
            if credential is None:
                return None, None
            return credential.practitioner.organization_id, None
        practitioner = get_practitioner_by_id(self.kwargs.get("practitioner_pk") or request.query_params.get("practitioner_id"))
        if practitioner is not None:
            return practitioner.organization_id, None
        return request.query_params.get("organization_id"), None

    def list(self, request, practitioner_pk=None):
        queryset = list_practitioner_credentials(
            practitioner_id=practitioner_pk or request.query_params.get("practitioner_id"),
            credential_type_id=request.query_params.get("credential_type_id"),
            organization_id=request.query_params.get("organization_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(PractitionerCredentialDetailSerializer(queryset, many=True).data)

    def create(self, request, practitioner_pk=None):
        serializer = PractitionerCredentialCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        practitioner_id = practitioner_pk or data.pop("practitioner_id", None)
        if practitioner_id is None:
            return Response({"detail": "practitioner_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            credential = add_practitioner_credential(practitioner_id=practitioner_id, **data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerCredentialDetailSerializer(credential).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        credential = get_practitioner_credential_by_id(pk)
        if credential is None:
            return Response({"detail": "Practitioner credential not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PractitionerCredentialDetailSerializer(credential).data)

    def partial_update(self, request, pk=None):
        serializer = PractitionerCredentialUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            credential = update_practitioner_credential(credential_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerCredentialDetailSerializer(credential).data)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        try:
            credential = verify_practitioner_credential(credential_id=pk, verified_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerCredentialDetailSerializer(credential).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        try:
            credential = reject_practitioner_credential(credential_id=pk, verified_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerCredentialDetailSerializer(credential).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            credential = deactivate_practitioner_credential(credential_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerCredentialDetailSerializer(credential).data)
