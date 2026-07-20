from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedActive
from apps.checkins._helpers import translate_domain_error
from apps.checkins.serializers import CheckinOutputSerializer
from apps.checkins.services import create_appointment_checkin
from apps.patients.selectors import (
    PATIENT_QUEUE_HISTORY_STATUSES,
    build_patient_queue_history_payload,
    build_patient_queue_payload,
    checkin_block_reason,
    get_authenticated_patient,
    get_checkin_eligibility,
    get_current_patient_queue_entry,
    list_patient_queue_entries,
)
from apps.patients.serializers import (
    PatientAppointmentCheckinResponseSerializer,
    PatientCheckinEligibilityQuerySerializer,
    PatientCheckinEligibilitySerializer,
    PatientQueueCurrentSerializer,
    PatientQueueHistoryResponseSerializer,
)
from apps.queueing.selectors import list_entries_by_checkin
from apps.scheduling.models import Appointment


PATIENT_MOBILE_DOCS_TAG = "Patient Mobile"


def _patient_not_found_response() -> Response:
    return Response({"detail": "Patient profile was not found for this account."}, status=status.HTTP_404_NOT_FOUND)


def _appointment_payload(eligibility) -> dict:
    appointment = eligibility.appointment
    facility_specialty = appointment.facility_specialty
    specialty = facility_specialty.specialty if facility_specialty else None
    department = facility_specialty.department if facility_specialty else None
    return {
        "appointment_id": appointment.id,
        "can_check_in": eligibility.can_check_in,
        "reason": eligibility.reason,
        "appointment_status": appointment.status,
        "scheduled_start": appointment.scheduled_start,
        "scheduled_end": appointment.scheduled_end,
        "facility": {
            "id": appointment.facility_id,
            "name": appointment.facility.name,
            "timezone": appointment.facility.timezone,
        },
        "specialty": {"id": specialty.id, "name": specialty.name} if specialty else None,
        "department": {"id": department.id, "name": department.name} if department else None,
        "existing_checkin": (
            {
                "id": eligibility.existing_checkin.id,
                "checked_in_at": eligibility.existing_checkin.checked_in_at,
                "checkin_method": eligibility.existing_checkin.checkin_method,
            }
            if eligibility.existing_checkin
            else None
        ),
        "has_active_token": eligibility.active_token is not None,
        "token_expires_at": eligibility.active_token.expires_at if eligibility.active_token else None,
    }


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientCheckinEligibilityAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="appointment_id", required=True, type=str, location=OpenApiParameter.QUERY),
        ],
        responses={200: PatientCheckinEligibilitySerializer},
    )
    def get(self, request):
        query_serializer = PatientCheckinEligibilityQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()

        eligibility = get_checkin_eligibility(
            patient=patient,
            appointment_id=query_serializer.validated_data["appointment_id"],
        )
        if eligibility is None:
            return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(PatientCheckinEligibilitySerializer(_appointment_payload(eligibility)).data)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientAppointmentCheckinAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(responses={201: PatientAppointmentCheckinResponseSerializer})
    def post(self, request, appointment_id):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()

        appointment = (
            Appointment.objects.select_related("facility", "facility_specialty")
            .filter(pk=appointment_id, patient=patient)
            .first()
        )
        if appointment is None:
            return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)

        reason = checkin_block_reason(appointment=appointment)
        if reason is not None:
            return Response({"detail": "Appointment cannot be checked in.", "reason": reason}, status=status.HTTP_400_BAD_REQUEST)

        try:
            checkin = create_appointment_checkin(
                facility_id=appointment.facility_id,
                patient_id=patient.id,
                appointment_id=appointment.id,
                facility_specialty_id=appointment.facility_specialty_id,
                checkin_method="mobile",
            )
        except Exception as exc:
            translate_domain_error(exc)

        queue_entry = list_entries_by_checkin(patient_checkin_id=checkin.id).first()
        payload = {
            "checkin": CheckinOutputSerializer(checkin).data,
            "queue_entry": build_patient_queue_payload(queue_entry) if queue_entry else None,
            "message": (
                "You are checked in. Please wait for reception to add you to the queue."
                if queue_entry is None
                else "Check-in successful. Your queue status is ready."
            ),
        }
        return Response(PatientAppointmentCheckinResponseSerializer(payload).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientCurrentQueueAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(responses={200: PatientQueueCurrentSerializer})
    def get(self, request):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()

        entry = get_current_patient_queue_entry(patient=patient)
        return Response(PatientQueueCurrentSerializer(build_patient_queue_payload(entry)).data)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientQueueHistoryAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="date_from", required=False, type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="date_to", required=False, type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="limit", required=False, type=int, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="offset", required=False, type=int, location=OpenApiParameter.QUERY),
        ],
        responses={200: PatientQueueHistoryResponseSerializer},
    )
    def get(self, request):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()

        limit = _positive_int(request.query_params.get("limit"), default=20, max_value=100)
        offset = _positive_int(request.query_params.get("offset"), default=0, max_value=10000)
        queryset = list_patient_queue_entries(patient=patient, statuses=PATIENT_QUEUE_HISTORY_STATUSES)
        if request.query_params.get("date_from"):
            queryset = queryset.filter(joined_at__date__gte=request.query_params["date_from"])
        if request.query_params.get("date_to"):
            queryset = queryset.filter(joined_at__date__lte=request.query_params["date_to"])

        count = queryset.count()
        results = [build_patient_queue_history_payload(entry) for entry in queryset[offset : offset + limit]]
        return Response(
            PatientQueueHistoryResponseSerializer(
                {"count": count, "limit": limit, "offset": offset, "results": results}
            ).data
        )


def _positive_int(value, *, default: int, max_value: int) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(parsed, max_value))
