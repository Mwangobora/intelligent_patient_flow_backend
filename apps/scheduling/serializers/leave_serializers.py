from __future__ import annotations

from rest_framework import serializers

from apps.scheduling.models import PractitionerLeaveRequest


class LeaveRequestDetailSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="practitioner_facility_assignment.facility.name", read_only=True)

    class Meta:
        model = PractitionerLeaveRequest
        fields = [
            "id",
            "practitioner_facility_assignment",
            "facility_name",
            "starts_at",
            "ends_at",
            "reason",
            "status",
            "requested_by",
            "decided_by",
            "decided_at",
            "decision_note",
            "cancelled_by",
            "cancelled_at",
            "cancellation_reason",
            "created_at",
            "updated_at",
        ]


class LeaveRequestCreateSerializer(serializers.Serializer):
    practitioner_facility_assignment_id = serializers.UUIDField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class LeaveDecisionSerializer(serializers.Serializer):
    decision_note = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class LeaveCancellationSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField()
