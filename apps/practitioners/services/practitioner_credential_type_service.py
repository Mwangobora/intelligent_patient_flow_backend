from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.practitioners.models import PractitionerCredentialType
from common.exceptions import ConflictError, NotFoundError, ValidationError
from common.services.code_generation import generate_code

from ._shared import get_organization, get_user, normalize_country_code, normalize_optional_text


def _get_credential_type_for_update(credential_type_id) -> PractitionerCredentialType:
    try:
        return PractitionerCredentialType.objects.select_for_update().get(pk=credential_type_id)
    except PractitionerCredentialType.DoesNotExist as exc:
        raise NotFoundError("Practitioner credential type not found.") from exc


def _get_scope_queryset(*, organization):
    if organization is None:
        return PractitionerCredentialType.objects.filter(organization__isnull=True)
    return PractitionerCredentialType.objects.filter(organization=organization)


def _ensure_unique_scope_values(*, organization, name: str, code: str, exclude_id=None) -> None:
    queryset = _get_scope_queryset(organization=organization).select_for_update()
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.filter(name__iexact=name).exists():
        raise ConflictError("Practitioner credential type name already exists in this scope.")
    if queryset.filter(code=code).exists():
        raise ConflictError("Practitioner credential type code already exists in this scope.")


@transaction.atomic
def create_practitioner_credential_type(
    *,
    name: str,
    organization_id=None,
    description: str | None = None,
    code: str | None = None,
    country_code: str | None = None,
    requires_expiry_date: bool = False,
    requires_verification: bool = True,
    created_by_id=None,
) -> PractitionerCredentialType:
    if not name or not name.strip():
        raise ValidationError("Practitioner credential type name is required.")
    organization = get_organization(organization_id, active_only=True, for_update=True) if organization_id is not None else None
    created_by = get_user(created_by_id, field_label="Creator user", active_only=True) if created_by_id is not None else None
    cleaned_name = name.strip()

    normalized_code = generate_code("practitioner_credential_type")

    _ensure_unique_scope_values(organization=organization, name=cleaned_name, code=normalized_code)

    try:
        return PractitionerCredentialType.objects.create(
            organization=organization,
            name=cleaned_name,
            code=normalized_code,
            description=normalize_optional_text(description),
            country_code=normalize_country_code(country_code),
            requires_expiry_date=bool(requires_expiry_date),
            requires_verification=bool(requires_verification),
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Practitioner credential type could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_practitioner_credential_type(*, credential_type_id, regenerate_code: bool = False, **updates) -> PractitionerCredentialType:
    credential_type = _get_credential_type_for_update(credential_type_id)
    allowed_fields = {"name", "description", "country_code", "requires_expiry_date", "requires_verification"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported practitioner credential type update fields: {unexpected}.")

    next_name = credential_type.name
    if "name" in updates:
        if not updates["name"] or not updates["name"].strip():
            raise ValidationError("Practitioner credential type name is required.")
        next_name = updates["name"].strip()

    next_code = credential_type.code

    _ensure_unique_scope_values(
        organization=credential_type.organization,
        name=next_name,
        code=next_code,
        exclude_id=credential_type.pk,
    )

    credential_type.name = next_name
    credential_type.code = next_code
    if "description" in updates:
        credential_type.description = normalize_optional_text(updates["description"])
    if "country_code" in updates:
        credential_type.country_code = normalize_country_code(updates["country_code"])
    if "requires_expiry_date" in updates:
        credential_type.requires_expiry_date = bool(updates["requires_expiry_date"])
    if "requires_verification" in updates:
        credential_type.requires_verification = bool(updates["requires_verification"])

    try:
        credential_type.save()
    except IntegrityError as exc:
        raise ConflictError("Practitioner credential type could not be updated because a unique value already exists.") from exc
    return credential_type


@transaction.atomic
def deactivate_practitioner_credential_type(*, credential_type_id) -> PractitionerCredentialType:
    credential_type = _get_credential_type_for_update(credential_type_id)
    if not credential_type.is_active:
        return credential_type
    credential_type.is_active = False
    credential_type.save(update_fields=["is_active", "updated_at"])
    return credential_type
