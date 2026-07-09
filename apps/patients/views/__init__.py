from .access_views import PatientAccessGrantViewSet
from .base import PATIENT_DOCS_TAG, PatientsBaseViewSet
from .identifier_views import PatientAddressViewSet, PatientIdentifierTypeViewSet, PatientIdentifierViewSet
from .patient_views import PatientViewSet
from .relationship_views import RelatedPersonContactViewSet, RelationshipTypeViewSet, PatientRelatedPersonViewSet

__all__ = [
    "PATIENT_DOCS_TAG",
    "PatientAccessGrantViewSet",
    "PatientAddressViewSet",
    "PatientIdentifierTypeViewSet",
    "PatientIdentifierViewSet",
    "PatientRelatedPersonViewSet",
    "PatientViewSet",
    "PatientsBaseViewSet",
    "RelatedPersonContactViewSet",
    "RelationshipTypeViewSet",
]
