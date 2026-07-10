from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.scheduling._helpers import translate_domain_error
from apps.scheduling.models import AppointmentSlot
from apps.scheduling.selectors import get_appointment_slot_by_id, list_appointment_slots
from apps.scheduling.serializers import AppointmentSlotCreateSerializer, AppointmentSlotDetailSerializer
from apps.scheduling.services._shared import get_shift
from apps.scheduling.services import block_appointment_slot, cancel_appointment_slot, create_appointment_slot, unblock_appointment_slot

from .base import SCHEDULING_DOCS_TAG, SchedulingBaseViewSet, _bool_query_param


@extend_schema(tags=[SCHEDULING_DOCS_TAG])
class AppointmentSlotViewSet(SchedulingBaseViewSet):
    queryset = AppointmentSlot.objects.all()
    serializer_class = AppointmentSlotDetailSerializer
    permission_map = {action: "scheduling_slot.manage" for action in ["list", "retrieve", "create", "block", "unblock", "cancel"]}

    def get_serializer_class(self):
        return {"create": AppointmentSlotCreateSerializer}.get(self.action, AppointmentSlotDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            shift_id = request.data.get("practitioner_shift_id")
            if not shift_id:
                return None, None
            shift = get_shift(shift_id)
            return shift.practitioner_facility_assignment.practitioner.organization_id, shift.practitioner_facility_assignment.facility_id
        slot = get_appointment_slot_by_id(self.kwargs.get("pk")) if self.action in {"retrieve", "block", "unblock", "cancel"} else None
        if slot is not None:
            return slot.practitioner_shift.practitioner_facility_assignment.practitioner.organization_id, slot.practitioner_shift.practitioner_facility_assignment.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_appointment_slots(
            practitioner_shift_id=request.query_params.get("practitioner_shift_id"),
            facility_id=request.query_params.get("facility_id"),
            practitioner_id=request.query_params.get("practitioner_id"),
            facility_specialty_id=request.query_params.get("facility_specialty_id"),
            starts_from=request.query_params.get("starts_from"),
            ends_to=request.query_params.get("ends_to"),
            status=request.query_params.get("status"),
            only_available=request.query_params.get("only_available", "true").lower() != "false",
        )
        return Response(AppointmentSlotDetailSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = AppointmentSlotCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            slot = create_appointment_slot(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AppointmentSlotDetailSerializer(slot).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        slot = get_appointment_slot_by_id(pk)
        if slot is None:
            return Response({"detail": "Appointment slot not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AppointmentSlotDetailSerializer(slot).data)

    @action(detail=True, methods=["post"], url_path="block")
    def block(self, request, pk=None):
        try:
            slot = block_appointment_slot(slot_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AppointmentSlotDetailSerializer(slot).data)

    @action(detail=True, methods=["post"], url_path="unblock")
    def unblock(self, request, pk=None):
        try:
            slot = unblock_appointment_slot(slot_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AppointmentSlotDetailSerializer(slot).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        try:
            slot = cancel_appointment_slot(slot_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AppointmentSlotDetailSerializer(slot).data)
