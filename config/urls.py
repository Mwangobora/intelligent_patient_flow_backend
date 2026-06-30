from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from common.health import LiveHealthCheckView, ReadyHealthCheckView
from config.api_router import APIRootView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/v1/", APIRootView.as_view(), name="api-root"),
    path("health/live/", LiveHealthCheckView.as_view(), name="health-live"),
    path("health/ready/", ReadyHealthCheckView.as_view(), name="health-ready"),
]
