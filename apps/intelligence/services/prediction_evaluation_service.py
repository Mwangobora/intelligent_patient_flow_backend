from __future__ import annotations

from apps.intelligence.models import QueueWaitTimePrediction

from ._shared import PredictionEvaluation


def evaluate_prediction_accuracy(*, prediction_method=None, model_version=None, generated_from=None, generated_to=None, facility_id=None):
    queryset = QueueWaitTimePrediction.objects.select_related(
        "queue_entry",
        "queue_entry__queue",
        "queue_entry__queue__service_point",
    ).filter(queue_entry__service_started_at__isnull=False)
    if prediction_method:
        queryset = queryset.filter(prediction_method=prediction_method)
    if model_version:
        queryset = queryset.filter(model_version=model_version)
    if generated_from:
        queryset = queryset.filter(generated_at__gte=generated_from)
    if generated_to:
        queryset = queryset.filter(generated_at__lte=generated_to)
    if facility_id:
        queryset = queryset.filter(queue_entry__queue__service_point__facility_id=facility_id)

    evaluations = []
    for prediction in queryset.order_by("-generated_at"):
        actual_wait_minutes = max(int(round((prediction.queue_entry.service_started_at - prediction.queue_entry.joined_at).total_seconds() / 60)), 0)
        absolute_error = abs(prediction.predicted_wait_minutes - actual_wait_minutes)
        evaluations.append(
            PredictionEvaluation(
                prediction_id=prediction.id,
                queue_entry_id=prediction.queue_entry_id,
                predicted_wait_minutes=prediction.predicted_wait_minutes,
                actual_wait_minutes=actual_wait_minutes,
                absolute_error_minutes=absolute_error,
                prediction_method=prediction.prediction_method,
                model_version=prediction.model_version,
                generated_at=prediction.generated_at,
            )
        )
    return evaluations
