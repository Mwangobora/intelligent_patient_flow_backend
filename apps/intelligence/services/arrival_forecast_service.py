from __future__ import annotations

from collections import defaultdict

from django.db.models.functions import ExtractHour, ExtractIsoWeekDay

from apps.checkins.models import PatientCheckin
from apps.queueing.models import QueueEntry
from common.exceptions import ValidationError

from ._shared import ArrivalForecastRow


def _validate_date_range(*, date_from, date_to) -> None:
    if date_from and date_to and date_to < date_from:
        raise ValidationError("date_to must be greater than or equal to date_from.")


def forecast_patient_arrivals(
    *,
    facility_id,
    date_from,
    date_to,
    service_point_id=None,
    facility_specialty_id=None,
) -> list[ArrivalForecastRow]:
    _validate_date_range(date_from=date_from, date_to=date_to)
    use_queue_entries = service_point_id is not None or facility_specialty_id is not None

    if use_queue_entries:
        queryset = QueueEntry.objects.filter(queue__service_point__facility_id=facility_id)
        if date_from:
            queryset = queryset.filter(joined_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(joined_at__date__lte=date_to)
        if service_point_id:
            queryset = queryset.filter(queue__service_point_id=service_point_id)
        if facility_specialty_id:
            queryset = queryset.filter(queue__facility_specialty_id=facility_specialty_id)
        rows = queryset.annotate(day_of_week=ExtractIsoWeekDay("joined_at"), hour_of_day=ExtractHour("joined_at")).values("day_of_week", "hour_of_day", "joined_at__date")
    else:
        queryset = PatientCheckin.objects.filter(facility_id=facility_id)
        if date_from:
            queryset = queryset.filter(checked_in_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(checked_in_at__date__lte=date_to)
        rows = queryset.annotate(day_of_week=ExtractIsoWeekDay("checked_in_at"), hour_of_day=ExtractHour("checked_in_at")).values("day_of_week", "hour_of_day", "checked_in_at__date")

    grouped: dict[tuple[int, int], dict[str, object]] = defaultdict(lambda: {"total": 0, "dates": set()})
    for row in rows:
        key = (row["day_of_week"], row["hour_of_day"])
        grouped[key]["total"] += 1
        grouped[key]["dates"].add(row.get("joined_at__date") or row.get("checked_in_at__date"))

    forecast = []
    for (day_of_week, hour_of_day), aggregate in grouped.items():
        date_count = max(len(aggregate["dates"]), 1)
        total = aggregate["total"]
        forecast.append(
            ArrivalForecastRow(
                day_of_week=day_of_week,
                hour_of_day=hour_of_day,
                total_arrivals=total,
                average_arrivals=round(total / date_count, 2),
            )
        )
    return sorted(forecast, key=lambda row: (row.day_of_week, row.hour_of_day))
