from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.facilities.models import Facility, Organization
from common.db import TimeStampedModel


class ReportExport(TimeStampedModel):
    class ExportFormat(models.TextChoices):
        CSV = "csv", "CSV"
        XLSX = "xlsx", "XLSX"
        PDF = "pdf", "PDF"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="report_exports")
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="report_exports", blank=True, null=True)
    report_type = models.CharField(max_length=50)
    export_format = models.CharField(max_length=10, choices=ExportFormat.choices)
    parameters = models.JSONField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="requested_report_exports", blank=True, null=True)
    storage_key = models.CharField(max_length=500, blank=True, null=True)
    row_count = models.IntegerField(blank=True, null=True)
    generated_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    failed_at = models.DateTimeField(blank=True, null=True)
    failure_reason = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        db_table = "report_exports"
        constraints = [
            models.CheckConstraint(condition=Q(export_format__in=["csv", "xlsx", "pdf"]), name="ck_report_exports_format"),
            models.CheckConstraint(condition=Q(status__in=["pending", "processing", "completed", "failed", "expired", "cancelled"]), name="ck_report_exports_status"),
            models.CheckConstraint(condition=Q(row_count__isnull=True) | Q(row_count__gte=0), name="ck_report_exports_row_count"),
            models.CheckConstraint(condition=~Q(status="completed") | (Q(storage_key__isnull=False) & Q(generated_at__isnull=False)), name="ck_report_exports_completion"),
            models.CheckConstraint(condition=~Q(status="failed") | (Q(failed_at__isnull=False) & Q(failure_reason__isnull=False)), name="ck_report_exports_failure"),
            models.CheckConstraint(condition=Q(expires_at__isnull=True) | (Q(generated_at__isnull=False) & Q(expires_at__gt=models.F("generated_at"))), name="ck_report_exports_expiry"),
        ]
        indexes = [
            models.Index(fields=["requested_by", "-created_at"], name="idx_report_exp_req_time"),
            models.Index(fields=["organization", "status", "-created_at"], name="idx_report_exports_org_status"),
            models.Index(fields=["facility"], name="idx_report_exports_facility"),
        ]

    # TODO: enforce organization/facility scope validation trigger from the SQL file in a custom migration.
