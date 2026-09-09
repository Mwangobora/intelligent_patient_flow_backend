from __future__ import annotations

from django.db.models import Q

from apps.pharmacy.models import Medication, MedicationDispense, Prescription, PrescriptionItem


def list_medications(*, organization_id=None, is_active: bool | None = None, search=None):
    queryset = Medication.objects.select_related("organization")
    if organization_id:
        queryset = queryset.filter(organization_id=organization_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(
            Q(code__icontains=search)
            | Q(generic_name__icontains=search)
            | Q(brand_name__icontains=search)
        )
    return queryset.order_by("generic_name", "brand_name")


def get_medication_by_id(medication_id):
    return list_medications().filter(pk=medication_id).first()


def base_prescription_queryset():
    return Prescription.objects.select_related(
        "encounter",
        "encounter__facility",
        "encounter__facility__organization",
        "encounter__patient",
        "prescribed_by_practitioner_facility_assignment__practitioner",
        "cancelled_by",
    ).prefetch_related("items", "items__medication", "items__dispenses")


def list_prescriptions(
    *,
    facility_id=None,
    patient_id=None,
    encounter_id=None,
    status=None,
    search=None,
):
    queryset = base_prescription_queryset()
    if facility_id:
        queryset = queryset.filter(encounter__facility_id=facility_id)
    if patient_id:
        queryset = queryset.filter(encounter__patient_id=patient_id)
    if encounter_id:
        queryset = queryset.filter(encounter_id=encounter_id)
    if status:
        queryset = queryset.filter(status=status)
    if search:
        queryset = queryset.filter(
            Q(prescription_number__icontains=search)
            | Q(encounter__encounter_number__icontains=search)
            | Q(encounter__patient__patient_number__icontains=search)
            | Q(encounter__patient__first_name__icontains=search)
            | Q(encounter__patient__last_name__icontains=search)
        )
    return queryset.order_by("-prescribed_at")


def get_prescription_by_id(prescription_id):
    return base_prescription_queryset().filter(pk=prescription_id).first()


def list_prescription_items(*, prescription_id=None, medication_id=None):
    queryset = PrescriptionItem.objects.select_related(
        "prescription",
        "prescription__encounter",
        "prescription__encounter__facility",
        "prescription__encounter__patient",
        "medication",
    ).prefetch_related("dispenses")
    if prescription_id:
        queryset = queryset.filter(prescription_id=prescription_id)
    if medication_id:
        queryset = queryset.filter(medication_id=medication_id)
    return queryset.order_by("created_at")


def get_prescription_item_by_id(item_id):
    return list_prescription_items().filter(pk=item_id).first()


def list_medication_dispenses(
    *,
    prescription_item_id=None,
    prescription_id=None,
    status=None,
):
    queryset = MedicationDispense.objects.select_related(
        "prescription_item",
        "prescription_item__prescription",
        "prescription_item__prescription__encounter",
        "prescription_item__prescription__encounter__facility",
        "prescription_item__medication",
        "dispensed_by_practitioner_facility_assignment__practitioner",
    )
    if prescription_item_id:
        queryset = queryset.filter(prescription_item_id=prescription_item_id)
    if prescription_id:
        queryset = queryset.filter(prescription_item__prescription_id=prescription_id)
    if status:
        queryset = queryset.filter(status=status)
    return queryset.order_by("-dispensed_at")


def get_medication_dispense_by_id(dispense_id):
    return list_medication_dispenses().filter(pk=dispense_id).first()
