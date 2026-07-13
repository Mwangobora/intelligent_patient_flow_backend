from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.facilities.models import Facility, Organization
from common.exceptions import ConflictError, NotFoundError, ValidationError

from .audit_metadata_service import build_change_metadata, sanitize_audit_metadata

User = get_user_model()
OUTCOMES = {"success", "failure", "denied"}


def _clean_required(value: str | None, field_name: str) -> str:
    if value is None or not str(value).strip():
        raise ValidationError(f"{field_name} is required.")
    return str(value).strip()


def _get_user(user_id):
    if user_id is None:
        return None
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        raise NotFoundError("Actor user not found.")
    return user


def _get_organization(organization_id):
    if organization_id is None:
        return None
    organization = Organization.objects.filter(pk=organization_id).first()
    if organization is None:
        raise NotFoundError("Organization not found.")
    return organization


def _get_facility(facility_id):
    if facility_id is None:
        return None
    facility = Facility.objects.select_related("organization").filter(pk=facility_id).first()
    if facility is None:
        raise NotFoundError("Facility not found.")
    return facility


def _validate_scope(organization, facility) -> None:
    if organization and not organization.is_active:
        raise ValidationError("Organization must be active.")
    if facility:
        if not facility.is_active:
            raise ValidationError("Facility must be active.")
        if organization and facility.organization_id != organization.id:
            raise ValidationError("Facility must belong to the selected organization.")


@transaction.atomic
def record_audit_log(
    *,
    action: str,
    resource_type: str | None = None,
    entity_type: str | None = None,
    resource_id=None,
    entity_id=None,
    outcome: str = "success",
    source: str = AuditLog.Source.API,
    actor_user_id=None,
    organization_id=None,
    facility_id=None,
    request_id=None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict | None = None,
    changes: dict | None = None,
    occurred_at=None,
) -> AuditLog:
    action = _clean_required(action, "action")
    entity_type = _clean_required(entity_type or resource_type, "resource_type")
    if source not in AuditLog.Source.values:
        raise ValidationError("Invalid audit source.")
    if outcome not in OUTCOMES:
        raise ValidationError("Invalid audit outcome.")

    actor_user = _get_user(actor_user_id)
    organization = _get_organization(organization_id)
    facility = _get_facility(facility_id)
    _validate_scope(organization, facility)

    safe_metadata = sanitize_audit_metadata({**(metadata or {}), "outcome": outcome})
    safe_changes = sanitize_audit_metadata(changes or {}) if changes else None

    try:
        return AuditLog.objects.create(
            organization=organization,
            facility=facility,
            actor_user=actor_user,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id or resource_id,
            source=source,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:500] or None,
            changes=safe_changes,
            metadata=safe_metadata,
            occurred_at=occurred_at or timezone.now(),
        )
    except IntegrityError as exc:
        raise ConflictError("Audit log conflicts with database constraints.") from exc


def _safe_record(**kwargs):
    try:
        return record_audit_log(**kwargs)
    except Exception:
        return None


def record_success_event(**kwargs):
    return _safe_record(outcome="success", **kwargs)


def record_failure_event(*, failure_class: str | None = None, **kwargs):
    metadata = {**(kwargs.pop("metadata", {}) or {}), "failure_class": failure_class or "failure"}
    return _safe_record(outcome="failure", metadata=metadata, **kwargs)


def record_auth_event(*, action: str, actor_user_id=None, outcome: str = "success", metadata: dict | None = None, **kwargs):
    return _safe_record(action=action, actor_user_id=actor_user_id, resource_type="auth", outcome=outcome, metadata=metadata, **kwargs)


def record_resource_event(*, action: str, resource_type: str, resource_id=None, changes: dict | None = None, **kwargs):
    safe_changes = build_change_metadata(**changes) if changes and {"before", "after", "changed_fields"} & set(changes.keys()) else changes
    return _safe_record(action=action, resource_type=resource_type, resource_id=resource_id, changes=safe_changes, **kwargs)


def record_permission_denied_event(*, actor_user_id=None, action: str = "permission.denied", resource_type: str = "permission", metadata: dict | None = None, **kwargs):
    return _safe_record(
        action=action,
        resource_type=resource_type,
        actor_user_id=actor_user_id,
        outcome="denied",
        metadata={**(metadata or {}), "reason": "permission_denied"},
        **kwargs,
    )
