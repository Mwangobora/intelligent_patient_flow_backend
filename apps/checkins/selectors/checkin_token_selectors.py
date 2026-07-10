from __future__ import annotations

from django.utils import timezone

from apps.checkins.models import CheckinToken


def list_checkin_tokens(*, appointment_id=None, only_active: bool = False):
    queryset = CheckinToken.objects.select_related(
        "appointment",
        "appointment__facility",
        "appointment__patient",
        "patient_checkin",
        "created_by",
        "revoked_by",
    )
    if appointment_id:
        queryset = queryset.filter(appointment_id=appointment_id)
    if only_active:
        queryset = queryset.filter(
            used_at__isnull=True,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
    return queryset.order_by("-created_at")


def get_checkin_token_by_id(token_id):
    return list_checkin_tokens().filter(pk=token_id).first()


def list_active_tokens_for_appointment(*, appointment_id):
    return list_checkin_tokens(appointment_id=appointment_id, only_active=True)
