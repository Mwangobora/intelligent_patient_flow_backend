from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.facilities.models import ServicePoint
from apps.queueing._helpers import translate_domain_error
from apps.queueing.models import Queue
from apps.queueing.selectors import get_next_callable_entry, get_queue_by_id, list_queues
from apps.queueing.serializers import QueueCreateSerializer, QueueEntryOutputSerializer, QueueOutputSerializer, QueueStatusActionSerializer
from apps.queueing.services import cancel_queue, close_queue, create_queue, open_queue, pause_queue, resume_queue

from .base import QUEUEING_DOCS_TAG, QueueingBaseViewSet


@extend_schema(tags=[QUEUEING_DOCS_TAG])
class QueueViewSet(QueueingBaseViewSet):
    queryset = Queue.objects.all()
    serializer_class = QueueOutputSerializer
    permission_map = {
        "list": "queueing_queue.view",
        "retrieve": "queueing_queue.view",
        "next_entry": "queueing_entry.view",
        "create": "queueing_queue.manage",
        "open": "queueing_queue.manage",
        "pause": "queueing_queue.manage",
        "resume": "queueing_queue.manage",
        "close": "queueing_queue.manage",
        "cancel": "queueing_queue.manage",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            service_point = ServicePoint.objects.select_related("facility").filter(pk=request.data.get("service_point_id")).first()
            if service_point is None:
                return None, None
            return service_point.facility.organization_id, service_point.facility_id
        if self.action in {"retrieve", "open", "pause", "resume", "close", "cancel", "next_entry"}:
            queue = get_queue_by_id(self.kwargs.get("pk"))
            if queue is None:
                return None, None
            return queue.service_point.facility.organization_id, queue.service_point.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_queues(
            facility_id=request.query_params.get("facility_id"),
            service_point_id=request.query_params.get("service_point_id"),
            facility_specialty_id=request.query_params.get("facility_specialty_id"),
            queue_date=request.query_params.get("queue_date"),
            status=request.query_params.get("status"),
        )
        return Response(QueueOutputSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = QueueCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            queue = create_queue(**serializer.validated_data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueOutputSerializer(queue).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        queue = get_queue_by_id(pk)
        if queue is None:
            return Response({"detail": "Queue not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(QueueOutputSerializer(queue).data)

    @action(detail=True, methods=["post"], url_path="open")
    def open(self, request, pk=None):
        serializer = QueueStatusActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            queue = open_queue(queue_id=pk, opened_by_id=request.user.id, opened_at=serializer.validated_data.get("at"))
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueOutputSerializer(queue).data)

    @action(detail=True, methods=["post"], url_path="pause")
    def pause(self, request, pk=None):
        serializer = QueueStatusActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            queue = pause_queue(queue_id=pk, paused_at=serializer.validated_data.get("at"))
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueOutputSerializer(queue).data)

    @action(detail=True, methods=["post"], url_path="resume")
    def resume(self, request, pk=None):
        try:
            queue = resume_queue(queue_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueOutputSerializer(queue).data)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        serializer = QueueStatusActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            queue = close_queue(queue_id=pk, closed_by_id=request.user.id, closed_at=serializer.validated_data.get("at"))
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueOutputSerializer(queue).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        try:
            queue = cancel_queue(queue_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(QueueOutputSerializer(queue).data)

    @action(detail=True, methods=["get"], url_path="next-entry")
    def next_entry(self, request, pk=None):
        entry = get_next_callable_entry(queue_id=pk)
        if entry is None:
            return Response({"detail": "No callable queue entry found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(QueueEntryOutputSerializer(entry).data)
