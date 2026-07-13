from __future__ import annotations

from rest_framework import serializers

from apps.facilities.models import Facility


class DashboardQueryInputSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    facility_id = serializers.UUIDField(required=False, allow_null=True)
    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    department_id = serializers.UUIDField(required=False, allow_null=True)
    specialty_id = serializers.UUIDField(required=False, allow_null=True)
    service_point_id = serializers.UUIDField(required=False, allow_null=True)
    practitioner_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        organization_id = attrs.get("organization_id")
        facility_id = attrs.get("facility_id")
        if not organization_id and not facility_id:
            raise serializers.ValidationError("organization_id or facility_id is required.")

        if attrs.get("date_from") and attrs.get("date_to") and attrs["date_to"] < attrs["date_from"]:
            raise serializers.ValidationError("date_to must be greater than or equal to date_from.")

        if facility_id:
            facility = Facility.objects.filter(pk=facility_id).first()
            if facility is None:
                raise serializers.ValidationError("facility_id is invalid.")
            if organization_id and facility.organization_id != organization_id:
                raise serializers.ValidationError("facility_id must belong to organization_id.")
        return attrs


class DashboardOverviewOutputSerializer(serializers.Serializer):
    total_patients = serializers.IntegerField()
    total_appointments_today = serializers.IntegerField()
    total_checkins_today = serializers.IntegerField()
    total_waiting_now = serializers.IntegerField()
    total_called_now = serializers.IntegerField()
    total_in_service_now = serializers.IntegerField()
    completed_visits_today = serializers.IntegerField()
    cancelled_appointments_today = serializers.IntegerField()
    no_show_appointments_today = serializers.IntegerField()
    average_wait_minutes_today = serializers.FloatField(allow_null=True)
    active_queues = serializers.IntegerField()
    generated_at = serializers.DateTimeField()


class AppointmentDashboardOutputSerializer(serializers.Serializer):
    appointments_total = serializers.IntegerField()
    pending = serializers.IntegerField()
    confirmed = serializers.IntegerField()
    checked_in = serializers.IntegerField()
    queued = serializers.IntegerField()
    in_service = serializers.IntegerField()
    completed = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    no_show = serializers.IntegerField()
    rescheduled = serializers.IntegerField()
    appointments_by_status = serializers.ListField(child=serializers.DictField())
    appointments_by_specialty = serializers.ListField(child=serializers.DictField())
    appointments_by_hour = serializers.ListField(child=serializers.DictField())
    appointment_utilization_percentage = serializers.FloatField(allow_null=True)
    generated_at = serializers.DateTimeField()


class QueueDashboardOutputSerializer(serializers.Serializer):
    active_queues = serializers.IntegerField()
    waiting_patients = serializers.IntegerField()
    called_patients = serializers.IntegerField()
    in_service_patients = serializers.IntegerField()
    skipped_patients = serializers.IntegerField()
    completed_today = serializers.IntegerField()
    cancelled_today = serializers.IntegerField()
    transferred_today = serializers.IntegerField()
    average_wait_minutes = serializers.FloatField(allow_null=True)
    longest_wait_minutes = serializers.FloatField(allow_null=True)
    queues_by_service_point = serializers.ListField(child=serializers.DictField())
    next_entries_summary = serializers.ListField(child=serializers.DictField())
    generated_at = serializers.DateTimeField()


class CheckinDashboardOutputSerializer(serializers.Serializer):
    total_checkins = serializers.IntegerField()
    appointment_checkins = serializers.IntegerField()
    walkin_checkins = serializers.IntegerField()
    qr_checkins = serializers.IntegerField()
    reception_checkins = serializers.IntegerField()
    mobile_checkins = serializers.IntegerField()
    self_service_checkins = serializers.IntegerField()
    voided_checkins = serializers.IntegerField()
    checkins_by_hour = serializers.ListField(child=serializers.DictField())
    checkins_by_method = serializers.ListField(child=serializers.DictField())
    generated_at = serializers.DateTimeField()


class PractitionerDashboardOutputSerializer(serializers.Serializer):
    active_practitioners_today = serializers.IntegerField()
    practitioners_on_shift_now = serializers.IntegerField()
    scheduled_shifts = serializers.IntegerField()
    completed_shifts = serializers.IntegerField()
    cancelled_shifts = serializers.IntegerField()
    total_scheduled_hours = serializers.FloatField()
    completed_appointments_by_practitioner = serializers.ListField(child=serializers.DictField())
    average_service_time_by_practitioner = serializers.ListField(child=serializers.DictField())
    workload_summary = serializers.ListField(child=serializers.DictField())
    generated_at = serializers.DateTimeField()


class IntelligenceDashboardOutputSerializer(serializers.Serializer):
    predictions_generated = serializers.IntegerField()
    rule_based_predictions = serializers.IntegerField()
    machine_learning_predictions = serializers.IntegerField()
    average_predicted_wait_minutes = serializers.FloatField(allow_null=True)
    average_actual_wait_minutes = serializers.FloatField(allow_null=True)
    average_prediction_error_minutes = serializers.FloatField(allow_null=True)
    latest_predictions_summary = serializers.ListField(child=serializers.DictField())
    generated_at = serializers.DateTimeField()
