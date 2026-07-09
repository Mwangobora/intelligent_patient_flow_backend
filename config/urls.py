from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from common.health import LiveHealthCheckView, ReadyHealthCheckView
from config.api_router import APIRootView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(api_version="v1"), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/v1/", APIRootView.as_view(), name="api-root"),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.facilities.urls")),
    path("health/live/", LiveHealthCheckView.as_view(), name="health-live"),
    path("health/ready/", ReadyHealthCheckView.as_view(), name="health-ready"),
]
