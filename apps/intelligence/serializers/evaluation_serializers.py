from __future__ import annotations

from rest_framework import serializers


class PredictionEvaluationInputSerializer(serializers.Serializer):
    prediction_method = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    model_version = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    generated_from = serializers.DateTimeField(required=False, allow_null=True)
    generated_to = serializers.DateTimeField(required=False, allow_null=True)
    facility_id = serializers.UUIDField(required=False, allow_null=True)


class PredictionEvaluationOutputSerializer(serializers.Serializer):
    prediction_id = serializers.UUIDField()
    queue_entry_id = serializers.UUIDField()
    predicted_wait_minutes = serializers.IntegerField()
    actual_wait_minutes = serializers.IntegerField()
    absolute_error_minutes = serializers.IntegerField()
    prediction_method = serializers.CharField()
    model_version = serializers.CharField(allow_null=True)
    generated_at = serializers.DateTimeField()
