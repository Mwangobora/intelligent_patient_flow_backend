from .access_views import PatientAccessGrantViewSet
from .base import PATIENT_DOCS_TAG, PatientsBaseViewSet
from .identifier_views import PatientAddressViewSet, PatientIdentifierTypeViewSet, PatientIdentifierViewSet
from .patient_views import PatientViewSet
from .patient_mobile_views import (
    PATIENT_MOBILE_DOCS_TAG,
    PatientAppointmentCheckinAPIView,
    PatientAppointmentQrTokenIssueAPIView,
    PatientCheckinEligibilityAPIView,
    PatientClaimExistingRecordAPIView,
    PatientCurrentQueueAPIView,
    PatientMeAPIView,
    PatientQrConsumeAPIView,
    PatientQueueHistoryAPIView,
    PatientRegisterAPIView,
)
from .relationship_views import RelatedPersonContactViewSet, RelationshipTypeViewSet, PatientRelatedPersonViewSet

__all__ = [
    "PATIENT_MOBILE_DOCS_TAG",
    "PATIENT_DOCS_TAG",
    "PatientAccessGrantViewSet",
    "PatientAddressViewSet",
    "PatientAppointmentCheckinAPIView",
    "PatientAppointmentQrTokenIssueAPIView",
    "PatientCheckinEligibilityAPIView",
    "PatientClaimExistingRecordAPIView",
    "PatientCurrentQueueAPIView",
    "PatientMeAPIView",
    "PatientQrConsumeAPIView",
    "PatientIdentifierTypeViewSet",
    "PatientIdentifierViewSet",
    "PatientQueueHistoryAPIView",
    "PatientRegisterAPIView",
    "PatientRelatedPersonViewSet",
    "PatientViewSet",
    "PatientsBaseViewSet",
    "RelatedPersonContactViewSet",
    "RelationshipTypeViewSet",
]
