from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from apps.reporting.selectors import (
    get_appointment_dashboard_summary,
    get_checkin_dashboard_summary,
    get_dashboard_overview_summary,
    get_intelligence_dashboard_summary,
    get_practitioner_dashboard_summary,
    get_queue_dashboard_summary,
)
from apps.reporting.serializers import (
    AppointmentDashboardOutputSerializer,
    CheckinDashboardOutputSerializer,
    DashboardOverviewOutputSerializer,
    DashboardQueryInputSerializer,
    IntelligenceDashboardOutputSerializer,
    PractitionerDashboardOutputSerializer,
    QueueDashboardOutputSerializer,
)

from .base import REPORTING_DOCS_TAG, ReportingBaseViewSet


class DashboardBaseViewSet(ReportingBaseViewSet):
    permission_map = {"list": "reporting_analytics.view"}
    selector = None
    output_serializer_class = None

    def get_permission_scope(self, request):
        return request.query_params.get("organization_id"), request.query_params.get("facility_id")

    def list(self, request):
        input_serializer = DashboardQueryInputSerializer(data=request.query_params)
        input_serializer.is_valid(raise_exception=True)
        summary = self.selector(**input_serializer.validated_data)
        output_serializer = self.output_serializer_class(summary)
        return Response(output_serializer.data)


@extend_schema(tags=[REPORTING_DOCS_TAG])
class DashboardOverviewAPIView(DashboardBaseViewSet):
    selector = staticmethod(get_dashboard_overview_summary)
    output_serializer_class = DashboardOverviewOutputSerializer


@extend_schema(tags=[REPORTING_DOCS_TAG])
class DashboardAppointmentsAPIView(DashboardBaseViewSet):
    selector = staticmethod(get_appointment_dashboard_summary)
    output_serializer_class = AppointmentDashboardOutputSerializer


@extend_schema(tags=[REPORTING_DOCS_TAG])
class DashboardQueuesAPIView(DashboardBaseViewSet):
    selector = staticmethod(get_queue_dashboard_summary)
    output_serializer_class = QueueDashboardOutputSerializer


@extend_schema(tags=[REPORTING_DOCS_TAG])
class DashboardCheckinsAPIView(DashboardBaseViewSet):
    selector = staticmethod(get_checkin_dashboard_summary)
    output_serializer_class = CheckinDashboardOutputSerializer


@extend_schema(tags=[REPORTING_DOCS_TAG])
class DashboardPractitionersAPIView(DashboardBaseViewSet):
    selector = staticmethod(get_practitioner_dashboard_summary)
    output_serializer_class = PractitionerDashboardOutputSerializer


@extend_schema(tags=[REPORTING_DOCS_TAG])
class DashboardIntelligenceAPIView(DashboardBaseViewSet):
    selector = staticmethod(get_intelligence_dashboard_summary)
    output_serializer_class = IntelligenceDashboardOutputSerializer
