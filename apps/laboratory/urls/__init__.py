from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.laboratory.views import (
    LabOrderItemViewSet,
    LabOrderViewSet,
    LabResultValueViewSet,
    LabSpecimenViewSet,
    LabTestComponentViewSet,
    LabTestViewSet,
)

router = SimpleRouter()
router.register(r"laboratory/tests", LabTestViewSet, basename="laboratory-tests")
router.register(
    r"laboratory/test-components",
    LabTestComponentViewSet,
    basename="laboratory-test-components",
)
router.register(r"laboratory/orders", LabOrderViewSet, basename="laboratory-orders")
router.register(r"laboratory/order-items", LabOrderItemViewSet, basename="laboratory-order-items")
router.register(r"laboratory/specimens", LabSpecimenViewSet, basename="laboratory-specimens")
router.register(r"laboratory/results", LabResultValueViewSet, basename="laboratory-results")

urlpatterns = [
    path("", include(router.urls)),
]
