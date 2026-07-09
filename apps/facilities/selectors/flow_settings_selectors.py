from __future__ import annotations

from apps.facilities.models import FacilityFlowSetting


def list_flow_settings(*, facility_id=None):
    queryset = FacilityFlowSetting.objects.select_related("facility", "created_by")
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    return queryset.order_by("facility__name")


def get_flow_setting_by_id(flow_setting_id):
    return FacilityFlowSetting.objects.select_related("facility", "created_by").filter(pk=flow_setting_id).first()
