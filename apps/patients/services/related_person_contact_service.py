from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.patients.models import RelatedPersonContact
from common.exceptions import ConflictError, NotFoundError, ValidationError

from ._crypto import build_value_hash, encrypt_sensitive_value
from ._shared import get_related_person, get_user, normalize_email, normalize_optional_text, validate_phone_number


def _get_contact_for_update(contact_id) -> RelatedPersonContact:
    try:
        return RelatedPersonContact.objects.select_for_update().select_related(
            "related_person",
            "related_person__patient",
        ).get(pk=contact_id)
    except RelatedPersonContact.DoesNotExist as exc:
        raise NotFoundError("Related person contact not found.") from exc


def _normalize_contact_value(*, channel: str, value: str) -> str:
    if channel not in RelatedPersonContact.Channel.values:
        raise ValidationError("Invalid related person contact channel.")

    if channel == RelatedPersonContact.Channel.PHONE:
        normalized_value = validate_phone_number(value)
    else:
        normalized_value = normalize_email(value)

    if normalized_value is None:
        raise ValidationError("Related person contact value is required.")
    return normalized_value


def _clear_other_primary_contacts(*, related_person, channel: str, exclude_id=None) -> None:
    queryset = RelatedPersonContact.objects.select_for_update().filter(
        related_person=related_person,
        channel=channel,
        is_active=True,
        is_primary=True,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    queryset.update(is_primary=False, updated_at=timezone.now())


@transaction.atomic
def add_related_person_contact(
    *,
    related_person_id,
    channel: str,
    value: str,
    label: str | None = None,
    is_primary: bool = False,
    created_by_id=None,
) -> RelatedPersonContact:
    related_person = get_related_person(related_person_id, active_only=True, for_update=True)
    if not related_person.patient.is_active:
        raise ValidationError("Patient must be active.")

    created_by = get_user(created_by_id, field_label="Creator user") if created_by_id is not None else None
    normalized_value = _normalize_contact_value(channel=channel, value=value)
    value_hash = build_value_hash(normalized_value)

    if RelatedPersonContact.objects.select_for_update().filter(
        related_person=related_person,
        channel=channel,
        value_hash=value_hash,
    ).exists():
        raise ConflictError("This related person contact already exists.")

    if is_primary:
        _clear_other_primary_contacts(related_person=related_person, channel=channel)

    try:
        return RelatedPersonContact.objects.create(
            related_person=related_person,
            channel=channel,
            label=normalize_optional_text(label),
            value_encrypted=encrypt_sensitive_value(normalized_value),
            value_hash=value_hash,
            is_primary=bool(is_primary),
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Related person contact could not be created because a unique value already exists.") from exc


@transaction.atomic
def verify_related_person_contact(
    *,
    contact_id,
    verified_by_id,
    verified_at=None,
) -> RelatedPersonContact:
    contact = _get_contact_for_update(contact_id)
    if not contact.is_active:
        raise ValidationError("Related person contact must be active.")
    if not contact.related_person.is_active:
        raise ValidationError("Related person must be active.")
    if not contact.related_person.patient.is_active:
        raise ValidationError("Patient must be active.")

    if contact.verified_at is not None and contact.verified_by_id is not None:
        return contact

    contact.verified_by = get_user(verified_by_id, field_label="Verifying user")
    contact.verified_at = verified_at or timezone.now()
    contact.save(update_fields=["verified_at", "verified_by", "updated_at"])
    return contact


@transaction.atomic
def deactivate_related_person_contact(*, contact_id) -> RelatedPersonContact:
    contact = _get_contact_for_update(contact_id)
    if not contact.is_active:
        return contact
    if not contact.related_person.is_active:
        raise ValidationError("Related person must be active.")
    if not contact.related_person.patient.is_active:
        raise ValidationError("Patient must be active.")

    contact.is_active = False
    contact.is_primary = False
    contact.save(update_fields=["is_active", "is_primary", "updated_at"])
    return contact


@transaction.atomic
def set_primary_related_person_contact(*, contact_id) -> RelatedPersonContact:
    contact = _get_contact_for_update(contact_id)
    if not contact.is_active:
        raise ValidationError("Primary related person contact must be active.")
    if not contact.related_person.is_active:
        raise ValidationError("Related person must be active.")
    if not contact.related_person.patient.is_active:
        raise ValidationError("Patient must be active.")

    _clear_other_primary_contacts(
        related_person=contact.related_person,
        channel=contact.channel,
        exclude_id=contact.pk,
    )
    if contact.is_primary:
        return contact

    contact.is_primary = True
    contact.save(update_fields=["is_primary", "updated_at"])
    return contact
