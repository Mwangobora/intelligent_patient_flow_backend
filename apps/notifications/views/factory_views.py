from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from apps.notifications._helpers import translate_domain_error
from apps.notifications.serializers import (
    AppointmentNotificationFactoryInputSerializer,
    PatientNotificationOutputSerializer,
    QueueNotificationFactoryInputSerializer,
)
from apps.notifications.services import (
    create_appointment_cancelled_notification,
    create_appointment_confirmation_notification,
    create_appointment_reminder_notification,
    create_appointment_rescheduled_notification,
    create_queue_called_notification,
    create_queue_joined_notification,
    create_queue_updated_notification,
)
from apps.scheduling.models import Appointment
from apps.queueing.models import QueueEntry

from .base import NOTIFICATIONS_DOCS_TAG, NotificationBaseViewSet


def _appointment_scope(appointment_id):
    appointment = Appointment.objects.select_related("facility").filter(pk=appointment_id).first()
    if appointment is None:
        return None, None
    return appointment.facility.organization_id, appointment.facility_id


def _queue_entry_scope(queue_entry_id):
    entry = QueueEntry.objects.select_related("queue__service_point__facility").filter(pk=queue_entry_id).first()
    if entry is None:
        return None, None
    facility = entry.queue.service_point.facility
    return facility.organization_id, facility.id


class AppointmentFactoryBaseViewSet(NotificationBaseViewSet):
    permission_map = {"create": "notifications_notification.create"}
    factory_function = None

    def get_permission_scope(self, request):
        return _appointment_scope(request.data.get("appointment_id"))

    def create(self, request):
        serializer = AppointmentNotificationFactoryInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            notification = self.factory_function(created_by_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientNotificationOutputSerializer(notification).data, status=status.HTTP_201_CREATED)


class QueueFactoryBaseViewSet(NotificationBaseViewSet):
    permission_map = {"create": "notifications_notification.create"}
    factory_function = None

    def get_permission_scope(self, request):
        return _queue_entry_scope(request.data.get("queue_entry_id"))

    def create(self, request):
        serializer = QueueNotificationFactoryInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            notification = self.factory_function(created_by_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientNotificationOutputSerializer(notification).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=[NOTIFICATIONS_DOCS_TAG])
class AppointmentConfirmationNotificationViewSet(AppointmentFactoryBaseViewSet):
    factory_function = staticmethod(create_appointment_confirmation_notification)


@extend_schema(tags=[NOTIFICATIONS_DOCS_TAG])
class AppointmentReminderNotificationViewSet(AppointmentFactoryBaseViewSet):
    factory_function = staticmethod(create_appointment_reminder_notification)


@extend_schema(tags=[NOTIFICATIONS_DOCS_TAG])
class AppointmentRescheduledNotificationViewSet(AppointmentFactoryBaseViewSet):
    factory_function = staticmethod(create_appointment_rescheduled_notification)


@extend_schema(tags=[NOTIFICATIONS_DOCS_TAG])
class AppointmentCancelledNotificationViewSet(AppointmentFactoryBaseViewSet):
    factory_function = staticmethod(create_appointment_cancelled_notification)


@extend_schema(tags=[NOTIFICATIONS_DOCS_TAG])
class QueueJoinedNotificationViewSet(QueueFactoryBaseViewSet):
    factory_function = staticmethod(create_queue_joined_notification)


@extend_schema(tags=[NOTIFICATIONS_DOCS_TAG])
class QueueUpdatedNotificationViewSet(QueueFactoryBaseViewSet):
    factory_function = staticmethod(create_queue_updated_notification)


@extend_schema(tags=[NOTIFICATIONS_DOCS_TAG])
class QueueCalledNotificationViewSet(QueueFactoryBaseViewSet):
    factory_function = staticmethod(create_queue_called_notification)
