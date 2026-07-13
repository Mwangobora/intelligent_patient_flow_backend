from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.reporting.views import (
    AppointmentUtilizationAnalyticsViewSet,
    DailyAttendanceAnalyticsViewSet,
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
router.register(r"reporting/exports", ReportExportViewSet, basename="reporting-exports")

urlpatterns = [
    path("", include(router.urls)),
]
