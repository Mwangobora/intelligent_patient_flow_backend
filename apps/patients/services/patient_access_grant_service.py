from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.patients.models import PatientAccessGrant
from common.exceptions import ConflictError, NotFoundError, ValidationError

from ._shared import get_patient, get_related_person, get_role, get_user, normalize_optional_text


def _get_grant_for_update(grant_id) -> PatientAccessGrant:
    try:
        return PatientAccessGrant.objects.select_for_update().select_related(
            "patient",
            "patient__organization",
            "related_person",
            "related_person__patient",
            "grantee_user",
            "role",
        ).get(pk=grant_id)
    except PatientAccessGrant.DoesNotExist as exc:
        raise NotFoundError("Patient access grant not found.") from exc


def _resolve_grant_dates(*, starts_at=None, ends_at=None):
    resolved_starts_at = starts_at or timezone.now()
    if ends_at is not None and ends_at < resolved_starts_at:
        raise ValidationError("Patient access grant ends_at must be greater than or equal to starts_at.")
    return resolved_starts_at, ends_at


def _validate_patient_access_scope(*, patient, related_person, grantee_user, role) -> None:
    if not patient.is_active:
        raise ValidationError("Patient must be active.")
    if not patient.organization.is_active:
        raise ValidationError("Patient organization must be active.")
    if not related_person.is_active:
        raise ValidationError("Related person must be active.")
    if related_person.patient_id != patient.id:
        raise ValidationError("Related person must belong to the selected patient.")
    if related_person.linked_user_id != grantee_user.id:
        raise ValidationError("Related person linked user must match the grantee user.")
    if patient.user_id is not None and patient.user_id == grantee_user.id:
        raise ValidationError("Patient cannot receive a related-person access grant to their own record.")
    if not grantee_user.is_active:
        raise ValidationError("Grantee user must be active.")
    if not role.is_active:
        raise ValidationError("Role must be active.")
    if role.organization_id is None or role.organization_id != patient.organization_id:
        raise ValidationError("Patient access role must be scoped to the patient organization.")
    if role.facility_id is not None and role.facility.organization_id != patient.organization_id:
        raise ValidationError("Facility-scoped role must belong to the patient organization.")


def _ensure_no_active_grant(*, patient, grantee_user, role, exclude_id=None) -> None:
    queryset = PatientAccessGrant.objects.select_for_update().filter(
        patient=patient,
        grantee_user=grantee_user,
        role=role,
        is_active=True,
        revoked_at__isnull=True,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    if queryset.exists():
        raise ConflictError("An active patient access grant already exists for this patient, user, and role.")


@transaction.atomic
def grant_patient_access(
    *,
    patient_id,
    related_person_id,
    grantee_user_id,
    role_id,
    starts_at=None,
    ends_at=None,
    granted_by_id=None,
    created_by_id=None,
) -> PatientAccessGrant:
    patient = get_patient(patient_id, active_only=True, for_update=True)
    related_person = get_related_person(related_person_id, active_only=True, for_update=True)
    grantee_user = get_user(grantee_user_id, field_label="Grantee user", active_only=True, for_update=True)
    role = get_role(role_id, active_only=True, for_update=True)
    granted_by = (
        get_user(granted_by_id, field_label="Granting user", active_only=True)
        if granted_by_id is not None
        else None
    )
    created_by = (
        get_user(created_by_id, field_label="Creator user", active_only=True)
        if created_by_id is not None
        else None
    )
    resolved_starts_at, resolved_ends_at = _resolve_grant_dates(starts_at=starts_at, ends_at=ends_at)

    _validate_patient_access_scope(
        patient=patient,
        related_person=related_person,
        grantee_user=grantee_user,
        role=role,
    )
    _ensure_no_active_grant(patient=patient, grantee_user=grantee_user, role=role)

    try:
        return PatientAccessGrant.objects.create(
            patient=patient,
            related_person=related_person,
            grantee_user=grantee_user,
            role=role,
            granted_by=granted_by,
            starts_at=resolved_starts_at,
            ends_at=resolved_ends_at,
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Patient access grant could not be created because a unique value already exists.") from exc


@transaction.atomic
def revoke_patient_access(
    *,
    grant_id,
    revoked_by_id,
    revoked_reason: str,
    revoked_at=None,
) -> PatientAccessGrant:
    grant = _get_grant_for_update(grant_id)
    normalized_reason = normalize_optional_text(revoked_reason)
    if normalized_reason is None:
        raise ValidationError("Revocation reason is required.")

    if grant.revoked_at is not None and grant.revoked_by_id is not None and grant.revocation_reason is not None:
        return grant

    grant.revoked_by = get_user(revoked_by_id, field_label="Revoking user", active_only=True)
    grant.revoked_at = revoked_at or timezone.now()
    grant.revocation_reason = normalized_reason
    grant.is_active = False
    grant.save(update_fields=["revoked_by", "revoked_at", "revocation_reason", "is_active", "updated_at"])
    return grant


@transaction.atomic
def reactivate_patient_access_grant(
    *,
    grant_id,
    starts_at=None,
    ends_at=None,
    granted_by_id=None,
) -> PatientAccessGrant:
    grant = _get_grant_for_update(grant_id)
    if grant.is_active and grant.revoked_at is None:
        return grant

    resolved_starts_at, resolved_ends_at = _resolve_grant_dates(starts_at=starts_at, ends_at=ends_at)
    _validate_patient_access_scope(
        patient=grant.patient,
        related_person=grant.related_person,
        grantee_user=grant.grantee_user,
        role=grant.role,
    )
    _ensure_no_active_grant(
        patient=grant.patient,
        grantee_user=grant.grantee_user,
        role=grant.role,
        exclude_id=grant.pk,
    )

    grant.starts_at = resolved_starts_at
    grant.ends_at = resolved_ends_at
    grant.granted_by = (
        get_user(granted_by_id, field_label="Granting user", active_only=True)
        if granted_by_id is not None
        else grant.granted_by
    )
    grant.revoked_at = None
    grant.revoked_by = None
    grant.revocation_reason = None
    grant.is_active = True

    update_fields = [
        "starts_at",
        "ends_at",
        "revoked_at",
        "revoked_by",
        "revocation_reason",
        "is_active",
        "updated_at",
    ]
    if granted_by_id is not None:
        update_fields.append("granted_by")

    grant.save(update_fields=update_fields)
    return grant
