from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.clinical.models import Encounter
from apps.laboratory.models import (
    LabOrder,
    LabOrderItem,
    LabResultValue,
    LabSpecimen,
    LabTest,
    LabTestComponent,
)
from apps.practitioners.models import PractitionerFacilityAssignment
from apps.scheduling.services._crypto import encrypt_sensitive_value
from common.exceptions import ConflictError, NotFoundError, ValidationError

TERMINAL_ORDER_STATUSES = {LabOrder.Status.CANCELLED, LabOrder.Status.VERIFIED}
TERMINAL_ITEM_STATUSES = {LabOrderItem.Status.CANCELLED, LabOrderItem.Status.VERIFIED}


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _encrypt_optional(value: str | None) -> str | None:
    cleaned = _optional_text(value)
    return encrypt_sensitive_value(cleaned) if cleaned else None


def _get_encounter(encounter_id, *, for_update=False) -> Encounter:
    queryset = Encounter.objects.select_related("facility", "facility__organization", "patient")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    encounter = queryset.filter(pk=encounter_id).first()
    if encounter is None:
        raise NotFoundError("Encounter not found.")
    return encounter


def _get_assignment(assignment_id, *, for_update=False) -> PractitionerFacilityAssignment:
    queryset = PractitionerFacilityAssignment.objects.select_related("facility", "practitioner")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    assignment = queryset.filter(pk=assignment_id, is_active=True).first()
    if assignment is None:
        raise NotFoundError("Active practitioner facility assignment not found.")
    return assignment


def _get_lab_test(test_id, *, for_update=False) -> LabTest:
    queryset = LabTest.objects.select_related("organization")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    lab_test = queryset.filter(pk=test_id).first()
    if lab_test is None:
        raise NotFoundError("Lab test not found.")
    return lab_test


def _get_order(order_id, *, for_update=False) -> LabOrder:
    queryset = LabOrder.objects.select_related(
        "encounter", "encounter__facility", "encounter__facility__organization"
    )
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    order = queryset.filter(pk=order_id).first()
    if order is None:
        raise NotFoundError("Lab order not found.")
    return order


def _get_item(item_id, *, for_update=False) -> LabOrderItem:
    queryset = LabOrderItem.objects.select_related(
        "lab_order",
        "lab_order__encounter",
        "lab_order__encounter__facility",
        "lab_order__encounter__facility__organization",
        "lab_test",
    )
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    item = queryset.filter(pk=item_id).first()
    if item is None:
        raise NotFoundError("Lab order item not found.")
    return item


def _get_component(component_id) -> LabTestComponent:
    component = LabTestComponent.objects.select_related("lab_test").filter(pk=component_id).first()
    if component is None:
        raise NotFoundError("Lab test component not found.")
    return component


def _validate_assignment_facility(*, assignment, facility_id):
    if assignment.facility_id != facility_id:
        raise ValidationError("Practitioner assignment must belong to the encounter facility.")


def _normalize_code(code: str) -> str:
    cleaned = code.strip().upper()
    if not cleaned:
        raise ValidationError("Code is required.")
    return cleaned


