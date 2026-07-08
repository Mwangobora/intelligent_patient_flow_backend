from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.facilities.services.code_generation import generate_unique_code, normalize_code_value
from apps.patients.models import RelationshipType
from common.exceptions import ConflictError, NotFoundError, ValidationError

from ._shared import get_user, normalize_optional_text


def _get_relationship_type_for_update(relationship_type_id) -> RelationshipType:
    try:
        return RelationshipType.objects.select_for_update().get(pk=relationship_type_id)
    except RelationshipType.DoesNotExist as exc:
        raise NotFoundError("Relationship type not found.") from exc


def _ensure_unique_relationship_type(*, name: str, code: str, exclude_id=None) -> None:
    queryset = RelationshipType.objects.select_for_update()
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    if queryset.filter(name__iexact=name).exists():
        raise ConflictError("Relationship type name already exists.")
    if queryset.filter(code=code).exists():
        raise ConflictError("Relationship type code already exists.")


@transaction.atomic
def create_relationship_type(
    *,
    name: str,
    description: str | None = None,
    code: str | None = None,
    created_by_id=None,
) -> RelationshipType:
    if not name or not name.strip():
        raise ValidationError("Relationship type name is required.")

    cleaned_name = name.strip()
    created_by = get_user(created_by_id, field_label="Creator user") if created_by_id is not None else None

    if code is not None:
        normalized_code = normalize_code_value(code)
        if not normalized_code:
            raise ValidationError("Relationship type code cannot be empty.")
    else:
        normalized_code = generate_unique_code(
            model=RelationshipType,
            source_value=cleaned_name,
        )

    _ensure_unique_relationship_type(name=cleaned_name, code=normalized_code)

    try:
        return RelationshipType.objects.create(
            name=cleaned_name,
            code=normalized_code,
            description=normalize_optional_text(description),
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Relationship type could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_relationship_type(
    *,
    relationship_type_id,
    regenerate_code: bool = False,
    **updates,
) -> RelationshipType:
    relationship_type = _get_relationship_type_for_update(relationship_type_id)

    allowed_fields = {"name", "code", "description"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported relationship type update fields: {unexpected}.")

    next_name = relationship_type.name
    if "name" in updates:
        if not updates["name"] or not updates["name"].strip():
            raise ValidationError("Relationship type name is required.")
        next_name = updates["name"].strip()

    if regenerate_code:
        next_code = generate_unique_code(
            model=RelationshipType,
            source_value=next_name,
            queryset=RelationshipType.objects.exclude(pk=relationship_type.pk),
        )
    elif "code" in updates and updates["code"] is not None:
        next_code = normalize_code_value(updates["code"])
        if not next_code:
            raise ValidationError("Relationship type code cannot be empty.")
    else:
        next_code = relationship_type.code

    _ensure_unique_relationship_type(
        name=next_name,
        code=next_code,
        exclude_id=relationship_type.pk,
    )

    relationship_type.name = next_name
    relationship_type.code = next_code

    if "description" in updates:
        relationship_type.description = normalize_optional_text(updates["description"])

    try:
        relationship_type.save()
    except IntegrityError as exc:
        raise ConflictError("Relationship type could not be updated because a unique value already exists.") from exc
    return relationship_type


@transaction.atomic
def deactivate_relationship_type(*, relationship_type_id) -> RelationshipType:
    relationship_type = _get_relationship_type_for_update(relationship_type_id)
    if not relationship_type.is_active:
        return relationship_type

    relationship_type.is_active = False
    relationship_type.save(update_fields=["is_active", "updated_at"])
    return relationship_type
