from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.pharmacy.views import (
    MedicationDispenseViewSet,
    MedicationViewSet,
    PrescriptionItemViewSet,
    PrescriptionViewSet,
)

router = SimpleRouter()
router.register(r"pharmacy/medications", MedicationViewSet, basename="pharmacy-medications")
router.register(r"pharmacy/prescriptions", PrescriptionViewSet, basename="pharmacy-prescriptions")
router.register(
    r"pharmacy/prescription-items",
    PrescriptionItemViewSet,
    basename="pharmacy-prescription-items",
)
router.register(r"pharmacy/dispenses", MedicationDispenseViewSet, basename="pharmacy-dispenses")

urlpatterns = [
    path("", include(router.urls)),
]
