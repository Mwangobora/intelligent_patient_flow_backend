from __future__ import annotations

import hashlib
import hmac
import os

from django.conf import settings
from django.db import DatabaseError, connection

from common.exceptions import ValidationError


def _get_encryption_key() -> str:
    # TODO: move encrypted-field secrets to dedicated rotated environment keys in every environment.
    return os.getenv("APP_FIELD_ENCRYPTION_KEY") or settings.SECRET_KEY


def _get_hmac_key() -> bytes:
    # TODO: use a dedicated HMAC key instead of falling back to DJANGO_SECRET_KEY.
    return (os.getenv("APP_FIELD_HMAC_KEY") or settings.SECRET_KEY).encode("utf-8")


def encrypt_sensitive_value(value: str) -> str:
    if not value or not value.strip():
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


def decrypt_sensitive_value(value: str) -> str:
    if not value or not value.strip():
        raise ValidationError("Sensitive value cannot be empty.")

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pgp_sym_decrypt(
                    dearmor(CAST(%s AS text)),
                    CAST(%s AS text)
                )
                """,
                [value, _get_encryption_key()],
            )
            row = cursor.fetchone()
    except DatabaseError as exc:
        raise ValidationError("Sensitive field decryption is unavailable.") from exc

    decrypted_value = row[0] if row else None
    if decrypted_value is None:
        raise ValidationError("Sensitive field decryption did not return a value.")
    return decrypted_value


def build_value_hash(value: str) -> str:
    if not value or not value.strip():
        raise ValidationError("Sensitive value cannot be empty.")
    return hmac.new(_get_hmac_key(), value.strip().encode("utf-8"), hashlib.sha256).hexdigest().upper()
