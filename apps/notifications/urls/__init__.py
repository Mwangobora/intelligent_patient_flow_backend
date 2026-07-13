from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.notifications.views import (
    AppointmentCancelledNotificationViewSet,
    AppointmentConfirmationNotificationViewSet,
    AppointmentReminderNotificationViewSet,
    AppointmentRescheduledNotificationViewSet,
    NotificationViewSet,
    PushDeviceViewSet,
    QueueCalledNotificationViewSet,
    QueueJoinedNotificationViewSet,
    QueueUpdatedNotificationViewSet,
)

router = SimpleRouter()
router.register(r"notifications/push-devices", PushDeviceViewSet, basename="notification-push-devices")
router.register(r"notifications/appointment-confirmation", AppointmentConfirmationNotificationViewSet, basename="notification-appointment-confirmation")
router.register(r"notifications/appointment-reminder", AppointmentReminderNotificationViewSet, basename="notification-appointment-reminder")
router.register(r"notifications/appointment-rescheduled", AppointmentRescheduledNotificationViewSet, basename="notification-appointment-rescheduled")
router.register(r"notifications/appointment-cancelled", AppointmentCancelledNotificationViewSet, basename="notification-appointment-cancelled")
router.register(r"notifications/queue-joined", QueueJoinedNotificationViewSet, basename="notification-queue-joined")
router.register(r"notifications/queue-updated", QueueUpdatedNotificationViewSet, basename="notification-queue-updated")
router.register(r"notifications/queue-called", QueueCalledNotificationViewSet, basename="notification-queue-called")
router.register(r"notifications", NotificationViewSet, basename="notifications")

urlpatterns = [
    path("", include(router.urls)),
]
