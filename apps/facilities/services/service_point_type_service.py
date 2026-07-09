from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.facilities.models import ServicePointType
from common.exceptions import ConflictError, ValidationError

from ._shared import clean_optional_text, get_service_point_type_for_update, require_non_empty_name
from .code_generation import generate_unique_code, normalize_code_value


@transaction.atomic
def create_service_point_type(
    *,
    name: str,
    code: str | None = None,
    description: str | None = None,
) -> ServicePointType:
    cleaned_name = require_non_empty_name(value=name, label="Service point type name")
    queryset = ServicePointType.objects.select_for_update()

    if code is not None:
        normalized_code = normalize_code_value(code)
        if not normalized_code:
            raise ValidationError("Service point type code cannot be empty.")
    else:
        normalized_code = generate_unique_code(model=ServicePointType, source_value=cleaned_name)

    if queryset.filter(name__iexact=cleaned_name).exists():
        raise ConflictError("Service point type name already exists.")
    if queryset.filter(code=normalized_code).exists():
        raise ConflictError("Service point type code already exists.")

    try:
        return ServicePointType.objects.create(
            name=cleaned_name,
            code=normalized_code,
            description=clean_optional_text(description),
        )
    except IntegrityError as exc:
        raise ConflictError("Service point type could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_service_point_type(
    *,
    service_point_type_id,
    regenerate_code: bool = False,
    **updates,
) -> ServicePointType:
    service_point_type = get_service_point_type_for_update(service_point_type_id)
    allowed_fields = {"name", "code", "description"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        raise ValidationError(f"Unsupported service point type update fields: {', '.join(sorted(unexpected_fields))}.")

    next_name = service_point_type.name
    if "name" in updates:
        next_name = require_non_empty_name(value=updates["name"], label="Service point type name")

    queryset = ServicePointType.objects.select_for_update().exclude(pk=service_point_type.pk)
    if queryset.filter(name__iexact=next_name).exists():
        raise ConflictError("Service point type name already exists.")

    if regenerate_code:
        next_code = generate_unique_code(model=ServicePointType, source_value=next_name, queryset=queryset)
    elif "code" in updates and updates["code"] is not None:
        next_code = normalize_code_value(updates["code"])
        if not next_code:
            raise ValidationError("Service point type code cannot be empty.")
    else:
        next_code = service_point_type.code

    if queryset.filter(code=next_code).exists():
        raise ConflictError("Service point type code already exists.")

    service_point_type.name = next_name
    service_point_type.code = next_code
    if "description" in updates:
        service_point_type.description = clean_optional_text(updates["description"])

    try:
        service_point_type.save()
    except IntegrityError as exc:
        raise ConflictError("Service point type could not be updated because a unique value already exists.") from exc
    return service_point_type


@transaction.atomic
def deactivate_service_point_type(*, service_point_type_id) -> ServicePointType:
    service_point_type = get_service_point_type_for_update(service_point_type_id)
    if not service_point_type.is_active:
        return service_point_type

    service_point_type.is_active = False
    service_point_type.save(update_fields=["is_active", "updated_at"])
    return service_point_type
