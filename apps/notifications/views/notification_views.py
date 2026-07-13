from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.notifications._helpers import translate_domain_error
from apps.notifications.models import PatientNotification
from apps.notifications.selectors import get_notification_by_id, list_notifications
from apps.notifications.serializers import (
    MarkReadInputSerializer,
    NotificationCancelInputSerializer,
    NotificationDeliveryStatusOutputSerializer,
    PatientNotificationCreateInputSerializer,
    PatientNotificationOutputSerializer,
)
from apps.notifications.services import cancel_notification, create_patient_notification, mark_notification_read, send_notification
from apps.patients.models import Patient

from .base import NOTIFICATIONS_DOCS_TAG, NotificationBaseViewSet, _bool_query_param


def _patient_scope(patient_id):
    patient = Patient.objects.filter(pk=patient_id).first()
    if patient is None:
        return None, None
    return patient.organization_id, patient.registered_facility_id


def _notification_scope(notification_id):
    notification = get_notification_by_id(notification_id)
    if notification is None:
        return None, None
    return notification.patient.organization_id, notification.patient.registered_facility_id


@extend_schema(tags=[NOTIFICATIONS_DOCS_TAG])
class NotificationViewSet(NotificationBaseViewSet):
    queryset = PatientNotification.objects.all()
    serializer_class = PatientNotificationOutputSerializer
    permission_map = {
        "list": "notifications_notification.view",
        "retrieve": "notifications_notification.view",
        "create": "notifications_notification.create",
        "cancel": "notifications_notification.cancel",
        "mark_read": "notifications_notification.view",
        "send": "notifications_notification.send",
    }

    def get_permission_scope(self, request):
        if self.action == "create":
            return _patient_scope(request.data.get("patient_id"))
        if self.action in {"retrieve", "cancel", "mark_read", "send"}:
            return _notification_scope(self.kwargs.get("pk"))
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        queryset = list_notifications(
            patient_id=request.query_params.get("patient_id"),
            appointment_id=request.query_params.get("appointment_id"),
            queue_entry_id=request.query_params.get("queue_entry_id"),
            status=request.query_params.get("status"),
            channel=request.query_params.get("channel"),
            notification_type=request.query_params.get("notification_type"),
            scheduled_pending=_bool_query_param(request.query_params.get("scheduled_pending")),
        )
        return Response(PatientNotificationOutputSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = PatientNotificationCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            notification = create_patient_notification(created_by_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientNotificationOutputSerializer(notification).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        notification = get_notification_by_id(pk)
        if notification is None:
            return Response({"detail": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PatientNotificationOutputSerializer(notification).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        serializer = NotificationCancelInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            notification = cancel_notification(notification_id=pk, cancelled_by_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientNotificationOutputSerializer(notification).data)

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        serializer = MarkReadInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            notification = mark_notification_read(notification_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientNotificationOutputSerializer(notification).data)

    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request, pk=None):
        try:
            notification = send_notification(notification_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        response_status = status.HTTP_400_BAD_REQUEST if notification.status == PatientNotification.Status.FAILED else status.HTTP_200_OK
        return Response(NotificationDeliveryStatusOutputSerializer(notification).data, status=response_status)
