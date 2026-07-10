from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.scheduling.views import (
    AppointmentSlotViewSet,
    AppointmentViewSet,
    AvailabilityViewSet,
    LeaveRequestViewSet,
    ShiftViewSet,
)

router = SimpleRouter()
router.register(r"scheduling/availability", AvailabilityViewSet, basename="scheduling-availability")
router.register(r"scheduling/leave-requests", LeaveRequestViewSet, basename="scheduling-leave-requests")
router.register(r"scheduling/shifts", ShiftViewSet, basename="scheduling-shifts")
router.register(r"scheduling/slots", AppointmentSlotViewSet, basename="scheduling-slots")
router.register(r"scheduling/appointments", AppointmentViewSet, basename="scheduling-appointments")

urlpatterns = [
    path("", include(router.urls)),
]
