from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.clinical.selectors import get_encounter_by_id
from apps.laboratory._helpers import translate_domain_error
from apps.laboratory.models import (
    LabOrder,
    LabOrderItem,
    LabResultValue,
    LabSpecimen,
    LabTest,
    LabTestComponent,
)
from apps.laboratory.selectors import (
    get_lab_order_by_id,
    get_lab_order_item_by_id,
    get_lab_result_value_by_id,
    get_lab_specimen_by_id,
    get_lab_test_by_id,
    get_lab_test_component_by_id,
    list_lab_order_items,
    list_lab_orders,
    list_lab_result_values,
    list_lab_specimens,
    list_lab_test_components,
    list_lab_tests,
)
from apps.laboratory.serializers import (
    LabOrderCancelSerializer,
    LabOrderCreateSerializer,
    LabOrderItemSerializer,
    LabOrderItemStatusSerializer,
    LabOrderSerializer,
    LabResultValueCreateSerializer,
    LabResultValueSerializer,
    LabResultVerifySerializer,
    LabSpecimenCreateSerializer,
    LabSpecimenReceiveSerializer,
    LabSpecimenRejectSerializer,
    LabSpecimenSerializer,
    LabTestComponentSerializer,
    LabTestComponentWriteSerializer,
    LabTestSerializer,
    LabTestWriteSerializer,
)
from apps.laboratory.services import (
    cancel_lab_order,
    create_lab_order,
    create_lab_result_value,
    create_lab_specimen,
    create_lab_test,
    create_lab_test_component,
    mark_specimen_processing,
    receive_lab_specimen,
    reject_lab_specimen,
    update_lab_order_item_status,
    update_lab_test,
    update_lab_test_component,
    verify_lab_result_value,
)

from .base import LABORATORY_DOCS_TAG, LaboratoryBaseViewSet, _bool_query_param


