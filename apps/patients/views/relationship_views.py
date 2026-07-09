from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.patients._helpers import translate_domain_error
from apps.patients.models import PatientRelatedPerson, RelatedPersonContact, RelationshipType
from apps.patients.selectors import (
    get_patient_by_id,
    get_related_person_by_id,
    get_related_person_contact_by_id,
    get_relationship_type_by_id,
    list_related_person_contacts,
    list_related_persons,
    list_relationship_types,
)
from apps.patients.serializers import (
    PatientRelatedPersonCreateSerializer,
    PatientRelatedPersonDetailSerializer,
    PatientRelatedPersonUpdateSerializer,
    RelatedPersonContactCreateSerializer,
    RelatedPersonContactDetailSerializer,
    RelationshipTypeCreateSerializer,
    RelationshipTypeDetailSerializer,
    RelationshipTypeListSerializer,
    RelationshipTypeUpdateSerializer,
)
from apps.patients.services import (
    add_related_person,
    add_related_person_contact,
    create_relationship_type,
    deactivate_related_person,
    deactivate_related_person_contact,
    deactivate_relationship_type,
    set_primary_related_person_contact,
    update_related_person,
    update_relationship_type,
    verify_related_person_contact,
)

from .base import PATIENT_DOCS_TAG, PatientsBaseViewSet, _bool_query_param


