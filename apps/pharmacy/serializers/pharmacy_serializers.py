from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.pharmacy.models import Medication, MedicationDispense, Prescription, PrescriptionItem


def practitioner_name(assignment) -> str | None:
    if assignment is None:
        return None
    practitioner = assignment.practitioner
    return " ".join(part for part in [practitioner.first_name, practitioner.last_name] if part)


def dispensed_quantity(item) -> Decimal:
    total = Decimal("0")
    for dispense in item.dispenses.all():
        if dispense.status != MedicationDispense.Status.CANCELLED:
            total += dispense.quantity_dispensed
    return total


class MedicationSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = Medication
        fields = [
            "id",
            "organization",
            "organization_name",
            "code",
            "generic_name",
            "brand_name",
            "strength",
            "strength_unit",
            "dosage_form",
            "route_default",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class MedicationWriteSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    code = serializers.CharField(max_length=50)
    generic_name = serializers.CharField(max_length=200)
    brand_name = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=200
    )
    strength = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=80
    )
    strength_unit = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=50
    )
    dosage_form = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=80
    )
    route_default = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=80
    )
    is_active = serializers.BooleanField(required=False)


class PrescriptionItemPayloadSerializer(serializers.Serializer):
    medication_id = serializers.UUIDField()
    dose = serializers.DecimalField(
        required=False, allow_null=True, max_digits=12, decimal_places=3, min_value=Decimal("0.001")
    )
    dose_unit = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=50
    )
    route = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=80)
    frequency = serializers.CharField(max_length=100)
    duration_value = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    duration_unit = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=30
    )
    quantity_prescribed = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001")
    )
    instructions = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PrescriptionItemSerializer(serializers.ModelSerializer):
    medication_code = serializers.CharField(source="medication.code", read_only=True)
    medication_name = serializers.CharField(source="medication.generic_name", read_only=True)
    medication_brand_name = serializers.CharField(source="medication.brand_name", read_only=True)
    quantity_dispensed = serializers.SerializerMethodField()
    quantity_remaining = serializers.SerializerMethodField()

    class Meta:
        model = PrescriptionItem
        fields = [
            "id",
            "prescription",
            "medication",
            "medication_code",
            "medication_name",
            "medication_brand_name",
            "dose",
            "dose_unit",
            "route",
            "frequency",
            "duration_value",
            "duration_unit",
            "quantity_prescribed",
            "quantity_dispensed",
            "quantity_remaining",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_quantity_dispensed(self, obj):
        return f"{dispensed_quantity(obj):.3f}"

    def get_quantity_remaining(self, obj):
        remaining = obj.quantity_prescribed - dispensed_quantity(obj)
        return f"{max(remaining, Decimal('0')):.3f}"


class PrescriptionSerializer(serializers.ModelSerializer):
    facility = serializers.UUIDField(source="encounter.facility_id", read_only=True)
    facility_name = serializers.CharField(source="encounter.facility.name", read_only=True)
    patient = serializers.UUIDField(source="encounter.patient_id", read_only=True)
    patient_number = serializers.CharField(
        source="encounter.patient.patient_number", read_only=True
    )
    patient_name = serializers.SerializerMethodField()
    encounter_number = serializers.CharField(source="encounter.encounter_number", read_only=True)
    prescribed_by_name = serializers.SerializerMethodField()
    items = PrescriptionItemSerializer(many=True, read_only=True)

    class Meta:
        model = Prescription
        fields = [
            "id",
            "encounter",
            "encounter_number",
            "facility",
            "facility_name",
            "patient",
            "patient_number",
            "patient_name",
            "prescription_number",
            "prescribed_by_practitioner_facility_assignment",
            "prescribed_by_name",
            "status",
            "prescribed_at",
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

    def get_prescribed_by_name(self, obj):
        return practitioner_name(obj.prescribed_by_practitioner_facility_assignment)


class PrescriptionCreateSerializer(serializers.Serializer):
    encounter_id = serializers.UUIDField()
    prescribed_by_practitioner_facility_assignment_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=Prescription.Status.choices, required=False)
    prescribed_at = serializers.DateTimeField(required=False, allow_null=True)
    items = PrescriptionItemPayloadSerializer(many=True, min_length=1)


class PrescriptionCancelSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(max_length=250)
    cancelled_at = serializers.DateTimeField(required=False, allow_null=True)


class MedicationDispenseSerializer(serializers.ModelSerializer):
    prescription = serializers.UUIDField(source="prescription_item.prescription_id", read_only=True)
    prescription_number = serializers.CharField(
        source="prescription_item.prescription.prescription_number", read_only=True
    )
    medication_name = serializers.CharField(
        source="prescription_item.medication.generic_name", read_only=True
    )
    dispensed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MedicationDispense
        fields = [
            "id",
            "prescription",
            "prescription_number",
            "prescription_item",
            "medication_name",
            "stock_batch_id",
            "quantity_dispensed",
            "dispensed_by_practitioner_facility_assignment",
            "dispensed_by_name",
            "dispensed_at",
            "status",
            "created_at",
        ]
        read_only_fields = fields

    def get_dispensed_by_name(self, obj):
        return practitioner_name(obj.dispensed_by_practitioner_facility_assignment)


class MedicationDispenseCreateSerializer(serializers.Serializer):
    prescription_item_id = serializers.UUIDField()
    stock_batch_id = serializers.UUIDField(required=False, allow_null=True)
    quantity_dispensed = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001")
    )
    dispensed_by_practitioner_facility_assignment_id = serializers.UUIDField()
    dispensed_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
