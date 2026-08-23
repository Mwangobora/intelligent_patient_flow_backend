from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.practitioners._helpers import translate_domain_error
from apps.practitioners.models import Practitioner, PractitionerFacilityAssignment
from apps.practitioners.selectors import get_practitioner_by_id, list_practitioners
from apps.practitioners.serializers import PractitionerCreateSerializer, PractitionerDetailSerializer, PractitionerListSerializer, PractitionerUpdateSerializer
from apps.practitioners.services import create_practitioner, deactivate_practitioner, reactivate_practitioner, update_practitioner

from .base import PRACTITIONER_DOCS_TAG, PractitionersBaseViewSet, _bool_query_param


@extend_schema(tags=[PRACTITIONER_DOCS_TAG])
class PractitionerViewSet(PractitionersBaseViewSet):
    queryset = Practitioner.objects.all()
    serializer_class = PractitionerDetailSerializer
    permission_map = {
        "list": "practitioners_practitioner.view",
        "retrieve": "practitioners_practitioner.view",
        "create": "practitioners_practitioner.create",
        "partial_update": "practitioners_practitioner.update",
        "deactivate": "practitioners_practitioner.deactivate",
        "reactivate": "practitioners_practitioner.deactivate",
    }

    def _resolve_practitioner_facility_scope(self, request, practitioner):
        requested_facility_id = request.data.get("facility_id") or request.query_params.get("facility_id")
        if requested_facility_id:
            return requested_facility_id
        assignment = (
            PractitionerFacilityAssignment.objects.filter(
                practitioner=practitioner,
                is_active=True,
                facility__organization_id=practitioner.organization_id,
            )
            .order_by("-is_primary", "created_at")
            .first()
        )
        return assignment.facility_id if assignment else None

    def get_serializer_class(self):
        return {
            "list": PractitionerListSerializer,
            "retrieve": PractitionerDetailSerializer,
            "create": PractitionerCreateSerializer,
            "partial_update": PractitionerUpdateSerializer,
        }.get(self.action, PractitionerDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            return request.data.get("organization_id"), request.data.get("facility_id")
        if self.action in {"retrieve", "partial_update", "deactivate", "reactivate"}:
            practitioner = get_practitioner_by_id(self.kwargs.get("pk"))
            if practitioner is None:
                return None, None
            return practitioner.organization_id, self._resolve_practitioner_facility_scope(request, practitioner)
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_practitioners(
            organization_id=request.query_params.get("organization_id"),
            facility_id=request.query_params.get("facility_id"),
            practitioner_type_id=request.query_params.get("practitioner_type_id"),
            user_id=request.query_params.get("user_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(PractitionerListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = PractitionerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        practitioner_data = dict(serializer.validated_data)
        practitioner_data.pop("facility_id", None)
        try:
            practitioner = create_practitioner(**practitioner_data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerDetailSerializer(practitioner).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        practitioner = get_practitioner_by_id(pk)
        if practitioner is None:
            return Response({"detail": "Practitioner not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PractitionerDetailSerializer(practitioner).data)

    def partial_update(self, request, pk=None):
        serializer = PractitionerUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        practitioner_data = dict(serializer.validated_data)
        practitioner_data.pop("facility_id", None)
        try:
            practitioner = update_practitioner(practitioner_id=pk, **practitioner_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerDetailSerializer(practitioner).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            practitioner = deactivate_practitioner(practitioner_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerDetailSerializer(practitioner).data)

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, pk=None):
        try:
            practitioner = reactivate_practitioner(practitioner_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerDetailSerializer(practitioner).data)
