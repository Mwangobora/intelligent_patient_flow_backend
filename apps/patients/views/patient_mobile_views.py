from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.permissions import IsAuthenticatedActive
from apps.accounts.views._auth_cookies import set_auth_cookies
from apps.checkins.models import CheckinToken
from apps.checkins._helpers import translate_domain_error
from apps.checkins.serializers import CheckinOutputSerializer
from apps.checkins.services import consume_checkin_token, create_appointment_checkin, issue_checkin_token
from apps.checkins.services._crypto import build_token_hash
from apps.facilities.selectors import list_facilities, list_facility_specialties
from apps.facilities.serializers import FacilityListSerializer, FacilitySpecialtyDetailSerializer
from apps.notifications.models import PatientNotification
from apps.notifications.serializers import PatientNotificationPatientOutputSerializer
from apps.notifications.services import mark_notification_read
from apps.patients.selectors import (
    PATIENT_QUEUE_HISTORY_STATUSES,
    build_patient_queue_history_payload,
    build_patient_queue_payload,
    checkin_block_reason,
    get_authenticated_patient,
    get_checkin_eligibility,
    get_current_patient_queue_entry,
    get_next_checkin_eligibility_for_facility,
    list_patient_queue_entries,
)
from apps.patients.serializers import (
    PatientAppointmentCheckinResponseSerializer,
    PatientCheckinEligibilityQuerySerializer,
    PatientCheckinEligibilitySerializer,
    PatientClaimExistingRecordResponseSerializer,
    PatientClaimExistingRecordSerializer,
    PatientMobileProfileSerializer,
    PatientMobileProfileUpdateSerializer,
    PatientMobileAppointmentCancelSerializer,
    PatientMobileAppointmentCreateSerializer,
    PatientMobileAppointmentRescheduleSerializer,
    PatientMobileAppointmentSlotQuerySerializer,
    PatientMobileNotificationSerializer,
    PatientMobileRegisterSerializer,
    PatientMobileRegistrationResponseSerializer,
    PatientFacilityQrConsumeInputSerializer,
    PatientQrConsumeInputSerializer,
    PatientQrTokenIssueResponseSerializer,
    PatientQueueCurrentSerializer,
    PatientQueueHistoryResponseSerializer,
)
from apps.patients.services.patient_mobile_account_service import (
    _safe_patient_summary,
    claim_existing_patient_record,
    get_patient_for_user,
    register_mobile_patient,
    update_current_patient_profile,
)
from apps.queueing.selectors import list_entries_by_checkin
from apps.scheduling.models import Appointment
from apps.scheduling.selectors import (
    available_slots,
    get_appointment_status_history,
    list_appointments,
)
from apps.scheduling.serializers import (
    AppointmentDetailSerializer,
    AppointmentSlotDetailSerializer,
    AppointmentStatusHistorySerializer,
)
from apps.scheduling.services import cancel_appointment, create_appointment, reschedule_appointment


PATIENT_MOBILE_DOCS_TAG = "Patient Mobile"


def _patient_not_found_response() -> Response:
    return Response({"detail": "Patient profile was not found for this account."}, status=status.HTTP_404_NOT_FOUND)


