from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.patients.models import PatientIdentifierType
from common.exceptions import ConflictError, NotFoundError, ValidationError
from common.services.code_generation import generate_code

from ._shared import get_organization, get_user, normalize_optional_text


def _get_identifier_type_for_update(identifier_type_id) -> PatientIdentifierType:
    try:
        return PatientIdentifierType.objects.select_for_update().get(pk=identifier_type_id)
    except PatientIdentifierType.DoesNotExist as exc:
        raise NotFoundError("Patient identifier type not found.") from exc


def _get_scope_queryset(*, organization):
    if organization is None:
        return PatientIdentifierType.objects.filter(organization__isnull=True)
    return PatientIdentifierType.objects.filter(organization=organization)


def _ensure_unique_scope_values(*, organization, name: str, code: str, exclude_id=None) -> None:
    queryset = _get_scope_queryset(organization=organization).select_for_update()
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    if queryset.filter(name__iexact=name).exists():
        raise ConflictError("Patient identifier type name already exists in this scope.")
    if queryset.filter(code=code).exists():
        raise ConflictError("Patient identifier type code already exists in this scope.")


@transaction.atomic
def create_patient_identifier_type(
    *,
    name: str,
    organization_id=None,
    description: str | None = None,
    code: str | None = None,
    is_sensitive: bool = True,
    created_by_id=None,
) -> PatientIdentifierType:
    if not name or not name.strip():
        raise ValidationError("Patient identifier type name is required.")

    organization = (
        get_organization(organization_id, active_only=True, for_update=True)
        if organization_id is not None
        else None
    )
    created_by = get_user(created_by_id, field_label="Creator user") if created_by_id is not None else None
    cleaned_name = name.strip()

    normalized_code = generate_code("patient_identifier_type")

    _ensure_unique_scope_values(
        organization=organization,
        name=cleaned_name,
        code=normalized_code,
    )

    try:
        return PatientIdentifierType.objects.create(
            organization=organization,
            name=cleaned_name,
            code=normalized_code,
            description=normalize_optional_text(description),
            is_sensitive=bool(is_sensitive),
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Patient identifier type could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_patient_identifier_type(
    *,
    identifier_type_id,
    regenerate_code: bool = False,
    **updates,
) -> PatientIdentifierType:
    identifier_type = _get_identifier_type_for_update(identifier_type_id)

    allowed_fields = {"name", "description", "is_sensitive"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported patient identifier type update fields: {unexpected}.")

    next_name = identifier_type.name
    if "name" in updates:
        if not updates["name"] or not updates["name"].strip():
            raise ValidationError("Patient identifier type name is required.")
        next_name = updates["name"].strip()

    next_code = identifier_type.code

    _ensure_unique_scope_values(
        organization=identifier_type.organization,
        name=next_name,
        code=next_code,
        exclude_id=identifier_type.pk,
    )

    identifier_type.name = next_name
    identifier_type.code = next_code

    if "description" in updates:
        identifier_type.description = normalize_optional_text(updates["description"])
    if "is_sensitive" in updates:
        identifier_type.is_sensitive = bool(updates["is_sensitive"])

    try:
        identifier_type.save()
    except IntegrityError as exc:
        raise ConflictError("Patient identifier type could not be updated because a unique value already exists.") from exc
    return identifier_type


@transaction.atomic
def deactivate_patient_identifier_type(*, identifier_type_id) -> PatientIdentifierType:
    identifier_type = _get_identifier_type_for_update(identifier_type_id)
    if not identifier_type.is_active:
        return identifier_type

    identifier_type.is_active = False
    identifier_type.save(update_fields=["is_active", "updated_at"])
    return identifier_type
