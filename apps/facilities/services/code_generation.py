from __future__ import annotations

import re

from django.db import models

from common.exceptions import ValidationError

UNSUPPORTED_CODE_CHARS_RE = re.compile(r"[^A-Z0-9_]+")
SEPARATOR_RE = re.compile(r"[\s\-]+")
UNDERSCORE_RE = re.compile(r"_+")


def normalize_code_value(value: str) -> str:
    """Normalize display text into an uppercase underscore code."""
    normalized = SEPARATOR_RE.sub("_", value.strip().upper())
    normalized = UNSUPPORTED_CODE_CHARS_RE.sub("", normalized)
    normalized = UNDERSCORE_RE.sub("_", normalized).strip("_")
    return normalized


def generate_unique_code(
    *,
    model: type[models.Model],
    source_value: str,
    queryset: models.QuerySet | None = None,
    code_field: str = "code",
    max_length: int | None = None,
) -> str:
    """
    Generate a normalized unique code, using row locks to avoid duplicate suffixes.
    """
    normalized_base = normalize_code_value(source_value)
    if not normalized_base:
        raise ValidationError("A valid non-empty source value is required to generate a code.")

    if queryset is None:
        queryset = model._default_manager.all()

    if max_length is None:
        max_length = model._meta.get_field(code_field).max_length

    base_code = normalized_base[:max_length].rstrip("_")
    if not base_code:
        raise ValidationError("The generated code is empty after normalization.")

    locked_queryset = queryset.select_for_update()
    suffix = 1
    while True:
        if suffix == 1:
            candidate = base_code
        else:
            suffix_text = f"_{suffix}"
            trimmed_base = base_code[: max_length - len(suffix_text)].rstrip("_")
            if not trimmed_base:
                raise ValidationError("Unable to generate a non-empty unique code within the field length.")
            candidate = f"{trimmed_base}{suffix_text}"

        if not candidate:
            raise ValidationError("Unable to generate a non-empty unique code.")

        if not locked_queryset.filter(**{code_field: candidate}).exists():
            return candidate
        suffix += 1
