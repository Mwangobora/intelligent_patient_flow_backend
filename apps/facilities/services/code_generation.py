from __future__ import annotations

import re

from django.db import models

from common.exceptions import ValidationError

UNSUPPORTED_CODE_CHARS_RE = re.compile(r"[^A-Z0-9_]+")
SEPARATOR_RE = re.compile(r"[\s\-]+")
UNDERSCORE_RE = re.compile(r"_+")
SUFFIX_RE_TEMPLATE = r"^{prefix}(?:_(?P<suffix>\d+))?$"


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
    base_code = normalize_code_value(source_value)
    if not base_code:
        raise ValidationError("A valid non-empty source value is required to generate a code.")

    if queryset is None:
        queryset = model._default_manager.all()

    if max_length is None:
        max_length = model._meta.get_field(code_field).max_length

    base_code = base_code[:max_length].rstrip("_")
    if not base_code:
        raise ValidationError("The generated code is empty after normalization.")

    candidate_queryset = queryset.select_for_update().filter(**{f"{code_field}__startswith": base_code})
    existing_codes = list(candidate_queryset.values_list(code_field, flat=True))
    if base_code not in existing_codes:
        return base_code

    suffix_pattern = re.compile(SUFFIX_RE_TEMPLATE.format(prefix=re.escape(base_code)))
    next_suffix = 2
    for existing_code in existing_codes:
        match = suffix_pattern.match(existing_code)
        if not match:
            continue
        suffix_value = match.group("suffix")
        if suffix_value is not None:
            next_suffix = max(next_suffix, int(suffix_value) + 1)

    while True:
        suffix = f"_{next_suffix}"
        trimmed_base = base_code[: max_length - len(suffix)].rstrip("_")
        candidate = f"{trimmed_base}{suffix}"
        if candidate not in existing_codes:
            return candidate
        next_suffix += 1
