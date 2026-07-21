from __future__ import annotations

from dataclasses import dataclass
import re

from django.apps import apps
from django.db import IntegrityError, models, transaction

from common.exceptions import ValidationError

UNSUPPORTED_CODE_CHARS_RE = re.compile(r"[^A-Z0-9_]+")
SEPARATOR_RE = re.compile(r"[\s\-]+")
UNDERSCORE_RE = re.compile(r"_+")


@dataclass(frozen=True)
class CodeSequenceDefinition:
    key: str
    prefix: str
    model_label: str
    field_name: str = "code"
    padding: int = 4


CODE_SEQUENCE_DEFINITIONS: dict[str, CodeSequenceDefinition] = {
    "organization": CodeSequenceDefinition("organization", "ORG", "facilities.Organization"),
    "facility_type": CodeSequenceDefinition("facility_type", "FTY", "facilities.FacilityType"),
    "facility": CodeSequenceDefinition("facility", "FAC", "facilities.Facility"),
    "department": CodeSequenceDefinition("department", "DEP", "facilities.Department"),
    "specialty": CodeSequenceDefinition("specialty", "SPC", "facilities.Specialty"),
    "service_point_type": CodeSequenceDefinition("service_point_type", "SPT", "facilities.ServicePointType"),
    "service_point": CodeSequenceDefinition("service_point", "SVP", "facilities.ServicePoint"),
    "consultation_room": CodeSequenceDefinition("consultation_room", "ROOM", "facilities.ConsultationRoom"),
    "role": CodeSequenceDefinition("role", "ROLE", "accounts.Role"),
    "patient_identifier_type": CodeSequenceDefinition("patient_identifier_type", "PIT", "patients.PatientIdentifierType"),
    "relationship_type": CodeSequenceDefinition("relationship_type", "REL", "patients.RelationshipType"),
    "practitioner_type": CodeSequenceDefinition("practitioner_type", "PRT", "practitioners.PractitionerType"),
    "practitioner_credential_type": CodeSequenceDefinition(
        "practitioner_credential_type",
        "PCT",
        "practitioners.PractitionerCredentialType",
    ),
}


def normalize_code_value(value: str) -> str:
    normalized = SEPARATOR_RE.sub("_", value.strip().upper())
    normalized = UNSUPPORTED_CODE_CHARS_RE.sub("", normalized)
    return UNDERSCORE_RE.sub("_", normalized).strip("_")


def _get_sequence_model() -> type[models.Model]:
    return apps.get_model("accounts", "CodeSequence")


def _get_model(model_label: str) -> type[models.Model]:
    app_label, model_name = model_label.split(".", 1)
    return apps.get_model(app_label, model_name)


def _extract_sequence_number(*, code: str, prefix: str) -> int | None:
    suffix = code.removeprefix(prefix)
    if not suffix.isdigit():
        return None
    return int(suffix)


def _existing_max_number(*, model: type[models.Model], field_name: str, prefix: str) -> int:
    max_number = 0
    lookup = {f"{field_name}__startswith": prefix}
    for code in model._default_manager.filter(**lookup).values_list(field_name, flat=True):
        number = _extract_sequence_number(code=code or "", prefix=prefix)
        if number is not None:
            max_number = max(max_number, number)
    return max_number


def _get_or_create_locked_sequence(*, definition: CodeSequenceDefinition):
    CodeSequence = _get_sequence_model()
    try:
        return CodeSequence.objects.select_for_update().get(key=definition.key)
    except CodeSequence.DoesNotExist:
        try:
            return CodeSequence.objects.create(
                key=definition.key,
                prefix=definition.prefix,
                padding=definition.padding,
                last_number=0,
            )
        except IntegrityError:
            return CodeSequence.objects.select_for_update().get(key=definition.key)


def generate_code_for_sequence(*, definition: CodeSequenceDefinition) -> str:
    model = _get_model(definition.model_label)
    max_length = model._meta.get_field(definition.field_name).max_length
    if len(definition.prefix) + definition.padding > max_length:
        raise ValidationError("Configured generated code does not fit the model field length.")

    with transaction.atomic():
        sequence = _get_or_create_locked_sequence(definition=definition)
        if sequence.prefix != definition.prefix or sequence.padding != definition.padding:
            sequence.prefix = definition.prefix
            sequence.padding = definition.padding

        existing_max = _existing_max_number(
            model=model,
            field_name=definition.field_name,
            prefix=definition.prefix,
        )
        if sequence.last_number < existing_max:
            sequence.last_number = existing_max

        while True:
            sequence.last_number += 1
            candidate = f"{definition.prefix}{sequence.last_number:0{definition.padding}d}"
            if len(candidate) > max_length:
                raise ValidationError("Generated code exceeded the model field length.")
            if not model._default_manager.filter(**{definition.field_name: candidate}).exists():
                sequence.save(update_fields=["prefix", "padding", "last_number", "updated_at"])
                return candidate


def generate_code(key: str) -> str:
    try:
        definition = CODE_SEQUENCE_DEFINITIONS[key]
    except KeyError as exc:
        raise ValidationError(f"No code sequence is configured for '{key}'.") from exc
    return generate_code_for_sequence(definition=definition)


def generate_code_for_model(*, model: type[models.Model], field_name: str = "code") -> str:
    model_label = f"{model._meta.app_label}.{model.__name__}"
    for definition in CODE_SEQUENCE_DEFINITIONS.values():
        if definition.model_label == model_label and definition.field_name == field_name:
            return generate_code_for_sequence(definition=definition)
    raise ValidationError(f"No code sequence is configured for {model_label}.{field_name}.")
