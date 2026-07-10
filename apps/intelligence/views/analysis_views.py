from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from apps.facilities.models import FacilitySpecialty
from apps.intelligence._helpers import translate_domain_error
from apps.intelligence.serializers import (
    ArrivalForecastInputSerializer,
    ArrivalForecastOutputSerializer,
    PredictionEvaluationInputSerializer,
    PredictionEvaluationOutputSerializer,
    SlotSuggestionInputSerializer,
    SlotSuggestionOutputSerializer,
)
from apps.intelligence.services import evaluate_prediction_accuracy, forecast_patient_arrivals, suggest_optimal_appointment_slots

from .base import INTELLIGENCE_DOCS_TAG, IntelligenceBaseViewSet


@extend_schema(tags=[INTELLIGENCE_DOCS_TAG])
class ArrivalForecastViewSet(IntelligenceBaseViewSet):
    permission_map = {
        "list": "intelligence_forecast.view",
    }

    def get_permission_scope(self, request):
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        serializer = ArrivalForecastInputSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            rows = forecast_patient_arrivals(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ArrivalForecastOutputSerializer(rows, many=True).data)


@extend_schema(tags=[INTELLIGENCE_DOCS_TAG])
class SlotSuggestionViewSet(IntelligenceBaseViewSet):
    permission_map = {
        "list": "intelligence_slot_suggestion.view",
    }

    def get_permission_scope(self, request):
        facility_specialty = FacilitySpecialty.objects.select_related("facility").filter(pk=request.query_params.get("facility_specialty_id")).first()
        if facility_specialty is None:
            return None, None
        return facility_specialty.facility.organization_id, facility_specialty.facility_id

    def list(self, request):
        serializer = SlotSuggestionInputSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            suggestions = suggest_optimal_appointment_slots(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(SlotSuggestionOutputSerializer(suggestions, many=True).data)


@extend_schema(tags=[INTELLIGENCE_DOCS_TAG])
class PredictionEvaluationViewSet(IntelligenceBaseViewSet):
    permission_map = {
        "list": "intelligence_prediction.evaluate",
    }

    def get_permission_scope(self, request):
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        serializer = PredictionEvaluationInputSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            evaluations = evaluate_prediction_accuracy(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PredictionEvaluationOutputSerializer(evaluations, many=True).data)
