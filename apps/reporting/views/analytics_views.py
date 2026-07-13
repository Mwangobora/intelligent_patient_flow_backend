from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from apps.reporting.selectors import (
    get_appointment_utilization_data,
    get_daily_attendance_data,
    get_doctor_workload_data,
    get_patient_waiting_time_data,
    get_prediction_accuracy_data,
)
from apps.reporting.serializers import AnalyticsQueryInputSerializer

from .base import REPORTING_DOCS_TAG, ReportingBaseViewSet


class AnalyticsBaseViewSet(ReportingBaseViewSet):
    permission_map = {"list": "reporting_analytics.view"}
    selector = None

    def get_permission_scope(self, request):
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        serializer = AnalyticsQueryInputSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        parameters = {
            key: value.isoformat()
            for key, value in {"date_from": payload.get("date_from"), "date_to": payload.get("date_to")}.items()
            if value
        }
        rows = self.selector(
            organization_id=payload["organization_id"],
            facility_id=payload.get("facility_id"),
            parameters=parameters,
        )
        return Response({"rows": rows, "row_count": len(rows)})


@extend_schema(tags=[REPORTING_DOCS_TAG])
class PatientWaitingTimeAnalyticsViewSet(AnalyticsBaseViewSet):
    selector = staticmethod(get_patient_waiting_time_data)


@extend_schema(tags=[REPORTING_DOCS_TAG])
class AppointmentUtilizationAnalyticsViewSet(AnalyticsBaseViewSet):
    selector = staticmethod(get_appointment_utilization_data)


@extend_schema(tags=[REPORTING_DOCS_TAG])
class DoctorWorkloadAnalyticsViewSet(AnalyticsBaseViewSet):
    selector = staticmethod(get_doctor_workload_data)


@extend_schema(tags=[REPORTING_DOCS_TAG])
class DailyAttendanceAnalyticsViewSet(AnalyticsBaseViewSet):
    selector = staticmethod(get_daily_attendance_data)


@extend_schema(tags=[REPORTING_DOCS_TAG])
class PredictionAccuracyAnalyticsViewSet(AnalyticsBaseViewSet):
    selector = staticmethod(get_prediction_accuracy_data)
