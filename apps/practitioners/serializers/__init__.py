from .assignment_serializers import (
    PractitionerDepartmentAssignmentCreateSerializer,
    PractitionerDepartmentAssignmentDetailSerializer,
    PractitionerDepartmentAssignmentUpdateSerializer,
    PractitionerFacilityAssignmentCreateSerializer,
    PractitionerFacilityAssignmentDetailSerializer,
    PractitionerFacilityAssignmentUpdateSerializer,
    PractitionerSpecialtyAssignmentCreateSerializer,
    PractitionerSpecialtyAssignmentDetailSerializer,
    PractitionerSpecialtyAssignmentUpdateSerializer,
)
from .credential_serializers import (
    PractitionerCredentialCreateSerializer,
    PractitionerCredentialDetailSerializer,
    PractitionerCredentialUpdateSerializer,
)
from .practitioner_serializers import (
    PractitionerCreateSerializer,
    PractitionerDetailSerializer,
    PractitionerListSerializer,
    PractitionerUpdateSerializer,
)
from .type_serializers import (
    PractitionerCredentialTypeCreateSerializer,
    PractitionerCredentialTypeDetailSerializer,
    PractitionerCredentialTypeListSerializer,
    PractitionerCredentialTypeUpdateSerializer,
    PractitionerTypeCreateSerializer,
    PractitionerTypeDetailSerializer,
    PractitionerTypeListSerializer,
    PractitionerTypeUpdateSerializer,
)

__all__ = [
    "PractitionerCreateSerializer",
    "PractitionerCredentialCreateSerializer",
    "PractitionerCredentialDetailSerializer",
    "PractitionerCredentialTypeCreateSerializer",
    "PractitionerCredentialTypeDetailSerializer",
    "PractitionerCredentialTypeListSerializer",
    "PractitionerCredentialTypeUpdateSerializer",
    "PractitionerCredentialUpdateSerializer",
    "PractitionerDepartmentAssignmentCreateSerializer",
    "PractitionerDepartmentAssignmentDetailSerializer",
    "PractitionerDepartmentAssignmentUpdateSerializer",
    "PractitionerDetailSerializer",
    "PractitionerFacilityAssignmentCreateSerializer",
    "PractitionerFacilityAssignmentDetailSerializer",
    "PractitionerFacilityAssignmentUpdateSerializer",
    "PractitionerListSerializer",
    "PractitionerSpecialtyAssignmentCreateSerializer",
    "PractitionerSpecialtyAssignmentDetailSerializer",
    "PractitionerSpecialtyAssignmentUpdateSerializer",
    "PractitionerTypeCreateSerializer",
    "PractitionerTypeDetailSerializer",
    "PractitionerTypeListSerializer",
    "PractitionerTypeUpdateSerializer",
    "PractitionerUpdateSerializer",
]
