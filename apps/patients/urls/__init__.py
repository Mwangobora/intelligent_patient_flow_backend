from django.urls import include, path
from rest_framework_nested.routers import NestedSimpleRouter, SimpleRouter

from apps.patients.views import (
    PatientAccessGrantViewSet,
    PatientAddressViewSet,
    PatientAppointmentCancelAPIView,
    PatientAppointmentCheckinAPIView,
    PatientAppointmentDetailAPIView,
    PatientAppointmentListCreateAPIView,
    PatientAppointmentQrTokenIssueAPIView,
    PatientAppointmentRescheduleAPIView,
    PatientAppointmentSlotListAPIView,
    PatientAppointmentStatusHistoryAPIView,
    PatientCheckinEligibilityAPIView,
    PatientClaimExistingRecordAPIView,
    PatientCurrentQueueAPIView,
    PatientFacilityListAPIView,
    PatientFacilitySpecialtyListAPIView,
    PatientMeAPIView,
    PatientIdentifierTypeViewSet,
    PatientIdentifierViewSet,
    PatientQrConsumeAPIView,
    PatientQueueHistoryAPIView,
    PatientRegisterAPIView,
    PatientRelatedPersonViewSet,
    PatientViewSet,
    RelatedPersonContactViewSet,
    RelationshipTypeViewSet,
)

router = SimpleRouter()
router.register(r"patients/identifier-types", PatientIdentifierTypeViewSet, basename="patients-identifier-types")
router.register(r"patients/identifiers", PatientIdentifierViewSet, basename="patients-identifiers")
router.register(r"patients/addresses", PatientAddressViewSet, basename="patients-addresses")
router.register(r"patients/relationship-types", RelationshipTypeViewSet, basename="patients-relationship-types")
router.register(r"patients/related-persons", PatientRelatedPersonViewSet, basename="patients-related-persons")
router.register(r"patients/related-person-contacts", RelatedPersonContactViewSet, basename="patients-related-person-contacts")
router.register(r"patients/access-grants", PatientAccessGrantViewSet, basename="patients-access-grants")
router.register(r"patients", PatientViewSet, basename="patients")

patient_router = NestedSimpleRouter(router, r"patients", lookup="patient")
patient_router.register(r"identifiers", PatientIdentifierViewSet, basename="patients-patient-identifiers")
patient_router.register(r"addresses", PatientAddressViewSet, basename="patients-patient-addresses")
patient_router.register(r"related-persons", PatientRelatedPersonViewSet, basename="patients-patient-related-persons")
patient_router.register(r"access-grants", PatientAccessGrantViewSet, basename="patients-patient-access-grants")

related_person_router = NestedSimpleRouter(router, r"patients/related-persons", lookup="related_person")
related_person_router.register(r"contacts", RelatedPersonContactViewSet, basename="patients-related-person-contacts-nested")

urlpatterns = [
    path("patient/register/", PatientRegisterAPIView.as_view(), name="patient-register"),
    path("patient/me/", PatientMeAPIView.as_view(), name="patient-me"),
    path("patient/claim-existing-record/", PatientClaimExistingRecordAPIView.as_view(), name="patient-claim-existing-record"),
    path("patient/facilities/", PatientFacilityListAPIView.as_view(), name="patient-facilities"),
    path(
        "patient/facilities/<uuid:facility_id>/specialties/",
        PatientFacilitySpecialtyListAPIView.as_view(),
        name="patient-facility-specialties",
    ),
    path("patient/appointment-slots/", PatientAppointmentSlotListAPIView.as_view(), name="patient-appointment-slots"),
    path("patient/appointments/", PatientAppointmentListCreateAPIView.as_view(), name="patient-appointments"),
    path("patient/appointments/<uuid:appointment_id>/", PatientAppointmentDetailAPIView.as_view(), name="patient-appointment-detail"),
    path(
        "patient/appointments/<uuid:appointment_id>/cancel/",
        PatientAppointmentCancelAPIView.as_view(),
        name="patient-appointment-cancel",
    ),
    path(
        "patient/appointments/<uuid:appointment_id>/reschedule/",
        PatientAppointmentRescheduleAPIView.as_view(),
        name="patient-appointment-reschedule",
    ),
    path(
        "patient/appointments/<uuid:appointment_id>/status-history/",
        PatientAppointmentStatusHistoryAPIView.as_view(),
        name="patient-appointment-status-history",
    ),
    path("patient/checkins/eligibility/", PatientCheckinEligibilityAPIView.as_view(), name="patient-checkin-eligibility"),
    path(
        "patient/checkins/appointments/<uuid:appointment_id>/check-in/",
        PatientAppointmentCheckinAPIView.as_view(),
        name="patient-appointment-checkin",
    ),
    path(
        "patient/checkins/appointments/<uuid:appointment_id>/qr-token/",
        PatientAppointmentQrTokenIssueAPIView.as_view(),
        name="patient-appointment-qr-token",
    ),
    path("patient/checkins/qr/consume/", PatientQrConsumeAPIView.as_view(), name="patient-qr-consume"),
    path("patient/queue/current/", PatientCurrentQueueAPIView.as_view(), name="patient-current-queue"),
    path("patient/queue/history/", PatientQueueHistoryAPIView.as_view(), name="patient-queue-history"),
    path("", include(router.urls)),
    path("", include(patient_router.urls)),
    path("", include(related_person_router.urls)),
]
