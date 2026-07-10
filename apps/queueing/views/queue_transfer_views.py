from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from apps.queueing.models import QueueTransfer
from apps.queueing.selectors import list_queue_transfers
from apps.queueing.serializers import QueueTransferOutputSerializer

from .base import QUEUEING_DOCS_TAG, QueueingBaseViewSet


@extend_schema(tags=[QUEUEING_DOCS_TAG])
class QueueTransferViewSet(QueueingBaseViewSet):
    queryset = QueueTransfer.objects.all()
    serializer_class = QueueTransferOutputSerializer
    permission_map = {
        "list": "queueing_entry.view",
    }

    def get_permission_scope(self, request):
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_queue_transfers(
            source_queue_entry_id=request.query_params.get("source_queue_entry_id"),
            destination_queue_entry_id=request.query_params.get("destination_queue_entry_id"),
            facility_id=request.query_params.get("facility_id"),
            transferred_from=request.query_params.get("transferred_from"),
            transferred_to=request.query_params.get("transferred_to"),
        )
        return Response(QueueTransferOutputSerializer(queryset, many=True).data)