def _user_summary(user) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "phone_number": user.phone_number,
        "first_name": user.first_name,
        "middle_name": user.middle_name,
        "last_name": user.last_name,
        "is_active": user.is_active,
    }


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
class PatientRegisterAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=PatientMobileRegisterSerializer,
        responses={201: PatientMobileRegistrationResponseSerializer},
    )
    def post(self, request):
        serializer = PatientMobileRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user, patient = register_mobile_patient(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)

        refresh = RefreshToken.for_user(user)
        response = Response(
            PatientMobileRegistrationResponseSerializer(
                {"user": _user_summary(user), "patient": _safe_patient_summary(patient)}
            ).data,
            status=status.HTTP_201_CREATED,
        )
        return set_auth_cookies(
            response=response,
            access_token=str(refresh.access_token),
            refresh_token=str(refresh),
        )


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientMeAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(responses={200: PatientMobileProfileSerializer})
    def get(self, request):
        try:
            patient = get_patient_for_user(request.user)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientMobileProfileSerializer(_safe_patient_summary(patient)).data)

    @extend_schema(request=PatientMobileProfileUpdateSerializer, responses={200: PatientMobileProfileSerializer})
    def patch(self, request):
        serializer = PatientMobileProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            patient = update_current_patient_profile(user=request.user, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientMobileProfileSerializer(_safe_patient_summary(patient)).data)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientClaimExistingRecordAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=PatientClaimExistingRecordSerializer,
        responses={200: PatientClaimExistingRecordResponseSerializer},
    )
    def post(self, request):
        serializer = PatientClaimExistingRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = claim_existing_patient_record(**serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)

        if result.get("status") == "linked":
            user = result["user"]
            patient = result["patient"]
            refresh = RefreshToken.for_user(user)
            response = Response(
                PatientClaimExistingRecordResponseSerializer(
                    {
                        "status": result["status"],
                        "message": result["message"],
                        "user": _user_summary(user),
                        "patient": _safe_patient_summary(patient),
                    }
                ).data
            )
            return set_auth_cookies(
                response=response,
                access_token=str(refresh.access_token),
                refresh_token=str(refresh),
            )

        return Response(PatientClaimExistingRecordResponseSerializer(result).data)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientAppointmentListCreateAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(responses={200: AppointmentDetailSerializer(many=True)})
    def get(self, request):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()

        queryset = list_appointments(
            patient_id=patient.id,
            status=request.query_params.get("status"),
            starts_from=request.query_params.get("starts_from"),
            ends_to=request.query_params.get("ends_to"),
        )
        return Response(AppointmentDetailSerializer(queryset, many=True).data)

    @extend_schema(request=PatientMobileAppointmentCreateSerializer, responses={201: AppointmentDetailSerializer})
    def post(self, request):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()

        serializer = PatientMobileAppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            appointment = create_appointment(
                patient_id=patient.id,
                booking_channel=Appointment.BookingChannel.MOBILE,
                created_by_id=request.user.id,
                **serializer.validated_data,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AppointmentDetailSerializer(appointment).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientAppointmentDetailAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    def _get_patient_appointment(self, request, appointment_id):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return None, _patient_not_found_response()
        appointment = list_appointments(patient_id=patient.id).filter(pk=appointment_id).first()
        if appointment is None:
            return None, Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)
        return appointment, None

    @extend_schema(responses={200: AppointmentDetailSerializer})
    def get(self, request, appointment_id):
        appointment, error = self._get_patient_appointment(request, appointment_id)
        if error is not None:
            return error
        return Response(AppointmentDetailSerializer(appointment).data)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientAppointmentStatusHistoryAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(responses={200: AppointmentStatusHistorySerializer(many=True)})
    def get(self, request, appointment_id):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()
        if not list_appointments(patient_id=patient.id).filter(pk=appointment_id).exists():
            return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)
        history = get_appointment_status_history(appointment_id=appointment_id)
        return Response(AppointmentStatusHistorySerializer(history, many=True).data)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientAppointmentCancelAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(request=PatientMobileAppointmentCancelSerializer, responses={200: AppointmentDetailSerializer})
    def post(self, request, appointment_id):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()
        if not list_appointments(patient_id=patient.id).filter(pk=appointment_id).exists():
            return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PatientMobileAppointmentCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            appointment = cancel_appointment(
                appointment_id=appointment_id,
                cancelled_by_id=request.user.id,
                **serializer.validated_data,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AppointmentDetailSerializer(appointment).data)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientAppointmentRescheduleAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(request=PatientMobileAppointmentRescheduleSerializer, responses={201: AppointmentDetailSerializer})
    def post(self, request, appointment_id):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()
        if not list_appointments(patient_id=patient.id).filter(pk=appointment_id).exists():
            return Response({"detail": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PatientMobileAppointmentRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            appointment = reschedule_appointment(
                appointment_id=appointment_id,
                booking_channel=Appointment.BookingChannel.MOBILE,
                created_by_id=request.user.id,
                **serializer.validated_data,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(AppointmentDetailSerializer(appointment).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientFacilityListAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(responses={200: FacilityListSerializer(many=True)})
    def get(self, request):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()
        queryset = list_facilities(organization_id=patient.organization_id, is_active=True)
        return Response(FacilityListSerializer(queryset, many=True).data)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientFacilitySpecialtyListAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(responses={200: FacilitySpecialtyDetailSerializer(many=True)})
    def get(self, request, facility_id):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()
        facilities = list_facilities(organization_id=patient.organization_id, is_active=True).filter(pk=facility_id)
        if not facilities.exists():
            return Response({"detail": "Facility not found."}, status=status.HTTP_404_NOT_FOUND)
        queryset = list_facility_specialties(facility_id=facility_id, is_active=True).filter(accepts_appointments=True)
        return Response(FacilitySpecialtyDetailSerializer(queryset, many=True).data)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientAppointmentSlotListAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="facility_id", required=True, type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="facility_specialty_id", required=True, type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="starts_from", required=True, type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="ends_to", required=True, type=str, location=OpenApiParameter.QUERY),
        ],
        responses={200: AppointmentSlotDetailSerializer(many=True)},
    )
    def get(self, request):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()
        serializer = PatientMobileAppointmentSlotQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        facility_id = serializer.validated_data["facility_id"]
        facility_specialty_id = serializer.validated_data["facility_specialty_id"]
        if not list_facilities(organization_id=patient.organization_id, is_active=True).filter(pk=facility_id).exists():
            return Response({"detail": "Facility not found."}, status=status.HTTP_404_NOT_FOUND)
        if not list_facility_specialties(facility_id=facility_id, is_active=True).filter(
            pk=facility_specialty_id,
            accepts_appointments=True,
        ).exists():
            return Response({"detail": "Appointment service not found."}, status=status.HTTP_404_NOT_FOUND)
        queryset = available_slots(
            facility_id=facility_id,
            facility_specialty_id=facility_specialty_id,
            starts_from=serializer.validated_data["starts_from"],
            ends_to=serializer.validated_data["ends_to"],
        )
        return Response(AppointmentSlotDetailSerializer(queryset, many=True).data)


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
class PatientAppointmentQrTokenIssueAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(responses={201: PatientQrTokenIssueResponseSerializer})
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
            return Response({"detail": "QR token cannot be issued.", "reason": reason}, status=status.HTTP_400_BAD_REQUEST)

        try:
            issued = issue_checkin_token(appointment_id=appointment.id, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)

        payload = {
            "id": issued.token.id,
            "appointment_id": appointment.id,
            "raw_token": issued.raw_token,
            "expires_at": issued.token.expires_at,
        }
        return Response(PatientQrTokenIssueResponseSerializer(payload).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientQrConsumeAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(request=PatientQrConsumeInputSerializer, responses={201: PatientAppointmentCheckinResponseSerializer})
    def post(self, request):
        serializer = PatientQrConsumeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()

        raw_token = serializer.validated_data["token"]
        token = (
            CheckinToken.objects.select_related("appointment", "appointment__patient")
            .filter(token_hash=build_token_hash(raw_token))
            .first()
        )
        if token is None:
            return Response({"detail": "This QR code is not valid.", "reason": "invalid_qr"}, status=status.HTTP_400_BAD_REQUEST)
        if token.appointment.patient_id != patient.id:
            return Response(
                {"detail": "This QR code does not belong to your account.", "reason": "not_your_appointment"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            checkin = consume_checkin_token(raw_token=raw_token)
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
class PatientFacilityQrConsumeAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(request=PatientFacilityQrConsumeInputSerializer, responses={201: PatientAppointmentCheckinResponseSerializer})
    def post(self, request):
        serializer = PatientFacilityQrConsumeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()

        facility_id = serializer.validated_data["facility_id"]
        if not list_facilities(organization_id=patient.organization_id, is_active=True).filter(pk=facility_id).exists():
            return Response({"detail": "Facility not found."}, status=status.HTTP_404_NOT_FOUND)

        eligibility = get_next_checkin_eligibility_for_facility(patient=patient, facility_id=facility_id)
        if eligibility is None:
            return Response(
                {"detail": "No appointment is ready for check-in at this facility.", "reason": "no_eligible_appointment"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not eligibility.can_check_in:
            return Response(
                {"detail": "Appointment cannot be checked in.", "reason": eligibility.reason},
                status=status.HTTP_400_BAD_REQUEST,
            )

        appointment = eligibility.appointment
        try:
            checkin = create_appointment_checkin(
                facility_id=appointment.facility_id,
                patient_id=patient.id,
                appointment_id=appointment.id,
                facility_specialty_id=appointment.facility_specialty_id,
                checkin_method="qr_code",
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


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientNotificationListAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(responses={200: PatientMobileNotificationSerializer(many=True)})
    def get(self, request):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()

        queryset = (
            PatientNotification.objects.select_related("patient", "recipient_user", "appointment", "queue_entry")
            .filter(patient=patient)
            .order_by("-created_at")
        )
        if request.query_params.get("unread_only", "").lower() == "true":
            queryset = queryset.filter(read_at__isnull=True).exclude(status=PatientNotification.Status.CANCELLED)
        return Response(PatientNotificationPatientOutputSerializer(queryset, many=True).data)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientNotificationDetailAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(responses={200: PatientMobileNotificationSerializer})
    def get(self, request, notification_id):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()

        notification = PatientNotification.objects.filter(pk=notification_id, patient=patient).first()
        if notification is None:
            return Response({"detail": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PatientNotificationPatientOutputSerializer(notification).data)


@extend_schema(tags=[PATIENT_MOBILE_DOCS_TAG])
class PatientNotificationMarkReadAPIView(APIView):
    permission_classes = [IsAuthenticatedActive]

    @extend_schema(responses={200: PatientMobileNotificationSerializer})
    def post(self, request, notification_id):
        patient = get_authenticated_patient(request.user)
        if patient is None:
            return _patient_not_found_response()

        notification = PatientNotification.objects.filter(pk=notification_id, patient=patient).first()
        if notification is None:
            return Response({"detail": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            notification = mark_notification_read(notification_id=notification.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientNotificationPatientOutputSerializer(notification).data)


def _positive_int(value, *, default: int, max_value: int) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(parsed, max_value))
