from __future__ import annotations

from django.urls import path

from .consumers import PatientNotificationConsumer

websocket_urlpatterns = [
    path("ws/patient/notifications/", PatientNotificationConsumer.as_asgi()),
]
