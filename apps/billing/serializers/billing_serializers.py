from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.billing.models import (
    EncounterCharge,
    Invoice,
    InvoiceItem,
    Payment,
    PaymentRefund,
    Service,
    ServicePrice,
)


class ServiceSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Service
        fields = [
            "id",
            "organization",
            "organization_name",
            "code",
            "name",
            "description",
            "service_category",
            "is_active",
            "created_at",
            "updated_at",
        ]


class ServiceWriteSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    service_category = serializers.ChoiceField(choices=Service.Category.choices)
    is_active = serializers.BooleanField(required=False)


class ServicePriceSerializer(serializers.ModelSerializer):
    service_code = serializers.CharField(source="service.code", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True)

    class Meta:
        model = ServicePrice
        fields = [
            "id",
            "service",
            "service_code",
            "service_name",
            "facility",
            "facility_name",
            "amount",
            "currency",
            "effective_from",
            "effective_to",
            "is_active",
            "created_at",
            "updated_at",
        ]


class ServicePriceWriteSerializer(serializers.Serializer):
    service_id = serializers.UUIDField()
    facility_id = serializers.UUIDField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.00"))
    currency = serializers.CharField(max_length=3, required=False)
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)


class EncounterChargeSerializer(serializers.ModelSerializer):
    service_code = serializers.CharField(source="service.code", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    encounter_number = serializers.CharField(source="encounter.encounter_number", read_only=True)
    patient = serializers.UUIDField(source="encounter.patient_id", read_only=True)
    patient_number = serializers.CharField(
        source="encounter.patient.patient_number", read_only=True
    )
    facility = serializers.UUIDField(source="encounter.facility_id", read_only=True)
    facility_name = serializers.CharField(source="encounter.facility.name", read_only=True)

    class Meta:
        model = EncounterCharge
        fields = [
            "id",
            "encounter",
            "encounter_number",
            "facility",
            "facility_name",
            "patient",
            "patient_number",
            "service",
            "service_code",
            "service_name",
            "quantity",
            "unit_price",
            "amount",
            "source_type",
            "source_reference_id",
            "status",
            "performed_at",
            "created_by",
            "voided_at",
            "voided_by",
            "void_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EncounterChargeCreateSerializer(serializers.Serializer):
    encounter_id = serializers.UUIDField()
    service_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    unit_price = serializers.DecimalField(
        required=False, allow_null=True, max_digits=18, decimal_places=2, min_value=Decimal("0.00")
    )
    source_type = serializers.ChoiceField(choices=EncounterCharge.SourceType.choices)
    source_reference_id = serializers.UUIDField(required=False, allow_null=True)
    performed_at = serializers.DateTimeField(required=False, allow_null=True)


class EncounterChargeVoidSerializer(serializers.Serializer):
    void_reason = serializers.CharField(max_length=250)
    voided_at = serializers.DateTimeField(required=False, allow_null=True)


class InvoiceItemSerializer(serializers.ModelSerializer):
    service_code = serializers.CharField(source="service.code", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)

    class Meta:
        model = InvoiceItem
        fields = [
            "id",
            "invoice",
            "encounter_charge",
            "service",
            "service_code",
            "service_name",
            "description",
            "quantity",
            "unit_price",
            "discount_amount",
            "tax_amount",
            "line_total",
            "created_at",
        ]
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)
    patient_name = serializers.SerializerMethodField()
    encounter_number = serializers.CharField(source="encounter.encounter_number", read_only=True)
    items = InvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "facility",
            "facility_name",
            "patient",
            "patient_number",
            "patient_name",
            "encounter",
            "encounter_number",
            "invoice_number",
            "status",
            "subtotal",
            "discount_amount",
            "tax_amount",
            "total_amount",
            "paid_amount",
            "balance_amount",
            "issued_at",
            "due_at",
            "created_by",
            "created_at",
            "updated_at",
            "items",
        ]
        read_only_fields = fields

    def get_patient_name(self, obj):
        return " ".join(
            part
            for part in [obj.patient.first_name, obj.patient.middle_name, obj.patient.last_name]
            if part
        )


class InvoiceCreateSerializer(serializers.Serializer):
    encounter_id = serializers.UUIDField()
    charge_ids = serializers.ListField(child=serializers.UUIDField(), required=False, min_length=1)
    issued_at = serializers.DateTimeField(required=False, allow_null=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)


class InvoiceCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=250)


class InvoiceSettleSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.CharField(max_length=3, required=False)
    payment_method = serializers.ChoiceField(choices=Payment.Method.choices)
    transaction_reference = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=150
    )
    received_at = serializers.DateTimeField(required=False, allow_null=True)


class PaymentSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "facility",
            "facility_name",
            "patient",
            "patient_number",
            "payment_number",
            "amount",
            "currency",
            "payment_method",
            "transaction_reference",
            "status",
            "received_by",
            "received_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PaymentRefundSerializer(serializers.ModelSerializer):
    payment_number = serializers.CharField(source="payment.payment_number", read_only=True)

    class Meta:
        model = PaymentRefund
        fields = [
            "id",
            "payment",
            "payment_number",
            "amount",
            "reason",
            "status",
            "requested_by",
            "approved_by",
            "refunded_at",
            "transaction_reference",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PaymentRefundCreateSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    reason = serializers.CharField(max_length=250)


class PaymentRefundCompleteSerializer(serializers.Serializer):
    approved_by_id = serializers.UUIDField(required=False, allow_null=True)
    transaction_reference = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=150
    )
    refunded_at = serializers.DateTimeField(required=False, allow_null=True)
