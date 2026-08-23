from __future__ import annotations

from http.cookies import SimpleCookie
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


@database_sync_to_async
def _authenticate_token(raw_token: str | None):
    close_old_connections()
    if not raw_token:
        return AnonymousUser()
    authenticator = JWTAuthentication()
    try:
        validated_token = authenticator.get_validated_token(raw_token)
        return authenticator.get_user(validated_token)
    except (InvalidToken, TokenError):
        return AnonymousUser()


def _token_from_headers(headers: dict[bytes, bytes]) -> str | None:
    cookie_header = headers.get(b"cookie", b"").decode("latin1")
    cookies = SimpleCookie()
    cookies.load(cookie_header)
    if settings.AUTH_COOKIE_ACCESS_NAME in cookies:
        return cookies[settings.AUTH_COOKIE_ACCESS_NAME].value

    auth_header = headers.get(b"authorization", b"").decode("latin1")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


def _token_from_query(scope) -> str | None:
    query = parse_qs(scope.get("query_string", b"").decode())
    values = query.get("token")
    return values[0] if values else None


class JWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers") or [])
        raw_token = _token_from_headers(headers) or _token_from_query(scope)
        scope["user"] = await _authenticate_token(raw_token)
        return await self.app(scope, receive, send)
