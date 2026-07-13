from .analytics_views import (
    AppointmentUtilizationAnalyticsViewSet,
    DailyAttendanceAnalyticsViewSet,
    DoctorWorkloadAnalyticsViewSet,
    PatientWaitingTimeAnalyticsViewSet,
    PredictionAccuracyAnalyticsViewSet,
)
from .report_export_views import ReportExportViewSet

__all__ = [
    "AppointmentUtilizationAnalyticsViewSet",
    "DailyAttendanceAnalyticsViewSet",
    "DoctorWorkloadAnalyticsViewSet",
    "PatientWaitingTimeAnalyticsViewSet",
    "PredictionAccuracyAnalyticsViewSet",
    "ReportExportViewSet",
]
