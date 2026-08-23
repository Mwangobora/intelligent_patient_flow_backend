from __future__ import annotations

from django.urls import path

from .consumers import PatientQueueConsumer, QueueConsumer, QueueFacilityConsumer

websocket_urlpatterns = [
    path("ws/queueing/facilities/<uuid:facility_id>/", QueueFacilityConsumer.as_asgi()),
    path("ws/queueing/queues/<uuid:queue_id>/", QueueConsumer.as_asgi()),
    path("ws/patient/queue/", PatientQueueConsumer.as_asgi()),
]
