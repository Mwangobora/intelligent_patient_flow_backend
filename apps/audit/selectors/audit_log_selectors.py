from __future__ import annotations

from collections import Counter, defaultdict

from django.db.models import Q

from apps.audit.models import AuditLog
from apps.audit.services.audit_metadata_service import sanitize_audit_metadata


def audit_log_queryset():
    return AuditLog.objects.select_related("actor_user", "organization", "facility").order_by("-occurred_at", "-created_at")


def _apply_filters(
    queryset,
    *,
    actor_user_id=None,
    organization_id=None,
    facility_id=None,
    action=None,
    resource_type=None,
    entity_type=None,
    resource_id=None,
    entity_id=None,
    outcome=None,
    date_from=None,
    date_to=None,
    search=None,
):
    if actor_user_id:
        queryset = queryset.filter(actor_user_id=actor_user_id)
    if organization_id:
        queryset = queryset.filter(organization_id=organization_id)
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if action:
        queryset = queryset.filter(action=action)
    if resource_type or entity_type:
        queryset = queryset.filter(entity_type=resource_type or entity_type)
    if resource_id or entity_id:
        queryset = queryset.filter(entity_id=resource_id or entity_id)
    if outcome:
        queryset = queryset.filter(metadata__outcome=outcome)
    if date_from:
        queryset = queryset.filter(occurred_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(occurred_at__date__lte=date_to)
    if search:
        queryset = queryset.filter(Q(action__icontains=search) | Q(entity_type__icontains=search) | Q(metadata__icontains=search))
    return queryset


def list_audit_logs(**filters):
    return _apply_filters(audit_log_queryset(), **filters)


def get_audit_log_by_id(audit_log_id):
    return audit_log_queryset().filter(pk=audit_log_id).first()


def list_audit_logs_by_actor(*, actor_user_id):
    return list_audit_logs(actor_user_id=actor_user_id)


def list_audit_logs_by_organization(*, organization_id):
    return list_audit_logs(organization_id=organization_id)


def list_audit_logs_by_facility(*, facility_id):
    return list_audit_logs(facility_id=facility_id)


def list_audit_logs_by_action(*, action):
    return list_audit_logs(action=action)


def list_audit_logs_by_resource(*, resource_type, resource_id=None):
    return list_audit_logs(resource_type=resource_type, resource_id=resource_id)


def list_audit_logs_by_outcome(*, outcome):
    return list_audit_logs(outcome=outcome)


def list_audit_logs_by_date_range(*, date_from=None, date_to=None):
    return list_audit_logs(date_from=date_from, date_to=date_to)


def get_audit_summary(**filters):
    logs = list(_apply_filters(audit_log_queryset(), **filters)[:1000])
    outcomes = Counter((log.metadata or {}).get("outcome", "unknown") for log in logs)
    actions = Counter(log.action for log in logs)
    events_by_day = defaultdict(int)
    for log in logs:
        events_by_day[log.occurred_at.date().isoformat()] += 1

    recent_failed = [
        {
            "id": str(log.id),
            "action": log.action,
            "resource_type": log.entity_type,
            "outcome": (log.metadata or {}).get("outcome"),
            "occurred_at": log.occurred_at,
            "metadata": sanitize_audit_metadata(log.metadata or {}),
        }
        for log in logs
        if (log.metadata or {}).get("outcome") in {"failure", "denied"}
    ][:10]

    return {
        "total_logs": len(logs),
        "success_count": outcomes.get("success", 0),
        "failure_count": outcomes.get("failure", 0),
        "denied_count": outcomes.get("denied", 0),
        "top_actions": [{"action": action, "count": count} for action, count in actions.most_common(10)],
        "recent_critical_events": recent_failed,
        "events_by_day": [{"date": day, "count": count} for day, count in sorted(events_by_day.items())],
    }
