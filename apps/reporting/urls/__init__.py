from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.reporting.views import (
    AppointmentUtilizationAnalyticsViewSet,
    DailyAttendanceAnalyticsViewSet,
    DashboardAppointmentsAPIView,
    DashboardCheckinsAPIView,
    DashboardIntelligenceAPIView,
    DashboardOverviewAPIView,
    DashboardPractitionersAPIView,
    DashboardQueuesAPIView,
    DoctorWorkloadAnalyticsViewSet,
    PatientWaitingTimeAnalyticsViewSet,
    PredictionAccuracyAnalyticsViewSet,
    ReportExportViewSet,
)

router = SimpleRouter()
router.register(r"reporting/analytics/patient-waiting-time", PatientWaitingTimeAnalyticsViewSet, basename="reporting-patient-waiting-time")
router.register(r"reporting/analytics/appointment-utilization", AppointmentUtilizationAnalyticsViewSet, basename="reporting-appointment-utilization")
router.register(r"reporting/analytics/doctor-workload", DoctorWorkloadAnalyticsViewSet, basename="reporting-doctor-workload")
router.register(r"reporting/analytics/daily-attendance", DailyAttendanceAnalyticsViewSet, basename="reporting-daily-attendance")
router.register(r"reporting/analytics/prediction-accuracy", PredictionAccuracyAnalyticsViewSet, basename="reporting-prediction-accuracy")
router.register(r"reporting/dashboard/overview", DashboardOverviewAPIView, basename="reporting-dashboard-overview")
router.register(r"reporting/dashboard/appointments", DashboardAppointmentsAPIView, basename="reporting-dashboard-appointments")
router.register(r"reporting/dashboard/queues", DashboardQueuesAPIView, basename="reporting-dashboard-queues")
router.register(r"reporting/dashboard/checkins", DashboardCheckinsAPIView, basename="reporting-dashboard-checkins")
router.register(r"reporting/dashboard/practitioners", DashboardPractitionersAPIView, basename="reporting-dashboard-practitioners")
router.register(r"reporting/dashboard/intelligence", DashboardIntelligenceAPIView, basename="reporting-dashboard-intelligence")
router.register(r"reporting/exports", ReportExportViewSet, basename="reporting-exports")

urlpatterns = [
    path("", include(router.urls)),
]