@extend_schema(tags=[PATIENT_DOCS_TAG])
class RelationshipTypeViewSet(PatientsBaseViewSet):
    queryset = RelationshipType.objects.all()
    serializer_class = RelationshipTypeDetailSerializer
    permission_map = {action: "patients_relationship_type.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {
            "list": RelationshipTypeListSerializer,
            "retrieve": RelationshipTypeDetailSerializer,
            "create": RelationshipTypeCreateSerializer,
            "partial_update": RelationshipTypeUpdateSerializer,
        }.get(self.action, RelationshipTypeDetailSerializer)

    def list(self, request):
        queryset = list_relationship_types(
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(RelationshipTypeListSerializer(queryset, many=True).data)

    def create(self, request):
        serializer = RelationshipTypeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            relationship_type = create_relationship_type(**serializer.validated_data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(RelationshipTypeDetailSerializer(relationship_type).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        relationship_type = get_relationship_type_by_id(pk)
        if relationship_type is None:
            return Response({"detail": "Relationship type not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(RelationshipTypeDetailSerializer(relationship_type).data)

    def partial_update(self, request, pk=None):
        serializer = RelationshipTypeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        regenerate_code = data.pop("regenerate_code", False)
        try:
            relationship_type = update_relationship_type(
                relationship_type_id=pk,
                regenerate_code=regenerate_code,
                **data,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(RelationshipTypeDetailSerializer(relationship_type).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            relationship_type = deactivate_relationship_type(relationship_type_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(RelationshipTypeDetailSerializer(relationship_type).data)


@extend_schema(tags=[PATIENT_DOCS_TAG])
class PatientRelatedPersonViewSet(PatientsBaseViewSet):
    queryset = PatientRelatedPerson.objects.all()
    serializer_class = PatientRelatedPersonDetailSerializer
    permission_map = {action: "patients_related_person.manage" for action in ["list", "retrieve", "create", "partial_update", "deactivate"]}

    def get_serializer_class(self):
        return {
            "create": PatientRelatedPersonCreateSerializer,
            "partial_update": PatientRelatedPersonUpdateSerializer,
        }.get(self.action, PatientRelatedPersonDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            patient = get_patient_by_id(self.kwargs.get("patient_pk") or request.data.get("patient_id"))
            if patient is None:
                return None, None
            return patient.organization_id, patient.registered_facility_id
        if self.action in {"retrieve", "partial_update", "deactivate"}:
            related_person = get_related_person_by_id(self.kwargs.get("pk"))
            if related_person is None:
                return None, None
            return related_person.patient.organization_id, related_person.patient.registered_facility_id
        patient = get_patient_by_id(self.kwargs.get("patient_pk") or request.query_params.get("patient_id"))
        if patient is not None:
            return patient.organization_id, patient.registered_facility_id
        return request.query_params.get("organization_id"), request.query_params.get("registered_facility_id")

    def list(self, request, patient_pk=None):
        queryset = list_related_persons(
            patient_id=patient_pk or request.query_params.get("patient_id"),
            linked_user_id=request.query_params.get("linked_user_id"),
            organization_id=request.query_params.get("organization_id"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
            search=request.query_params.get("search"),
        )
        return Response(PatientRelatedPersonDetailSerializer(queryset, many=True).data)

    def create(self, request, patient_pk=None):
        serializer = PatientRelatedPersonCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        patient_id = patient_pk or data.pop("patient_id", None)
        if patient_id is None:
            return Response({"detail": "patient_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            related_person = add_related_person(patient_id=patient_id, **data, created_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientRelatedPersonDetailSerializer(related_person).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        related_person = get_related_person_by_id(pk)
        if related_person is None:
            return Response({"detail": "Patient related person not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PatientRelatedPersonDetailSerializer(related_person).data)

    def partial_update(self, request, pk=None):
        serializer = PatientRelatedPersonUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            related_person = update_related_person(related_person_id=pk, **serializer.validated_data)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientRelatedPersonDetailSerializer(related_person).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            related_person = deactivate_related_person(related_person_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(PatientRelatedPersonDetailSerializer(related_person).data)


@extend_schema(tags=[PATIENT_DOCS_TAG])
class RelatedPersonContactViewSet(PatientsBaseViewSet):
    queryset = RelatedPersonContact.objects.all()
    serializer_class = RelatedPersonContactDetailSerializer
    permission_map = {action: "patients_related_person_contact.manage" for action in ["list", "retrieve", "create", "verify", "set_primary", "deactivate"]}

    def get_serializer_class(self):
        return {"create": RelatedPersonContactCreateSerializer}.get(self.action, RelatedPersonContactDetailSerializer)

    def get_permission_scope(self, request):
        if self.action == "create":
            related_person = get_related_person_by_id(self.kwargs.get("related_person_pk") or request.data.get("related_person_id"))
            if related_person is None:
                return None, None
            return related_person.patient.organization_id, related_person.patient.registered_facility_id
        if self.action in {"retrieve", "verify", "set_primary", "deactivate"}:
            contact = get_related_person_contact_by_id(self.kwargs.get("pk"))
            if contact is None:
                return None, None
            return contact.related_person.patient.organization_id, contact.related_person.patient.registered_facility_id
        related_person = get_related_person_by_id(self.kwargs.get("related_person_pk") or request.query_params.get("related_person_id"))
        if related_person is not None:
            return related_person.patient.organization_id, related_person.patient.registered_facility_id
        return request.query_params.get("organization_id"), request.query_params.get("registered_facility_id")

    def list(self, request, related_person_pk=None):
        queryset = list_related_person_contacts(
            related_person_id=related_person_pk or request.query_params.get("related_person_id"),
            patient_id=request.query_params.get("patient_id"),
            channel=request.query_params.get("channel"),
            is_active=_bool_query_param(request.query_params.get("is_active")),
        )
        return Response(RelatedPersonContactDetailSerializer(queryset, many=True).data)

    def create(self, request, related_person_pk=None):
        serializer = RelatedPersonContactCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        related_person_id = related_person_pk or data.pop("related_person_id", None)
        if related_person_id is None:
            return Response({"detail": "related_person_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            contact = add_related_person_contact(
                related_person_id=related_person_id,
                **data,
                created_by_id=request.user.id,
            )
        except Exception as exc:
            translate_domain_error(exc)
        return Response(RelatedPersonContactDetailSerializer(contact).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        contact = get_related_person_contact_by_id(pk)
        if contact is None:
            return Response({"detail": "Related person contact not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(RelatedPersonContactDetailSerializer(contact).data)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        try:
            contact = verify_related_person_contact(contact_id=pk, verified_by_id=request.user.id)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(RelatedPersonContactDetailSerializer(contact).data)

    @action(detail=True, methods=["post"], url_path="set-primary")
    def set_primary(self, request, pk=None):
        try:
            contact = set_primary_related_person_contact(contact_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(RelatedPersonContactDetailSerializer(contact).data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        try:
            contact = deactivate_related_person_contact(contact_id=pk)
        except Exception as exc:
            translate_domain_error(exc)
        return Response(RelatedPersonContactDetailSerializer(contact).data)
