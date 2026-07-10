from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.intelligence.models import QueueWaitTimePrediction
from common.exceptions import ConflictError, ValidationError

from ._shared import active_patients_ahead, average_service_minutes, get_queue_entry, validate_predictable_queue_entry, validate_prediction_values


@transaction.atomic
def create_wait_time_prediction(
    *,
    queue_entry_id,
    predicted_wait_minutes: int,
    prediction_method: str,
    model_version: str | None = None,
    confidence_score=None,
    generated_at=None,
) -> QueueWaitTimePrediction:
    queue_entry = get_queue_entry(queue_entry_id, for_update=True)
    prediction_time = generated_at or timezone.now()
    validate_predictable_queue_entry(queue_entry=queue_entry, generated_at=prediction_time)
    validate_prediction_values(
        predicted_wait_minutes=predicted_wait_minutes,
        prediction_method=prediction_method,
        model_version=model_version,
        confidence_score=confidence_score,
    )

    try:
        return QueueWaitTimePrediction.objects.create(
            queue_entry=queue_entry,
            predicted_wait_minutes=predicted_wait_minutes,
            prediction_method=prediction_method,
            model_version=model_version,
            confidence_score=Decimal(str(confidence_score)) if confidence_score is not None else None,
            generated_at=prediction_time,
        )
    except IntegrityError as exc:
        raise ConflictError("Waiting-time prediction could not be created because of a conflicting database state.") from exc


@transaction.atomic
def generate_rule_based_prediction(*, queue_entry_id, generated_at=None) -> QueueWaitTimePrediction:
    queue_entry = get_queue_entry(queue_entry_id, for_update=True)
    prediction_time = generated_at or timezone.now()
    validate_predictable_queue_entry(queue_entry=queue_entry, generated_at=prediction_time)
    patients_ahead = active_patients_ahead(queue_entry=queue_entry)
    avg_minutes, sample_size = average_service_minutes(queue_entry=queue_entry)
    predicted_wait_minutes = patients_ahead * avg_minutes
    confidence_score = None
    if sample_size >= 5:
        confidence_score = min(Decimal("0.8000"), Decimal("0.3000") + (Decimal(sample_size) / Decimal("50.0000")))

    return create_wait_time_prediction(
        queue_entry_id=queue_entry.id,
        predicted_wait_minutes=predicted_wait_minutes,
        prediction_method=QueueWaitTimePrediction.PredictionMethod.RULE_BASED,
        confidence_score=confidence_score,
        generated_at=prediction_time,
    )


def generate_machine_learning_prediction_placeholder(*, queue_entry_id):
    get_queue_entry(queue_entry_id)
    raise ValidationError("Machine learning model is not configured yet.")
