from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.facilities.models import Facility, Organization
from common.db import CreatedAtModel


class AuditLog(CreatedAtModel):
    class Source(models.TextChoices):
        WEB = "web", "Web"
        MOBILE = "mobile", "Mobile"
        API = "api", "API"
        SYSTEM = "system", "System"
        ADMIN = "admin", "Admin"

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="audit_logs", blank=True, null=True)
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="audit_logs", blank=True, null=True)
    actor_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="audit_logs", blank=True, null=True)
    action = models.CharField(max_length=50)
    entity_type = models.CharField(max_length=100)
    entity_id = models.UUIDField(blank=True, null=True)
    source = models.CharField(max_length=20, choices=Source.choices)
    request_id = models.UUIDField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True, null=True)
    changes = models.JSONField(blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "audit_logs"
        constraints = [
            models.CheckConstraint(condition=Q(source__in=[c for c, _ in Source.choices]), name="ck_audit_logs_source"),
            models.CheckConstraint(condition=Q(action__regex=r".*\S.*"), name="ck_audit_logs_action_not_blank"),
            models.CheckConstraint(condition=Q(entity_type__regex=r".*\S.*"), name="ck_audit_logs_entity_type_not_blank"),
        ]
        indexes = [
            models.Index(fields=["organization", "-occurred_at"], name="idx_audit_logs_org_time"),
            models.Index(fields=["facility", "-occurred_at"], name="idx_audit_logs_facility_time"),
            models.Index(fields=["actor_user", "-occurred_at"], name="idx_audit_logs_actor_time"),
            models.Index(fields=["entity_type", "entity_id", "-occurred_at"], name="idx_audit_logs_entity"),
            models.Index(fields=["request_id"], name="idx_audit_logs_request", condition=Q(request_id__isnull=False)),
        ]

    # TODO: enforce organization/facility scope validation and append-only trigger from the SQL file in a custom migration.
