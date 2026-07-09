from django.urls import include, path
from rest_framework_nested.routers import NestedSimpleRouter, SimpleRouter

from apps.facilities.views import (
    ConsultationRoomViewSet,
    DepartmentViewSet,
    FacilityFlowSettingViewSet,
    FacilityOperatingHourViewSet,
    FacilityScheduleExceptionViewSet,
    FacilitySpecialtyViewSet,
    FacilityTypeViewSet,
    FacilityViewSet,
    OrganizationViewSet,
    ServicePointTypeViewSet,
    ServicePointViewSet,
    SpecialtyViewSet,
)

router = SimpleRouter()
router.register(r"facilities/organizations", OrganizationViewSet, basename="facilities-organizations")
router.register(r"facilities/facility-types", FacilityTypeViewSet, basename="facilities-facility-types")
router.register(r"facilities/facilities", FacilityViewSet, basename="facilities-facilities")
router.register(r"facilities/departments", DepartmentViewSet, basename="facilities-departments")
router.register(r"facilities/specialties", SpecialtyViewSet, basename="facilities-specialties")
router.register(r"facilities/facility-specialties", FacilitySpecialtyViewSet, basename="facilities-facility-specialties")
router.register(r"facilities/service-point-types", ServicePointTypeViewSet, basename="facilities-service-point-types")
router.register(r"facilities/service-points", ServicePointViewSet, basename="facilities-service-points")
router.register(r"facilities/consultation-rooms", ConsultationRoomViewSet, basename="facilities-consultation-rooms")
router.register(r"facilities/operating-hours", FacilityOperatingHourViewSet, basename="facilities-operating-hours")
router.register(r"facilities/schedule-exceptions", FacilityScheduleExceptionViewSet, basename="facilities-schedule-exceptions")
router.register(r"facilities/flow-settings", FacilityFlowSettingViewSet, basename="facilities-flow-settings")

facility_router = NestedSimpleRouter(router, r"facilities/facilities", lookup="facility")
facility_router.register(r"departments", DepartmentViewSet, basename="facilities-facility-departments")
facility_router.register(r"facility-specialties", FacilitySpecialtyViewSet, basename="facilities-facility-specialties-nested")
facility_router.register(r"service-points", ServicePointViewSet, basename="facilities-facility-service-points")
facility_router.register(r"consultation-rooms", ConsultationRoomViewSet, basename="facilities-facility-consultation-rooms")
facility_router.register(r"operating-hours", FacilityOperatingHourViewSet, basename="facilities-facility-operating-hours")
facility_router.register(r"schedule-exceptions", FacilityScheduleExceptionViewSet, basename="facilities-facility-schedule-exceptions")
facility_router.register(r"flow-settings", FacilityFlowSettingViewSet, basename="facilities-facility-flow-settings")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(facility_router.urls)),
]
