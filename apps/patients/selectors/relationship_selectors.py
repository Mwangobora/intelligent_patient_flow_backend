from __future__ import annotations

from django.db.models import Prefetch, Q

from apps.patients.models import PatientRelatedPerson, RelatedPersonContact, RelationshipType


def list_relationship_types(*, is_active: bool | None = None, search: str | None = None):
    queryset = RelationshipType.objects.select_related("created_by")
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
    return queryset.order_by("name")


def get_relationship_type_by_id(relationship_type_id):
    return RelationshipType.objects.select_related("created_by").filter(pk=relationship_type_id).first()


def list_related_persons(
    *,
    patient_id=None,
    linked_user_id=None,
    organization_id=None,
    is_active: bool | None = None,
    search: str | None = None,
):
    queryset = PatientRelatedPerson.objects.select_related(
        "patient",
        "patient__organization",
        "patient__registered_facility",
        "relationship_type",
        "linked_user",
    ).prefetch_related(
        Prefetch("contacts", queryset=RelatedPersonContact.objects.select_related("verified_by").order_by("-is_primary", "-created_at"))
    )
    if patient_id:
        queryset = queryset.filter(patient_id=patient_id)
    if linked_user_id:
        queryset = queryset.filter(linked_user_id=linked_user_id)
    if organization_id:
        queryset = queryset.filter(patient__organization_id=organization_id)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if search:
        queryset = queryset.filter(
            Q(first_name__icontains=search) | Q(middle_name__icontains=search) | Q(last_name__icontains=search)
        )
    return queryset.order_by("priority_order", "last_name", "first_name")


def get_related_person_by_id(related_person_id):
    return (
        PatientRelatedPerson.objects.select_related(
            "patient",
            "patient__organization",
            "patient__registered_facility",
            "patient__user",
            "relationship_type",
            "linked_user",
        )
        .prefetch_related(
            Prefetch("contacts", queryset=RelatedPersonContact.objects.select_related("verified_by").order_by("-is_primary", "-created_at"))
        )
        .filter(pk=related_person_id)
        .first()
    )


def list_related_person_contacts(
    *,
    related_person_id=None,
    patient_id=None,
    channel: str | None = None,
    is_active: bool | None = None,
):
    queryset = RelatedPersonContact.objects.select_related(
        "related_person",
        "related_person__patient",
        "related_person__patient__organization",
        "related_person__patient__registered_facility",
        "verified_by",
    )
    if related_person_id:
        queryset = queryset.filter(related_person_id=related_person_id)
    if patient_id:
        queryset = queryset.filter(related_person__patient_id=patient_id)
    if channel:
        queryset = queryset.filter(channel=channel)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    return queryset.order_by("channel", "-is_primary", "-created_at")


def get_related_person_contact_by_id(contact_id):
    return (
        RelatedPersonContact.objects.select_related(
            "related_person",
            "related_person__patient",
            "related_person__patient__organization",
            "related_person__patient__registered_facility",
            "verified_by",
        )
        .filter(pk=contact_id)
        .first()
    )
