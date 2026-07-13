from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import DatabaseError
from django.test import RequestFactory
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.selectors import get_audit_log_by_id
from apps.audit.services import (
    audit_api_request,
    record_audit_log,
    record_failure_event,
    record_permission_denied_event,
    sanitize_audit_metadata,
)


pytestmark = pytest.mark.django_db


def _grant_all_audit_permissions(user, grant_system_permission):
    for code in ["audit_log.view", "audit_log.create", "audit_log.export", "audit_log.summary"]:
        grant_system_permission(user=user, permission_code=code)


def _create_log(organization, facility, audit_user, **overrides):
    defaults = {
        "actor_user_id": audit_user.id,
        "organization_id": organization.id,
        "facility_id": facility.id,
        "action": "patient.create",
        "resource_type": "patient",
        "outcome": "success",
        "source": AuditLog.Source.API,
        "metadata": {"safe": "value"},
    }
    defaults.update(overrides)
    return record_audit_log(**defaults)


def test_unauthenticated_users_cannot_access_audit_endpoints(api_client):
    response = api_client.get("/api/v1/audit/logs/")
    assert response.status_code == 401


def test_unauthorized_users_cannot_view_audit_logs(authenticated_client, user_factory):
    client = authenticated_client(user_factory())
    response = client.get("/api/v1/audit/logs/")
    assert response.status_code == 403


def test_authorized_user_can_list_audit_logs(authenticated_client, user_factory, grant_system_permission, organization, facility, audit_user):
    user = user_factory()
    _grant_all_audit_permissions(user, grant_system_permission)
    _create_log(organization, facility, audit_user)
    client = authenticated_client(user)

    response = client.get(f"/api/v1/audit/logs/?organization_id={organization.id}")

    assert response.status_code == 200
    assert len(response.data) == 1


def test_authorized_user_can_get_audit_log_detail(authenticated_client, user_factory, grant_system_permission, organization, facility, audit_user):
    user = user_factory()
    _grant_all_audit_permissions(user, grant_system_permission)
    audit_log = _create_log(organization, facility, audit_user)
    client = authenticated_client(user)

    response = client.get(f"/api/v1/audit/logs/{audit_log.id}/")

    assert response.status_code == 200
    assert response.data["id"] == str(audit_log.id)


