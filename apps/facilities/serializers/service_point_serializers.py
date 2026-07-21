from __future__ import annotations

from rest_framework import serializers

from apps.facilities.models import ConsultationRoom, ServicePoint, ServicePointType


class ServicePointTypeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePointType
        fields = ["id", "name", "code", "description", "is_active"]


class ServicePointTypeDetailSerializer(ServicePointTypeListSerializer):
    class Meta(ServicePointTypeListSerializer.Meta):
        fields = ServicePointTypeListSerializer.Meta.fields + ["created_at", "updated_at"]


class ServicePointTypeCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ServicePointTypeUpdateSerializer(ServicePointTypeCreateSerializer):
    name = serializers.CharField(required=False)


class ServicePointDetailSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    service_point_type_name = serializers.CharField(source="service_point_type.name", read_only=True)

    class Meta:
        model = ServicePoint
        fields = [
            "id",
            "facility",
            "facility_name",
            "department",
            "department_name",
            "service_point_type",
            "service_point_type_name",
            "name",
            "code",
            "location_description",
            "floor",
            "display_order",
            "is_active",
            "created_at",
            "updated_at",
        ]


class ServicePointCreateSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    department_id = serializers.UUIDField(required=False, allow_null=True)
    service_point_type_id = serializers.UUIDField()
    name = serializers.CharField()
    location_description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    floor = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    display_order = serializers.IntegerField(required=False, default=0)


class ServicePointUpdateSerializer(ServicePointCreateSerializer):
    facility_id = serializers.UUIDField(required=False)
    service_point_type_id = serializers.UUIDField(required=False)
    name = serializers.CharField(required=False)


class ConsultationRoomDetailSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = ConsultationRoom
        fields = [
            "id",
            "facility",
            "facility_name",
            "department",
            "department_name",
            "name",
            "code",
            "location_description",
            "floor",
            "capacity",
            "is_active",
            "created_at",
            "updated_at",
        ]


class ConsultationRoomCreateSerializer(serializers.Serializer):
    facility_id = serializers.UUIDField()
    department_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField()
    location_description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    floor = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    capacity = serializers.IntegerField(required=False, default=1)


class ConsultationRoomUpdateSerializer(ConsultationRoomCreateSerializer):
    facility_id = serializers.UUIDField(required=False)
    name = serializers.CharField(required=False)
