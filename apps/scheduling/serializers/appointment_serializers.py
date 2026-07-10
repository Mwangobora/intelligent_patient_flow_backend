from __future__ import annotations

from rest_framework import serializers

from apps.scheduling.models import Appointment, AppointmentStatusHistory


class AppointmentStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_email = serializers.CharField(source="changed_by.email", read_only=True)

    class Meta:
        model = AppointmentStatusHistory
        fields = [
            "id",
            "appointment",
            "from_status",
            "to_status",
            "change_source",
            "changed_by",
            "changed_by_email",
            "reason",
            "changed_at",
        ]
        read_only_fields = fields


class AppointmentDetailSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    specialty_name = serializers.CharField(source="facility_specialty.specialty.name", read_only=True)
    practitioner_number = serializers.CharField(source="practitioner_facility_assignment.practitioner.practitioner_number", read_only=True)
    slot_status = serializers.CharField(source="appointment_slot.status", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "facility",
            "facility_name",
            "patient",
            "facility_specialty",
            "specialty_name",
            "practitioner_facility_assignment",
            "practitioner_number",
            "practitioner_specialty_assignment",
            "practitioner_shift",
            "appointment_slot",
            "slot_status",
            "appointment_number",
            "scheduled_start",
            "scheduled_end",
            "status",
            "booking_channel",
            "rescheduled_from",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "created_by",
            "created_at",
            "updated_at",
        ]


class AppointmentCreateSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    patient_id = serializers.UUIDField()
    facility_specialty_id = serializers.UUIDField()
    practitioner_facility_assignment_id = serializers.UUIDField(required=False, allow_null=True)
    practitioner_specialty_assignment_id = serializers.UUIDField(required=False, allow_null=True)
    practitioner_shift_id = serializers.UUIDField(required=False, allow_null=True)
    appointment_slot_id = serializers.UUIDField(required=False, allow_null=True)
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    booking_channel = serializers.ChoiceField(choices=Appointment.BookingChannel.choices)
    reason_for_visit = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class AppointmentUpdateSerializer(serializers.Serializer):
    facility_specialty_id = serializers.UUIDField(required=False)
    scheduled_start = serializers.DateTimeField(required=False)
    scheduled_end = serializers.DateTimeField(required=False)
    booking_channel = serializers.ChoiceField(choices=Appointment.BookingChannel.choices, required=False)
    reason_for_visit = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class AppointmentCancellationSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField()


class AppointmentRescheduleSerializer(serializers.Serializer):
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    booking_channel = serializers.ChoiceField(choices=Appointment.BookingChannel.choices, required=False)
    practitioner_facility_assignment_id = serializers.UUIDField(required=False, allow_null=True)
    practitioner_specialty_assignment_id = serializers.UUIDField(required=False, allow_null=True)
    practitioner_shift_id = serializers.UUIDField(required=False, allow_null=True)
    appointment_slot_id = serializers.UUIDField(required=False, allow_null=True)
    reason_for_visit = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class AppointmentAssignPractitionerSerializer(serializers.Serializer):
    practitioner_facility_assignment_id = serializers.UUIDField()
    practitioner_specialty_assignment_id = serializers.UUIDField()
    practitioner_shift_id = serializers.UUIDField(required=False, allow_null=True)
    appointment_slot_id = serializers.UUIDField(required=False, allow_null=True)
