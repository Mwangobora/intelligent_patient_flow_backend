from __future__ import annotations

from django.db import transaction

from apps.scheduling.models import Appointment

from ._shared import get_facility, to_local_date


@transaction.atomic
def generate_appointment_number(*, facility, scheduled_start) -> str:
    locked_facility = get_facility(facility.id if hasattr(facility, "id") else facility, active_only=True, for_update=True)
    local_date = to_local_date(facility=locked_facility, value=scheduled_start)
    prefix = f"APT-{local_date.strftime('%Y%m%d')}-"
    daily_count = Appointment.objects.select_for_update().filter(
        facility=locked_facility,
        appointment_number__startswith=prefix,
    ).count()
    return f"{prefix}{daily_count + 1:04d}"
