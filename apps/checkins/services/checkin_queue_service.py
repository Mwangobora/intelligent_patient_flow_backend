from __future__ import annotations

import logging

from django.db import transaction

from apps.checkins.models import PatientCheckin
from apps.facilities.models import ServicePoint
from apps.queueing.models import Queue, QueueEntry
from apps.queueing.services import create_queue, create_queue_entry, open_queue, resume_queue
from apps.queueing.services._shared import facility_local_date
from common.exceptions import ConflictError, ValidationError

logger = logging.getLogger(__name__)


def _service_point_for_checkin(checkin: PatientCheckin) -> ServicePoint | None:
    specialty = checkin.facility_specialty or getattr(checkin.appointment, "facility_specialty", None)
    queryset = ServicePoint.objects.select_related("facility", "department").filter(
        facility_id=checkin.facility_id,
        is_active=True,
    )
    if specialty and specialty.department_id:
        matching_department = queryset.filter(department_id=specialty.department_id).order_by("display_order", "code").first()
        if matching_department is not None:
            return matching_department
    return queryset.order_by("display_order", "code").first()


def _get_or_open_queue(*, service_point: ServicePoint, facility_specialty_id, created_by_id=None) -> Queue:
    queue_date = facility_local_date(service_point.facility)
    queue = (
        Queue.objects.select_for_update()
        .filter(
            service_point=service_point,
            facility_specialty_id=facility_specialty_id,
            queue_date=queue_date,
        )
        .first()
    )
    if queue is None:
        queue = create_queue(
            service_point_id=service_point.id,
            facility_specialty_id=facility_specialty_id,
            queue_date=queue_date,
            created_by_id=created_by_id,
        )
    if queue.status == Queue.Status.PAUSED:
        return resume_queue(queue_id=queue.id)
    if queue.status == Queue.Status.DRAFT:
        return open_queue(queue_id=queue.id, opened_by_id=created_by_id)
    if queue.status == Queue.Status.OPEN:
        return queue
    raise ValidationError("The queue for this service is closed or cancelled.")


@transaction.atomic
def enqueue_checkin_after_arrival(*, checkin_id, created_by_id=None) -> QueueEntry | None:
    checkin = (
        PatientCheckin.objects.select_for_update(of=("self",))
        .select_related(
            "facility",
            "appointment",
            "appointment__facility_specialty",
            "facility_specialty",
            "facility_specialty__department",
        )
        .filter(pk=checkin_id, voided_at__isnull=True)
        .first()
    )
    if checkin is None:
        return None
    existing_entry = (
        QueueEntry.objects.select_related("queue", "queue__service_point")
        .filter(patient_checkin=checkin)
        .exclude(status__in=[QueueEntry.Status.CANCELLED, QueueEntry.Status.TRANSFERRED])
        .order_by("-joined_at")
        .first()
    )
    if existing_entry is not None:
        return existing_entry

    service_point = _service_point_for_checkin(checkin)
    if service_point is None:
        logger.info("Automatic queue skipped for check-in %s because no active service point exists.", checkin.id)
        return None

    specialty_id = checkin.facility_specialty_id or (
        checkin.appointment.facility_specialty_id if checkin.appointment_id else None
    )
    queue = _get_or_open_queue(
        service_point=service_point,
        facility_specialty_id=specialty_id,
        created_by_id=created_by_id,
    )
    try:
        return create_queue_entry(
            queue_id=queue.id,
            patient_checkin_id=checkin.id,
            created_by_id=created_by_id,
        )
    except ConflictError:
        return QueueEntry.objects.filter(queue=queue, patient_checkin=checkin).first()
