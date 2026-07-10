from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.queueing.views import QueueEntryViewSet, QueueTransferViewSet, QueueViewSet

router = SimpleRouter()
router.register(r"queueing/queues", QueueViewSet, basename="queueing-queues")
router.register(r"queueing/entries", QueueEntryViewSet, basename="queueing-entries")
router.register(r"queueing/transfers", QueueTransferViewSet, basename="queueing-transfers")

urlpatterns = [
    path("", include(router.urls)),
]
