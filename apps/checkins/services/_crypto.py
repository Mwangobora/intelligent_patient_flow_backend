from __future__ import annotations

import hashlib
import hmac
import os
import secrets

from django.conf import settings

from common.exceptions import ValidationError


def _get_hmac_key() -> bytes:
    # TODO: use a dedicated HMAC key instead of falling back to DJANGO_SECRET_KEY.
    return (os.getenv("APP_FIELD_HMAC_KEY") or settings.SECRET_KEY).encode("utf-8")


def generate_raw_token() -> str:
    return secrets.token_urlsafe(32)


def build_token_hash(raw_token: str) -> str:
    if not raw_token or not raw_token.strip():
        raise ValidationError("Token cannot be empty.")
    return hmac.new(_get_hmac_key(), raw_token.strip().encode("utf-8"), hashlib.sha256).hexdigest().upper()
