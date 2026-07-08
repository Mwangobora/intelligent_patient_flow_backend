from __future__ import annotations

import re

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from common.exceptions import ConflictError, NotFoundError, ValidationError

PHONE_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")


def _normalize_email(email: str | None) -> str | None:
    return email.strip().lower() if email else None


def _validate_phone_number(phone_number: str | None) -> str | None:
    if phone_number is None:
        return None

    normalized_phone = phone_number.strip()
    if not PHONE_RE.fullmatch(normalized_phone):
        raise ValidationError("Phone number must be in E.164 format.")
    return normalized_phone


def _ensure_contact(email: str | None, phone_number: str | None) -> tuple[str | None, str | None]:
    normalized_email = _normalize_email(email)
    normalized_phone = _validate_phone_number(phone_number)
    if not normalized_email and not normalized_phone:
        raise ValidationError("At least one of email or phone_number is required.")
    return normalized_email, normalized_phone


def _get_user_for_update(user_id) -> User:
    try:
        return User.objects.select_for_update().get(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError("User not found.") from exc


def _ensure_unique_contact(*, email: str | None, phone_number: str | None, exclude_id=None) -> None:
    queryset = User.objects.select_for_update()
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    if email and queryset.filter(email__iexact=email).exists():
        raise ConflictError("A user with this email already exists.")
    if phone_number and queryset.filter(phone_number=phone_number).exists():
        raise ConflictError("A user with this phone number already exists.")


@transaction.atomic
def create_user(
    *,
    password: str | None = None,
    email: str | None = None,
    phone_number: str | None = None,
    first_name: str,
    last_name: str,
    middle_name: str | None = None,
) -> User:
    if not first_name or not first_name.strip():
        raise ValidationError("First name is required.")
    if not last_name or not last_name.strip():
        raise ValidationError("Last name is required.")

    normalized_email, normalized_phone = _ensure_contact(email, phone_number)
    _ensure_unique_contact(email=normalized_email, phone_number=normalized_phone)

    return User.objects.create_user(
        email=normalized_email,
        phone_number=normalized_phone,
        password=password,
        first_name=first_name.strip(),
        middle_name=middle_name.strip() if middle_name else None,
        last_name=last_name.strip(),
        is_staff=False,
        is_superuser=False,
    )


@transaction.atomic
def create_superuser_user(
    *,
    password: str,
    email: str,
    first_name: str,
    last_name: str,
    middle_name: str | None = None,
    phone_number: str | None = None,
) -> User:
    if not password:
        raise ValidationError("Password is required for superuser creation.")

    normalized_email, normalized_phone = _ensure_contact(email, phone_number)
    if not normalized_email:
        raise ValidationError("Superuser creation requires an email address.")

    _ensure_unique_contact(email=normalized_email, phone_number=normalized_phone)
    return User.objects.create_superuser(
        email=normalized_email,
        password=password,
        first_name=first_name.strip(),
        middle_name=middle_name.strip() if middle_name else None,
        last_name=last_name.strip(),
        phone_number=normalized_phone,
    )


@transaction.atomic
def activate_user(*, user_id) -> User:
    user = _get_user_for_update(user_id)
    if user.is_active:
        return user

    user.is_active = True
    user.save(update_fields=["is_active", "updated_at"])
    return user


@transaction.atomic
def deactivate_user(*, user_id) -> User:
    user = _get_user_for_update(user_id)
    if not user.is_active:
        return user

    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])
    return user


@transaction.atomic
def verify_email(*, user_id) -> User:
    user = _get_user_for_update(user_id)
    if not user.email:
        raise ValidationError("User does not have an email address to verify.")

    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at", "updated_at"])
    return user


@transaction.atomic
def verify_phone(*, user_id) -> User:
    user = _get_user_for_update(user_id)
    if not user.phone_number:
        raise ValidationError("User does not have a phone number to verify.")

    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at", "updated_at"])
    return user
