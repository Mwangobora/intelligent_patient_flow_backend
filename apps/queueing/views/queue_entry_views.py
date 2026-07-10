from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.queueing._helpers import translate_domain_error
from apps.queueing.models import Queue, QueueEntry
from apps.queueing.selectors import get_queue_entry_by_id, list_queue_entries, list_queue_entry_events
from apps.queueing.serializers import (
    QueueEntryActionSerializer,
    QueueEntryCancelSerializer,
    QueueEntryCreateSerializer,
    QueueEntryEventOutputSerializer,
    QueueEntryOutputSerializer,
    QueueEntryPrioritySerializer,
    QueueTransferInputSerializer,
    QueueTransferOutputSerializer,
)
from apps.queueing.services import (
    call_queue_entry,
    cancel_queue_entry,
    change_priority,
    complete_service,
    create_queue_entry,
    recall_queue_entry,
    skip_queue_entry,
    start_service,
    transfer_queue_entry,
)

from .base import QUEUEING_DOCS_TAG, QueueingBaseViewSet, _bool_query_param


@extend_schema(tags=[QUEUEING_DOCS_TAG])
class QueueEntryViewSet(QueueingBaseViewSet):
    queryset = QueueEntry.objects.all()
    serializer_class = QueueEntryOutputSerializer
    permission_map = {
        "list": "queueing_entry.view",
        "retrieve": "queueing_entry.view",
        "events": "queueing_entry.view",
        "create": "queueing_entry.create",
        "call": "queueing_entry.call",
        "recall": "queueing_entry.call",
        "skip": "queueing_entry.skip",
        "start_service_action": "queueing_entry.start_service",
        "complete_service_action": "queueing_entry.complete_service",
        "cancel": "queueing_entry.cancel",
        "transfer": "queueing_entry.transfer",
        "change_priority_action": "queueing_priority.manage",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            queue = Queue.objects.select_related("service_point__facility").filter(pk=request.data.get("queue_id")).first()
            if queue is None:
                return None, None
            return queue.service_point.facility.organization_id, queue.service_point.facility_id
        if self.action in {
            "retrieve",
            "call",
            "recall",
            "skip",
            "start_service_action",
            "complete_service_action",
            "cancel",
            "transfer",
            "change_priority_action",
            "events",
        }:
            entry = get_queue_entry_by_id(self.kwargs.get("pk"))
            if entry is None:
                return None, None
            return entry.queue.service_point.facility.organization_id, entry.queue.service_point.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_queue_entries(
            queue_id=request.query_params.get("queue_id"),
            facility_id=request.query_params.get("facility_id"),
            patient_id=request.query_params.get("patient_id"),
            patient_checkin_id=request.query_params.get("patient_checkin_id"),
            status=request.query_params.get("status"),
            active_only=_bool_query_param(request.query_params.get("active_only")),
        )
        return Response(QueueEntryOutputSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = QueueEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entry = create_queue_entry(**serializer.validated_data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueEntryOutputSerializer(entry).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        entry = get_queue_entry_by_id(pk)
        if entry is None:
            return Response({"detail": "Queue entry not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(QueueEntryOutputSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="call")
    def call(self, request, pk=None):
        serializer = QueueEntryActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entry = call_queue_entry(queue_entry_id=pk, performed_by_id=request.user.id, called_at=serializer.validated_data.get("at"))
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueEntryOutputSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="recall")
    def recall(self, request, pk=None):
        serializer = QueueEntryActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entry = recall_queue_entry(queue_entry_id=pk, performed_by_id=request.user.id, recalled_at=serializer.validated_data.get("at"))
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueEntryOutputSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="skip")
    def skip(self, request, pk=None):
        serializer = QueueEntryActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entry = skip_queue_entry(
                queue_entry_id=pk,
                performed_by_id=request.user.id,
                reason=serializer.validated_data.get("reason"),
                skipped_at=serializer.validated_data.get("at"),
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueEntryOutputSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="start-service", url_name="start-service")
    def start_service_action(self, request, pk=None):
        serializer = QueueEntryActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entry = start_service(queue_entry_id=pk, performed_by_id=request.user.id, started_at=serializer.validated_data.get("at"))
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueEntryOutputSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="complete-service", url_name="complete-service")
    def complete_service_action(self, request, pk=None):
        serializer = QueueEntryActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entry = complete_service(queue_entry_id=pk, performed_by_id=request.user.id, completed_at=serializer.validated_data.get("at"))
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueEntryOutputSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        serializer = QueueEntryCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entry = cancel_queue_entry(queue_entry_id=pk, cancelled_by_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueEntryOutputSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="change-priority", url_name="change-priority")
    def change_priority_action(self, request, pk=None):
        serializer = QueueEntryPrioritySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entry = change_priority(queue_entry_id=pk, performed_by_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueEntryOutputSerializer(entry).data)

    @action(detail=True, methods=["post"], url_path="transfer")
    def transfer(self, request, pk=None):
        serializer = QueueTransferInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            transfer = transfer_queue_entry(source_queue_entry_id=pk, transferred_by_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueTransferOutputSerializer(transfer).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="events")
    def events(self, request, pk=None):
        events = list_queue_entry_events(queue_entry_id=pk)
        return Response(QueueEntryEventOutputSerializer(events, many=True).data)
