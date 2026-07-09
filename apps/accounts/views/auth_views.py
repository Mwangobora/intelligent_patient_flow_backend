from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.permissions import IsAuthenticatedActive
from apps.accounts.selectors import get_user_by_email_or_phone
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    MeUpdateSerializer,
    UserSummarySerializer,
)
from apps.accounts.services import change_user_password, update_user

from ._helpers import translate_domain_error


@extend_schema(tags=["Auth APIs"])
class AuthViewSet(viewsets.GenericViewSet):
    serializer_class = UserSummarySerializer

    def get_permissions(self):
        if self.action in {"login", "refresh"}:
            return [AllowAny()]
        return [IsAuthenticatedActive()]

    @action(detail=False, methods=["post"], permission_classes=[AllowAny], authentication_classes=[], url_path="login")
    def login(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_user_by_email_or_phone(serializer.validated_data["email_or_phone"])
        if user is None or not user.check_password(serializer.validated_data["password"]):
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return Response({"detail": "User account is inactive."}, status=status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSummarySerializer(user).data,
            }
        )

    @action(detail=False, methods=["post"], permission_classes=[AllowAny], authentication_classes=[], url_path="refresh")
    def refresh(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)

    @action(detail=False, methods=["post"], url_path="logout")
    def logout(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh = RefreshToken(serializer.validated_data["refresh"])
        if not hasattr(refresh, "blacklist"):
            return Response(
                {"detail": "Refresh token blacklist is not configured."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        refresh.blacklist()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        if request.method == "GET":
            return Response(UserSummarySerializer(request.user).data)

        serializer = MeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            user = update_user(user_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(UserSummarySerializer(user).data)

    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            change_user_password(user_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)
