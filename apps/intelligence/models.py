from __future__ import annotations

from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.queueing.models import QueueEntry
from common.db import CreatedAtModel


class QueueWaitTimePrediction(CreatedAtModel):
    class PredictionMethod(models.TextChoices):
        RULE_BASED = "rule_based", "Rule Based"
        MACHINE_LEARNING = "machine_learning", "Machine Learning"

    queue_entry = models.ForeignKey(QueueEntry, on_delete=models.PROTECT, related_name="wait_time_predictions")
    predicted_wait_minutes = models.IntegerField()
    prediction_method = models.CharField(max_length=30, choices=PredictionMethod.choices)
    model_version = models.CharField(max_length=100, blank=True, null=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4, blank=True, null=True)
    generated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "queue_wait_time_predictions"
        constraints = [
            models.CheckConstraint(condition=Q(predicted_wait_minutes__gte=0), name="ck_queue_predictions_minutes"),
            models.CheckConstraint(condition=Q(prediction_method__in=["rule_based", "machine_learning"]), name="ck_queue_predictions_method"),
            models.CheckConstraint(condition=~Q(prediction_method="machine_learning") | Q(model_version__isnull=False), name="ck_queue_predictions_model"),
            models.CheckConstraint(condition=Q(confidence_score__isnull=True) | Q(confidence_score__gte=0, confidence_score__lte=1), name="ck_queue_predictions_confidence"),
        ]
        indexes = [
            models.Index(fields=["queue_entry", "-generated_at"], name="idx_qwait_pred_entry_time"),
            models.Index(fields=["model_version", "generated_at"], name="idx_qwait_pred_model_time"),
        ]
