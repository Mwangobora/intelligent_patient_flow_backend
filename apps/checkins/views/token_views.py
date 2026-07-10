from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.checkins._helpers import translate_domain_error
from apps.checkins.models import CheckinToken
from apps.checkins.selectors import get_checkin_token_by_id, list_checkin_tokens
from apps.checkins.serializers import (
    CheckinOutputSerializer,
    CheckinTokenSafeOutputSerializer,
    ConsumeCheckinTokenInputSerializer,
    IssueCheckinTokenInputSerializer,
    RevokeCheckinTokenInputSerializer,
)
from apps.checkins.services import consume_checkin_token, issue_checkin_token, revoke_checkin_token
from apps.scheduling.models import Appointment

from .base import CHECKIN_DOCS_TAG, CheckinsBaseViewSet


@extend_schema(tags=[CHECKIN_DOCS_TAG])
class CheckinTokenViewSet(CheckinsBaseViewSet):
    queryset = CheckinToken.objects.all()
    serializer_class = CheckinTokenSafeOutputSerializer
    permission_map = {
        "list": "checkins_token.create",
        "retrieve": "checkins_token.create",
        "issue": "checkins_token.create",
        "consume": "checkins_token.consume",
        "revoke": "checkins_token.revoke",
    }

    def get_permission_scope(self, request):
        if self.action == "issue":
            appointment = Appointment.objects.select_related("facility").filter(pk=request.data.get("appointment_id")).first()
            if appointment is None:
                return None, None
            return appointment.facility.organization_id, appointment.facility_id
        if self.action in {"retrieve", "revoke"}:
            token = get_checkin_token_by_id(self.kwargs.get("pk"))
            if token is None:
                return None, None
            return token.appointment.facility.organization_id, token.appointment.facility_id
        if self.action == "list":
            appointment_id = request.query_params.get("appointment_id")
            if appointment_id:
                appointment = Appointment.objects.select_related("facility").filter(pk=appointment_id).first()
                if appointment is not None:
                    return appointment.facility.organization_id, appointment.facility_id
            return request.query_params.get("organization_id"), request.query_params.get("facility_id")
        return None, None

    def list(self, request):
        queryset = list_checkin_tokens(
            appointment_id=request.query_params.get("appointment_id"),
            only_active=request.query_params.get("only_active", "false").lower() == "true",
        )
        return Response(CheckinTokenSafeOutputSerializer(queryset, many=True).data)

    def retrieve(self, request, pk=None):
        token = get_checkin_token_by_id(pk)
        if token is None:
            return Response({"detail": "Check-in token not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CheckinTokenSafeOutputSerializer(token).data)

    @action(detail=False, methods=["post"], url_path="issue")
    def issue(self, request):
        serializer = IssueCheckinTokenInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            issued = issue_checkin_token(**serializer.validated_data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        payload = CheckinTokenSafeOutputSerializer(issued.token).data
        payload["raw_token"] = issued.raw_token
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="consume")
    def consume(self, request):
        serializer = ConsumeCheckinTokenInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = dict(serializer.validated_data)
        payload.setdefault("checked_in_by_id", request.user.id)
        try:
            checkin = consume_checkin_token(**payload)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(CheckinOutputSerializer(checkin).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        serializer = RevokeCheckinTokenInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = revoke_checkin_token(token_id=pk, revoked_by_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(CheckinTokenSafeOutputSerializer(token).data)
