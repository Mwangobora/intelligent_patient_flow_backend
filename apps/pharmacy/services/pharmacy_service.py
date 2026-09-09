from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.clinical.models import Encounter
from apps.pharmacy.models import Medication, MedicationDispense, Prescription, PrescriptionItem
from apps.practitioners.models import PractitionerFacilityAssignment
from apps.scheduling.services._crypto import encrypt_sensitive_value
from common.exceptions import ConflictError, NotFoundError, ValidationError

TERMINAL_PRESCRIPTION_STATUSES = {
    Prescription.Status.CANCELLED,
    Prescription.Status.DISPENSED,
}


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _encrypt_optional(value: str | None) -> str | None:
    cleaned = _optional_text(value)
    return encrypt_sensitive_value(cleaned) if cleaned else None


def _normalize_code(code: str) -> str:
    cleaned = code.strip().upper()
    if not cleaned:
        raise ValidationError("Code is required.")
    return cleaned


def _get_encounter(encounter_id, *, for_update=False) -> Encounter:
    queryset = Encounter.objects.select_related("facility", "facility__organization", "patient")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    encounter = queryset.filter(pk=encounter_id).first()
    if encounter is None:
        raise NotFoundError("Encounter not found.")
    return encounter


def _get_assignment(assignment_id) -> PractitionerFacilityAssignment:
    assignment = (
        PractitionerFacilityAssignment.objects.select_related("facility", "practitioner")
        .filter(pk=assignment_id, is_active=True)
        .first()
    )
    if assignment is None:
        raise NotFoundError("Active practitioner facility assignment not found.")
    return assignment


def _get_medication(medication_id, *, for_update=False) -> Medication:
    queryset = Medication.objects.select_related("organization")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    medication = queryset.filter(pk=medication_id).first()
    if medication is None:
        raise NotFoundError("Medication not found.")
    return medication


def _get_prescription(prescription_id, *, for_update=False) -> Prescription:
    queryset = Prescription.objects.select_related(
        "encounter", "encounter__facility", "encounter__facility__organization"
    ).prefetch_related("items", "items__dispenses")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    prescription = queryset.filter(pk=prescription_id).first()
    if prescription is None:
        raise NotFoundError("Prescription not found.")
    return prescription


def _get_prescription_item(item_id, *, for_update=False) -> PrescriptionItem:
    queryset = PrescriptionItem.objects.select_related(
        "prescription",
        "prescription__encounter",
        "prescription__encounter__facility",
        "prescription__encounter__facility__organization",
        "medication",
    ).prefetch_related("dispenses")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    item = queryset.filter(pk=item_id).first()
    if item is None:
        raise NotFoundError("Prescription item not found.")
    return item


def _validate_assignment_facility(*, assignment, facility_id):
    if assignment.facility_id != facility_id:
        raise ValidationError("Practitioner assignment must belong to the encounter facility.")


def _dispensed_total(item: PrescriptionItem) -> Decimal:
    total = Decimal("0")
    for dispense in item.dispenses.all():
        if dispense.status != MedicationDispense.Status.CANCELLED:
            total += dispense.quantity_dispensed
    return total


def _refresh_prescription_status(prescription: Prescription) -> Prescription:
    if prescription.status == Prescription.Status.CANCELLED:
        return prescription
    items = list(
        PrescriptionItem.objects.prefetch_related("dispenses").filter(prescription=prescription)
    )
    if not items:
        prescription.status = Prescription.Status.DRAFT
    else:
        totals = [_dispensed_total(item) for item in items]
        if all(
            total >= item.quantity_prescribed for item, total in zip(items, totals, strict=True)
        ):
            prescription.status = Prescription.Status.DISPENSED
        elif any(total > 0 for total in totals):
            prescription.status = Prescription.Status.PARTIALLY_DISPENSED
        else:
            prescription.status = Prescription.Status.ACTIVE
    prescription.save(update_fields=["status", "updated_at"])
    return prescription


