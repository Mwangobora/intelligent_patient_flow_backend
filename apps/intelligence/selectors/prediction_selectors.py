from __future__ import annotations

from apps.intelligence.models import QueueWaitTimePrediction


def base_prediction_queryset():
    return QueueWaitTimePrediction.objects.select_related(
        "queue_entry",
        "queue_entry__queue",
        "queue_entry__queue__service_point",
        "queue_entry__queue__service_point__facility",
        "queue_entry__patient_checkin",
    )


def list_predictions(*, queue_entry_id=None, prediction_method=None, model_version=None, generated_from=None, generated_to=None, facility_id=None):
    queryset = base_prediction_queryset()
    if queue_entry_id:
        queryset = queryset.filter(queue_entry_id=queue_entry_id)
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
    return queryset.order_by("-generated_at", "-created_at")


def get_prediction_by_id(prediction_id):
    return base_prediction_queryset().filter(pk=prediction_id).first()


def list_predictions_by_queue_entry(*, queue_entry_id):
    return list_predictions(queue_entry_id=queue_entry_id)


def get_latest_prediction_for_queue_entry(*, queue_entry_id):
    return list_predictions_by_queue_entry(queue_entry_id=queue_entry_id).first()


def list_predictions_by_method(*, prediction_method):
    return list_predictions(prediction_method=prediction_method)


def list_predictions_by_model_version(*, model_version):
    return list_predictions(model_version=model_version)


def list_predictions_by_generated_at_range(*, generated_from=None, generated_to=None):
    return list_predictions(generated_from=generated_from, generated_to=generated_to)


def list_predictions_for_facility(*, facility_id):
    return list_predictions(facility_id=facility_id)
