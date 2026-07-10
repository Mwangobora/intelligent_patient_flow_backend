from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Q

from apps.queueing.models import QueueEntry
from common.exceptions import NotFoundError, ValidationError

PREDICTABLE_ENTRY_STATUSES = {
    QueueEntry.Status.WAITING,
    QueueEntry.Status.CALLED,
    QueueEntry.Status.SKIPPED,
}

FALLBACK_AVERAGE_SERVICE_MINUTES = 15


@dataclass(frozen=True)
class ArrivalForecastRow:
    day_of_week: int
    hour_of_day: int
    total_arrivals: int
    average_arrivals: float


@dataclass(frozen=True)
class SlotSuggestion:
    appointment_slot_id: object
    practitioner_shift_id: object
    facility_specialty_id: object
    starts_at: object
    ends_at: object
    capacity: int
    booked_count: int
    booking_ratio: float
    historical_average_wait_minutes: float | None
    score_rank: tuple


@dataclass(frozen=True)
class PredictionEvaluation:
    prediction_id: object
    queue_entry_id: object
    predicted_wait_minutes: int
    actual_wait_minutes: int
    absolute_error_minutes: int
    prediction_method: str
    model_version: str | None
    generated_at: object


def get_queue_entry(queue_entry_id, *, for_update: bool = False) -> QueueEntry:
    queryset = QueueEntry.objects.select_related(
        "queue",
        "queue__service_point",
        "queue__service_point__facility",
        "queue__facility_specialty",
        "patient_checkin",
        "patient_checkin__appointment",
    )
    if for_update:
        queryset = QueueEntry.objects.select_for_update().select_related("queue", "queue__service_point", "queue__service_point__facility", "patient_checkin")
    entry = queryset.filter(pk=queue_entry_id).first()
    if entry is None:
        raise NotFoundError("Queue entry not found.")
    return entry


def validate_predictable_queue_entry(*, queue_entry: QueueEntry, generated_at) -> None:
    if queue_entry.status not in PREDICTABLE_ENTRY_STATUSES:
        raise ValidationError("Waiting-time prediction is not allowed for this queue-entry status.")
    if generated_at < queue_entry.joined_at:
        raise ValidationError("Prediction cannot be generated before queue entry joined_at.")
    if queue_entry.service_started_at is not None and generated_at >= queue_entry.service_started_at:
        raise ValidationError("Prediction must be generated before service starts.")


def validate_prediction_values(*, predicted_wait_minutes: int, prediction_method: str, model_version: str | None, confidence_score) -> None:
    if predicted_wait_minutes < 0:
        raise ValidationError("predicted_wait_minutes must be greater than or equal to 0.")
    if prediction_method not in {"rule_based", "machine_learning"}:
        raise ValidationError("Invalid prediction_method.")
    if prediction_method == "machine_learning" and not model_version:
        raise ValidationError("machine_learning prediction requires model_version.")
    if confidence_score is not None:
        score = Decimal(str(confidence_score))
        if score < 0 or score > 1:
            raise ValidationError("confidence_score must be between 0 and 1.")


def active_patients_ahead(*, queue_entry: QueueEntry) -> int:
    return QueueEntry.objects.filter(
        queue_id=queue_entry.queue_id,
        status__in=PREDICTABLE_ENTRY_STATUSES,
    ).filter(
        Q(priority_level__gt=queue_entry.priority_level)
        | Q(priority_level=queue_entry.priority_level, joined_at__lt=queue_entry.joined_at)
        | Q(priority_level=queue_entry.priority_level, joined_at=queue_entry.joined_at, sequence_number__lt=queue_entry.sequence_number)
    ).count()


def completed_service_duration_minutes_queryset(*, queue_entry: QueueEntry):
    return QueueEntry.objects.filter(
        status=QueueEntry.Status.COMPLETED,
        service_started_at__isnull=False,
        service_completed_at__isnull=False,
    ).filter(
        Q(queue_id=queue_entry.queue_id) | Q(queue__service_point_id=queue_entry.queue.service_point_id)
    )


def average_service_minutes(*, queue_entry: QueueEntry, minimum_samples: int = 1) -> tuple[int, int]:
    durations = []
    for entry in completed_service_duration_minutes_queryset(queue_entry=queue_entry).order_by("-service_completed_at")[:50]:
        duration = entry.service_completed_at - entry.service_started_at
        minutes = max(int(round(duration.total_seconds() / 60)), 0)
        durations.append(minutes)
    if len(durations) < minimum_samples or not durations:
        return FALLBACK_AVERAGE_SERVICE_MINUTES, len(durations)
    return int(round(sum(durations) / len(durations))), len(durations)
