from __future__ import annotations

from rest_framework import serializers

from apps.facilities.models import Facility, FacilityType, Organization


class OrganizationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "legal_name", "code", "email", "phone_number", "registration_number", "is_active"]


class OrganizationDetailSerializer(OrganizationListSerializer):
    class Meta(OrganizationListSerializer.Meta):
        fields = OrganizationListSerializer.Meta.fields + ["created_at", "updated_at"]


class OrganizationCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    legal_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    registration_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class OrganizationUpdateSerializer(OrganizationCreateSerializer):
    name = serializers.CharField(required=False)


class FacilityTypeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacilityType
        fields = ["id", "name", "code", "description", "is_active"]


class FacilityTypeDetailSerializer(FacilityTypeListSerializer):
    class Meta(FacilityTypeListSerializer.Meta):
        fields = FacilityTypeListSerializer.Meta.fields + ["created_at", "updated_at"]


class FacilityTypeCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class FacilityTypeUpdateSerializer(FacilityTypeCreateSerializer):
    name = serializers.CharField(required=False)


class FacilityListSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    facility_type_name = serializers.CharField(source="facility_type.name", read_only=True)

    class Meta:
        model = Facility
        fields = [
            "id",
            "organization",
            "organization_name",
            "facility_type",
            "facility_type_name",
            "name",
            "code",
            "timezone",
            "is_primary",
            "is_active",
        ]


class FacilityDetailSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    facility_type_name = serializers.CharField(source="facility_type.name", read_only=True)

    class Meta:
        model = Facility
        fields = [
            "id",
            "organization",
            "organization_name",
            "facility_type",
            "facility_type_name",
            "name",
            "code",
            "license_number",
            "email",
            "phone_number",
            "address_line1",
            "address_line2",
            "country_code",
            "region",
            "district",
            "ward",
            "postal_code",
            "latitude",
            "longitude",
            "timezone",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]


class FacilityCreateSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField()
    facility_type_id = serializers.UUIDField()
    name = serializers.CharField()
    license_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address_line1 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address_line2 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    country_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    region = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    district = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ward = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    postal_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    latitude = serializers.DecimalField(required=False, allow_null=True, max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(required=False, allow_null=True, max_digits=10, decimal_places=7)
    timezone = serializers.CharField(required=False, default="Africa/Dar_es_Salaam")
    is_primary = serializers.BooleanField(required=False, default=False)


class FacilityUpdateSerializer(FacilityCreateSerializer):
    organization_id = serializers.UUIDField(required=False)
    facility_type_id = serializers.UUIDField(required=False)
    name = serializers.CharField(required=False)
