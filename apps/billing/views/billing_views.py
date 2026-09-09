from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.billing._helpers import translate_domain_error
from apps.billing.models import (
    EncounterCharge,
    Invoice,
    InvoiceItem,
    Payment,
    PaymentRefund,
    Service,
    ServicePrice,
)
from apps.billing.selectors import (
    get_encounter_charge_by_id,
    get_invoice_by_id,
    get_invoice_item_by_id,
    get_payment_by_id,
    get_payment_refund_by_id,
    get_service_by_id,
    get_service_price_by_id,
    list_encounter_charges,
    list_invoice_items,
    list_invoices,
    list_payment_refunds,
    list_payments,
    list_service_prices,
    list_services,
)
from apps.billing.serializers import (
    EncounterChargeCreateSerializer,
    EncounterChargeSerializer,
    EncounterChargeVoidSerializer,
    InvoiceCancelSerializer,
    InvoiceCreateSerializer,
    InvoiceItemSerializer,
    InvoiceSerializer,
    InvoiceSettleSerializer,
    PaymentRefundCompleteSerializer,
    PaymentRefundCreateSerializer,
    PaymentRefundSerializer,
    PaymentSerializer,
    ServicePriceSerializer,
    ServicePriceWriteSerializer,
    ServiceSerializer,
    ServiceWriteSerializer,
)
from apps.billing.services import (
    cancel_invoice,
    complete_payment_refund,
    create_encounter_charge,
    create_service,
    create_service_price,
    generate_invoice_from_charges,
    request_payment_refund,
    settle_invoice,
    update_service,
    update_service_price,
    void_encounter_charge,
)
from apps.clinical.selectors import get_encounter_by_id

from .base import BILLING_DOCS_TAG, BillingBaseViewSet, _bool_query_param


