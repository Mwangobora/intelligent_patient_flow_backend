from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.audit.views import ActorAuditViewSet, AuditLogViewSet, AuditSummaryViewSet, ResourceAuditViewSet

router = SimpleRouter()
router.register(r"audit/resources/(?P<resource_type>[^/.]+)/(?P<resource_id>[^/.]+)", ResourceAuditViewSet, basename="audit-resources")
router.register(r"audit/actors/(?P<user_id>[^/.]+)", ActorAuditViewSet, basename="audit-actors")
router.register(r"audit/summary", AuditSummaryViewSet, basename="audit-summary")
router.register(r"audit/logs", AuditLogViewSet, basename="audit-logs")

urlpatterns = [
    path("", include(router.urls)),
]
