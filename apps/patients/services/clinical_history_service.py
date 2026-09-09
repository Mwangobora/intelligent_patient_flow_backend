from __future__ import annotations

from django.utils import timezone

from apps.patients.models import Patient, PatientAllergy, PatientCondition
from apps.scheduling.services._crypto import encrypt_sensitive_value
from common.exceptions import NotFoundError


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _encrypt_optional(value: str | None) -> str | None:
    cleaned = _optional_text(value)
    return encrypt_sensitive_value(cleaned) if cleaned else None


def _get_patient(patient_id) -> Patient:
    patient = Patient.objects.filter(pk=patient_id, is_active=True).first()
    if patient is None:
        raise NotFoundError("Patient not found.")
    return patient


def create_patient_allergy(*, patient_id, recorded_by_id=None, **data) -> PatientAllergy:
    patient = _get_patient(patient_id)
    return PatientAllergy.objects.create(
        patient=patient,
        recorded_by_id=recorded_by_id,
        recorded_at=data.pop("recorded_at", None) or timezone.now(),
        allergen=data.pop("allergen").strip(),
        allergy_type=_optional_text(data.pop("allergy_type", None)),
        reaction=_optional_text(data.pop("reaction", None)),
        severity=_optional_text(data.pop("severity", None)),
        **data,
    )


def update_patient_allergy(*, allergy_id, **updates) -> PatientAllergy:
    allergy = PatientAllergy.objects.filter(pk=allergy_id).first()
    if allergy is None:
        raise NotFoundError("Patient allergy not found.")
    if "patient_id" in updates:
        allergy.patient = _get_patient(updates.pop("patient_id"))
    for field in ["allergen", "allergy_type", "reaction", "severity"]:
        if field in updates:
            setattr(allergy, field, _optional_text(updates.pop(field)))
    for field, value in updates.items():
        setattr(allergy, field, value)
    allergy.save()
    return allergy


def create_patient_condition(*, patient_id, recorded_by_id=None, **data) -> PatientCondition:
    patient = _get_patient(patient_id)
    return PatientCondition.objects.create(
        patient=patient,
        recorded_by_id=recorded_by_id,
        condition_name=data.pop("condition_name").strip(),
        notes_encrypted=_encrypt_optional(data.pop("notes", None)),
        **data,
    )


def update_patient_condition(*, condition_id, **updates) -> PatientCondition:
    condition = PatientCondition.objects.filter(pk=condition_id).first()
    if condition is None:
        raise NotFoundError("Patient condition not found.")
    if "patient_id" in updates:
        condition.patient = _get_patient(updates.pop("patient_id"))
    if "condition_name" in updates:
        condition.condition_name = updates.pop("condition_name").strip()
    if "notes" in updates:
        condition.notes_encrypted = _encrypt_optional(updates.pop("notes"))
    for field, value in updates.items():
        setattr(condition, field, value)
    condition.save()
    return condition
