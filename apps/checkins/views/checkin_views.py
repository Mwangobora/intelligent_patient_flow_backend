from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.checkins._helpers import translate_domain_error
from apps.checkins.models import PatientCheckin
from apps.checkins.selectors import get_checkin_by_id, list_checkins
from apps.checkins.serializers import (
    AppointmentCheckinInputSerializer,
    CheckinOutputSerializer,
    VoidCheckinInputSerializer,
    WalkinCheckinInputSerializer,
)
from apps.checkins.services import create_appointment_checkin, create_walkin_checkin, void_checkin
from apps.scheduling.models import Appointment

from .base import CHECKIN_DOCS_TAG, CheckinsBaseViewSet, _bool_query_param


@extend_schema(tags=[CHECKIN_DOCS_TAG])
class CheckinViewSet(CheckinsBaseViewSet):
    queryset = PatientCheckin.objects.all()
    serializer_class = CheckinOutputSerializer
    permission_map = {
        "list": "checkins_checkin.view",
        "retrieve": "checkins_checkin.view",
        "appointment": "checkins_checkin.create",
        "walk_in": "checkins_checkin.create",
        "void": "checkins_checkin.void",
    }

    def get_permission_scope(self, request):
        if self.action == "appointment":
            appointment = Appointment.objects.select_related("facility").filter(pk=request.data.get("appointment_id")).first()
            if appointment is not None:
                return appointment.facility.organization_id, appointment.facility_id
            return None, request.data.get("facility_id")
        if self.action == "walk_in":
            return None, request.data.get("facility_id")
        if self.action in {"retrieve", "void"}:
            checkin = get_checkin_by_id(self.kwargs.get("pk"))
            if checkin is None:
                return None, None
            return checkin.facility.organization_id, checkin.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_checkins(
            facility_id=request.query_params.get("facility_id"),
            patient_id=request.query_params.get("patient_id"),
            appointment_id=request.query_params.get("appointment_id"),
            checked_in_from=request.query_params.get("checked_in_from"),
            checked_in_to=request.query_params.get("checked_in_to"),
            is_voided=_bool_query_param(request.query_params.get("is_voided")),
        )
        return Response(CheckinOutputSerializer(queryset, many=True).data)

    def retrieve(self, request, pk=None):
        checkin = get_checkin_by_id(pk)
        if checkin is None:
            return Response({"detail": "Check-in not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CheckinOutputSerializer(checkin).data)

    @action(detail=False, methods=["post"], url_path="appointment")
    def appointment(self, request):
        serializer = AppointmentCheckinInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            checkin = create_appointment_checkin(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(CheckinOutputSerializer(checkin).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="walk-in")
    def walk_in(self, request):
        serializer = WalkinCheckinInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            checkin = create_walkin_checkin(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(CheckinOutputSerializer(checkin).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="void")
    def void(self, request, pk=None):
        serializer = VoidCheckinInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            checkin = void_checkin(checkin_id=pk, voided_by_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(CheckinOutputSerializer(checkin).data)
