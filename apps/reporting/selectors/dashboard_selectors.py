from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db.models import Count, Q, Sum
from django.db.models.functions import ExtractHour
from django.utils import timezone

from apps.checkins.models import PatientCheckin
from apps.facilities.models import Facility
from apps.intelligence.models import QueueWaitTimePrediction
from apps.patients.models import Patient
from apps.queueing.models import Queue, QueueEntry
from apps.queueing.services._shared import build_display_queue_number
from apps.scheduling.models import Appointment, AppointmentSlot, PractitionerShift


ACTIVE_QUEUE_STATUSES = [Queue.Status.OPEN, Queue.Status.PAUSED]
CURRENT_QUEUE_ENTRY_STATUSES = [
    QueueEntry.Status.WAITING,
    QueueEntry.Status.CALLED,
    QueueEntry.Status.IN_SERVICE,
    QueueEntry.Status.SKIPPED,
]


def _safe_zoneinfo(timezone_name: str | None):
    if not timezone_name:
        return timezone.get_current_timezone()
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.get_current_timezone()


def _resolve_facility(facility_id):
    if not facility_id:
        return None
    return Facility.objects.select_related("organization").filter(pk=facility_id).first()


def _date_bounds(*, date_from=None, date_to=None, facility=None):
    local_timezone = _safe_zoneinfo(getattr(facility, "timezone", None))
    today = timezone.now().astimezone(local_timezone).date()
    start_date = date_from or today
    end_date = date_to or date_from or today
    start = datetime.combine(start_date, time.min, tzinfo=local_timezone)
    end = datetime.combine(end_date, time.max, tzinfo=local_timezone)
    return start, end


def _scope_context(*, organization_id=None, facility_id=None, date_from=None, date_to=None):
    facility = _resolve_facility(facility_id)
    resolved_organization_id = organization_id or (facility.organization_id if facility else None)
    start, end = _date_bounds(date_from=date_from, date_to=date_to, facility=facility)
    return resolved_organization_id, facility, start, end


def _apply_facility_scope(queryset, *, organization_id, facility=None, facility_path="facility"):
    queryset = queryset.filter(**{f"{facility_path}__organization_id": organization_id})
    if facility is not None:
        queryset = queryset.filter(**{f"{facility_path}_id": facility.id})
    return queryset


def _apply_appointment_filters(queryset, *, filters):
    if filters.get("department_id"):
        queryset = queryset.filter(facility_specialty__department_id=filters["department_id"])
    if filters.get("specialty_id"):
        queryset = queryset.filter(facility_specialty__specialty_id=filters["specialty_id"])
    if filters.get("practitioner_id"):
        queryset = queryset.filter(practitioner_facility_assignment__practitioner_id=filters["practitioner_id"])
    return queryset


def _apply_queue_filters(queryset, *, filters):
    if filters.get("department_id"):
        queryset = queryset.filter(Q(service_point__department_id=filters["department_id"]) | Q(facility_specialty__department_id=filters["department_id"]))
    if filters.get("specialty_id"):
        queryset = queryset.filter(facility_specialty__specialty_id=filters["specialty_id"])
    if filters.get("service_point_id"):
        queryset = queryset.filter(service_point_id=filters["service_point_id"])
    return queryset


def _apply_queue_entry_filters(queryset, *, filters):
    if filters.get("department_id"):
        queryset = queryset.filter(Q(queue__service_point__department_id=filters["department_id"]) | Q(queue__facility_specialty__department_id=filters["department_id"]))
    if filters.get("specialty_id"):
        queryset = queryset.filter(Q(queue__facility_specialty__specialty_id=filters["specialty_id"]) | Q(patient_checkin__facility_specialty__specialty_id=filters["specialty_id"]))
    if filters.get("service_point_id"):
        queryset = queryset.filter(queue__service_point_id=filters["service_point_id"])
    if filters.get("practitioner_id"):
        queryset = queryset.filter(practitioner_shift__practitioner_facility_assignment__practitioner_id=filters["practitioner_id"])
    return queryset


