from __future__ import annotations

from django.db.models import Q

from apps.laboratory.models import (
    LabOrder,
    LabOrderItem,
    LabResultValue,
    LabSpecimen,
    LabTest,
    LabTestComponent,
)


def list_lab_tests(*, organization_id=None, is_active: bool | None = None, search=None):
    queryset = LabTest.objects.select_related("organization")
    if organization_id:
        queryset = queryset.filter(organization_id=organization_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(code__icontains=search) | Q(name__icontains=search))
    return queryset.order_by("name")


def get_lab_test_by_id(lab_test_id):
    return list_lab_tests().filter(pk=lab_test_id).first()


def list_lab_test_components(*, lab_test_id=None, is_active: bool | None = None, search=None):
    queryset = LabTestComponent.objects.select_related("lab_test", "lab_test__organization")
    if lab_test_id:
        queryset = queryset.filter(lab_test_id=lab_test_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(code__icontains=search) | Q(name__icontains=search))
    return queryset.order_by("lab_test__name", "display_order", "name")


def get_lab_test_component_by_id(component_id):
    return list_lab_test_components().filter(pk=component_id).first()


def base_lab_order_queryset():
    return LabOrder.objects.select_related(
        "encounter",
        "encounter__facility",
        "encounter__facility__organization",
        "encounter__patient",
        "encounter__department",
        "encounter__facility_specialty__specialty",
        "ordered_by_practitioner_facility_assignment__practitioner",
        "cancelled_by",
    ).prefetch_related("items", "items__lab_test")


def list_lab_orders(
    *,
    facility_id=None,
    patient_id=None,
    encounter_id=None,
    status=None,
    priority=None,
    search=None,
):
    queryset = base_lab_order_queryset()
    if facility_id:
        queryset = queryset.filter(encounter__facility_id=facility_id)
    if patient_id:
        queryset = queryset.filter(encounter__patient_id=patient_id)
    if encounter_id:
        queryset = queryset.filter(encounter_id=encounter_id)
    if status:
        queryset = queryset.filter(status=status)
    if priority:
        queryset = queryset.filter(priority=priority)
    if search:
        queryset = queryset.filter(
            Q(order_number__icontains=search)
            | Q(encounter__encounter_number__icontains=search)
            | Q(encounter__patient__patient_number__icontains=search)
            | Q(encounter__patient__first_name__icontains=search)
            | Q(encounter__patient__last_name__icontains=search)
        )
    return queryset.order_by("-ordered_at")


def get_lab_order_by_id(order_id):
    return base_lab_order_queryset().filter(pk=order_id).first()


def list_lab_order_items(*, lab_order_id=None, status=None):
    queryset = LabOrderItem.objects.select_related(
        "lab_order",
        "lab_order__encounter",
        "lab_order__encounter__facility",
        "lab_order__encounter__patient",
        "lab_test",
    )
    if lab_order_id:
        queryset = queryset.filter(lab_order_id=lab_order_id)
    if status:
        queryset = queryset.filter(status=status)
    return queryset.order_by("-ordered_at")


def get_lab_order_item_by_id(item_id):
    return list_lab_order_items().filter(pk=item_id).first()


def list_lab_specimens(*, lab_order_item_id=None, status=None, search=None):
    queryset = LabSpecimen.objects.select_related(
        "lab_order_item",
        "lab_order_item__lab_order",
        "lab_order_item__lab_order__encounter",
        "lab_order_item__lab_order__encounter__facility",
        "collected_by_practitioner_facility_assignment__practitioner",
        "received_by_practitioner_facility_assignment__practitioner",
    )
    if lab_order_item_id:
        queryset = queryset.filter(lab_order_item_id=lab_order_item_id)
    if status:
        queryset = queryset.filter(status=status)
    if search:
        queryset = queryset.filter(specimen_number__icontains=search)
    return queryset.order_by("-created_at")


def get_lab_specimen_by_id(specimen_id):
    return list_lab_specimens().filter(pk=specimen_id).first()


def list_lab_result_values(
    *,
    lab_order_item_id=None,
    lab_order_id=None,
    abnormal_flag=None,
    verified: bool | None = None,
):
    queryset = LabResultValue.objects.select_related(
        "lab_order_item",
        "lab_order_item__lab_order",
        "lab_order_item__lab_order__encounter",
        "lab_order_item__lab_order__encounter__facility",
        "lab_test_component",
        "entered_by_practitioner_facility_assignment__practitioner",
        "verified_by_practitioner_facility_assignment__practitioner",
    )
    if lab_order_item_id:
        queryset = queryset.filter(lab_order_item_id=lab_order_item_id)
    if lab_order_id:
        queryset = queryset.filter(lab_order_item__lab_order_id=lab_order_id)
    if abnormal_flag:
        queryset = queryset.filter(abnormal_flag=abnormal_flag)
    if verified is not None:
        queryset = queryset.filter(verified_at__isnull=not verified)
    return queryset.order_by("-entered_at")


def get_lab_result_value_by_id(result_id):
    return list_lab_result_values().filter(pk=result_id).first()
