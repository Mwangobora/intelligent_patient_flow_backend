from __future__ import annotations

from rest_framework import serializers

from apps.patients.models import PatientRelatedPerson, RelatedPersonContact, RelationshipType


class RelationshipTypeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = RelationshipType
        fields = ["id", "name", "code", "description", "is_active"]


class RelationshipTypeDetailSerializer(RelationshipTypeListSerializer):
    class Meta(RelationshipTypeListSerializer.Meta):
        fields = RelationshipTypeListSerializer.Meta.fields + ["created_at", "updated_at"]


class RelationshipTypeCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class RelationshipTypeUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class PatientRelatedPersonDetailSerializer(serializers.ModelSerializer):
    patient_number = serializers.CharField(source="patient.patient_number", read_only=True)
    relationship_type_name = serializers.CharField(source="relationship_type.name", read_only=True)
    linked_user_email = serializers.CharField(source="linked_user.email", read_only=True)

    class Meta:
        model = PatientRelatedPerson
        fields = [
            "id",
            "patient",
            "patient_number",
            "relationship_type",
            "relationship_type_name",
            "linked_user",
            "linked_user_email",
            "first_name",
            "middle_name",
            "last_name",
            "is_guardian",
            "is_caregiver",
            "is_next_of_kin",
            "is_emergency_contact",
            "priority_order",
            "is_active",
            "created_at",
            "updated_at",
        ]


class PatientRelatedPersonCreateSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField(required=False)
    relationship_type_id = serializers.UUIDField()
    linked_user_id = serializers.UUIDField(required=False, allow_null=True)
    first_name = serializers.CharField()
    middle_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    last_name = serializers.CharField()
    is_guardian = serializers.BooleanField(required=False, default=False)
    is_caregiver = serializers.BooleanField(required=False, default=False)
    is_next_of_kin = serializers.BooleanField(required=False, default=False)
    is_emergency_contact = serializers.BooleanField(required=False, default=False)
    priority_order = serializers.IntegerField(required=False, default=1)


class PatientRelatedPersonUpdateSerializer(serializers.Serializer):
    relationship_type_id = serializers.UUIDField(required=False)
    linked_user_id = serializers.UUIDField(required=False, allow_null=True)
    first_name = serializers.CharField(required=False)
    middle_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    last_name = serializers.CharField(required=False)
    is_guardian = serializers.BooleanField(required=False)
    is_caregiver = serializers.BooleanField(required=False)
    is_next_of_kin = serializers.BooleanField(required=False)
    is_emergency_contact = serializers.BooleanField(required=False)
    priority_order = serializers.IntegerField(required=False)


class RelatedPersonContactDetailSerializer(serializers.ModelSerializer):
    related_person_name = serializers.SerializerMethodField()
    verified_by_email = serializers.CharField(source="verified_by.email", read_only=True)
    value_present = serializers.SerializerMethodField()

    class Meta:
        model = RelatedPersonContact
        fields = [
            "id",
            "related_person",
            "related_person_name",
            "channel",
            "label",
            "value_present",
            "verified_at",
            "verified_by",
            "verified_by_email",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_related_person_name(self, obj) -> str:
        names = [obj.related_person.first_name, obj.related_person.middle_name, obj.related_person.last_name]
        return " ".join(name for name in names if name).strip()

    def get_value_present(self, obj) -> bool:
        return bool(obj.value_encrypted)


class RelatedPersonContactCreateSerializer(serializers.Serializer):
    related_person_id = serializers.UUIDField(required=False)
    channel = serializers.ChoiceField(choices=RelatedPersonContact.Channel.choices)
    value = serializers.CharField()
    label = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    is_primary = serializers.BooleanField(required=False, default=False)
