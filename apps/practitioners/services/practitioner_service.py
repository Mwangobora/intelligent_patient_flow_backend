from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.practitioners.models import Practitioner
from common.exceptions import ConflictError, ValidationError

from ._shared import (
    get_organization,
    get_practitioner,
    get_practitioner_type,
    get_user,
    normalize_email,
    normalize_optional_text,
    validate_phone_number,
)
from .practitioner_number_service import generate_practitioner_number


def _ensure_unique_practitioner_user(*, organization, user, exclude_id=None) -> None:
    if user is None:
        return
    queryset = Practitioner.objects.select_for_update().filter(organization=organization, user=user)
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.exists():
        raise ConflictError("This user already has a practitioner profile in the selected organization.")


def _ensure_unique_practitioner_number(*, organization, practitioner_number: str, exclude_id=None) -> None:
    queryset = Practitioner.objects.select_for_update().filter(
        organization=organization,
        practitioner_number=practitioner_number,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.exists():
        raise ConflictError("Practitioner number already exists in the selected organization.")


@transaction.atomic
def create_practitioner(
    *,
    organization_id,
    practitioner_type_id,
    first_name: str,
    last_name: str,
    practitioner_number: str | None = None,
    user_id=None,
    middle_name: str | None = None,
    preferred_name: str | None = None,
    email: str | None = None,
    phone_number: str | None = None,
    created_by_id=None,
) -> Practitioner:
    if not first_name or not first_name.strip():
        raise ValidationError("Practitioner first_name is required.")
    if not last_name or not last_name.strip():
        raise ValidationError("Practitioner last_name is required.")

    organization = get_organization(organization_id, active_only=True, for_update=True)
    practitioner_type = get_practitioner_type(practitioner_type_id, active_only=True, for_update=True)
    user = get_user(user_id, field_label="Practitioner user", active_only=True, for_update=True) if user_id is not None else None
    created_by = get_user(created_by_id, field_label="Creator user", active_only=True) if created_by_id is not None else None

    _ensure_unique_practitioner_user(organization=organization, user=user)

    normalized_practitioner_number = normalize_optional_text(practitioner_number)
    if normalized_practitioner_number is None:
        normalized_practitioner_number = generate_practitioner_number(organization=organization)
    else:
        _ensure_unique_practitioner_number(
            organization=organization,
            practitioner_number=normalized_practitioner_number,
        )

    try:
        return Practitioner.objects.create(
            organization=organization,
            user=user,
            practitioner_type=practitioner_type,
            practitioner_number=normalized_practitioner_number,
            first_name=first_name.strip(),
            middle_name=normalize_optional_text(middle_name),
            last_name=last_name.strip(),
            preferred_name=normalize_optional_text(preferred_name),
            email=normalize_email(email),
            phone_number=validate_phone_number(phone_number),
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Practitioner could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_practitioner(*, practitioner_id, **updates) -> Practitioner:
    practitioner = get_practitioner(practitioner_id, for_update=True)
    allowed_fields = {
        "practitioner_type_id",
        "practitioner_number",
        "user_id",
        "first_name",
        "middle_name",
        "last_name",
        "preferred_name",
        "email",
        "phone_number",
    }
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported practitioner update fields: {unexpected}.")

    organization = practitioner.organization
    if not organization.is_active:
        raise ValidationError("Organization must be active.")

    if "practitioner_type_id" in updates:
        practitioner.practitioner_type = get_practitioner_type(
            updates["practitioner_type_id"],
            active_only=True,
            for_update=True,
        )
    elif not practitioner.practitioner_type.is_active:
        raise ValidationError("Practitioner type must be active.")

    if "user_id" in updates:
        practitioner.user = (
            get_user(updates["user_id"], field_label="Practitioner user", active_only=True, for_update=True)
            if updates["user_id"] is not None
            else None
        )
    elif practitioner.user_id is not None and not practitioner.user.is_active:
        raise ValidationError("Practitioner user must be active.")

    _ensure_unique_practitioner_user(organization=organization, user=practitioner.user, exclude_id=practitioner.pk)

    if "practitioner_number" in updates:
        normalized_practitioner_number = normalize_optional_text(updates["practitioner_number"])
        if normalized_practitioner_number is None:
            raise ValidationError("Practitioner number cannot be empty.")
        _ensure_unique_practitioner_number(
            organization=organization,
            practitioner_number=normalized_practitioner_number,
            exclude_id=practitioner.pk,
        )
        practitioner.practitioner_number = normalized_practitioner_number

    if "first_name" in updates:
        if not updates["first_name"] or not updates["first_name"].strip():
            raise ValidationError("Practitioner first_name is required.")
        practitioner.first_name = updates["first_name"].strip()

    if "middle_name" in updates:
        practitioner.middle_name = normalize_optional_text(updates["middle_name"])

    if "last_name" in updates:
        if not updates["last_name"] or not updates["last_name"].strip():
            raise ValidationError("Practitioner last_name is required.")
        practitioner.last_name = updates["last_name"].strip()

    if "preferred_name" in updates:
        practitioner.preferred_name = normalize_optional_text(updates["preferred_name"])

    if "email" in updates:
        practitioner.email = normalize_email(updates["email"])

    if "phone_number" in updates:
        practitioner.phone_number = validate_phone_number(updates["phone_number"])

    try:
        practitioner.save()
    except IntegrityError as exc:
        raise ConflictError("Practitioner could not be updated because a unique value already exists.") from exc
    return practitioner


@transaction.atomic
def deactivate_practitioner(*, practitioner_id) -> Practitioner:
    practitioner = get_practitioner(practitioner_id, for_update=True)
    if not practitioner.is_active:
        return practitioner
    practitioner.is_active = False
    practitioner.save(update_fields=["is_active", "updated_at"])
    return practitioner


@transaction.atomic
def reactivate_practitioner(*, practitioner_id) -> Practitioner:
    practitioner = get_practitioner(practitioner_id, for_update=True)
    if practitioner.is_active:
        return practitioner
    if not practitioner.organization.is_active:
        raise ValidationError("Organization must be active.")
    if not practitioner.practitioner_type.is_active:
        raise ValidationError("Practitioner type must be active.")
    if practitioner.user_id is not None and not practitioner.user.is_active:
        raise ValidationError("Practitioner user must be active.")
    practitioner.is_active = True
    practitioner.save(update_fields=["is_active", "updated_at"])
    return practitioner
