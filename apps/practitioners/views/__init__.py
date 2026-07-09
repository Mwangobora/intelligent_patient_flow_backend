from .assignment_views import (
    PractitionerDepartmentAssignmentViewSet,
    PractitionerFacilityAssignmentViewSet,
    PractitionerSpecialtyAssignmentViewSet,
)
from .base import PRACTITIONER_DOCS_TAG, PractitionersBaseViewSet
from .credential_views import PractitionerCredentialViewSet
from .practitioner_views import PractitionerViewSet
from .type_views import PractitionerCredentialTypeViewSet, PractitionerTypeViewSet

__all__ = [
    "PRACTITIONER_DOCS_TAG",
    "PractitionerCredentialTypeViewSet",
    "PractitionerCredentialViewSet",
    "PractitionerDepartmentAssignmentViewSet",
    "PractitionerFacilityAssignmentViewSet",
    "PractitionersBaseViewSet",
    "PractitionerSpecialtyAssignmentViewSet",
    "PractitionerTypeViewSet",
    "PractitionerViewSet",
]
