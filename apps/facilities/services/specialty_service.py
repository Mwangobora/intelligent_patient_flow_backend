from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.facilities.models import Specialty
from common.exceptions import ConflictError, ValidationError

from ._shared import clean_optional_text, ensure_parent_specialty_valid, get_specialty_for_update, require_non_empty_name
from .code_generation import generate_unique_code, normalize_code_value


@transaction.atomic
def create_specialty(
    *,
    name: str,
    code: str | None = None,
    description: str | None = None,
    parent_specialty_id=None,
) -> Specialty:
    cleaned_name = require_non_empty_name(value=name, label="Specialty name")
    parent_specialty = get_specialty_for_update(parent_specialty_id) if parent_specialty_id else None
    ensure_parent_specialty_valid(parent_specialty=parent_specialty)

    if code is not None:
        normalized_code = normalize_code_value(code)
        if not normalized_code:
            raise ValidationError("Specialty code cannot be empty.")
    else:
        normalized_code = generate_unique_code(model=Specialty, source_value=cleaned_name)

    queryset = Specialty.objects.select_for_update()
    if queryset.filter(code=normalized_code).exists():
        raise ConflictError("Specialty code already exists.")
    if queryset.filter(name__iexact=cleaned_name).exists():
        raise ConflictError("Specialty name already exists.")

    try:
        return Specialty.objects.create(
            parent_specialty=parent_specialty,
            name=cleaned_name,
            code=normalized_code,
            description=clean_optional_text(description),
        )
    except IntegrityError as exc:
        raise ConflictError("Specialty could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_specialty(
    *,
    specialty_id,
    regenerate_code: bool = False,
    **updates,
) -> Specialty:
    specialty = get_specialty_for_update(specialty_id)
    allowed_fields = {"parent_specialty_id", "name", "code", "description"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        raise ValidationError(f"Unsupported specialty update fields: {', '.join(sorted(unexpected_fields))}.")

    parent_specialty = (
        get_specialty_for_update(updates["parent_specialty_id"])
        if "parent_specialty_id" in updates and updates["parent_specialty_id"] is not None
        else None if "parent_specialty_id" in updates else specialty.parent_specialty
    )
    ensure_parent_specialty_valid(specialty_id=specialty.id, parent_specialty=parent_specialty)

    next_name = specialty.name
    if "name" in updates:
        next_name = require_non_empty_name(value=updates["name"], label="Specialty name")

    queryset = Specialty.objects.select_for_update().exclude(pk=specialty.pk)
    if queryset.filter(name__iexact=next_name).exists():
        raise ConflictError("Specialty name already exists.")

    if regenerate_code:
        next_code = generate_unique_code(model=Specialty, source_value=next_name, queryset=queryset)
    elif "code" in updates and updates["code"] is not None:
        next_code = normalize_code_value(updates["code"])
        if not next_code:
            raise ValidationError("Specialty code cannot be empty.")
    else:
        next_code = specialty.code

    if queryset.filter(code=next_code).exists():
        raise ConflictError("Specialty code already exists.")

    specialty.parent_specialty = parent_specialty
    specialty.name = next_name
    specialty.code = next_code
    if "description" in updates:
        specialty.description = clean_optional_text(updates["description"])

    try:
        specialty.save()
    except IntegrityError as exc:
        raise ConflictError("Specialty could not be updated because a unique value already exists.") from exc
    return specialty


@transaction.atomic
def deactivate_specialty(*, specialty_id) -> Specialty:
    specialty = get_specialty_for_update(specialty_id)
    if not specialty.is_active:
        return specialty

    specialty.is_active = False
    specialty.save(update_fields=["is_active", "updated_at"])
    return specialty
