from __future__ import annotations

import hashlib
import hmac
import os
import re

from django.conf import settings
from django.db import DatabaseError, connection

from common.exceptions import ValidationError

NON_ALNUM_RE = re.compile(r"[^A-Za-z0-9]+")


def _get_encryption_key() -> str:
    # TODO: move encrypted-field secrets to dedicated rotated environment keys in every environment.
    return os.getenv("APP_FIELD_ENCRYPTION_KEY") or settings.SECRET_KEY


def _get_hmac_key() -> bytes:
    # TODO: use a dedicated HMAC key instead of falling back to DJANGO_SECRET_KEY.
    return (os.getenv("APP_FIELD_HMAC_KEY") or settings.SECRET_KEY).encode("utf-8")


def encrypt_sensitive_value(value: str) -> str:
    if not value:
        raise ValidationError("Sensitive value cannot be empty.")

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT armor(
                    pgp_sym_encrypt(
                        CAST(%s AS text),
                        CAST(%s AS text),
                        'cipher-algo=aes256,compress-algo=1'
                    )
                )
                """,
                [value, _get_encryption_key()],
            )
            row = cursor.fetchone()
    except DatabaseError as exc:
        raise ValidationError(
            "Sensitive field encryption is unavailable. Ensure pgcrypto and encryption keys are configured."
        ) from exc

    encrypted_value = row[0] if row else None
    if not encrypted_value:
        raise ValidationError("Sensitive field encryption did not return a value.")
    return encrypted_value


def build_value_hash(value: str) -> str:
    if not value:
        raise ValidationError("Sensitive value cannot be empty.")
    return hmac.new(_get_hmac_key(), value.encode("utf-8"), hashlib.sha256).hexdigest().upper()


def derive_last_four(value: str) -> str | None:
    stripped_value = NON_ALNUM_RE.sub("", value)
    if len(stripped_value) < 4:
        return None
    return stripped_value[-4:]


def normalize_credential_number_for_lookup(value: str) -> str:
    normalized = NON_ALNUM_RE.sub("", value.strip().upper())
    if not normalized:
        raise ValidationError("Credential number cannot be empty.")
    return normalized