@extend_schema(tags=[LABORATORY_DOCS_TAG])
class LabTestViewSet(LaboratoryBaseViewSet):
    queryset = LabTest.objects.all()
    permission_map = {
        "list": "laboratory_test.view",
        "retrieve": "laboratory_test.view",
        "create": "laboratory_test.create",
        "partial_update": "laboratory_test.update",
        "deactivate": "laboratory_test.deactivate",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            return request.data.get("organization_id"), None
        if self.action in {"retrieve", "partial_update", "deactivate"}:
            lab_test = get_lab_test_by_id(self.kwargs.get("pk"))
            return (lab_test.organization_id, None) if lab_test else (None, None)
        return request.query_params.get("organization_id"), None

    def list(self, request):
        return Response(
            LabTestSerializer(
                list_lab_tests(
                    organization_id=request.query_params.get("organization_id"),
                    is_active=_bool_query_param(request.query_params.get("is_active")),
                    search=request.query_params.get("search"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = LabTestWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            lab_test = create_lab_test(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabTestSerializer(lab_test).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        lab_test = get_lab_test_by_id(pk)
        return (
            Response(LabTestSerializer(lab_test).data)
            if lab_test
            else Response({"detail": "Lab test not found."}, status=404)
        )

    def partial_update(self, request, pk=None):
        serializer = LabTestWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            lab_test = update_lab_test(lab_test_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabTestSerializer(lab_test).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        try:
            lab_test = update_lab_test(lab_test_id=pk, is_active=False)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabTestSerializer(lab_test).data)


@extend_schema(tags=[LABORATORY_DOCS_TAG])
class LabTestComponentViewSet(LaboratoryBaseViewSet):
    queryset = LabTestComponent.objects.all()
    permission_map = {
        "list": "laboratory_test.view",
        "retrieve": "laboratory_test.view",
        "create": "laboratory_test.update",
        "partial_update": "laboratory_test.update",
        "deactivate": "laboratory_test.update",
    }

    def get_permission_scope(self, request):
        lab_test = None
        if self.action == "create":
            lab_test = get_lab_test_by_id(request.data.get("lab_test_id"))
        elif self.action in {"retrieve", "partial_update", "deactivate"}:
            component = get_lab_test_component_by_id(self.kwargs.get("pk"))
            lab_test = component.lab_test if component else None
        else:
            lab_test = get_lab_test_by_id(request.query_params.get("lab_test_id"))
        return (
            (lab_test.organization_id, None)
            if lab_test
            else (request.query_params.get("organization_id"), None)
        )

    def list(self, request):
        return Response(
            LabTestComponentSerializer(
                list_lab_test_components(
                    lab_test_id=request.query_params.get("lab_test_id"),
                    is_active=_bool_query_param(request.query_params.get("is_active")),
                    search=request.query_params.get("search"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = LabTestComponentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            component = create_lab_test_component(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabTestComponentSerializer(component).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        component = get_lab_test_component_by_id(pk)
        return (
            Response(LabTestComponentSerializer(component).data)
            if component
            else Response({"detail": "Lab test component not found."}, status=404)
        )

    def partial_update(self, request, pk=None):
        serializer = LabTestComponentWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            component = update_lab_test_component(component_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabTestComponentSerializer(component).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        try:
            component = update_lab_test_component(component_id=pk, is_active=False)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabTestComponentSerializer(component).data)


@extend_schema(tags=[LABORATORY_DOCS_TAG])
class LabOrderViewSet(LaboratoryBaseViewSet):
    queryset = LabOrder.objects.all()
    permission_map = {
        "list": "laboratory_order.view",
        "retrieve": "laboratory_order.view",
        "create": "laboratory_order.create",
        "cancel": "laboratory_order.cancel",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            encounter = get_encounter_by_id(request.data.get("encounter_id"))
        elif self.action in {"retrieve", "cancel"}:
            order = get_lab_order_by_id(self.kwargs.get("pk"))
            encounter = order.encounter if order else None
        else:
            encounter = get_encounter_by_id(request.query_params.get("encounter_id"))
        if encounter:
            return encounter.facility.organization_id, encounter.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        return Response(
            LabOrderSerializer(
                list_lab_orders(
                    facility_id=request.query_params.get("facility_id"),
                    patient_id=request.query_params.get("patient_id"),
                    encounter_id=request.query_params.get("encounter_id"),
                    status=request.query_params.get("status"),
                    priority=request.query_params.get("priority"),
                    search=request.query_params.get("search"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = LabOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = create_lab_order(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabOrderSerializer(order).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        order = get_lab_order_by_id(pk)
        return (
            Response(LabOrderSerializer(order).data)
            if order
            else Response({"detail": "Lab order not found."}, status=404)
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        serializer = LabOrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = cancel_lab_order(
                order_id=pk, cancelled_by_id=request.user.id, **serializer.validated_data
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabOrderSerializer(order).data)


@extend_schema(tags=[LABORATORY_DOCS_TAG])
class LabOrderItemViewSet(LaboratoryBaseViewSet):
    queryset = LabOrderItem.objects.all()
    permission_map = {
        "list": "laboratory_order.view",
        "retrieve": "laboratory_order.view",
        "change_status": "laboratory_order.update",
    }

    def get_permission_scope(self, request):
        item = get_lab_order_item_by_id(self.kwargs.get("pk")) if self.action != "list" else None
        if item:
            encounter = item.lab_order.encounter
            return encounter.facility.organization_id, encounter.facility_id
        order = get_lab_order_by_id(request.query_params.get("lab_order_id"))
        if order:
            return order.encounter.facility.organization_id, order.encounter.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        return Response(
            LabOrderItemSerializer(
                list_lab_order_items(
                    lab_order_id=request.query_params.get("lab_order_id"),
                    status=request.query_params.get("status"),
                ),
                many=True,
            ).data
        )

    def retrieve(self, request, pk=None):
        item = get_lab_order_item_by_id(pk)
        return (
            Response(LabOrderItemSerializer(item).data)
            if item
            else Response({"detail": "Lab order item not found."}, status=404)
        )

    @action(detail=True, methods=["post"], url_path="change-status")
    def change_status(self, request, pk=None):
        serializer = LabOrderItemStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = update_lab_order_item_status(item_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabOrderItemSerializer(item).data)


@extend_schema(tags=[LABORATORY_DOCS_TAG])
class LabSpecimenViewSet(LaboratoryBaseViewSet):
    queryset = LabSpecimen.objects.all()
    permission_map = {
        "list": "laboratory_specimen.view",
        "retrieve": "laboratory_specimen.view",
        "create": "laboratory_specimen.manage",
        "receive": "laboratory_specimen.manage",
        "reject": "laboratory_specimen.manage",
        "mark_processing": "laboratory_specimen.manage",
    }

    def get_permission_scope(self, request):
        specimen = (
            get_lab_specimen_by_id(self.kwargs.get("pk"))
            if self.action != "list" and self.action != "create"
            else None
        )
        item = (
            get_lab_order_item_by_id(request.data.get("lab_order_item_id"))
            if self.action == "create"
            else None
        )
        if specimen:
            encounter = specimen.lab_order_item.lab_order.encounter
            return encounter.facility.organization_id, encounter.facility_id
        if item:
            encounter = item.lab_order.encounter
            return encounter.facility.organization_id, encounter.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        return Response(
            LabSpecimenSerializer(
                list_lab_specimens(
                    lab_order_item_id=request.query_params.get("lab_order_item_id"),
                    status=request.query_params.get("status"),
                    search=request.query_params.get("search"),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = LabSpecimenCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            specimen = create_lab_specimen(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabSpecimenSerializer(specimen).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        specimen = get_lab_specimen_by_id(pk)
        return (
            Response(LabSpecimenSerializer(specimen).data)
            if specimen
            else Response({"detail": "Lab specimen not found."}, status=404)
        )

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        serializer = LabSpecimenReceiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            specimen = receive_lab_specimen(specimen_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabSpecimenSerializer(specimen).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = LabSpecimenRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            specimen = reject_lab_specimen(specimen_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabSpecimenSerializer(specimen).data)

    @action(detail=True, methods=["post"], url_path="mark-processing")
    def mark_processing(self, request, pk=None):
        try:
            specimen = mark_specimen_processing(specimen_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabSpecimenSerializer(specimen).data)


@extend_schema(tags=[LABORATORY_DOCS_TAG])
class LabResultValueViewSet(LaboratoryBaseViewSet):
    queryset = LabResultValue.objects.all()
    permission_map = {
        "list": "laboratory_result.view",
        "retrieve": "laboratory_result.view",
        "create": "laboratory_result.create",
        "verify": "laboratory_result.verify",
    }

    def get_permission_scope(self, request):
        result = (
            get_lab_result_value_by_id(self.kwargs.get("pk"))
            if self.action not in {"list", "create"}
            else None
        )
        item = (
            get_lab_order_item_by_id(request.data.get("lab_order_item_id"))
            if self.action == "create"
            else None
        )
        if result:
            encounter = result.lab_order_item.lab_order.encounter
            return encounter.facility.organization_id, encounter.facility_id
        if item:
            encounter = item.lab_order.encounter
            return encounter.facility.organization_id, encounter.facility_id
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        return Response(
            LabResultValueSerializer(
                list_lab_result_values(
                    lab_order_item_id=request.query_params.get("lab_order_item_id"),
                    lab_order_id=request.query_params.get("lab_order_id"),
                    abnormal_flag=request.query_params.get("abnormal_flag"),
                    verified=_bool_query_param(request.query_params.get("verified")),
                ),
                many=True,
            ).data
        )

    def create(self, request):
        serializer = LabResultValueCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = create_lab_result_value(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabResultValueSerializer(result).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        result = get_lab_result_value_by_id(pk)
        return (
            Response(LabResultValueSerializer(result).data)
            if result
            else Response({"detail": "Lab result not found."}, status=404)
        )

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        serializer = LabResultVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = verify_lab_result_value(result_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(LabResultValueSerializer(result).data)
