from .appointment_views import AppointmentViewSet
from .availability_views import AvailabilityViewSet
from .base import SCHEDULING_DOCS_TAG, SchedulingBaseViewSet
from .leave_views import LeaveRequestViewSet
from .shift_views import ShiftViewSet
from .slot_views import AppointmentSlotViewSet

__all__ = [
    "AppointmentSlotViewSet",
    "AppointmentViewSet",
    "AvailabilityViewSet",
    "LeaveRequestViewSet",
    "SCHEDULING_DOCS_TAG",
    "SchedulingBaseViewSet",
    "ShiftViewSet",
]
