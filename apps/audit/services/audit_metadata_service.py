from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

REDACTED = "[REDACTED]"
MAX_METADATA_BYTES = 12000
MAX_DEPTH = 6
MAX_LIST_ITEMS = 50
SENSITIVE_KEY_FRAGMENTS = {
    "password",
    "token",
    "access",
    "refresh",
    "authorization",
    "cookie",
    "secret",
    "api_key",
    "otp",
    "pin",
    "body_encrypted",
    "destination_encrypted",
    "subject_encrypted",
    "token_encrypted",
    "token_hash",
    "id_number",
    "medical_notes",
}


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def redact_sensitive_value(value):
    return REDACTED


def _json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    return str(value)


def redact_sensitive_dict(data, *, depth: int = 0):
    if depth >= MAX_DEPTH:
        return "[TRUNCATED_DEPTH]"
    if isinstance(data, dict):
        safe = {}
        for key, value in data.items():
            key_string = str(key)
            safe[key_string] = redact_sensitive_value(value) if _is_sensitive_key(key_string) else redact_sensitive_dict(value, depth=depth + 1)
        return safe
    if isinstance(data, (list, tuple, set)):
        values = list(data)[:MAX_LIST_ITEMS]
        safe_values = [redact_sensitive_dict(value, depth=depth + 1) for value in values]
        if len(data) > MAX_LIST_ITEMS:
            safe_values.append("[TRUNCATED_LIST]")
        return safe_values
    return _json_safe(data)


def limit_metadata_size(metadata: dict | None) -> dict:
    metadata = metadata or {}
    encoded = json.dumps(metadata, sort_keys=True, default=str)
    if len(encoded.encode("utf-8")) <= MAX_METADATA_BYTES:
        return metadata

    limited = {"truncated": True}
    for key, value in metadata.items():
        candidate = {**limited, key: value}
        encoded_candidate = json.dumps(candidate, sort_keys=True, default=str)
        if len(encoded_candidate.encode("utf-8")) > MAX_METADATA_BYTES:
            limited[key] = "[TRUNCATED]"
            break
        limited[key] = value
    return limited


def sanitize_audit_metadata(metadata: dict | None) -> dict:
    redacted = redact_sensitive_dict(metadata or {})
    if not isinstance(redacted, dict):
        redacted = {"value": redacted}
    return limit_metadata_size(redacted)


def build_change_metadata(*, before: dict | None = None, after: dict | None = None, changed_fields: list[str] | None = None) -> dict:
    return sanitize_audit_metadata(
        {
            "before": before or {},
            "after": after or {},
            "changed_fields": changed_fields or [],
        }
    )


def build_safe_request_metadata(
    *,
    method: str | None = None,
    path: str | None = None,
    query_params: dict | None = None,
    status_code: int | None = None,
    request_id=None,
    user_agent: str | None = None,
    ip_address: str | None = None,
    failure_class: str | None = None,
) -> dict:
    return sanitize_audit_metadata(
        {
            "method": method,
            "path": path,
            "query_params": query_params or {},
            "status_code": status_code,
            "request_id": str(request_id) if request_id else None,
            "user_agent": user_agent,
            "ip_address": ip_address,
            "failure_class": failure_class,
        }
    )
