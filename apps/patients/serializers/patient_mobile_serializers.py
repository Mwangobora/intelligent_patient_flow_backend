from __future__ import annotations

from rest_framework import serializers

from apps.checkins.serializers import CheckinOutputSerializer
from apps.patients.models import Patient


class PatientMobileRegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    middle_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    last_name = serializers.CharField()
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    date_of_birth_is_estimated = serializers.BooleanField(required=False, default=False)
    sex_code = serializers.ChoiceField(choices=Patient.SexCode.choices, required=False, allow_null=True)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)


class PatientMobileUserSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField(allow_null=True)
    phone_number = serializers.CharField(allow_null=True)
    first_name = serializers.CharField()
    middle_name = serializers.CharField(allow_null=True)
    last_name = serializers.CharField()
    is_active = serializers.BooleanField()


class PatientMobileProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    patient_number = serializers.CharField()
    first_name = serializers.CharField()
    middle_name = serializers.CharField(allow_null=True)
    last_name = serializers.CharField()
    date_of_birth = serializers.DateField(allow_null=True)
    date_of_birth_is_estimated = serializers.BooleanField()
    sex_code = serializers.CharField(allow_null=True)
    email = serializers.EmailField(allow_null=True)
    phone_number = serializers.CharField(allow_null=True)
    organization = serializers.UUIDField()
    organization_name = serializers.CharField()
    registered_facility = serializers.UUIDField(allow_null=True)
    registered_facility_name = serializers.CharField(allow_null=True)
    is_active = serializers.BooleanField()


class PatientMobileRegistrationResponseSerializer(serializers.Serializer):
    user = PatientMobileUserSummarySerializer()
    patient = PatientMobileProfileSerializer()


class PatientMobileProfileUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class PatientMobileAppointmentCreateSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    facility_specialty_id = serializers.UUIDField()
    appointment_slot_id = serializers.UUIDField()
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    reason_for_visit = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PatientMobileAppointmentRescheduleSerializer(serializers.Serializer):
    appointment_slot_id = serializers.UUIDField()
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    reason_for_visit = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PatientMobileAppointmentCancelSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField()


class PatientMobileAppointmentSlotQuerySerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    facility_specialty_id = serializers.UUIDField()
    starts_from = serializers.DateTimeField()
    ends_to = serializers.DateTimeField()


class PatientCreateMobileAccountSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    temporary_password = serializers.CharField(required=False, allow_null=True, allow_blank=True, write_only=True)


class PatientMobileAccountCreatedSerializer(serializers.Serializer):
    user = PatientMobileUserSummarySerializer()
    patient = PatientMobileProfileSerializer()
    temporary_password = serializers.CharField()
    generated_password = serializers.BooleanField()


class PatientClaimExistingRecordSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    date_of_birth = serializers.DateField()
    patient_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    password = serializers.CharField(required=False, allow_null=True, allow_blank=True, write_only=True)
    password_confirm = serializers.CharField(required=False, allow_null=True, allow_blank=True, write_only=True)


class PatientClaimExistingRecordResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()
    user = PatientMobileUserSummarySerializer(required=False)
    patient = PatientMobileProfileSerializer(required=False)


class PatientAppointmentSummarySerializer(serializers.Serializer):
    appointment_id = serializers.UUIDField()
    appointment_number = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    facility = serializers.DictField()
    specialty = serializers.DictField(allow_null=True)
    department = serializers.DictField(allow_null=True)


class PatientCheckinEligibilityQuerySerializer(serializers.Serializer):
    appointment_id = serializers.UUIDField()


class PatientCheckinEligibilitySerializer(serializers.Serializer):
    appointment_id = serializers.UUIDField()
    can_check_in = serializers.BooleanField()
    reason = serializers.CharField(allow_null=True)
    appointment_status = serializers.CharField()
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    facility = serializers.DictField()
    specialty = serializers.DictField(allow_null=True)
    department = serializers.DictField(allow_null=True)
    existing_checkin = serializers.DictField(allow_null=True)
    has_active_token = serializers.BooleanField()
    token_expires_at = serializers.DateTimeField(allow_null=True)


class PatientAppointmentCheckinResponseSerializer(serializers.Serializer):
    checkin = serializers.DictField()
    queue_entry = serializers.DictField(allow_null=True)
    message = serializers.CharField()


class PatientQrTokenIssueResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    appointment_id = serializers.UUIDField()
    raw_token = serializers.CharField()
    expires_at = serializers.DateTimeField()


class PatientQrConsumeInputSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True, trim_whitespace=True)


class PatientQueueCurrentSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField(allow_null=True)
    queue_number = serializers.CharField(allow_null=True)
    queue_name = serializers.CharField(allow_null=True)
    service_point = serializers.DictField(allow_null=True)
    facility = serializers.DictField(allow_null=True)
    status = serializers.CharField(allow_null=True)
    priority_label = serializers.CharField(allow_null=True)
    estimated_wait_minutes = serializers.IntegerField(allow_null=True)
    people_ahead = serializers.IntegerField(allow_null=True)
    joined_at = serializers.DateTimeField(allow_null=True)
    called_at = serializers.DateTimeField(allow_null=True)
    service_started_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    last_updated_at = serializers.DateTimeField()


class PatientQueueHistorySerializer(PatientQueueCurrentSerializer):
    cancelled_at = serializers.DateTimeField(allow_null=True)


class PatientQueueHistoryResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    results = PatientQueueHistorySerializer(many=True)