def _apply_prediction_filters(queryset, *, filters):
    if filters.get("department_id"):
        queryset = queryset.filter(
            Q(queue_entry__queue__service_point__department_id=filters["department_id"])
            | Q(queue_entry__queue__facility_specialty__department_id=filters["department_id"])
        )
    if filters.get("specialty_id"):
        queryset = queryset.filter(
            Q(queue_entry__queue__facility_specialty__specialty_id=filters["specialty_id"])
            | Q(queue_entry__patient_checkin__facility_specialty__specialty_id=filters["specialty_id"])
        )
    if filters.get("service_point_id"):
        queryset = queryset.filter(queue_entry__queue__service_point_id=filters["service_point_id"])
    if filters.get("practitioner_id"):
        queryset = queryset.filter(queue_entry__practitioner_shift__practitioner_facility_assignment__practitioner_id=filters["practitioner_id"])
    return queryset


def _apply_checkin_filters(queryset, *, filters):
    if filters.get("department_id"):
        queryset = queryset.filter(facility_specialty__department_id=filters["department_id"])
    if filters.get("specialty_id"):
        queryset = queryset.filter(facility_specialty__specialty_id=filters["specialty_id"])
    return queryset


def _apply_shift_filters(queryset, *, filters):
    if filters.get("department_id"):
        queryset = queryset.filter(Q(practitioner_department_assignment__department_id=filters["department_id"]) | Q(service_point__department_id=filters["department_id"]))
    if filters.get("service_point_id"):
        queryset = queryset.filter(service_point_id=filters["service_point_id"])
    if filters.get("practitioner_id"):
        queryset = queryset.filter(practitioner_facility_assignment__practitioner_id=filters["practitioner_id"])
    return queryset


def _minutes_between(start, end):
    if not start or not end:
        return None
    return round((end - start).total_seconds() / 60, 2)


