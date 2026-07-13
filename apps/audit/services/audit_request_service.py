from __future__ import annotations

from apps.audit.models import AuditLog

from .audit_log_service import record_audit_log
from .audit_metadata_service import build_safe_request_metadata


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
IGNORED_PATH_PREFIXES = ("/static/", "/media/", "/health/")


def _client_ip(request) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR")


def build_request_audit_context(*, request, response=None, exception=None) -> dict:
    status_code = getattr(response, "status_code", None)
    failure_class = exception.__class__.__name__ if exception else None
    request_id = getattr(request, "request_id", None) or request.META.get("HTTP_X_REQUEST_ID")
    return {
        "actor_user_id": request.user.id if getattr(request, "user", None) and request.user.is_authenticated else None,
        "request_id": request_id,
        "ip_address": _client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT"),
        "method": request.method,
        "path": request.path,
        "status_code": status_code,
        "failure_class": failure_class,
        "metadata": build_safe_request_metadata(
            method=request.method,
            path=request.path,
            query_params=dict(request.GET),
            status_code=status_code,
            request_id=request_id,
            user_agent=request.META.get("HTTP_USER_AGENT"),
            ip_address=_client_ip(request),
            failure_class=failure_class,
        ),
    }


def should_audit_request(request) -> bool:
    path = getattr(request, "path", "")
    if not request.method or request.method.upper() not in WRITE_METHODS:
        return False
    return not path.startswith(IGNORED_PATH_PREFIXES)


def audit_api_request(*, request, response=None, exception=None, action: str | None = None, resource_type: str = "api_request"):
    if not should_audit_request(request):
        return None
    context = build_request_audit_context(request=request, response=response, exception=exception)
    outcome = "success"
    if exception is not None or (context.get("status_code") and context["status_code"] >= 500):
        outcome = "failure"
    elif context.get("status_code") in {401, 403}:
        outcome = "denied"

    return record_audit_log(
        action=action or f"{request.method.lower()} {request.path}",
        resource_type=resource_type,
        outcome=outcome,
        source=AuditLog.Source.API,
        actor_user_id=context["actor_user_id"],
        request_id=context["request_id"],
        ip_address=context["ip_address"],
        user_agent=context["user_agent"],
        metadata=context["metadata"],
    )
