from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.notifications._helpers import translate_domain_error
from apps.notifications.models import UserPushDevice
from apps.notifications.selectors import get_push_device_by_id, list_push_devices
from apps.notifications.serializers import PushDeviceOutputSerializer, PushDeviceRegisterInputSerializer
from apps.notifications.services import deactivate_push_device, register_push_device, revoke_push_device, update_push_device_last_seen

from .base import NOTIFICATIONS_DOCS_TAG, NotificationBaseViewSet, _bool_query_param


@extend_schema(tags=[NOTIFICATIONS_DOCS_TAG])
class PushDeviceViewSet(NotificationBaseViewSet):
    queryset = UserPushDevice.objects.all()
    serializer_class = PushDeviceOutputSerializer
    permission_map = {
        "list": "notifications_device.view",
        "create": "notifications_device.manage",
        "last_seen": "notifications_device.manage",
        "revoke": "notifications_device.manage",
        "deactivate": "notifications_device.manage",
    }

    def list(self, request):
        queryset = list_push_devices(
            user_id=request.query_params.get("user_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
            revoked=_bool_query_param(request.query_params.get("revoked")),
        )
        return Response(PushDeviceOutputSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = PushDeviceRegisterInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            device = register_push_device(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PushDeviceOutputSerializer(device).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="last-seen")
    def last_seen(self, request, pk=None):
        try:
            device = update_push_device_last_seen(device_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PushDeviceOutputSerializer(device).data)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        try:
            device = revoke_push_device(device_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PushDeviceOutputSerializer(device).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            device = deactivate_push_device(device_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PushDeviceOutputSerializer(device).data)
