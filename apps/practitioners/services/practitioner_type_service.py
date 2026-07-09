from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.facilities.services.code_generation import generate_unique_code, normalize_code_value
from apps.practitioners.models import PractitionerType
from common.exceptions import ConflictError, NotFoundError, ValidationError

from ._shared import get_user, normalize_optional_text


def _get_practitioner_type_for_update(practitioner_type_id) -> PractitionerType:
    try:
        return PractitionerType.objects.select_for_update().get(pk=practitioner_type_id)
    except PractitionerType.DoesNotExist as exc:
        raise NotFoundError("Practitioner type not found.") from exc


def _ensure_unique_practitioner_type(*, name: str, code: str, exclude_id=None) -> None:
    queryset = PractitionerType.objects.select_for_update()
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.filter(name__iexact=name).exists():
        raise ConflictError("Practitioner type name already exists.")
    if queryset.filter(code=code).exists():
        raise ConflictError("Practitioner type code already exists.")


@transaction.atomic
def create_practitioner_type(
    *,
    name: str,
    description: str | None = None,
    code: str | None = None,
    requires_license: bool = False,
    created_by_id=None,
) -> PractitionerType:
    if not name or not name.strip():
        raise ValidationError("Practitioner type name is required.")
    cleaned_name = name.strip()
    created_by = get_user(created_by_id, field_label="Creator user") if created_by_id is not None else None

    if code is not None:
        normalized_code = normalize_code_value(code)
        if not normalized_code:
            raise ValidationError("Practitioner type code cannot be empty.")
    else:
        normalized_code = generate_unique_code(model=PractitionerType, source_value=cleaned_name)

    _ensure_unique_practitioner_type(name=cleaned_name, code=normalized_code)

    try:
        return PractitionerType.objects.create(
            name=cleaned_name,
            code=normalized_code,
            description=normalize_optional_text(description),
            requires_license=bool(requires_license),
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Practitioner type could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_practitioner_type(*, practitioner_type_id, regenerate_code: bool = False, **updates) -> PractitionerType:
    practitioner_type = _get_practitioner_type_for_update(practitioner_type_id)
    allowed_fields = {"name", "code", "description", "requires_license"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported practitioner type update fields: {unexpected}.")

    next_name = practitioner_type.name
    if "name" in updates:
        if not updates["name"] or not updates["name"].strip():
            raise ValidationError("Practitioner type name is required.")
        next_name = updates["name"].strip()

    if regenerate_code:
        next_code = generate_unique_code(
            model=PractitionerType,
            source_value=next_name,
            queryset=PractitionerType.objects.exclude(pk=practitioner_type.pk),
        )
    elif "code" in updates and updates["code"] is not None:
        next_code = normalize_code_value(updates["code"])
        if not next_code:
            raise ValidationError("Practitioner type code cannot be empty.")
    else:
        next_code = practitioner_type.code

    _ensure_unique_practitioner_type(name=next_name, code=next_code, exclude_id=practitioner_type.pk)

    practitioner_type.name = next_name
    practitioner_type.code = next_code
    if "description" in updates:
        practitioner_type.description = normalize_optional_text(updates["description"])
    if "requires_license" in updates:
        practitioner_type.requires_license = bool(updates["requires_license"])

    try:
        practitioner_type.save()
    except IntegrityError as exc:
        raise ConflictError("Practitioner type could not be updated because a unique value already exists.") from exc
    return practitioner_type


@transaction.atomic
def deactivate_practitioner_type(*, practitioner_type_id) -> PractitionerType:
    practitioner_type = _get_practitioner_type_for_update(practitioner_type_id)
    if not practitioner_type.is_active:
        return practitioner_type
    practitioner_type.is_active = False
    practitioner_type.save(update_fields=["is_active", "updated_at"])
    return practitioner_type