def _next_prescription_number(*, prescribed_at) -> str:
    prefix = f"RX-{prescribed_at:%Y%m%d}-"
    latest = (
        Prescription.objects.select_for_update()
        .filter(prescription_number__startswith=prefix)
        .order_by("-prescription_number")
        .values_list("prescription_number", flat=True)
        .first()
    )
    next_number = int(latest.rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"{prefix}{next_number:04d}"


@transaction.atomic
def create_medication(**data) -> Medication:
    try:
        return Medication.objects.create(
            organization_id=data["organization_id"],
            code=_normalize_code(data["code"]),
            generic_name=data["generic_name"].strip(),
            brand_name=_optional_text(data.get("brand_name")),
            strength=_optional_text(data.get("strength")),
            strength_unit=_optional_text(data.get("strength_unit")),
            dosage_form=_optional_text(data.get("dosage_form")),
            route_default=_optional_text(data.get("route_default")),
            is_active=data.get("is_active", True),
        )
    except IntegrityError as exc:
        raise ConflictError(
            "A medication with this code already exists for this organization."
        ) from exc


@transaction.atomic
def update_medication(*, medication_id, **updates) -> Medication:
    medication = _get_medication(medication_id, for_update=True)
    for field in [
        "generic_name",
        "brand_name",
        "strength",
        "strength_unit",
        "dosage_form",
        "route_default",
        "is_active",
    ]:
        if field in updates:
            value = updates[field]
            if field != "is_active":
                value = _optional_text(value)
            setattr(medication, field, value)
    if "code" in updates:
        medication.code = _normalize_code(updates["code"])
    if "organization_id" in updates:
        medication.organization_id = updates["organization_id"]
    try:
        medication.save()
    except IntegrityError as exc:
        raise ConflictError(
            "A medication with this code already exists for this organization."
        ) from exc
    return medication


@transaction.atomic
def create_prescription(
    *,
    encounter_id,
    prescribed_by_practitioner_facility_assignment_id,
    items,
    status=Prescription.Status.ACTIVE,
    prescribed_at=None,
) -> Prescription:
    encounter = _get_encounter(encounter_id, for_update=True)
    assignment = _get_assignment(prescribed_by_practitioner_facility_assignment_id)
    _validate_assignment_facility(assignment=assignment, facility_id=encounter.facility_id)
    prescribed_time = prescribed_at or timezone.now()
    medication_ids = [item["medication_id"] for item in items]
    if len(medication_ids) != len(set(medication_ids)):
        raise ValidationError("Duplicate medications are not allowed in one prescription.")

    medications = {
        medication.id: medication
        for medication in [_get_medication(med_id) for med_id in medication_ids]
    }
    for medication in medications.values():
        if medication.organization_id != encounter.facility.organization_id:
            raise ValidationError("Medication must belong to the encounter organization.")
        if not medication.is_active:
            raise ValidationError("Inactive medication cannot be prescribed.")

    try:
        prescription = Prescription.objects.create(
            encounter=encounter,
            prescription_number=_next_prescription_number(prescribed_at=prescribed_time),
            prescribed_by_practitioner_facility_assignment=assignment,
            status=status,
            prescribed_at=prescribed_time,
        )
        PrescriptionItem.objects.bulk_create(
            [
                PrescriptionItem(
                    prescription=prescription,
                    medication=medications[item["medication_id"]],
                    dose=item.get("dose"),
                    dose_unit=_optional_text(item.get("dose_unit")),
                    route=_optional_text(item.get("route"))
                    or medications[item["medication_id"]].route_default,
                    frequency=item["frequency"].strip(),
                    duration_value=item.get("duration_value"),
                    duration_unit=_optional_text(item.get("duration_unit")),
                    quantity_prescribed=item["quantity_prescribed"],
                    instructions_encrypted=_encrypt_optional(item.get("instructions")),
                )
                for item in items
            ]
        )
    except IntegrityError as exc:
        raise ConflictError(
            "Prescription could not be created because a conflicting record exists."
        ) from exc
    return prescription


@transaction.atomic
def cancel_prescription(
    *, prescription_id, cancelled_by_id=None, cancellation_reason, cancelled_at=None
) -> Prescription:
    prescription = _get_prescription(prescription_id, for_update=True)
    if prescription.status in {
        Prescription.Status.CANCELLED,
        Prescription.Status.DISPENSED,
        Prescription.Status.PARTIALLY_DISPENSED,
    }:
        raise ConflictError("This prescription cannot be cancelled.")
    reason = _optional_text(cancellation_reason)
    if not reason:
        raise ValidationError("Cancellation reason is required.")
    prescription.status = Prescription.Status.CANCELLED
    prescription.cancelled_at = cancelled_at or timezone.now()
    prescription.cancelled_by_id = cancelled_by_id
    prescription.cancellation_reason = reason
    prescription.save()
    return prescription


@transaction.atomic
def dispense_medication(
    *,
    prescription_item_id,
    quantity_dispensed,
    dispensed_by_practitioner_facility_assignment_id,
    stock_batch_id=None,
    dispensed_at=None,
    notes=None,
) -> MedicationDispense:
    item = _get_prescription_item(prescription_item_id, for_update=True)
    prescription = _get_prescription(item.prescription_id, for_update=True)
    if prescription.status in {Prescription.Status.CANCELLED, Prescription.Status.DISPENSED}:
        raise ConflictError("Medication cannot be dispensed for this prescription.")
    dispenser = _get_assignment(dispensed_by_practitioner_facility_assignment_id)
    _validate_assignment_facility(
        assignment=dispenser, facility_id=prescription.encounter.facility_id
    )
    remaining = item.quantity_prescribed - _dispensed_total(item)
    if quantity_dispensed > remaining:
        raise ValidationError("Dispensed quantity cannot exceed remaining prescribed quantity.")
    dispense_status = (
        MedicationDispense.Status.DISPENSED
        if quantity_dispensed == remaining
        else MedicationDispense.Status.PARTIALLY_DISPENSED
    )
    dispense = MedicationDispense.objects.create(
        prescription_item=item,
        stock_batch_id=stock_batch_id,
        quantity_dispensed=quantity_dispensed,
        dispensed_by_practitioner_facility_assignment=dispenser,
        dispensed_at=dispensed_at or timezone.now(),
        status=dispense_status,
        notes_encrypted=_encrypt_optional(notes),
    )
    _refresh_prescription_status(prescription)
    return dispense
