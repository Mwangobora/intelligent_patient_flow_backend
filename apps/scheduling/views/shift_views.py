from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.scheduling._helpers import translate_domain_error
from apps.scheduling.models import PractitionerShift
from apps.scheduling.selectors import get_shift_by_id, list_shifts
from apps.scheduling.services._shared import get_practitioner_facility_assignment
from apps.scheduling.serializers import (
    GenerateSlotsSerializer,
    PractitionerShiftCreateSerializer,
    PractitionerShiftDetailSerializer,
    PractitionerShiftUpdateSerializer,
    ShiftCancellationSerializer,
)
from apps.scheduling.services import (
    cancel_practitioner_shift,
    complete_practitioner_shift,
    create_practitioner_shift,
    generate_slots_for_shift,
    start_practitioner_shift,
    update_practitioner_shift,
)

from .base import SCHEDULING_DOCS_TAG, SchedulingBaseViewSet


@extend_schema(tags=[SCHEDULING_DOCS_TAG])
class ShiftViewSet(SchedulingBaseViewSet):
    queryset = PractitionerShift.objects.all()
    serializer_class = PractitionerShiftDetailSerializer
    permission_map = {
        "list": "scheduling_shift.manage",
        "retrieve": "scheduling_shift.manage",
        "create": "scheduling_shift.manage",
        "partial_update": "scheduling_shift.manage",
        "cancel": "scheduling_shift.manage",
        "start": "scheduling_shift.manage",
        "complete": "scheduling_shift.manage",
        "generate_slots": "scheduling_slot.manage",
    }

    def get_serializer_class(self):
        return {
            "create": PractitionerShiftCreateSerializer,
            "partial_update": PractitionerShiftUpdateSerializer,
            "cancel": ShiftCancellationSerializer,
            "generate_slots": GenerateSlotsSerializer,
        }.get(self.action, PractitionerShiftDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            assignment_id = request.data.get("practitioner_facility_assignment_id")
            if not assignment_id:
                return None, None
            assignment = get_practitioner_facility_assignment(assignment_id)
            return assignment.practitioner.organization_id, assignment.facility_id
        shift = get_shift_by_id(self.kwargs.get("pk")) if self.action in {"retrieve", "partial_update", "cancel", "start", "complete", "generate_slots"} else None
        if shift is not None:
            return shift.practitioner_facility_assignment.practitioner.organization_id, shift.practitioner_facility_assignment.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_shifts(
            practitioner_facility_assignment_id=request.query_params.get("practitioner_facility_assignment_id"),
            practitioner_id=request.query_params.get("practitioner_id"),
            facility_id=request.query_params.get("facility_id"),
            department_assignment_id=request.query_params.get("practitioner_department_assignment_id"),
            service_point_id=request.query_params.get("service_point_id"),
            consultation_room_id=request.query_params.get("consultation_room_id"),
            status=request.query_params.get("status"),
            starts_from=request.query_params.get("starts_from"),
            ends_to=request.query_params.get("ends_to"),
        )
        return Response(PractitionerShiftDetailSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = PractitionerShiftCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            shift = create_practitioner_shift(**serializer.validated_data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerShiftDetailSerializer(shift).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        shift = get_shift_by_id(pk)
        if shift is None:
            return Response({"detail": "Shift not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PractitionerShiftDetailSerializer(shift).data)

    def partial_update(self, request, pk=None):
        serializer = PractitionerShiftUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            shift = update_practitioner_shift(shift_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerShiftDetailSerializer(shift).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        serializer = ShiftCancellationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            shift = cancel_practitioner_shift(shift_id=pk, cancelled_by_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerShiftDetailSerializer(shift).data)

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        try:
            shift = start_practitioner_shift(shift_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerShiftDetailSerializer(shift).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        try:
            shift = complete_practitioner_shift(shift_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PractitionerShiftDetailSerializer(shift).data)

    @action(detail=True, methods=["post"], url_path="generate-slots")
    def generate_slots(self, request, pk=None):
        serializer = GenerateSlotsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            slots = generate_slots_for_shift(practitioner_shift_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response({"count": len(slots), "slot_ids": [str(slot.id) for slot in slots]})
