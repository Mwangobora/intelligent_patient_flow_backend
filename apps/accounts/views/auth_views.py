from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.permissions import IsAuthenticatedActive
from apps.accounts.selectors import get_user_by_email_or_phone
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    CurrentUserSerializer,
    LoginSerializer,
    LogoutSerializer,
    MeUpdateSerializer,
)
from apps.accounts.services import change_user_password, update_user

from ._auth_cookies import clear_auth_cookies, set_auth_cookies
from ._helpers import translate_domain_error


@extend_schema(tags=["Auth APIs"])
class AuthViewSet(viewsets.GenericViewSet):
    serializer_class = CurrentUserSerializer

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
        response = Response(
            {
                "user": CurrentUserSerializer(user).data,
            }
        )
        return set_auth_cookies(
            response=response,
            access_token=str(refresh.access_token),
            refresh_token=str(refresh),
        )

    @action(detail=False, methods=["post"], permission_classes=[AllowAny], authentication_classes=[], url_path="refresh")
    def refresh(self, request):
        refresh_token = request.data.get("refresh") or request.COOKIES.get("refresh_token")
        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
        serializer.is_valid(raise_exception=True)
        response = Response({"detail": "Session refreshed."})
        return set_auth_cookies(
            response=response,
            access_token=serializer.validated_data["access"],
            refresh_token=refresh_token,
        )

    @action(detail=False, methods=["post"], url_path="logout")
    def logout(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data.get("refresh") or request.COOKIES.get("refresh_token")
        if refresh_token:
            try:
                refresh = RefreshToken(refresh_token)
                if hasattr(refresh, "blacklist"):
                    refresh.blacklist()
            except TokenError:
                pass

        response = Response(status=status.HTTP_204_NO_CONTENT)
        return clear_auth_cookies(response)

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        if request.method == "GET":
            return Response(CurrentUserSerializer(request.user).data)

        serializer = MeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            user = update_user(user_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(CurrentUserSerializer(user).data)

    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            change_user_password(user_id=request.user.id, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)