def _average(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _count_by_status(queryset, statuses):
    counts = {status: 0 for status in statuses}
    for row in queryset.values("status").annotate(count=Count("id")):
        counts[row["status"]] = row["count"]
    return counts


def _count_by_hour(queryset, *, datetime_field):
    return [
        {"hour": row["hour"], "count": row["count"]}
        for row in queryset.annotate(hour=ExtractHour(datetime_field)).values("hour").annotate(count=Count("id")).order_by("hour")
        if row["hour"] is not None
    ]


def get_dashboard_overview_summary(**filters):
    organization_id, facility, start, end = _scope_context(**filters)
    generated_at = timezone.now()

    patients = Patient.objects.filter(organization_id=organization_id, is_active=True)
    if facility is not None:
        patients = patients.filter(registered_facility_id=facility.id)

    appointments = _apply_facility_scope(Appointment.objects.all(), organization_id=organization_id, facility=facility)
    appointments = _apply_appointment_filters(appointments, filters=filters)
    appointments_in_range = appointments.filter(scheduled_start__gte=start, scheduled_start__lte=end)

    checkins = _apply_facility_scope(PatientCheckin.objects.all(), organization_id=organization_id, facility=facility)
    checkins = _apply_checkin_filters(checkins, filters=filters)
    checkins_in_range = checkins.filter(checked_in_at__gte=start, checked_in_at__lte=end)

    active_entries = _apply_facility_scope(QueueEntry.objects.all(), organization_id=organization_id, facility=facility, facility_path="queue__service_point__facility")
    active_entries = _apply_queue_entry_filters(active_entries, filters=filters).filter(queue__status__in=ACTIVE_QUEUE_STATUSES)
    current_counts = _count_by_status(active_entries.filter(status__in=CURRENT_QUEUE_ENTRY_STATUSES), CURRENT_QUEUE_ENTRY_STATUSES)

    completed_entries = active_entries.filter(status=QueueEntry.Status.COMPLETED, service_completed_at__gte=start, service_completed_at__lte=end)
    wait_entries = active_entries.filter(service_started_at__isnull=False, service_started_at__gte=start, service_started_at__lte=end)

    queues = _apply_facility_scope(Queue.objects.all(), organization_id=organization_id, facility=facility, facility_path="service_point__facility")
    queues = _apply_queue_filters(queues, filters=filters)

    return {
        "total_patients": patients.count(),
        "total_appointments_today": appointments_in_range.count(),
        "total_checkins_today": checkins_in_range.count(),
        "total_waiting_now": current_counts[QueueEntry.Status.WAITING],
        "total_called_now": current_counts[QueueEntry.Status.CALLED],
        "total_in_service_now": current_counts[QueueEntry.Status.IN_SERVICE],
        "completed_visits_today": completed_entries.count() or appointments_in_range.filter(status=Appointment.Status.COMPLETED).count(),
        "cancelled_appointments_today": appointments_in_range.filter(status=Appointment.Status.CANCELLED).count(),
        "no_show_appointments_today": appointments_in_range.filter(status=Appointment.Status.NO_SHOW).count(),
        "average_wait_minutes_today": _average(_minutes_between(entry.joined_at, entry.service_started_at) for entry in wait_entries.iterator()),
        "active_queues": queues.filter(status__in=ACTIVE_QUEUE_STATUSES, queue_date__gte=start.date(), queue_date__lte=end.date()).count(),
        "generated_at": generated_at,
    }


def get_appointment_dashboard_summary(**filters):
    organization_id, facility, start, end = _scope_context(**filters)
    appointments = _apply_facility_scope(Appointment.objects.select_related("facility_specialty__specialty"), organization_id=organization_id, facility=facility)
    appointments = _apply_appointment_filters(appointments, filters=filters).filter(scheduled_start__gte=start, scheduled_start__lte=end)
    statuses = [choice.value for choice in Appointment.Status]
    status_counts = _count_by_status(appointments, statuses)

    specialty_rows = appointments.values("facility_specialty__specialty_id", "facility_specialty__specialty__name").annotate(count=Count("id")).order_by("facility_specialty__specialty__name")
    slots = _apply_facility_scope(AppointmentSlot.objects.all(), organization_id=organization_id, facility=facility, facility_path="facility_specialty__facility")
    if filters.get("department_id"):
        slots = slots.filter(facility_specialty__department_id=filters["department_id"])
    if filters.get("specialty_id"):
        slots = slots.filter(facility_specialty__specialty_id=filters["specialty_id"])
    if filters.get("practitioner_id"):
        slots = slots.filter(practitioner_shift__practitioner_facility_assignment__practitioner_id=filters["practitioner_id"])
    slots = slots.filter(starts_at__gte=start, starts_at__lte=end)
    slot_totals = slots.aggregate(capacity=Sum("capacity"), booked=Sum("booked_count"))
    capacity = slot_totals["capacity"] or 0
    booked = slot_totals["booked"] or 0

    return {
        "appointments_total": appointments.count(),
        "pending": status_counts[Appointment.Status.PENDING],
        "confirmed": status_counts[Appointment.Status.CONFIRMED],
        "checked_in": status_counts[Appointment.Status.CHECKED_IN],
        "queued": status_counts[Appointment.Status.QUEUED],
        "in_service": status_counts[Appointment.Status.IN_SERVICE],
        "completed": status_counts[Appointment.Status.COMPLETED],
        "cancelled": status_counts[Appointment.Status.CANCELLED],
        "no_show": status_counts[Appointment.Status.NO_SHOW],
        "rescheduled": status_counts[Appointment.Status.RESCHEDULED],
        "appointments_by_status": [{"status": status, "count": status_counts[status]} for status in statuses if status_counts[status]],
        "appointments_by_specialty": [
            {"specialty_id": row["facility_specialty__specialty_id"], "specialty_name": row["facility_specialty__specialty__name"], "count": row["count"]}
            for row in specialty_rows
        ],
        "appointments_by_hour": _count_by_hour(appointments, datetime_field="scheduled_start"),
        "appointment_utilization_percentage": round((booked / capacity) * 100, 2) if capacity else None,
        "generated_at": timezone.now(),
    }


def get_queue_dashboard_summary(**filters):
    organization_id, facility, start, end = _scope_context(**filters)
    queues = _apply_facility_scope(Queue.objects.select_related("service_point"), organization_id=organization_id, facility=facility, facility_path="service_point__facility")
    queues = _apply_queue_filters(queues, filters=filters)
    active_queues = queues.filter(status__in=ACTIVE_QUEUE_STATUSES, queue_date__gte=start.date(), queue_date__lte=end.date())

    entries = _apply_facility_scope(QueueEntry.objects.select_related("queue__service_point", "queue__service_point__facility"), organization_id=organization_id, facility=facility, facility_path="queue__service_point__facility")
    entries = _apply_queue_entry_filters(entries, filters=filters)
    current_entries = entries.filter(queue__status__in=ACTIVE_QUEUE_STATUSES, status__in=CURRENT_QUEUE_ENTRY_STATUSES)
    current_counts = _count_by_status(current_entries, CURRENT_QUEUE_ENTRY_STATUSES)

    completed = entries.filter(status=QueueEntry.Status.COMPLETED, service_completed_at__gte=start, service_completed_at__lte=end)
    cancelled = entries.filter(status=QueueEntry.Status.CANCELLED, cancelled_at__gte=start, cancelled_at__lte=end)
    transferred = entries.filter(status=QueueEntry.Status.TRANSFERRED, joined_at__gte=start, joined_at__lte=end)
    wait_minutes = [_minutes_between(entry.joined_at, entry.service_started_at) for entry in entries.filter(service_started_at__isnull=False, service_started_at__gte=start, service_started_at__lte=end).iterator()]

    by_service_point = defaultdict(lambda: {"waiting": 0, "called": 0, "in_service": 0, "skipped": 0})
    service_points = {}
    for entry in current_entries:
        service_point = entry.queue.service_point
        key = service_point.id
        service_points[key] = service_point
        by_service_point[key][entry.status] += 1

    next_entries = []
    for queue in active_queues.prefetch_related("entries").order_by("service_point__name"):
        entry = queue.entries.filter(status__in=[QueueEntry.Status.WAITING, QueueEntry.Status.CALLED, QueueEntry.Status.SKIPPED]).order_by("-priority_level", "joined_at", "sequence_number").first()
        if entry is None:
            continue
        next_entries.append(
            {
                "queue_id": queue.id,
                "service_point_name": queue.service_point.name,
                "display_queue_number": build_display_queue_number(queue=queue, sequence_number=entry.sequence_number),
                "priority_level": entry.priority_level,
                "waiting_minutes": int((timezone.now() - entry.joined_at).total_seconds() // 60),
            }
        )

    return {
        "active_queues": active_queues.count(),
        "waiting_patients": current_counts[QueueEntry.Status.WAITING],
        "called_patients": current_counts[QueueEntry.Status.CALLED],
        "in_service_patients": current_counts[QueueEntry.Status.IN_SERVICE],
        "skipped_patients": current_counts[QueueEntry.Status.SKIPPED],
        "completed_today": completed.count(),
        "cancelled_today": cancelled.count(),
        "transferred_today": transferred.count(),
        "average_wait_minutes": _average(wait_minutes),
        "longest_wait_minutes": max(wait_minutes) if wait_minutes else None,
        "queues_by_service_point": [
            {
                "service_point_id": service_point_id,
                "service_point_name": service_points[service_point_id].name,
                "service_point_code": service_points[service_point_id].code,
                **counts,
            }
            for service_point_id, counts in by_service_point.items()
        ],
        "next_entries_summary": next_entries,
        "generated_at": timezone.now(),
    }


def get_checkin_dashboard_summary(**filters):
    organization_id, facility, start, end = _scope_context(**filters)
    checkins = _apply_facility_scope(PatientCheckin.objects.all(), organization_id=organization_id, facility=facility)
    checkins = _apply_checkin_filters(checkins, filters=filters).filter(checked_in_at__gte=start, checked_in_at__lte=end)
    method_counts = {method.value: 0 for method in PatientCheckin.CheckinMethod}
    for row in checkins.values("checkin_method").annotate(count=Count("id")):
        method_counts[row["checkin_method"]] = row["count"]

    return {
        "total_checkins": checkins.count(),
        "appointment_checkins": checkins.filter(appointment__isnull=False).count(),
        "walkin_checkins": checkins.filter(appointment__isnull=True).count(),
        "qr_checkins": method_counts[PatientCheckin.CheckinMethod.QR_CODE],
        "reception_checkins": method_counts[PatientCheckin.CheckinMethod.RECEPTION],
        "mobile_checkins": method_counts[PatientCheckin.CheckinMethod.MOBILE],
        "self_service_checkins": method_counts[PatientCheckin.CheckinMethod.SELF_SERVICE],
        "voided_checkins": checkins.filter(voided_at__isnull=False).count(),
        "checkins_by_hour": _count_by_hour(checkins, datetime_field="checked_in_at"),
        "checkins_by_method": [{"method": method, "count": count} for method, count in method_counts.items() if count],
        "generated_at": timezone.now(),
    }


def get_practitioner_dashboard_summary(**filters):
    organization_id, facility, start, end = _scope_context(**filters)
    shifts = _apply_facility_scope(PractitionerShift.objects.select_related("practitioner_facility_assignment__practitioner"), organization_id=organization_id, facility=facility, facility_path="practitioner_facility_assignment__facility")
    shifts = _apply_shift_filters(shifts, filters=filters).filter(starts_at__lte=end, ends_at__gte=start)
    now = timezone.now()

    completed_appointments = _apply_facility_scope(Appointment.objects.select_related("practitioner_facility_assignment__practitioner"), organization_id=organization_id, facility=facility)
    completed_appointments = _apply_appointment_filters(completed_appointments, filters=filters).filter(status=Appointment.Status.COMPLETED, scheduled_start__gte=start, scheduled_start__lte=end)

    completed_by_practitioner = {
        row["practitioner_facility_assignment__practitioner_id"]: row["count"]
        for row in completed_appointments.values("practitioner_facility_assignment__practitioner_id").annotate(count=Count("id"))
        if row["practitioner_facility_assignment__practitioner_id"]
    }

    workload = {}
    for shift in shifts:
        practitioner = shift.practitioner_facility_assignment.practitioner
        row = workload.setdefault(
            practitioner.id,
            {
                "practitioner_id": practitioner.id,
                "practitioner_name": f"{practitioner.first_name} {practitioner.last_name}",
                "shifts_count": 0,
                "scheduled_hours": 0.0,
                "completed_appointments": completed_by_practitioner.get(practitioner.id, 0),
            },
        )
        row["shifts_count"] += 1
        row["scheduled_hours"] = round(row["scheduled_hours"] + ((shift.ends_at - shift.starts_at).total_seconds() / 3600), 2)

    service_time_by_practitioner = defaultdict(list)
    entries = _apply_facility_scope(QueueEntry.objects.select_related("practitioner_shift__practitioner_facility_assignment__practitioner"), organization_id=organization_id, facility=facility, facility_path="queue__service_point__facility")
    entries = _apply_queue_entry_filters(entries, filters=filters).filter(service_started_at__isnull=False, service_completed_at__isnull=False, service_completed_at__gte=start, service_completed_at__lte=end)
    names = {}
    for entry in entries:
        if not entry.practitioner_shift_id:
            continue
        practitioner = entry.practitioner_shift.practitioner_facility_assignment.practitioner
        names[practitioner.id] = f"{practitioner.first_name} {practitioner.last_name}"
        service_time_by_practitioner[practitioner.id].append(_minutes_between(entry.service_started_at, entry.service_completed_at))

    return {
        "active_practitioners_today": shifts.values("practitioner_facility_assignment__practitioner_id").distinct().count(),
        "practitioners_on_shift_now": shifts.filter(starts_at__lte=now, ends_at__gte=now, status__in=[PractitionerShift.Status.SCHEDULED, PractitionerShift.Status.IN_PROGRESS]).values("practitioner_facility_assignment__practitioner_id").distinct().count(),
        "scheduled_shifts": shifts.filter(status=PractitionerShift.Status.SCHEDULED).count(),
        "completed_shifts": shifts.filter(status=PractitionerShift.Status.COMPLETED).count(),
        "cancelled_shifts": shifts.filter(status=PractitionerShift.Status.CANCELLED).count(),
        "total_scheduled_hours": round(sum((shift.ends_at - shift.starts_at).total_seconds() / 3600 for shift in shifts), 2),
        "completed_appointments_by_practitioner": [
            {"practitioner_id": row["practitioner_facility_assignment__practitioner_id"], "practitioner_name": f"{row['practitioner_facility_assignment__practitioner__first_name']} {row['practitioner_facility_assignment__practitioner__last_name']}", "completed_appointments": row["count"]}
            for row in completed_appointments.values(
                "practitioner_facility_assignment__practitioner_id",
                "practitioner_facility_assignment__practitioner__first_name",
                "practitioner_facility_assignment__practitioner__last_name",
            ).annotate(count=Count("id"))
            if row["practitioner_facility_assignment__practitioner_id"]
        ],
        "average_service_time_by_practitioner": [
            {"practitioner_id": practitioner_id, "practitioner_name": names[practitioner_id], "average_service_minutes": _average(values)}
            for practitioner_id, values in service_time_by_practitioner.items()
        ],
        "workload_summary": list(workload.values()),
        "generated_at": timezone.now(),
    }


def get_intelligence_dashboard_summary(**filters):
    organization_id, facility, start, end = _scope_context(**filters)
    predictions = _apply_facility_scope(
        QueueWaitTimePrediction.objects.select_related("queue_entry__queue__service_point__facility", "queue_entry"),
        organization_id=organization_id,
        facility=facility,
        facility_path="queue_entry__queue__service_point__facility",
    ).filter(generated_at__gte=start, generated_at__lte=end)
    predictions = _apply_prediction_filters(predictions, filters=filters)

    actual_waits = []
    errors = []
    latest = []
    for prediction in predictions.order_by("-generated_at")[:10]:
        entry = prediction.queue_entry
        actual_wait = _minutes_between(entry.joined_at, entry.service_started_at) if entry.service_started_at else None
        error = abs(prediction.predicted_wait_minutes - actual_wait) if actual_wait is not None else None
        if actual_wait is not None:
            actual_waits.append(actual_wait)
            errors.append(error)
        latest.append(
            {
                "prediction_id": prediction.id,
                "queue_entry_id": entry.id,
                "prediction_method": prediction.prediction_method,
                "predicted_wait_minutes": prediction.predicted_wait_minutes,
                "actual_wait_minutes": actual_wait,
                "absolute_error_minutes": round(error, 2) if error is not None else None,
                "generated_at": prediction.generated_at,
            }
        )

    method_counts = predictions.values("prediction_method").annotate(count=Count("id"))
    counts = {QueueWaitTimePrediction.PredictionMethod.RULE_BASED: 0, QueueWaitTimePrediction.PredictionMethod.MACHINE_LEARNING: 0}
    for row in method_counts:
        counts[row["prediction_method"]] = row["count"]

    return {
        "predictions_generated": predictions.count(),
        "rule_based_predictions": counts[QueueWaitTimePrediction.PredictionMethod.RULE_BASED],
        "machine_learning_predictions": counts[QueueWaitTimePrediction.PredictionMethod.MACHINE_LEARNING],
        "average_predicted_wait_minutes": _average(predictions.values_list("predicted_wait_minutes", flat=True)),
        "average_actual_wait_minutes": _average(actual_waits),
        "average_prediction_error_minutes": _average(errors),
        "latest_predictions_summary": latest,
        "generated_at": timezone.now(),
    }