@extend_schema(tags=[BILLING_DOCS_TAG])
class ServiceViewSet(BillingBaseViewSet):
    queryset = Service.objects.all()
    permission_map = {
        "list": "billing_service.view",
        "retrieve": "billing_service.view",
        "create": "billing_service.create",
        "partial_update": "billing_service.update",
        "deactivate": "billing_service.deactivate",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            return request.data.get("organization_id"), None
        if self.action in {"retrieve", "partial_update", "deactivate"}:
            service = get_service_by_id(self.kwargs.get("pk"))
            return (service.organization_id, None) if service else (None, None)
        return request.query_params.get("organization_id"), None

    def list(self, request):
        return Response(
            ServiceSerializer(
                list_services(
                    organization_id=request.query_params.get("organization_id"),
                    service_category=request.query_params.get("service_category"),
                    is_active=_bool_query_param(request.query_params.get("is_active")),
                    search=request.query_params.get("search"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = ServiceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            service = create_service(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ServiceSerializer(service).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        service = get_service_by_id(pk)
        if service is None:
            return Response(
                {"detail": "Billing service not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(ServiceSerializer(service).data)

    def partial_update(self, request, pk=None):
        serializer = ServiceWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            service = update_service(service_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ServiceSerializer(service).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        try:
            service = update_service(service_id=pk, is_active=False)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ServiceSerializer(service).data)


@extend_schema(tags=[BILLING_DOCS_TAG])
class ServicePriceViewSet(BillingBaseViewSet):
    queryset = ServicePrice.objects.all()
    permission_map = {
        "list": "billing_price.view",
        "retrieve": "billing_price.view",
        "create": "billing_price.manage",
        "partial_update": "billing_price.manage",
    }

    def get_permission_scope(self, request):
        service = None
        if self.action == "create":
            service = get_service_by_id(request.data.get("service_id"))
        elif self.action in {"retrieve", "partial_update"}:
            price = get_service_price_by_id(self.kwargs.get("pk"))
            service = price.service if price else None
        else:
            service = get_service_by_id(request.query_params.get("service_id"))
        return (
            (service.organization_id, None)
            if service
            else (request.query_params.get("organization_id"), None)
        )

    def list(self, request):
        return Response(
            ServicePriceSerializer(
                list_service_prices(
                    service_id=request.query_params.get("service_id"),
                    facility_id=request.query_params.get("facility_id"),
                    is_active=_bool_query_param(request.query_params.get("is_active")),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = ServicePriceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            price = create_service_price(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ServicePriceSerializer(price).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        price = get_service_price_by_id(pk)
        if price is None:
            return Response(
                {"detail": "Service price not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(ServicePriceSerializer(price).data)

    def partial_update(self, request, pk=None):
        serializer = ServicePriceWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            price = update_service_price(price_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(ServicePriceSerializer(price).data)


@extend_schema(tags=[BILLING_DOCS_TAG])
class EncounterChargeViewSet(BillingBaseViewSet):
    queryset = EncounterCharge.objects.all()
    permission_map = {
        "list": "billing_charge.view",
        "retrieve": "billing_charge.view",
        "create": "billing_charge.create",
        "void": "billing_charge.void",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            encounter = get_encounter_by_id(request.data.get("encounter_id"))
        elif self.action in {"retrieve", "void"}:
            charge = get_encounter_charge_by_id(self.kwargs.get("pk"))
            encounter = charge.encounter if charge else None
        else:
            encounter = get_encounter_by_id(request.query_params.get("encounter_id"))
        if encounter:
            return encounter.facility.organization_id, encounter.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        return Response(
            EncounterChargeSerializer(
                list_encounter_charges(
                    encounter_id=request.query_params.get("encounter_id"),
                    patient_id=request.query_params.get("patient_id"),
                    facility_id=request.query_params.get("facility_id"),
                    status=request.query_params.get("status"),
                    source_type=request.query_params.get("source_type"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = EncounterChargeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            charge = create_encounter_charge(
                **serializer.validated_data,
                created_by_id=request.user.id,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(EncounterChargeSerializer(charge).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        charge = get_encounter_charge_by_id(pk)
        if charge is None:
            return Response(
                {"detail": "Encounter charge not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(EncounterChargeSerializer(charge).data)

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        serializer = EncounterChargeVoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            charge = void_encounter_charge(
                charge_id=pk,
                voided_by_id=request.user.id,
                **serializer.validated_data,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(EncounterChargeSerializer(charge).data)


@extend_schema(tags=[BILLING_DOCS_TAG])
class InvoiceViewSet(BillingBaseViewSet):
    queryset = Invoice.objects.all()
    permission_map = {
        "list": "billing_invoice.view",
        "retrieve": "billing_invoice.view",
        "create": "billing_invoice.create",
        "cancel": "billing_invoice.cancel",
        "settle": "billing_payment.create",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            encounter = get_encounter_by_id(request.data.get("encounter_id"))
        elif self.action in {"retrieve", "cancel", "settle"}:
            invoice = get_invoice_by_id(self.kwargs.get("pk"))
            return (
                (invoice.facility.organization_id, invoice.facility_id) if invoice else (None, None)
            )
        else:
            encounter = get_encounter_by_id(request.query_params.get("encounter_id"))
        if encounter:
            return encounter.facility.organization_id, encounter.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        return Response(
            InvoiceSerializer(
                list_invoices(
                    facility_id=request.query_params.get("facility_id"),
                    patient_id=request.query_params.get("patient_id"),
                    encounter_id=request.query_params.get("encounter_id"),
                    status=request.query_params.get("status"),
                    search=request.query_params.get("search"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = InvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invoice = generate_invoice_from_charges(
                **serializer.validated_data,
                created_by_id=request.user.id,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        invoice = get_invoice_by_id(pk)
        if invoice is None:
            return Response({"detail": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(InvoiceSerializer(invoice).data)

    @action(detail=True, methods=["post"])
    def settle(self, request, pk=None):
        serializer = InvoiceSettleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment = settle_invoice(
                invoice_id=pk,
                received_by_id=request.user.id,
                **serializer.validated_data,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        serializer = InvoiceCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invoice = cancel_invoice(invoice_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(InvoiceSerializer(invoice).data)


@extend_schema(tags=[BILLING_DOCS_TAG])
class InvoiceItemViewSet(BillingBaseViewSet):
    queryset = InvoiceItem.objects.all()
    permission_map = {
        "list": "billing_invoice.view",
        "retrieve": "billing_invoice.view",
    }

    def get_permission_scope(self, request):
        item = get_invoice_item_by_id(self.kwargs.get("pk")) if self.action != "list" else None
        invoice = (
            item.invoice if item else get_invoice_by_id(request.query_params.get("invoice_id"))
        )
        return (invoice.facility.organization_id, invoice.facility_id) if invoice else (None, None)

    def list(self, request):
        return Response(
            InvoiceItemSerializer(
                list_invoice_items(invoice_id=request.query_params.get("invoice_id")), many=True
            ).data
        )

    def retrieve(self, request, pk=None):
        item = get_invoice_item_by_id(pk)
        if item is None:
            return Response({"detail": "Invoice item not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(InvoiceItemSerializer(item).data)


@extend_schema(tags=[BILLING_DOCS_TAG])
class PaymentViewSet(BillingBaseViewSet):
    queryset = Payment.objects.all()
    permission_map = {
        "list": "billing_payment.view",
        "retrieve": "billing_payment.view",
    }

    def get_permission_scope(self, request):
        payment = get_payment_by_id(self.kwargs.get("pk")) if self.action != "list" else None
        if payment:
            return payment.facility.organization_id, payment.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        return Response(
            PaymentSerializer(
                list_payments(
                    facility_id=request.query_params.get("facility_id"),
                    patient_id=request.query_params.get("patient_id"),
                    status=request.query_params.get("status"),
                    search=request.query_params.get("search"),
                ),
                many=True,
            ).data
        )

    def retrieve(self, request, pk=None):
        payment = get_payment_by_id(pk)
        if payment is None:
            return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PaymentSerializer(payment).data)


@extend_schema(tags=[BILLING_DOCS_TAG])
class PaymentRefundViewSet(BillingBaseViewSet):
    queryset = PaymentRefund.objects.all()
    permission_map = {
        "list": "billing_refund.view",
        "retrieve": "billing_refund.view",
        "create": "billing_refund.create",
        "complete": "billing_refund.complete",
    }

    def get_permission_scope(self, request):
        refund = (
            get_payment_refund_by_id(self.kwargs.get("pk"))
            if self.action not in {"list", "create"}
            else None
        )
        payment = (
            get_payment_by_id(request.data.get("payment_id")) if self.action == "create" else None
        )
        if refund:
            return refund.payment.facility.organization_id, refund.payment.facility_id
        if payment:
            return payment.facility.organization_id, payment.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        return Response(
            PaymentRefundSerializer(
                list_payment_refunds(
                    payment_id=request.query_params.get("payment_id"),
                    status=request.query_params.get("status"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = PaymentRefundCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refund = request_payment_refund(
                **serializer.validated_data,
                requested_by_id=request.user.id,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PaymentRefundSerializer(refund).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        refund = get_payment_refund_by_id(pk)
        if refund is None:
            return Response(
                {"detail": "Payment refund not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(PaymentRefundSerializer(refund).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        serializer = PaymentRefundCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refund = complete_payment_refund(refund_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PaymentRefundSerializer(refund).data)
