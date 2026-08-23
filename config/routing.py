from __future__ import annotations

from apps.notifications.routing import websocket_urlpatterns as notification_websocket_urlpatterns
from apps.queueing.routing import websocket_urlpatterns as queueing_websocket_urlpatterns

websocket_urlpatterns = [
    *queueing_websocket_urlpatterns,
    *notification_websocket_urlpatterns,
]