def _next_order_number(*, ordered_at) -> str:
    prefix = f"LAB-{ordered_at:%Y%m%d}-"
    latest = (
        LabOrder.objects.select_for_update()
        .filter(order_number__startswith=prefix)
        .order_by("-order_number")
        .values_list("order_number", flat=True)
        .first()
    )
    next_number = int(latest.rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"{prefix}{next_number:04d}"


def _next_specimen_number(*, collected_at) -> str:
    prefix = f"SPEC-{collected_at:%Y%m%d}-"
    latest = (
        LabSpecimen.objects.select_for_update()
        .filter(specimen_number__startswith=prefix)
        .order_by("-specimen_number")
        .values_list("specimen_number", flat=True)
        .first()
    )
    next_number = int(latest.rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"{prefix}{next_number:04d}"


def _refresh_order_status(order: LabOrder) -> LabOrder:
    statuses = list(order.items.values_list("status", flat=True))
    if not statuses or order.status == LabOrder.Status.CANCELLED:
        return order
    if all(status == LabOrderItem.Status.VERIFIED for status in statuses):
        order.status = LabOrder.Status.VERIFIED
    elif all(
        status in {LabOrderItem.Status.RESULTED, LabOrderItem.Status.VERIFIED}
        for status in statuses
    ):
        order.status = LabOrder.Status.RESULTED
    elif any(
        status in {LabOrderItem.Status.RESULTED, LabOrderItem.Status.VERIFIED}
        for status in statuses
    ):
        order.status = LabOrder.Status.PARTIALLY_RESULTED
    elif any(status == LabOrderItem.Status.PROCESSING for status in statuses):
        order.status = LabOrder.Status.PROCESSING
    elif any(status == LabOrderItem.Status.SAMPLE_COLLECTION for status in statuses):
        order.status = LabOrder.Status.SAMPLE_COLLECTION
    else:
        order.status = LabOrder.Status.ORDERED
    order.save(update_fields=["status", "updated_at"])
    return order


@transaction.atomic
def create_lab_test(**data) -> LabTest:
    data["code"] = _normalize_code(data["code"])
    try:
        return LabTest.objects.create(
            organization_id=data["organization_id"],
            code=data["code"],
            name=data["name"].strip(),
            description=_optional_text(data.get("description")),
            specimen_type=_optional_text(data.get("specimen_type")),
            turnaround_minutes=data.get("turnaround_minutes"),
            billing_service_id=data.get("billing_service_id"),
            is_active=data.get("is_active", True),
        )
    except IntegrityError as exc:
        raise ConflictError(
            "A lab test with this code already exists for this organization."
        ) from exc


@transaction.atomic
def update_lab_test(*, lab_test_id, **updates) -> LabTest:
    lab_test = _get_lab_test(lab_test_id, for_update=True)
    for field in [
        "name",
        "description",
        "specimen_type",
        "turnaround_minutes",
        "billing_service_id",
        "is_active",
    ]:
        if field in updates:
            value = updates[field]
            if field in {"description", "specimen_type"}:
                value = _optional_text(value)
            setattr(lab_test, field, value)
    if "code" in updates:
        lab_test.code = _normalize_code(updates["code"])
    if "organization_id" in updates:
        lab_test.organization_id = updates["organization_id"]
    try:
        lab_test.save()
    except IntegrityError as exc:
        raise ConflictError(
            "A lab test with this code already exists for this organization."
        ) from exc
    return lab_test


@transaction.atomic
def create_lab_test_component(**data) -> LabTestComponent:
    lab_test = _get_lab_test(data["lab_test_id"])
    try:
        return LabTestComponent.objects.create(
            lab_test=lab_test,
            code=_normalize_code(data["code"]),
            name=data["name"].strip(),
            unit=_optional_text(data.get("unit")),
            reference_low=data.get("reference_low"),
            reference_high=data.get("reference_high"),
            display_order=data.get("display_order", 0),
            is_active=data.get("is_active", True),
        )
    except IntegrityError as exc:
        raise ConflictError("A component with this code already exists for this lab test.") from exc


@transaction.atomic
def update_lab_test_component(*, component_id, **updates) -> LabTestComponent:
    component = _get_component(component_id)
    for field in ["name", "unit", "reference_low", "reference_high", "display_order", "is_active"]:
        if field in updates:
            value = updates[field]
            if field == "unit":
                value = _optional_text(value)
            setattr(component, field, value)
    if "code" in updates:
        component.code = _normalize_code(updates["code"])
    if "lab_test_id" in updates:
        component.lab_test = _get_lab_test(updates["lab_test_id"])
    try:
        component.save()
    except IntegrityError as exc:
        raise ConflictError("A component with this code already exists for this lab test.") from exc
    return component


@transaction.atomic
def create_lab_order(
    *,
    encounter_id,
    ordered_by_practitioner_facility_assignment_id,
    lab_test_ids,
    priority=LabOrder.Priority.ROUTINE,
    clinical_notes=None,
    ordered_at=None,
) -> LabOrder:
    encounter = _get_encounter(encounter_id, for_update=True)
    assignment = _get_assignment(ordered_by_practitioner_facility_assignment_id)
    _validate_assignment_facility(assignment=assignment, facility_id=encounter.facility_id)
    ordered_time = ordered_at or timezone.now()
    unique_test_ids = list(dict.fromkeys(lab_test_ids))
    if len(unique_test_ids) != len(lab_test_ids):
        raise ValidationError("Duplicate lab tests are not allowed in one order.")

    lab_tests = [_get_lab_test(test_id) for test_id in unique_test_ids]
    for lab_test in lab_tests:
        if lab_test.organization_id != encounter.facility.organization_id:
            raise ValidationError("Lab tests must belong to the encounter organization.")
        if not lab_test.is_active:
            raise ValidationError("Inactive lab tests cannot be ordered.")

    try:
        order = LabOrder.objects.create(
            encounter=encounter,
            ordered_by_practitioner_facility_assignment=assignment,
            order_number=_next_order_number(ordered_at=ordered_time),
            priority=priority,
            clinical_notes_encrypted=_encrypt_optional(clinical_notes),
            ordered_at=ordered_time,
        )
        LabOrderItem.objects.bulk_create(
            [
                LabOrderItem(lab_order=order, lab_test=lab_test, ordered_at=ordered_time)
                for lab_test in lab_tests
            ]
        )
    except IntegrityError as exc:
        raise ConflictError(
            "Lab order could not be created because a conflicting record exists."
        ) from exc
    return order


@transaction.atomic
def cancel_lab_order(
    *, order_id, cancelled_by_id=None, cancellation_reason, cancelled_at=None
) -> LabOrder:
    order = _get_order(order_id, for_update=True)
    if order.status in TERMINAL_ORDER_STATUSES:
        raise ConflictError("This lab order cannot be cancelled.")
    reason = _optional_text(cancellation_reason)
    if not reason:
        raise ValidationError("Cancellation reason is required.")
    event_time = cancelled_at or timezone.now()
    order.status = LabOrder.Status.CANCELLED
    order.cancelled_at = event_time
    order.cancelled_by_id = cancelled_by_id
    order.cancellation_reason = reason
    order.save()
    order.items.exclude(status=LabOrderItem.Status.VERIFIED).update(
        status=LabOrderItem.Status.CANCELLED
    )
    return order


@transaction.atomic
def update_lab_order_item_status(*, item_id, status, occurred_at=None) -> LabOrderItem:
    item = _get_item(item_id, for_update=True)
    if item.status in TERMINAL_ITEM_STATUSES:
        raise ConflictError("This lab order item cannot change status.")
    event_time = occurred_at or timezone.now()
    item.status = status
    if status == LabOrderItem.Status.SAMPLE_COLLECTION and item.collected_at is None:
        item.collected_at = event_time
    elif status == LabOrderItem.Status.PROCESSING and item.processing_started_at is None:
        item.processing_started_at = event_time
    elif status == LabOrderItem.Status.RESULTED and item.resulted_at is None:
        item.resulted_at = event_time
    elif status == LabOrderItem.Status.VERIFIED and item.verified_at is None:
        item.verified_at = event_time
    item.save()
    _refresh_order_status(item.lab_order)
    return item


@transaction.atomic
def create_lab_specimen(
    *,
    lab_order_item_id,
    specimen_type,
    collected_by_practitioner_facility_assignment_id=None,
    collected_at=None,
) -> LabSpecimen:
    item = _get_item(lab_order_item_id, for_update=True)
    if item.status in TERMINAL_ITEM_STATUSES:
        raise ConflictError("Specimen cannot be created for this order item.")
    event_time = collected_at or timezone.now()
    collector = None
    status = LabSpecimen.Status.PENDING
    if collected_by_practitioner_facility_assignment_id:
        collector = _get_assignment(collected_by_practitioner_facility_assignment_id)
        _validate_assignment_facility(
            assignment=collector, facility_id=item.lab_order.encounter.facility_id
        )
        status = LabSpecimen.Status.COLLECTED
        item.status = LabOrderItem.Status.SAMPLE_COLLECTION
        item.collected_at = event_time
        item.save()
    specimen = LabSpecimen.objects.create(
        lab_order_item=item,
        specimen_number=_next_specimen_number(collected_at=event_time),
        specimen_type=specimen_type.strip(),
        collected_by_practitioner_facility_assignment=collector,
        collected_at=event_time if collector else None,
        status=status,
    )
    _refresh_order_status(item.lab_order)
    return specimen


@transaction.atomic
def receive_lab_specimen(
    *, specimen_id, received_by_practitioner_facility_assignment_id, received_at=None
) -> LabSpecimen:
    specimen = (
        LabSpecimen.objects.select_related(
            "lab_order_item", "lab_order_item__lab_order", "lab_order_item__lab_order__encounter"
        )
        .select_for_update()
        .filter(pk=specimen_id)
        .first()
    )
    if specimen is None:
        raise NotFoundError("Lab specimen not found.")
    receiver = _get_assignment(received_by_practitioner_facility_assignment_id)
    _validate_assignment_facility(
        assignment=receiver, facility_id=specimen.lab_order_item.lab_order.encounter.facility_id
    )
    specimen.status = LabSpecimen.Status.RECEIVED
    specimen.received_by_practitioner_facility_assignment = receiver
    specimen.received_at = received_at or timezone.now()
    specimen.save()
    return specimen


@transaction.atomic
def reject_lab_specimen(*, specimen_id, rejection_reason) -> LabSpecimen:
    specimen = LabSpecimen.objects.select_for_update().filter(pk=specimen_id).first()
    if specimen is None:
        raise NotFoundError("Lab specimen not found.")
    reason = _optional_text(rejection_reason)
    if not reason:
        raise ValidationError("Rejection reason is required.")
    specimen.status = LabSpecimen.Status.REJECTED
    specimen.rejection_reason = reason
    specimen.save()
    return specimen


@transaction.atomic
def mark_specimen_processing(*, specimen_id) -> LabSpecimen:
    specimen = (
        LabSpecimen.objects.select_related("lab_order_item")
        .select_for_update()
        .filter(pk=specimen_id)
        .first()
    )
    if specimen is None:
        raise NotFoundError("Lab specimen not found.")
    specimen.status = LabSpecimen.Status.PROCESSING
    specimen.save()
    update_lab_order_item_status(
        item_id=specimen.lab_order_item_id, status=LabOrderItem.Status.PROCESSING
    )
    return specimen


@transaction.atomic
def create_lab_result_value(
    *,
    lab_order_item_id,
    entered_by_practitioner_facility_assignment_id,
    lab_test_component_id=None,
    value_numeric=None,
    value_text=None,
    unit=None,
    reference_low=None,
    reference_high=None,
    abnormal_flag=LabResultValue.AbnormalFlag.NORMAL,
    entered_at=None,
    notes=None,
) -> LabResultValue:
    item = _get_item(lab_order_item_id, for_update=True)
    if item.status in TERMINAL_ITEM_STATUSES:
        raise ConflictError("Result cannot be entered for this order item.")
    entered_by = _get_assignment(entered_by_practitioner_facility_assignment_id)
    _validate_assignment_facility(
        assignment=entered_by, facility_id=item.lab_order.encounter.facility_id
    )
    component = _get_component(lab_test_component_id) if lab_test_component_id else None
    if component and component.lab_test_id != item.lab_test_id:
        raise ValidationError("Result component must belong to the ordered lab test.")
    result = LabResultValue.objects.create(
        lab_order_item=item,
        lab_test_component=component,
        value_numeric=value_numeric,
        value_text=_optional_text(value_text),
        unit=_optional_text(unit) or getattr(component, "unit", None),
        reference_low=reference_low
        if reference_low is not None
        else getattr(component, "reference_low", None),
        reference_high=reference_high
        if reference_high is not None
        else getattr(component, "reference_high", None),
        abnormal_flag=abnormal_flag,
        entered_by_practitioner_facility_assignment=entered_by,
        entered_at=entered_at or timezone.now(),
        notes_encrypted=_encrypt_optional(notes),
    )
    item.status = LabOrderItem.Status.RESULTED
    if item.resulted_at is None:
        item.resulted_at = result.entered_at
    item.save()
    _refresh_order_status(item.lab_order)
    return result


@transaction.atomic
def verify_lab_result_value(
    *, result_id, verified_by_practitioner_facility_assignment_id, verified_at=None
) -> LabResultValue:
    result = (
        LabResultValue.objects.select_related(
            "lab_order_item",
            "lab_order_item__lab_order",
            "lab_order_item__lab_order__encounter",
        )
        .select_for_update()
        .filter(pk=result_id)
        .first()
    )
    if result is None:
        raise NotFoundError("Lab result not found.")
    if result.verified_at is not None:
        raise ConflictError("Lab result is already verified.")
    verifier = _get_assignment(verified_by_practitioner_facility_assignment_id)
    _validate_assignment_facility(
        assignment=verifier, facility_id=result.lab_order_item.lab_order.encounter.facility_id
    )
    result.verified_by_practitioner_facility_assignment = verifier
    result.verified_at = verified_at or timezone.now()
    result.save()
    item = result.lab_order_item
    if not item.result_values.filter(verified_at__isnull=True).exists():
        item.status = LabOrderItem.Status.VERIFIED
        item.verified_at = result.verified_at
        item.save()
    _refresh_order_status(item.lab_order)
    return result
