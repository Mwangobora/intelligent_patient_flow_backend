from __future__ import annotations

from django.conf import settings
from rest_framework.response import Response


def _cookie_kwargs(*, max_age: int) -> dict[str, object]:
    return {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "path": "/",
        "max_age": max_age,
    }


def set_auth_cookies(*, response: Response, access_token: str, refresh_token: str | None) -> Response:
    response.set_cookie(
        settings.AUTH_COOKIE_ACCESS_NAME,
        access_token,
        **_cookie_kwargs(max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())),
    )
    if refresh_token:
        response.set_cookie(
            settings.AUTH_COOKIE_REFRESH_NAME,
            refresh_token,
            **_cookie_kwargs(max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())),
        )
    return response


def clear_auth_cookies(response: Response) -> Response:
    response.delete_cookie(settings.AUTH_COOKIE_ACCESS_NAME, path="/", samesite=settings.AUTH_COOKIE_SAMESITE)
    response.delete_cookie(settings.AUTH_COOKIE_REFRESH_NAME, path="/", samesite=settings.AUTH_COOKIE_SAMESITE)
    return response
