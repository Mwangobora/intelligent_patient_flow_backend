from __future__ import annotations

from rest_framework import serializers


class ArrivalForecastInputSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    service_point_id = serializers.UUIDField(required=False, allow_null=True)
    facility_specialty_id = serializers.UUIDField(required=False, allow_null=True)


class ArrivalForecastOutputSerializer(serializers.Serializer):
    day_of_week = serializers.IntegerField()
    hour_of_day = serializers.IntegerField()
    total_arrivals = serializers.IntegerField()
    average_arrivals = serializers.FloatField()
