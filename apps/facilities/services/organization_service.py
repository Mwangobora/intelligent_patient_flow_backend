from __future__ import annotations

import re

from django.db import IntegrityError, transaction

from apps.facilities.models import Organization
from common.exceptions import ConflictError, NotFoundError, ValidationError

from .code_generation import generate_unique_code

PHONE_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")


def _normalize_email(email: str | None) -> str | None:
    if email is None:
        return None

    normalized_email = email.strip().lower()
    return normalized_email or None


def _validate_phone_number(phone_number: str | None) -> str | None:
    if phone_number is None:
        return None

    normalized_phone = phone_number.strip()
    if not normalized_phone:
        return None
    if not PHONE_RE.fullmatch(normalized_phone):
        raise ValidationError("Phone number must be in E.164 format.")
    return normalized_phone


def _get_organization_for_update(organization_id) -> Organization:
    try:
        return Organization.objects.select_for_update().get(pk=organization_id)
    except Organization.DoesNotExist as exc:
        raise NotFoundError("Organization not found.") from exc


@transaction.atomic
def create_organization(
    *,
    name: str,
    legal_name: str | None = None,
    email: str | None = None,
    phone_number: str | None = None,
    registration_number: str | None = None,
    code: str | None = None,
) -> Organization:
    if not name or not name.strip():
        raise ValidationError("Organization name is required.")

    normalized_code = generate_unique_code(model=Organization, source_value=name)
    if Organization.objects.select_for_update().filter(code=normalized_code).exists():
        raise ConflictError("Organization code already exists.")

    try:
        organization = Organization.objects.create(
            name=name.strip(),
            legal_name=legal_name.strip() if legal_name else None,
            email=_normalize_email(email),
            phone_number=_validate_phone_number(phone_number),
            registration_number=registration_number.strip() if registration_number else None,
            code=normalized_code,
        )
    except IntegrityError as exc:
        raise ConflictError("Organization could not be created because a unique value already exists.") from exc
    return organization


@transaction.atomic
def update_organization(
    *,
    organization_id,
    regenerate_code: bool = False,
    **updates,
) -> Organization:
    organization = _get_organization_for_update(organization_id)

    allowed_fields = {"name", "legal_name", "email", "phone_number", "registration_number"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported organization update fields: {unexpected}.")

    if "name" in updates:
        if not updates["name"] or not updates["name"].strip():
            raise ValidationError("Organization name is required.")
        organization.name = updates["name"].strip()

    if "legal_name" in updates:
        organization.legal_name = updates["legal_name"].strip() if updates["legal_name"] else None

    if "email" in updates:
        organization.email = _normalize_email(updates["email"])

    if "phone_number" in updates:
        organization.phone_number = _validate_phone_number(updates["phone_number"])

    if "registration_number" in updates:
        organization.registration_number = updates["registration_number"].strip() if updates["registration_number"] else None

    try:
        organization.save()
    except IntegrityError as exc:
        raise ConflictError("Organization could not be updated because a unique value already exists.") from exc
    return organization


@transaction.atomic
def deactivate_organization(*, organization_id) -> Organization:
    organization = _get_organization_for_update(organization_id)
    if not organization.is_active:
        return organization

    organization.is_active = False
    organization.save(update_fields=["is_active", "updated_at"])
    return organization
