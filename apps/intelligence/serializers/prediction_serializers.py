from __future__ import annotations

from rest_framework import serializers

from apps.intelligence.models import QueueWaitTimePrediction


class WaitTimePredictionOutputSerializer(serializers.ModelSerializer):
    queue = serializers.UUIDField(source="queue_entry.queue_id", read_only=True)
    service_point = serializers.UUIDField(source="queue_entry.queue.service_point_id", read_only=True)
    facility = serializers.UUIDField(source="queue_entry.queue.service_point.facility_id", read_only=True)
    queue_entry_status = serializers.CharField(source="queue_entry.status", read_only=True)

    class Meta:
        model = QueueWaitTimePrediction
        fields = [
            "id",
            "queue_entry",
            "queue",
            "service_point",
            "facility",
            "queue_entry_status",
            "predicted_wait_minutes",
            "prediction_method",
            "model_version",
            "confidence_score",
            "generated_at",
            "created_at",
        ]


class CreatePredictionInputSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField()
    predicted_wait_minutes = serializers.IntegerField(min_value=0)
    prediction_method = serializers.ChoiceField(choices=QueueWaitTimePrediction.PredictionMethod.choices)
    model_version = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)
    confidence_score = serializers.DecimalField(required=False, allow_null=True, max_digits=5, decimal_places=4, min_value=0, max_value=1)
    generated_at = serializers.DateTimeField(required=False, allow_null=True)


class RuleBasedPredictionInputSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField()
    generated_at = serializers.DateTimeField(required=False, allow_null=True)


class MachineLearningPredictionInputSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField()
