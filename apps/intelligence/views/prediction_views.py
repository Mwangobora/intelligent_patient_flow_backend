from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.intelligence._helpers import translate_domain_error
from apps.intelligence.models import QueueWaitTimePrediction
from apps.intelligence.selectors import (
    get_latest_prediction_for_queue_entry,
    get_prediction_by_id,
    list_predictions,
    list_predictions_by_queue_entry,
)
from apps.intelligence.serializers import (
    CreatePredictionInputSerializer,
    MachineLearningPredictionInputSerializer,
    RuleBasedPredictionInputSerializer,
    WaitTimePredictionOutputSerializer,
)
from apps.intelligence.services import (
    create_wait_time_prediction,
    generate_machine_learning_prediction_placeholder,
    generate_rule_based_prediction,
)
from apps.queueing.models import QueueEntry

from .base import INTELLIGENCE_DOCS_TAG, IntelligenceBaseViewSet


def _entry_scope(entry_id):
    entry = QueueEntry.objects.select_related("queue__service_point__facility").filter(pk=entry_id).first()
    if entry is None:
        return None, None
    return entry.queue.service_point.facility.organization_id, entry.queue.service_point.facility_id


@extend_schema(tags=[INTELLIGENCE_DOCS_TAG])
class PredictionViewSet(IntelligenceBaseViewSet):
    queryset = QueueWaitTimePrediction.objects.all()
    serializer_class = WaitTimePredictionOutputSerializer
    permission_map = {
        "list": "intelligence_prediction.view",
        "retrieve": "intelligence_prediction.view",
        "create": "intelligence_prediction.create",
        "rule_based": "intelligence_prediction.create",
        "machine_learning": "intelligence_prediction.create",
    }

    def get_permission_scope(self, request):
        if self.action in {"create", "rule_based", "machine_learning"}:
            return _entry_scope(request.data.get("queue_entry_id"))
        if self.action == "retrieve":
            prediction = get_prediction_by_id(self.kwargs.get("pk"))
            if prediction is None:
                return None, None
            facility = prediction.queue_entry.queue.service_point.facility
            return facility.organization_id, facility.id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_predictions(
            queue_entry_id=request.query_params.get("queue_entry_id"),
            prediction_method=request.query_params.get("prediction_method"),
            model_version=request.query_params.get("model_version"),
            generated_from=request.query_params.get("generated_from"),
            generated_to=request.query_params.get("generated_to"),
            facility_id=request.query_params.get("facility_id"),
        )
        return Response(WaitTimePredictionOutputSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = CreatePredictionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            prediction = create_wait_time_prediction(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(WaitTimePredictionOutputSerializer(prediction).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        prediction = get_prediction_by_id(pk)
        if prediction is None:
            return Response({"detail": "Prediction not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(WaitTimePredictionOutputSerializer(prediction).data)

    @action(detail=False, methods=["post"], url_path="rule-based")
    def rule_based(self, request):
        serializer = RuleBasedPredictionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            prediction = generate_rule_based_prediction(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(WaitTimePredictionOutputSerializer(prediction).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="machine-learning")
    def machine_learning(self, request):
        serializer = MachineLearningPredictionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            generate_machine_learning_prediction_placeholder(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


@extend_schema(tags=[INTELLIGENCE_DOCS_TAG])
class QueueEntryPredictionViewSet(IntelligenceBaseViewSet):
    queryset = QueueEntry.objects.all()
    serializer_class = WaitTimePredictionOutputSerializer
    permission_map = {
        "latest_prediction": "intelligence_prediction.view",
        "predictions": "intelligence_prediction.view",
    }

    def get_permission_scope(self, request):
        return _entry_scope(self.kwargs.get("pk"))

    @action(detail=True, methods=["get"], url_path="latest-prediction")
    def latest_prediction(self, request, pk=None):
        prediction = get_latest_prediction_for_queue_entry(queue_entry_id=pk)
        if prediction is None:
            return Response({"detail": "Prediction not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(WaitTimePredictionOutputSerializer(prediction).data)

    @action(detail=True, methods=["get"], url_path="predictions")
    def predictions(self, request, pk=None):
        predictions = list_predictions_by_queue_entry(queue_entry_id=pk)
        return Response(WaitTimePredictionOutputSerializer(predictions, many=True).data)
