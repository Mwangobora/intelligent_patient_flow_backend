from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.checkins.views import CheckinTokenViewSet, CheckinViewSet

router = SimpleRouter()
router.register(r"checkins/tokens", CheckinTokenViewSet, basename="checkin-tokens")
router.register(r"checkins", CheckinViewSet, basename="checkins")

urlpatterns = [
    path("", include(router.urls)),
]
