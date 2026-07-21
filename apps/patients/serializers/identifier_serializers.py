from __future__ import annotations

from rest_framework import serializers

from apps.patients.models import PatientAddress, PatientIdentifier, PatientIdentifierType


class PatientIdentifierTypeListSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = PatientIdentifierType
        fields = [
            "id",
            "organization",
            "organization_name",
            "name",
            "code",
            "description",
            "is_sensitive",
            "is_active",
        ]


class PatientIdentifierTypeDetailSerializer(PatientIdentifierTypeListSerializer):
    class Meta(PatientIdentifierTypeListSerializer.Meta):
        fields = PatientIdentifierTypeListSerializer.Meta.fields + ["created_at", "updated_at"]


class PatientIdentifierTypeCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    is_sensitive = serializers.BooleanField(required=False, default=True)


class PatientIdentifierTypeUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    is_sensitive = serializers.BooleanField(required=False)


class PatientIdentifierDetailSerializer(serializers.ModelSerializer):
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)
    identifier_type_name = serializers.CharField(source="identifier_type.name", read_only=True)
    verified_by_email = serializers.CharField(source="verified_by.email", read_only=True)

    class Meta:
        model = PatientIdentifier
        fields = [
            "id",
            "patient",
            "patient_number",
            "identifier_type",
            "identifier_type_name",
            "last_four",
            "issuing_country_code",
            "issuing_authority",
            "issued_on",
            "expires_on",
            "verified_at",
            "verified_by",
            "verified_by_email",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]


class PatientIdentifierCreateSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField(required=False)
    identifier_type_id = serializers.UUIDField()
    value = serializers.CharField()
    issuing_country_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    issuing_authority = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    issued_on = serializers.DateField(required=False, allow_null=True)
    expires_on = serializers.DateField(required=False, allow_null=True)
    is_primary = serializers.BooleanField(required=False, default=False)


class PatientAddressDetailSerializer(serializers.ModelSerializer):
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)
    has_address_line1 = serializers.SerializerMethodField()
    has_address_line2 = serializers.SerializerMethodField()

    class Meta:
        model = PatientAddress
        fields = [
            "id",
            "patient",
            "patient_number",
            "label",
            "has_address_line1",
            "has_address_line2",
            "country_code",
            "region",
            "district",
            "ward",
            "postal_code",
            "latitude",
            "longitude",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_has_address_line1(self, obj) -> bool:
        return bool(obj.address_line1_encrypted)

    def get_has_address_line2(self, obj) -> bool:
        return bool(obj.address_line2_encrypted)


class PatientAddressCreateSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField(required=False)
    label = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address_line1 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address_line2 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    region = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    district = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ward = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    postal_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    latitude = serializers.DecimalField(required=False, allow_null=True, max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(required=False, allow_null=True, max_digits=10, decimal_places=7)
    is_primary = serializers.BooleanField(required=False, default=False)


class PatientAddressUpdateSerializer(serializers.Serializer):
    label = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address_line1 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address_line2 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    region = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    district = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ward = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    postal_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    latitude = serializers.DecimalField(required=False, allow_null=True, max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(required=False, allow_null=True, max_digits=10, decimal_places=7)
