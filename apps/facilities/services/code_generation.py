from __future__ import annotations

from django.db import models

from common.services.code_generation import generate_code_for_model, normalize_code_value


def generate_unique_code(
    *,
    model: type[models.Model],
    source_value: str | None = None,
    queryset: models.QuerySet | None = None,
    code_field: str = "code",
    max_length: int | None = None,
) -> str:
    """
    Compatibility wrapper for older services.

    Codes are now generated from backend-managed numeric sequences, not from
    user-provided names or manual form input.
    """
    return generate_code_for_model(model=model, field_name=code_field)
