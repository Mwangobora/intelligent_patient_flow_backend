from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.checkins.models import PatientCheckin
from apps.intelligence.models import QueueWaitTimePrediction
from apps.queueing.models import QueueEntry
from apps.queueing.services._shared import build_display_queue_number
from apps.scheduling.models import Appointment, AppointmentSlot, PractitionerShift

def _date_bounds(parameters: dict | None):
    parameters = parameters or {}
    date_from = parse_report_date(parameters.get("date_from")) if parameters.get("date_from") else None
    date_to = parse_report_date(parameters.get("date_to")) if parameters.get("date_to") else None
    start = timezone.make_aware(datetime.combine(date_from, time.min)) if date_from else None
    end = timezone.make_aware(datetime.combine(date_to, time.max)) if date_to else None
    return start, end


def parse_report_date(value):
    if value is None:
        return None
    if hasattr(value, "date") and not hasattr(value, "year"):
        return value.date()
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value
    return datetime.fromisoformat(str(value)).date()


def _filter_facility(queryset, *, organization_id, facility_id=None, facility_path="facility"):
    queryset = queryset.filter(**{f"{facility_path}__organization_id": organization_id})
    if facility_id:
        queryset = queryset.filter(**{f"{facility_path}_id": facility_id})
    return queryset


def get_patient_waiting_time_data(*, organization_id, facility_id=None, parameters: dict | None = None):
    start, end = _date_bounds(parameters)
    queryset = QueueEntry.objects.select_related(
        "queue__service_point__facility",
        "queue__service_point",
        "patient_checkin__patient",
    ).filter(service_started_at__isnull=False)
    queryset = _filter_facility(queryset, organization_id=organization_id, facility_id=facility_id, facility_path="queue__service_point__facility")
    if start:
        queryset = queryset.filter(joined_at__gte=start)
    if end:
        queryset = queryset.filter(joined_at__lte=end)

    rows = []
    for entry in queryset.order_by("joined_at"):
        waiting_minutes = int((entry.service_started_at - entry.joined_at).total_seconds() // 60)
        rows.append(
            {
                "facility": entry.queue.service_point.facility.name,
                "service_point": entry.queue.service_point.name,
                "patient_number": entry.patient_checkin.patient.patient_number,
                "queue_number": build_display_queue_number(queue=entry.queue, sequence_number=entry.sequence_number),
                "joined_at": entry.joined_at,
                "service_started_at": entry.service_started_at,
                "waiting_minutes": waiting_minutes,
                "priority_level": entry.priority_level,
                "status": entry.status,
            }
        )
    return rows


def get_appointment_utilization_data(*, organization_id, facility_id=None, parameters: dict | None = None):
    start, end = _date_bounds(parameters)
    slot_queryset = AppointmentSlot.objects.select_related("facility_specialty__facility", "facility_specialty__specialty")
    slot_queryset = _filter_facility(slot_queryset, organization_id=organization_id, facility_id=facility_id, facility_path="facility_specialty__facility")
    appointment_queryset = Appointment.objects.select_related("facility", "facility_specialty__specialty", "practitioner_facility_assignment__practitioner")
    appointment_queryset = _filter_facility(appointment_queryset, organization_id=organization_id, facility_id=facility_id)
    if start:
        slot_queryset = slot_queryset.filter(starts_at__gte=start)
        appointment_queryset = appointment_queryset.filter(scheduled_start__gte=start)
    if end:
        slot_queryset = slot_queryset.filter(starts_at__lte=end)
        appointment_queryset = appointment_queryset.filter(scheduled_start__lte=end)

    slot_totals = {
        row["facility_specialty_id"]: row
        for row in slot_queryset.values("facility_specialty_id").annotate(total_slots=Count("id"), booked_slots=Sum("booked_count"))
    }
    appointment_totals = {
        row["facility_specialty_id"]: row
        for row in appointment_queryset.values("facility_specialty_id").annotate(
            completed_appointments=Count("id", filter=Q(status=Appointment.Status.COMPLETED)),
            cancelled_appointments=Count("id", filter=Q(status=Appointment.Status.CANCELLED)),
            no_show_appointments=Count("id", filter=Q(status=Appointment.Status.NO_SHOW)),
        )
    }

    specialty_ids = set(slot_totals) | set(appointment_totals)
    rows = []
    for specialty_id in specialty_ids:
        sample = slot_queryset.filter(facility_specialty_id=specialty_id).first() or appointment_queryset.filter(facility_specialty_id=specialty_id).first()
        facility_specialty = sample.facility_specialty
        slots = slot_totals.get(specialty_id, {})
        appointments = appointment_totals.get(specialty_id, {})
        total_slots = slots.get("total_slots") or 0
        booked_slots = slots.get("booked_slots") or 0
        rows.append(
            {
                "facility": facility_specialty.facility.name,
                "specialty": facility_specialty.specialty.name,
                "practitioner": "",
                "total_slots": total_slots,
                "booked_slots": booked_slots,
                "completed_appointments": appointments.get("completed_appointments") or 0,
                "cancelled_appointments": appointments.get("cancelled_appointments") or 0,
                "no_show_appointments": appointments.get("no_show_appointments") or 0,
                "utilization_percentage": round((booked_slots / total_slots) * 100, 2) if total_slots else 0,
            }
        )
    return rows


def get_doctor_workload_data(*, organization_id, facility_id=None, parameters: dict | None = None):
    start, end = _date_bounds(parameters)
    shift_queryset = PractitionerShift.objects.select_related(
        "practitioner_facility_assignment__practitioner",
        "practitioner_facility_assignment__facility",
        "practitioner_department_assignment__department",
    )
    shift_queryset = _filter_facility(shift_queryset, organization_id=organization_id, facility_id=facility_id, facility_path="practitioner_facility_assignment__facility")
    appointment_queryset = Appointment.objects.select_related("practitioner_facility_assignment__practitioner", "facility")
    appointment_queryset = _filter_facility(appointment_queryset, organization_id=organization_id, facility_id=facility_id)
    if start:
        shift_queryset = shift_queryset.filter(starts_at__gte=start)
        appointment_queryset = appointment_queryset.filter(scheduled_start__gte=start)
    if end:
        shift_queryset = shift_queryset.filter(starts_at__lte=end)
        appointment_queryset = appointment_queryset.filter(scheduled_start__lte=end)

    rows_by_assignment = {}
    for shift in shift_queryset.order_by("starts_at"):
        practitioner = shift.practitioner_facility_assignment.practitioner
        key = shift.practitioner_facility_assignment_id
        row = rows_by_assignment.setdefault(
            key,
            {
                "practitioner": f"{practitioner.first_name} {practitioner.last_name}",
                "facility": shift.practitioner_facility_assignment.facility.name,
                "department": shift.practitioner_department_assignment.department.name if shift.practitioner_department_assignment_id else "",
                "specialty": "",
                "shifts_count": 0,
                "total_scheduled_hours": 0,
                "completed_appointments": 0,
                "average_service_minutes": None,
            },
        )
        row["shifts_count"] += 1
        row["total_scheduled_hours"] += round((shift.ends_at - shift.starts_at).total_seconds() / 3600, 2)

    completed_counts = appointment_queryset.values("practitioner_facility_assignment_id").annotate(
        completed_appointments=Count("id", filter=Q(status=Appointment.Status.COMPLETED))
    )
    for item in completed_counts:
        if item["practitioner_facility_assignment_id"] in rows_by_assignment:
            rows_by_assignment[item["practitioner_facility_assignment_id"]]["completed_appointments"] = item["completed_appointments"]

    return list(rows_by_assignment.values())


def get_daily_attendance_data(*, organization_id, facility_id=None, parameters: dict | None = None):
    start, end = _date_bounds(parameters)
    checkins = PatientCheckin.objects.select_related("facility")
    checkins = _filter_facility(checkins, organization_id=organization_id, facility_id=facility_id)
    queue_entries = QueueEntry.objects.select_related("queue__service_point__facility")
    queue_entries = _filter_facility(queue_entries, organization_id=organization_id, facility_id=facility_id, facility_path="queue__service_point__facility")
    if start:
        checkins = checkins.filter(checked_in_at__gte=start)
        queue_entries = queue_entries.filter(joined_at__gte=start)
    if end:
        checkins = checkins.filter(checked_in_at__lte=end)
        queue_entries = queue_entries.filter(joined_at__lte=end)

    grouped = defaultdict(lambda: {"total_checkins": 0, "appointment_checkins": 0, "walkin_checkins": 0, "voided_checkins": 0, "completed_queue_entries": 0})
    facilities = {}
    for checkin in checkins:
        key = (checkin.checked_in_at.date(), checkin.facility_id)
        facilities[key] = checkin.facility.name
        grouped[key]["total_checkins"] += 1
        grouped[key]["appointment_checkins"] += 1 if checkin.appointment_id else 0
        grouped[key]["walkin_checkins"] += 1 if checkin.appointment_id is None else 0
        grouped[key]["voided_checkins"] += 1 if checkin.voided_at else 0
    for entry in queue_entries.filter(status=QueueEntry.Status.COMPLETED):
        key = (entry.joined_at.date(), entry.queue.service_point.facility_id)
        facilities[key] = entry.queue.service_point.facility.name
        grouped[key]["completed_queue_entries"] += 1

    return [
        {"date": key[0], "facility": facilities[key], **values}
        for key, values in sorted(grouped.items(), key=lambda item: item[0])
    ]


def get_prediction_accuracy_data(*, organization_id, facility_id=None, parameters: dict | None = None):
    start, end = _date_bounds(parameters)
    queryset = QueueWaitTimePrediction.objects.select_related(
        "queue_entry__queue__service_point__facility",
        "queue_entry__queue__service_point",
    ).filter(queue_entry__service_started_at__isnull=False)
    queryset = _filter_facility(queryset, organization_id=organization_id, facility_id=facility_id, facility_path="queue_entry__queue__service_point__facility")
    if start:
        queryset = queryset.filter(generated_at__gte=start)
    if end:
        queryset = queryset.filter(generated_at__lte=end)

    rows = []
    for prediction in queryset.order_by("generated_at"):
        entry = prediction.queue_entry
        actual_wait = int((entry.service_started_at - entry.joined_at).total_seconds() // 60)
        rows.append(
            {
                "prediction_method": prediction.prediction_method,
                "model_version": prediction.model_version or "",
                "predicted_wait_minutes": prediction.predicted_wait_minutes,
                "actual_wait_minutes": actual_wait,
                "absolute_error_minutes": abs(prediction.predicted_wait_minutes - actual_wait),
                "generated_at": prediction.generated_at,
                "queue": str(entry.queue_id),
                "service_point": entry.queue.service_point.name,
                "facility": entry.queue.service_point.facility.name,
            }
        )
    return rows
