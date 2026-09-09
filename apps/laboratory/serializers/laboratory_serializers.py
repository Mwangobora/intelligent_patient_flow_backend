from __future__ import annotations

from rest_framework import serializers

from apps.laboratory.models import (
    LabOrder,
    LabOrderItem,
    LabResultValue,
    LabSpecimen,
    LabTest,
    LabTestComponent,
)


def practitioner_name(assignment) -> str | None:
    if assignment is None:
        return None
    practitioner = assignment.practitioner
    return " ".join(part for part in [practitioner.first_name, practitioner.last_name] if part)


class LabTestSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = LabTest
        fields = [
            "id",
            "organization",
            "organization_name",
            "code",
            "name",
            "description",
            "specimen_type",
            "turnaround_minutes",
            "billing_service_id",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class LabTestWriteSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    specimen_type = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=80
    )
    turnaround_minutes = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    billing_service_id = serializers.UUIDField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)


class LabTestComponentSerializer(serializers.ModelSerializer):
    lab_test_code = serializers.CharField(source="lab_test.code", read_only=True)
    lab_test_name = serializers.CharField(source="lab_test.name", read_only=True)

    class Meta:
        model = LabTestComponent
        fields = [
            "id",
            "lab_test",
            "lab_test_code",
            "lab_test_name",
            "code",
            "name",
            "unit",
            "reference_low",
            "reference_high",
            "display_order",
            "is_active",
            "created_at",
            "updated_at",
        ]


class LabTestComponentWriteSerializer(serializers.Serializer):
    lab_test_id = serializers.UUIDField()
    code = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=200)
    unit = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    reference_low = serializers.DecimalField(
        required=False, allow_null=True, max_digits=18, decimal_places=4
    )
    reference_high = serializers.DecimalField(
        required=False, allow_null=True, max_digits=18, decimal_places=4
    )
    display_order = serializers.IntegerField(required=False, min_value=0)
    is_active = serializers.BooleanField(required=False)


class LabOrderItemSerializer(serializers.ModelSerializer):
    lab_test_code = serializers.CharField(source="lab_test.code", read_only=True)
    lab_test_name = serializers.CharField(source="lab_test.name", read_only=True)

    class Meta:
        model = LabOrderItem
        fields = [
            "id",
            "lab_order",
            "lab_test",
            "lab_test_code",
            "lab_test_name",
            "status",
            "ordered_at",
            "collected_at",
            "processing_started_at",
            "resulted_at",
            "verified_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class LabOrderSerializer(serializers.ModelSerializer):
    facility = serializers.UUIDField(source="encounter.facility_id", read_only=True)
    facility_name = serializers.CharField(source="encounter.facility.name", read_only=True)
    patient = serializers.UUIDField(source="encounter.patient_id", read_only=True)
    patient_number = serializers.CharField(
        source="encounter.patient.patient_number", read_only=True
    )
    patient_name = serializers.SerializerMethodField()
    encounter_number = serializers.CharField(source="encounter.encounter_number", read_only=True)
    specialty_name = serializers.CharField(
        source="encounter.facility_specialty.specialty.name", read_only=True
    )
    ordered_by_name = serializers.SerializerMethodField()
    items = LabOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = LabOrder
        fields = [
            "id",
            "encounter",
            "encounter_number",
            "facility",
            "facility_name",
            "patient",
            "patient_number",
            "patient_name",
            "specialty_name",
            "ordered_by_practitioner_facility_assignment",
            "ordered_by_name",
            "order_number",
            "priority",
            "status",
            "ordered_at",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_patient_name(self, obj):
        patient = obj.encounter.patient
        return " ".join(
            part for part in [patient.first_name, patient.middle_name, patient.last_name] if part
        )

    def get_ordered_by_name(self, obj):
        return practitioner_name(obj.ordered_by_practitioner_facility_assignment)


class LabOrderCreateSerializer(serializers.Serializer):
    encounter_id = serializers.UUIDField()
    ordered_by_practitioner_facility_assignment_id = serializers.UUIDField()
    lab_test_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    priority = serializers.ChoiceField(
        choices=LabOrder.Priority.choices, default=LabOrder.Priority.ROUTINE
    )
    clinical_notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ordered_at = serializers.DateTimeField(required=False, allow_null=True)


class LabOrderCancelSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(max_length=250)
    cancelled_at = serializers.DateTimeField(required=False, allow_null=True)


class LabOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=LabOrder.Status.choices)


class LabOrderItemStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=LabOrderItem.Status.choices)
    occurred_at = serializers.DateTimeField(required=False, allow_null=True)


class LabSpecimenSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(
        source="lab_order_item.lab_order.order_number", read_only=True
    )
    lab_test_name = serializers.CharField(source="lab_order_item.lab_test.name", read_only=True)
    collected_by_name = serializers.SerializerMethodField()
    received_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LabSpecimen
        fields = [
            "id",
            "lab_order_item",
            "order_number",
            "lab_test_name",
            "specimen_number",
            "specimen_type",
            "collected_by_practitioner_facility_assignment",
            "collected_by_name",
            "collected_at",
            "received_by_practitioner_facility_assignment",
            "received_by_name",
            "received_at",
            "status",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_collected_by_name(self, obj):
        return practitioner_name(obj.collected_by_practitioner_facility_assignment)

    def get_received_by_name(self, obj):
        return practitioner_name(obj.received_by_practitioner_facility_assignment)


class LabSpecimenCreateSerializer(serializers.Serializer):
    lab_order_item_id = serializers.UUIDField()
    specimen_type = serializers.CharField(max_length=80)
    collected_by_practitioner_facility_assignment_id = serializers.UUIDField(
        required=False, allow_null=True
    )
    collected_at = serializers.DateTimeField(required=False, allow_null=True)


class LabSpecimenReceiveSerializer(serializers.Serializer):
    received_by_practitioner_facility_assignment_id = serializers.UUIDField()
    received_at = serializers.DateTimeField(required=False, allow_null=True)


class LabSpecimenRejectSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(max_length=250)


class LabResultValueSerializer(serializers.ModelSerializer):
    component_code = serializers.CharField(source="lab_test_component.code", read_only=True)
    component_name = serializers.CharField(source="lab_test_component.name", read_only=True)
    order_number = serializers.CharField(
        source="lab_order_item.lab_order.order_number", read_only=True
    )
    entered_by_name = serializers.SerializerMethodField()
    verified_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LabResultValue
        fields = [
            "id",
            "lab_order_item",
            "order_number",
            "lab_test_component",
            "component_code",
            "component_name",
            "value_numeric",
            "value_text",
            "unit",
            "reference_low",
            "reference_high",
            "abnormal_flag",
            "entered_by_practitioner_facility_assignment",
            "entered_by_name",
            "entered_at",
            "verified_by_practitioner_facility_assignment",
            "verified_by_name",
            "verified_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_entered_by_name(self, obj):
        return practitioner_name(obj.entered_by_practitioner_facility_assignment)

    def get_verified_by_name(self, obj):
        return practitioner_name(obj.verified_by_practitioner_facility_assignment)


class LabResultValueCreateSerializer(serializers.Serializer):
    lab_order_item_id = serializers.UUIDField()
    lab_test_component_id = serializers.UUIDField(required=False, allow_null=True)
    value_numeric = serializers.DecimalField(
        required=False, allow_null=True, max_digits=18, decimal_places=4
    )
    value_text = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    unit = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    reference_low = serializers.DecimalField(
        required=False, allow_null=True, max_digits=18, decimal_places=4
    )
    reference_high = serializers.DecimalField(
        required=False, allow_null=True, max_digits=18, decimal_places=4
    )
    abnormal_flag = serializers.ChoiceField(
        choices=LabResultValue.AbnormalFlag.choices, default=LabResultValue.AbnormalFlag.NORMAL
    )
    entered_by_practitioner_facility_assignment_id = serializers.UUIDField()
    entered_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        has_numeric = attrs.get("value_numeric") is not None
        has_text = bool((attrs.get("value_text") or "").strip())
        if has_numeric == has_text:
            raise serializers.ValidationError("Provide exactly one result value: numeric or text.")
        return attrs


class LabResultVerifySerializer(serializers.Serializer):
    verified_by_practitioner_facility_assignment_id = serializers.UUIDField()
    verified_at = serializers.DateTimeField(required=False, allow_null=True)
