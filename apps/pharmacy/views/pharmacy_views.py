from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.clinical.selectors import get_encounter_by_id
from apps.pharmacy._helpers import translate_domain_error
from apps.pharmacy.models import Medication, MedicationDispense, Prescription, PrescriptionItem
from apps.pharmacy.selectors import (
    get_medication_by_id,
    get_medication_dispense_by_id,
    get_prescription_by_id,
    get_prescription_item_by_id,
    list_medication_dispenses,
    list_medications,
    list_prescription_items,
    list_prescriptions,
)
from apps.pharmacy.serializers import (
    MedicationDispenseCreateSerializer,
    MedicationDispenseSerializer,
    MedicationSerializer,
    MedicationWriteSerializer,
    PrescriptionCancelSerializer,
    PrescriptionCreateSerializer,
    PrescriptionItemSerializer,
    PrescriptionSerializer,
)
from apps.pharmacy.services import (
    cancel_prescription,
    create_medication,
    create_prescription,
    dispense_medication,
    update_medication,
)

from .base import PHARMACY_DOCS_TAG, PharmacyBaseViewSet, _bool_query_param


@extend_schema(tags=[PHARMACY_DOCS_TAG])
class MedicationViewSet(PharmacyBaseViewSet):
    queryset = Medication.objects.all()
    permission_map = {
        "list": "pharmacy_medication.view",
        "retrieve": "pharmacy_medication.view",
        "create": "pharmacy_medication.create",
        "partial_update": "pharmacy_medication.update",
        "deactivate": "pharmacy_medication.deactivate",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            return request.data.get("organization_id"), None
        if self.action in {"retrieve", "partial_update", "deactivate"}:
            medication = get_medication_by_id(self.kwargs.get("pk"))
            return (medication.organization_id, None) if medication else (None, None)
        return request.query_params.get("organization_id"), None

    def list(self, request):
        return Response(
            MedicationSerializer(
                list_medications(
                    organization_id=request.query_params.get("organization_id"),
                    is_active=_bool_query_param(request.query_params.get("is_active")),
                    search=request.query_params.get("search"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = MedicationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            medication = create_medication(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(MedicationSerializer(medication).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        medication = get_medication_by_id(pk)
        if medication is None:
            return Response({"detail": "Medication not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(MedicationSerializer(medication).data)

    def partial_update(self, request, pk=None):
        serializer = MedicationWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            medication = update_medication(medication_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(MedicationSerializer(medication).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        try:
            medication = update_medication(medication_id=pk, is_active=False)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(MedicationSerializer(medication).data)


@extend_schema(tags=[PHARMACY_DOCS_TAG])
class PrescriptionViewSet(PharmacyBaseViewSet):
    queryset = Prescription.objects.all()
    permission_map = {
        "list": "pharmacy_prescription.view",
        "retrieve": "pharmacy_prescription.view",
        "create": "pharmacy_prescription.create",
        "cancel": "pharmacy_prescription.cancel",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            encounter = get_encounter_by_id(request.data.get("encounter_id"))
        elif self.action in {"retrieve", "cancel"}:
            prescription = get_prescription_by_id(self.kwargs.get("pk"))
            encounter = prescription.encounter if prescription else None
        else:
            encounter = get_encounter_by_id(request.query_params.get("encounter_id"))
        if encounter:
            return encounter.facility.organization_id, encounter.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        return Response(
            PrescriptionSerializer(
                list_prescriptions(
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
        serializer = PrescriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            prescription = create_prescription(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PrescriptionSerializer(prescription).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        prescription = get_prescription_by_id(pk)
        if prescription is None:
            return Response({"detail": "Prescription not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PrescriptionSerializer(prescription).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        serializer = PrescriptionCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            prescription = cancel_prescription(
                prescription_id=pk, cancelled_by_id=request.user.id, **serializer.validated_data
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PrescriptionSerializer(prescription).data)


@extend_schema(tags=[PHARMACY_DOCS_TAG])
class PrescriptionItemViewSet(PharmacyBaseViewSet):
    queryset = PrescriptionItem.objects.all()
    permission_map = {
        "list": "pharmacy_prescription.view",
        "retrieve": "pharmacy_prescription.view",
    }

    def get_permission_scope(self, request):
        item = get_prescription_item_by_id(self.kwargs.get("pk")) if self.action != "list" else None
        if item:
            encounter = item.prescription.encounter
            return encounter.facility.organization_id, encounter.facility_id
        prescription = get_prescription_by_id(request.query_params.get("prescription_id"))
        if prescription:
            return (
                prescription.encounter.facility.organization_id,
                prescription.encounter.facility_id,
            )
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        return Response(
            PrescriptionItemSerializer(
                list_prescription_items(
                    prescription_id=request.query_params.get("prescription_id"),
                    medication_id=request.query_params.get("medication_id"),
                ),
                many=True,
            ).data
        )

    def retrieve(self, request, pk=None):
        item = get_prescription_item_by_id(pk)
        if item is None:
            return Response(
                {"detail": "Prescription item not found."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(PrescriptionItemSerializer(item).data)


@extend_schema(tags=[PHARMACY_DOCS_TAG])
class MedicationDispenseViewSet(PharmacyBaseViewSet):
    queryset = MedicationDispense.objects.all()
    permission_map = {
        "list": "pharmacy_dispense.view",
        "retrieve": "pharmacy_dispense.view",
        "create": "pharmacy_dispense.create",
    }

    def get_permission_scope(self, request):
        dispense = (
            get_medication_dispense_by_id(self.kwargs.get("pk"))
            if self.action not in {"list", "create"}
            else None
        )
        item = (
            get_prescription_item_by_id(request.data.get("prescription_item_id"))
            if self.action == "create"
            else None
        )
        if dispense:
            encounter = dispense.prescription_item.prescription.encounter
            return encounter.facility.organization_id, encounter.facility_id
        if item:
            encounter = item.prescription.encounter
            return encounter.facility.organization_id, encounter.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        return Response(
            MedicationDispenseSerializer(
                list_medication_dispenses(
                    prescription_item_id=request.query_params.get("prescription_item_id"),
                    prescription_id=request.query_params.get("prescription_id"),
                    status=request.query_params.get("status"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = MedicationDispenseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            dispense = dispense_medication(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(MedicationDispenseSerializer(dispense).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        dispense = get_medication_dispense_by_id(pk)
        if dispense is None:
            return Response({"detail": "Dispense not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(MedicationDispenseSerializer(dispense).data)
