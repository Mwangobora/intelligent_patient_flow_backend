from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.scheduling._helpers import translate_domain_error
from apps.scheduling.models import Appointment
from apps.scheduling.selectors import get_appointment_by_id, get_appointment_status_history, list_appointments
from apps.scheduling.serializers import (
    AppointmentAssignPractitionerSerializer,
    AppointmentCancellationSerializer,
    AppointmentCreateSerializer,
    AppointmentDetailSerializer,
    AppointmentRescheduleSerializer,
    AppointmentStatusHistorySerializer,
    AppointmentUpdateSerializer,
)
from apps.scheduling.services import (
    assign_practitioner_to_appointment,
    cancel_appointment,
    create_appointment,
    reschedule_appointment,
    update_appointment,
)

from .base import SCHEDULING_DOCS_TAG, SchedulingBaseViewSet


@extend_schema(tags=[SCHEDULING_DOCS_TAG])
class AppointmentViewSet(SchedulingBaseViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentDetailSerializer
    permission_map = {
        "list": "scheduling_appointment.view",
        "retrieve": "scheduling_appointment.view",
        "status_history": "scheduling_appointment.view",
        "create": "scheduling_appointment.create",
        "partial_update": "scheduling_appointment.update",
        "cancel": "scheduling_appointment.cancel",
        "reschedule": "scheduling_appointment.reschedule",
        "assign_practitioner": "scheduling_appointment.assign",
    }

    def get_serializer_class(self):
        return {
            "create": AppointmentCreateSerializer,
            "partial_update": AppointmentUpdateSerializer,
            "cancel": AppointmentCancellationSerializer,
            "reschedule": AppointmentRescheduleSerializer,
            "assign_practitioner": AppointmentAssignPractitionerSerializer,
            "status_history": AppointmentStatusHistorySerializer,
        }.get(self.action, AppointmentDetailSerializer)

    def get_permission_scope(self, request):
        appointment = get_appointment_by_id(self.kwargs.get("pk")) if self.action in {"retrieve", "partial_update", "cancel", "reschedule", "assign_practitioner", "status_history"} else None
        if appointment is not None:
            return appointment.facility.organization_id, appointment.facility_id
        facility_id = request.data.get("facility_id") if self.action == "create" else request.query_params.get("facility_id")
        return request.query_params.get("organization_id"), facility_id

    def list(self, request):
        queryset = list_appointments(
            facility_id=request.query_params.get("facility_id"),
            patient_id=request.query_params.get("patient_id"),
            practitioner_id=request.query_params.get("practitioner_id"),
            practitioner_facility_assignment_id=request.query_params.get("practitioner_facility_assignment_id"),
            facility_specialty_id=request.query_params.get("facility_specialty_id"),
            status=request.query_params.get("status"),
            starts_from=request.query_params.get("starts_from"),
            ends_to=request.query_params.get("ends_to"),
        )
        return Response(AppointmentDetailSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = AppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            appointment = create_appointment(**serializer.validated_data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AppointmentDetailSerializer(appointment).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        appointment = get_appointment_by_id(pk)
        if appointment is None:
            return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AppointmentDetailSerializer(appointment).data)

    def partial_update(self, request, pk=None):
        serializer = AppointmentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            appointment = update_appointment(appointment_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AppointmentDetailSerializer(appointment).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        serializer = AppointmentCancellationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            appointment = cancel_appointment(appointment_id=pk, cancelled_by_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AppointmentDetailSerializer(appointment).data)

    @action(detail=True, methods=["post"], url_path="reschedule")
    def reschedule(self, request, pk=None):
        serializer = AppointmentRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            appointment = reschedule_appointment(appointment_id=pk, created_by_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AppointmentDetailSerializer(appointment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="assign-practitioner")
    def assign_practitioner(self, request, pk=None):
        serializer = AppointmentAssignPractitionerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            appointment = assign_practitioner_to_appointment(appointment_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AppointmentDetailSerializer(appointment).data)

    @action(detail=True, methods=["get"], url_path="status-history")
    def status_history(self, request, pk=None):
        history = get_appointment_status_history(appointment_id=pk)
        return Response(AppointmentStatusHistorySerializer(history, many=True).data)
