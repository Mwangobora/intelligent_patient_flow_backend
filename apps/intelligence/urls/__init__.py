from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.intelligence.views import (
    ArrivalForecastViewSet,
    PredictionEvaluationViewSet,
    PredictionViewSet,
    QueueEntryPredictionViewSet,
    SlotSuggestionViewSet,
)

router = SimpleRouter()
router.register(r"intelligence/predictions/evaluation", PredictionEvaluationViewSet, basename="intelligence-prediction-evaluation")
router.register(r"intelligence/predictions", PredictionViewSet, basename="intelligence-predictions")
router.register(r"intelligence/queue-entries", QueueEntryPredictionViewSet, basename="intelligence-queue-entries")
router.register(r"intelligence/arrival-forecast", ArrivalForecastViewSet, basename="intelligence-arrival-forecast")
router.register(r"intelligence/slot-suggestions", SlotSuggestionViewSet, basename="intelligence-slot-suggestions")

urlpatterns = [
    path("", include(router.urls)),
]
