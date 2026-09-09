from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.billing.views import (
    EncounterChargeViewSet,
    InvoiceItemViewSet,
    InvoiceViewSet,
    PaymentRefundViewSet,
    PaymentViewSet,
    ServicePriceViewSet,
    ServiceViewSet,
)

router = SimpleRouter()
router.register(r"billing/services", ServiceViewSet, basename="billing-services")
router.register(r"billing/service-prices", ServicePriceViewSet, basename="billing-service-prices")
router.register(
    r"billing/encounter-charges", EncounterChargeViewSet, basename="billing-encounter-charges"
)
router.register(r"billing/invoices", InvoiceViewSet, basename="billing-invoices")
router.register(r"billing/invoice-items", InvoiceItemViewSet, basename="billing-invoice-items")
router.register(r"billing/payments", PaymentViewSet, basename="billing-payments")
router.register(
    r"billing/payment-refunds", PaymentRefundViewSet, basename="billing-payment-refunds"
)

urlpatterns = [
    path("", include(router.urls)),
]
