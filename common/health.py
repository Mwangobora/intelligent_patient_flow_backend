from redis import Redis
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError


class LiveHealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class ReadyHealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            connections["default"].cursor()
        except OperationalError:
            return Response({"status": "error"}, status=503)

        try:
            redis_client = Redis.from_url(settings.REDIS_URL)
            redis_client.ping()
        except Exception:
            return Response({"status": "error"}, status=503)

        return Response({"status": "ok"})