def test_authorized_user_can_create_manual_audit_log(authenticated_client, user_factory, grant_system_permission, organization, facility, audit_user):
    user = user_factory()
    _grant_all_audit_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post(
        "/api/v1/audit/logs/",
        {
            "actor_user_id": str(audit_user.id),
            "organization_id": str(organization.id),
            "facility_id": str(facility.id),
            "action": "manual.review",
            "resource_type": "patient",
            "outcome": "success",
            "metadata": {"password": "secret", "safe": "yes"},
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["action"] == "manual.review"
    assert response.data["resource_type"] == "patient"
    assert response.data["outcome"] == "success"
    assert response.data["occurred_at"]
    assert response.data["metadata"]["password"] == "[REDACTED]"


def test_audit_logs_are_append_only(organization, facility, audit_user):
    audit_log = _create_log(organization, facility, audit_user)
    audit_log.action = "changed"
    with pytest.raises(DatabaseError):
        audit_log.save(update_fields=["action"])


def test_audit_log_update_and_delete_endpoints_are_not_allowed(authenticated_client, user_factory, grant_system_permission, organization, facility, audit_user):
    user = user_factory()
    _grant_all_audit_permissions(user, grant_system_permission)
    audit_log = _create_log(organization, facility, audit_user)
    client = authenticated_client(user)

    assert client.patch(f"/api/v1/audit/logs/{audit_log.id}/", {"action": "x"}, format="json").status_code == 405
    assert client.delete(f"/api/v1/audit/logs/{audit_log.id}/").status_code == 405


def test_sensitive_and_nested_metadata_keys_are_redacted(organization, facility, audit_user):
    audit_log = _create_log(
        organization,
        facility,
        audit_user,
        metadata={
            "password": "secret",
            "nested": {"token": "abc", "authorization": "Bearer x", "cookie": "session=x"},
            "body_encrypted": "plaintext should not appear",
        },
    )

    assert audit_log.metadata["password"] == "[REDACTED]"
    assert audit_log.metadata["nested"]["token"] == "[REDACTED]"
    assert audit_log.metadata["nested"]["authorization"] == "[REDACTED]"
    assert audit_log.metadata["nested"]["cookie"] == "[REDACTED]"
    assert audit_log.metadata["body_encrypted"] == "[REDACTED]"
    assert "secret" not in str(audit_log.metadata)


def test_request_body_is_not_stored_by_request_audit_service(user_factory):
    request = RequestFactory().post("/api/v1/patients/", data={"password": "secret", "name": "Patient"})
    request.user = user_factory()
    audit_log = audit_api_request(request=request, response=type("Response", (), {"status_code": 201})())

    assert audit_log is not None
    assert "password" not in str(audit_log.metadata).lower()
    assert "body" not in audit_log.metadata


def test_query_filters_work(authenticated_client, user_factory, grant_system_permission, organization, facility, audit_user):
    user = user_factory()
    _grant_all_audit_permissions(user, grant_system_permission)
    now = timezone.now()
    audit_log = _create_log(
        organization,
        facility,
        audit_user,
        action="appointment.cancel",
        resource_type="appointment",
        resource_id=facility.id,
        outcome="denied",
        occurred_at=now - timedelta(hours=1),
    )
    client = authenticated_client(user)
    query = (
        f"?actor_user_id={audit_user.id}&organization_id={organization.id}&facility_id={facility.id}"
        f"&action=appointment.cancel&resource_type=appointment&resource_id={facility.id}&outcome=denied"
        f"&date_from={(now - timedelta(days=1)).date()}&date_to={(now + timedelta(days=1)).date()}"
    )

    response = client.get(f"/api/v1/audit/logs/{query}")

    assert response.status_code == 200
    assert [item["id"] for item in response.data] == [str(audit_log.id)]


def test_resource_and_actor_audit_endpoints(authenticated_client, user_factory, grant_system_permission, organization, facility, audit_user):
    user = user_factory()
    _grant_all_audit_permissions(user, grant_system_permission)
    audit_log = _create_log(organization, facility, audit_user, resource_type="facility", resource_id=facility.id)
    client = authenticated_client(user)

    resource_response = client.get(f"/api/v1/audit/resources/facility/{facility.id}/")
    actor_response = client.get(f"/api/v1/audit/actors/{audit_user.id}/")

    assert resource_response.status_code == 200
    assert actor_response.status_code == 200
    assert resource_response.data[0]["id"] == str(audit_log.id)
    assert actor_response.data[0]["id"] == str(audit_log.id)


def test_audit_summary_returns_total_and_grouped_counts(authenticated_client, user_factory, grant_system_permission, organization, facility, audit_user):
    user = user_factory()
    _grant_all_audit_permissions(user, grant_system_permission)
    _create_log(organization, facility, audit_user, outcome="success", action="a.success")
    _create_log(organization, facility, audit_user, outcome="failure", action="a.failure")
    _create_log(organization, facility, audit_user, outcome="denied", action="a.denied")
    client = authenticated_client(user)

    response = client.get(f"/api/v1/audit/summary/?organization_id={organization.id}")

    assert response.status_code == 200
    assert response.data["total_logs"] == 3
    assert response.data["success_count"] == 1
    assert response.data["failure_count"] == 1
    assert response.data["denied_count"] == 1
    assert response.data["top_actions"]


def test_permission_denied_event_can_be_recorded_safely(audit_user):
    audit_log = record_permission_denied_event(actor_user_id=audit_user.id, metadata={"authorization": "Bearer token"})

    assert audit_log.metadata["outcome"] == "denied"
    assert audit_log.metadata["authorization"] == "[REDACTED]"


def test_failure_event_does_not_expose_stack_trace(audit_user):
    audit_log = record_failure_event(
        actor_user_id=audit_user.id,
        action="danger.failed",
        resource_type="danger",
        failure_class="ValueError",
        metadata={"traceback": "line 1\nline 2", "password": "secret"},
    )

    assert audit_log.metadata["failure_class"] == "ValueError"
    assert audit_log.metadata["password"] == "[REDACTED]"
    assert "line 2" in audit_log.metadata["traceback"]


def test_metadata_size_is_limited_safely():
    metadata = sanitize_audit_metadata({"safe": "x" * 30000})

    assert metadata["truncated"] is True


def test_selector_avoids_exposing_sensitive_metadata(organization, facility, audit_user):
    audit_log = _create_log(organization, facility, audit_user, metadata={"token": "secret"})
    selected = get_audit_log_by_id(audit_log.id)

    assert selected.metadata["token"] == "[REDACTED]"


def test_request_audit_service_does_not_log_authorization_or_cookie_headers(user_factory):
    request = RequestFactory().post("/api/v1/secure/", HTTP_AUTHORIZATION="Bearer secret", HTTP_COOKIE="session=secret", HTTP_USER_AGENT="pytest")
    request.user = user_factory()

    audit_log = audit_api_request(request=request, response=type("Response", (), {"status_code": 403})())

    assert audit_log.metadata["outcome"] == "denied"
    assert "authorization" not in str(audit_log.metadata).lower()
    assert "cookie" not in str(audit_log.metadata).lower()
