from __future__ import annotations

from rest_framework import serializers

from apps.checkins.models import PatientCheckin


class AppointmentCheckinInputSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    patient_id = serializers.UUIDField()
    appointment_id = serializers.UUIDField()
    facility_specialty_id = serializers.UUIDField(required=False, allow_null=True)
    checkin_method = serializers.ChoiceField(choices=PatientCheckin.CheckinMethod.choices)
    checked_in_at = serializers.DateTimeField(required=False, allow_null=True)
    checked_in_by_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=250)


class WalkinCheckinInputSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    patient_id = serializers.UUIDField()
    facility_specialty_id = serializers.UUIDField()
    checkin_method = serializers.ChoiceField(choices=PatientCheckin.CheckinMethod.choices)
    checked_in_at = serializers.DateTimeField(required=False, allow_null=True)
    checked_in_by_id = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=250)


class VoidCheckinInputSerializer(serializers.Serializer):
    void_reason = serializers.CharField(max_length=250)
    voided_at = serializers.DateTimeField(required=False, allow_null=True)


class CheckinOutputSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)
    patient_name = serializers.SerializerMethodField()
    appointment_number = serializers.CharField(source="appointment.appointment_number", read_only=True)
    specialty_name = serializers.CharField(source="facility_specialty.specialty.name", read_only=True)
    checked_in_by_email = serializers.CharField(source="checked_in_by.email", read_only=True)
    voided_by_email = serializers.CharField(source="voided_by.email", read_only=True)

    class Meta:
        model = PatientCheckin
        fields = [
            "id",
            "facility",
            "facility_name",
            "patient",
            "patient_number",
            "patient_name",
            "appointment",
            "appointment_number",
            "facility_specialty",
            "specialty_name",
            "checkin_method",
            "checked_in_at",
            "checked_in_by",
            "checked_in_by_email",
            "notes",
            "voided_at",
            "voided_by",
            "voided_by_email",
            "void_reason",
            "created_at",
            "updated_at",
        ]

    def get_patient_name(self, obj):
        return " ".join(part for part in [obj.patient.first_name, obj.patient.last_name] if part)
