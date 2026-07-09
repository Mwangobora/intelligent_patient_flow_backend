from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.patients.models import PatientRelatedPerson
from common.exceptions import ConflictError, NotFoundError, ValidationError

from ._shared import (
    get_patient,
    get_relationship_type,
    get_user,
    normalize_optional_text,
)


def _get_related_person_for_update(related_person_id) -> PatientRelatedPerson:
    try:
        return PatientRelatedPerson.objects.select_for_update().select_related(
            "patient",
            "relationship_type",
        ).get(pk=related_person_id)
    except PatientRelatedPerson.DoesNotExist as exc:
        raise NotFoundError("Patient related person not found.") from exc


def _validate_linked_user(*, patient, linked_user) -> None:
    if linked_user is None:
        return
    if patient.user_id is not None and linked_user.id == patient.user_id:
        raise ValidationError("Linked user cannot be the same as the patient user.")


def _validate_priority_order(priority_order) -> int:
    try:
        normalized_priority_order = int(priority_order)
    except (TypeError, ValueError) as exc:
        raise ValidationError("priority_order must be greater than 0.") from exc

    if normalized_priority_order <= 0:
        raise ValidationError("priority_order must be greater than 0.")
    return normalized_priority_order


def _ensure_unique_linked_user(*, patient, linked_user, exclude_id=None) -> None:
    if linked_user is None:
        return

    queryset = PatientRelatedPerson.objects.select_for_update().filter(
        patient=patient,
        linked_user=linked_user,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    if queryset.exists():
        raise ConflictError("This linked user is already attached to the patient as a related person.")


@transaction.atomic
def add_related_person(
    *,
    patient_id,
    relationship_type_id,
    first_name: str,
    last_name: str,
    middle_name: str | None = None,
    linked_user_id=None,
    is_guardian: bool = False,
    is_caregiver: bool = False,
    is_next_of_kin: bool = False,
    is_emergency_contact: bool = False,
    priority_order: int = 1,
    created_by_id=None,
) -> PatientRelatedPerson:
    if not first_name or not first_name.strip():
        raise ValidationError("Related person first_name is required.")
    if not last_name or not last_name.strip():
        raise ValidationError("Related person last_name is required.")

    patient = get_patient(patient_id, active_only=True, for_update=True)
    relationship_type = get_relationship_type(relationship_type_id, active_only=True, for_update=True)
    linked_user = (
        get_user(linked_user_id, field_label="Linked user", active_only=True, for_update=True)
        if linked_user_id is not None
        else None
    )
    created_by = get_user(created_by_id, field_label="Creator user") if created_by_id is not None else None

    _validate_linked_user(patient=patient, linked_user=linked_user)
    _ensure_unique_linked_user(patient=patient, linked_user=linked_user)

    try:
        return PatientRelatedPerson.objects.create(
            patient=patient,
            relationship_type=relationship_type,
            linked_user=linked_user,
            first_name=first_name.strip(),
            middle_name=normalize_optional_text(middle_name),
            last_name=last_name.strip(),
            is_guardian=bool(is_guardian),
            is_caregiver=bool(is_caregiver),
            is_next_of_kin=bool(is_next_of_kin),
            is_emergency_contact=bool(is_emergency_contact),
            priority_order=_validate_priority_order(priority_order),
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Related person could not be created because a unique value already exists.") from exc


@transaction.atomic
def update_related_person(
    *,
    related_person_id,
    **updates,
) -> PatientRelatedPerson:
    related_person = _get_related_person_for_update(related_person_id)
    if not related_person.patient.is_active:
        raise ValidationError("Patient must be active.")
    if not related_person.is_active:
        raise ValidationError("Related person must be active.")

    allowed_fields = {
        "relationship_type_id",
        "linked_user_id",
        "first_name",
        "middle_name",
        "last_name",
        "is_guardian",
        "is_caregiver",
        "is_next_of_kin",
        "is_emergency_contact",
        "priority_order",
    }
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported related person update fields: {unexpected}.")

    if "relationship_type_id" in updates:
        related_person.relationship_type = get_relationship_type(
            updates["relationship_type_id"],
            active_only=True,
            for_update=True,
        )
    elif not related_person.relationship_type.is_active:
        raise ValidationError("Relationship type must be active.")

    if "linked_user_id" in updates:
        related_person.linked_user = (
            get_user(updates["linked_user_id"], field_label="Linked user", active_only=True, for_update=True)
            if updates["linked_user_id"] is not None
            else None
        )
    elif related_person.linked_user_id is not None and not related_person.linked_user.is_active:
        raise ValidationError("Linked user must be active.")

    _validate_linked_user(patient=related_person.patient, linked_user=related_person.linked_user)
    _ensure_unique_linked_user(
        patient=related_person.patient,
        linked_user=related_person.linked_user,
        exclude_id=related_person.pk,
    )

    if "first_name" in updates:
        if not updates["first_name"] or not updates["first_name"].strip():
            raise ValidationError("Related person first_name is required.")
        related_person.first_name = updates["first_name"].strip()

    if "middle_name" in updates:
        related_person.middle_name = normalize_optional_text(updates["middle_name"])

    if "last_name" in updates:
        if not updates["last_name"] or not updates["last_name"].strip():
            raise ValidationError("Related person last_name is required.")
        related_person.last_name = updates["last_name"].strip()

    for field_name in ("is_guardian", "is_caregiver", "is_next_of_kin", "is_emergency_contact"):
        if field_name in updates:
            setattr(related_person, field_name, bool(updates[field_name]))

    if "priority_order" in updates:
        related_person.priority_order = _validate_priority_order(updates["priority_order"])

    try:
        related_person.save()
    except IntegrityError as exc:
        raise ConflictError("Related person could not be updated because a unique value already exists.") from exc
    return related_person


@transaction.atomic
def deactivate_related_person(*, related_person_id) -> PatientRelatedPerson:
    related_person = _get_related_person_for_update(related_person_id)
    if not related_person.is_active:
        return related_person
    if not related_person.patient.is_active:
        raise ValidationError("Patient must be active.")

    related_person.is_active = False
    related_person.save(update_fields=["is_active", "updated_at"])
    return related_person
