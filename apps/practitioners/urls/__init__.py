from django.urls import include, path
from rest_framework_nested.routers import NestedSimpleRouter, SimpleRouter

from apps.practitioners.views import (
    PractitionerCredentialTypeViewSet,
    PractitionerCredentialViewSet,
    PractitionerDepartmentAssignmentViewSet,
    PractitionerFacilityAssignmentViewSet,
    PractitionerSpecialtyAssignmentViewSet,
    PractitionerTypeViewSet,
    PractitionerViewSet,
)

router = SimpleRouter()
router.register(r"practitioners/types", PractitionerTypeViewSet, basename="practitioners-types")
router.register(r"practitioners/credential-types", PractitionerCredentialTypeViewSet, basename="practitioners-credential-types")
router.register(r"practitioners/facility-assignments", PractitionerFacilityAssignmentViewSet, basename="practitioners-facility-assignments")
router.register(r"practitioners/department-assignments", PractitionerDepartmentAssignmentViewSet, basename="practitioners-department-assignments")
router.register(r"practitioners/specialty-assignments", PractitionerSpecialtyAssignmentViewSet, basename="practitioners-specialty-assignments")
router.register(r"practitioners/credentials", PractitionerCredentialViewSet, basename="practitioners-credentials")
router.register(r"practitioners", PractitionerViewSet, basename="practitioners")

practitioner_router = NestedSimpleRouter(router, r"practitioners", lookup="practitioner")
practitioner_router.register(r"facility-assignments", PractitionerFacilityAssignmentViewSet, basename="practitioners-practitioner-facility-assignments")
practitioner_router.register(r"credentials", PractitionerCredentialViewSet, basename="practitioners-practitioner-credentials")

facility_assignment_router = NestedSimpleRouter(router, r"practitioners/facility-assignments", lookup="practitioner_facility_assignment")
facility_assignment_router.register(r"department-assignments", PractitionerDepartmentAssignmentViewSet, basename="practitioners-facility-department-assignments")
facility_assignment_router.register(r"specialty-assignments", PractitionerSpecialtyAssignmentViewSet, basename="practitioners-facility-specialty-assignments")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(practitioner_router.urls)),
    path("", include(facility_assignment_router.urls)),
]
