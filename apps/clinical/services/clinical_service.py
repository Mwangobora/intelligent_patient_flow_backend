from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.checkins.models import PatientCheckin
from apps.clinical.models import (
    ClinicalNote,
    DiagnosisCode,
    Encounter,
    EncounterDiagnosis,
    EncounterStatusHistory,
    TriageAssessment,
    VitalSign,
)
from apps.facilities.models import Department, FacilitySpecialty
from apps.practitioners.models import PractitionerFacilityAssignment
from apps.scheduling.models import Appointment
from apps.scheduling.services._crypto import encrypt_sensitive_value
from common.exceptions import ConflictError, NotFoundError, ValidationError


TERMINAL_ENCOUNTER_STATUSES = {Encounter.Status.COMPLETED, Encounter.Status.CANCELLED}


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _encrypt_optional(value: str | None) -> str | None:
    cleaned = _optional_text(value)
    return encrypt_sensitive_value(cleaned) if cleaned else None


def _get_checkin(checkin_id, *, for_update=False) -> PatientCheckin:
    queryset = PatientCheckin.objects.select_related(
        "facility", "patient", "appointment", "facility_specialty", "facility_specialty__department"
    )
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    checkin = queryset.filter(pk=checkin_id, voided_at__isnull=True).first()
    if checkin is None:
        raise NotFoundError("Active check-in not found.")
    return checkin


def _get_encounter(encounter_id, *, for_update=False) -> Encounter:
    queryset = Encounter.objects.select_related(
        "facility", "patient", "patient_checkin", "facility_specialty", "department"
    )
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    encounter = queryset.filter(pk=encounter_id).first()
    if encounter is None:
        raise NotFoundError("Encounter not found.")
    return encounter


def _get_practitioner_assignment(
    assignment_id, *, required=False
) -> PractitionerFacilityAssignment | None:
    if assignment_id is None:
        if required:
            raise ValidationError("Practitioner assignment is required.")
        return None
    assignment = (
        PractitionerFacilityAssignment.objects.select_related("facility", "practitioner")
        .filter(pk=assignment_id, is_active=True)
        .first()
    )
    if assignment is None:
        raise NotFoundError("Active practitioner facility assignment not found.")
    return assignment


def _validate_facility_specialty(
    *, facility_specialty: FacilitySpecialty | None, encounter: Encounter
) -> None:
    if facility_specialty is not None and facility_specialty.facility_id != encounter.facility_id:
        raise ValidationError("Facility specialty must belong to the encounter facility.")


def _validate_department(*, department: Department | None, encounter: Encounter) -> None:
    if department is not None and department.facility_id != encounter.facility_id:
        raise ValidationError("Department must belong to the encounter facility.")


def _validate_practitioner_assignment(
    *, assignment: PractitionerFacilityAssignment | None, encounter: Encounter
) -> None:
    if assignment is not None and assignment.facility_id != encounter.facility_id:
        raise ValidationError("Practitioner assignment must belong to the encounter facility.")


def _next_encounter_number(*, checkin: PatientCheckin, opened_at) -> str:
    prefix = f"ENC-{opened_at:%Y%m%d}-"
    latest = (
        Encounter.objects.select_for_update()
        .filter(facility_id=checkin.facility_id, encounter_number__startswith=prefix)
        .order_by("-encounter_number")
        .values_list("encounter_number", flat=True)
        .first()
    )
    next_number = int(latest.rsplit("-", 1)[-1]) + 1 if latest else 1
    return f"{prefix}{next_number:04d}"


def _record_status_history(
    *,
    encounter: Encounter,
    from_status,
    to_status,
    change_source,
    changed_by_id=None,
    reason=None,
    changed_at=None,
):
    return EncounterStatusHistory.objects.create(
        encounter=encounter,
        from_status=from_status,
        to_status=to_status,
        change_source=change_source,
        changed_by_id=changed_by_id,
        reason=_optional_text(reason),
        changed_at=changed_at or timezone.now(),
    )


@transaction.atomic
def create_encounter(
    *,
    patient_checkin_id,
    encounter_type,
    department_id=None,
    facility_specialty_id=None,
    attending_practitioner_facility_assignment_id=None,
    opened_at=None,
    opened_by_id=None,
) -> Encounter:
    checkin = _get_checkin(patient_checkin_id, for_update=True)
    if (
        Encounter.objects.select_for_update()
        .filter(patient_checkin=checkin)
        .exclude(status__in=TERMINAL_ENCOUNTER_STATUSES)
        .exists()
    ):
        raise ConflictError("Check-in already has an active encounter.")

    open_time = opened_at or timezone.now()
    appointment = checkin.appointment
    facility_specialty_id = (
        facility_specialty_id
        or checkin.facility_specialty_id
        or getattr(appointment, "facility_specialty_id", None)
    )
    department_id = department_id or getattr(checkin.facility_specialty, "department_id", None)
    facility_specialty = (
        FacilitySpecialty.objects.filter(pk=facility_specialty_id).first()
        if facility_specialty_id
        else None
    )
    department = Department.objects.filter(pk=department_id).first() if department_id else None
    assignment = _get_practitioner_assignment(attending_practitioner_facility_assignment_id)

    encounter = Encounter(
        facility=checkin.facility,
        patient=checkin.patient,
        patient_checkin=checkin,
        appointment=appointment,
        department=department,
        facility_specialty=facility_specialty,
        attending_practitioner_facility_assignment=assignment,
        encounter_number=_next_encounter_number(checkin=checkin, opened_at=open_time),
        encounter_type=encounter_type,
        opened_at=open_time,
        opened_by_id=opened_by_id,
    )
    _validate_facility_specialty(facility_specialty=facility_specialty, encounter=encounter)
    _validate_department(department=department, encounter=encounter)
    _validate_practitioner_assignment(assignment=assignment, encounter=encounter)
    try:
        encounter.save()
    except IntegrityError as exc:
        raise ConflictError(
            "Encounter could not be created because a conflicting record exists."
        ) from exc
    _record_status_history(
        encounter=encounter,
        from_status=None,
        to_status=encounter.status,
        change_source=EncounterStatusHistory.ChangeSource.SYSTEM,
        changed_by_id=opened_by_id,
        changed_at=open_time,
    )
    return encounter


@transaction.atomic
def update_encounter(*, encounter_id, **updates) -> Encounter:
    encounter = _get_encounter(encounter_id, for_update=True)
    if encounter.status in TERMINAL_ENCOUNTER_STATUSES:
        raise ConflictError("Completed or cancelled encounters cannot be updated.")
    for field, model in [
        ("department_id", Department),
        ("facility_specialty_id", FacilitySpecialty),
    ]:
        if field in updates:
            obj = model.objects.filter(pk=updates[field]).first() if updates[field] else None
            if updates[field] and obj is None:
                label = "Department" if field == "department_id" else "Facility specialty"
                raise NotFoundError(f"{label} not found.")
            setattr(encounter, field, updates[field])
            (_validate_department if field == "department_id" else _validate_facility_specialty)(
                **{field.removesuffix("_id"): obj, "encounter": encounter}
            )
    if "attending_practitioner_facility_assignment_id" in updates:
        assignment = _get_practitioner_assignment(
            updates["attending_practitioner_facility_assignment_id"]
        )
        _validate_practitioner_assignment(assignment=assignment, encounter=encounter)
        encounter.attending_practitioner_facility_assignment = assignment
    if "encounter_type" in updates:
        encounter.encounter_type = updates["encounter_type"]
    encounter.save()
    return encounter


@transaction.atomic
def change_encounter_status(
    *,
    encounter_id,
    to_status,
    changed_by_id=None,
    reason=None,
    changed_at=None,
    change_source=EncounterStatusHistory.ChangeSource.CLINICAL,
) -> Encounter:
    encounter = _get_encounter(encounter_id, for_update=True)
    if encounter.status in TERMINAL_ENCOUNTER_STATUSES:
        raise ConflictError("Terminal encounters cannot change status.")
    if encounter.status == to_status:
        return encounter
    previous_status = encounter.status
    encounter.status = to_status
    encounter.save(update_fields=["status", "updated_at"])
    _record_status_history(
        encounter=encounter,
        from_status=previous_status,
        to_status=to_status,
        change_source=change_source,
        changed_by_id=changed_by_id,
        reason=reason,
        changed_at=changed_at,
    )
    return encounter


@transaction.atomic
def complete_encounter(*, encounter_id, completed_by_id=None, completed_at=None) -> Encounter:
    event_time = completed_at or timezone.now()
    encounter = _get_encounter(encounter_id, for_update=True)
    if encounter.status in TERMINAL_ENCOUNTER_STATUSES:
        raise ConflictError("Encounter is already closed.")
    previous_status = encounter.status
    encounter.status = Encounter.Status.COMPLETED
    encounter.completed_at = event_time
    encounter.completed_by_id = completed_by_id
    encounter.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])
    _record_status_history(
        encounter=encounter,
        from_status=previous_status,
        to_status=Encounter.Status.COMPLETED,
        change_source=EncounterStatusHistory.ChangeSource.CLINICAL,
        changed_by_id=completed_by_id,
        changed_at=event_time,
    )
    return encounter


@transaction.atomic
def cancel_encounter(
    *, encounter_id, cancellation_reason, cancelled_by_id=None, cancelled_at=None
) -> Encounter:
    encounter = _get_encounter(encounter_id, for_update=True)
    if encounter.status in TERMINAL_ENCOUNTER_STATUSES:
        raise ConflictError("Encounter is already closed.")
    event_time = cancelled_at or timezone.now()
    previous_status = encounter.status
    encounter.status = Encounter.Status.CANCELLED
    encounter.cancelled_at = event_time
    encounter.cancelled_by_id = cancelled_by_id
    encounter.cancellation_reason = _optional_text(cancellation_reason)
    if not encounter.cancellation_reason:
        raise ValidationError("Cancellation reason is required.")
    encounter.save()
    _record_status_history(
        encounter=encounter,
        from_status=previous_status,
        to_status=Encounter.Status.CANCELLED,
        change_source=EncounterStatusHistory.ChangeSource.CLINICAL,
        changed_by_id=cancelled_by_id,
        reason=encounter.cancellation_reason,
        changed_at=event_time,
    )
    return encounter


def create_triage_assessment(**data) -> TriageAssessment:
    encounter = _get_encounter(data.pop("encounter_id"))
    assignment = _get_practitioner_assignment(
        data.pop("performed_by_practitioner_facility_assignment_id", None)
    )
    _validate_practitioner_assignment(assignment=assignment, encounter=encounter)
    return TriageAssessment.objects.create(
        encounter=encounter,
        performed_by_practitioner_facility_assignment=assignment,
        chief_complaint_encrypted=_encrypt_optional(data.pop("chief_complaint", None)),
        notes_encrypted=_encrypt_optional(data.pop("notes", None)),
        **data,
    )


def update_triage_assessment(*, assessment_id, **updates) -> TriageAssessment:
    assessment = (
        TriageAssessment.objects.select_related("encounter").filter(pk=assessment_id).first()
    )
    if assessment is None:
        raise NotFoundError("Triage assessment not found.")
    if "performed_by_practitioner_facility_assignment_id" in updates:
        assignment = _get_practitioner_assignment(
            updates.pop("performed_by_practitioner_facility_assignment_id")
        )
        _validate_practitioner_assignment(assignment=assignment, encounter=assessment.encounter)
        assessment.performed_by_practitioner_facility_assignment = assignment
    for source, target in [
        ("chief_complaint", "chief_complaint_encrypted"),
        ("notes", "notes_encrypted"),
    ]:
        if source in updates:
            setattr(assessment, target, _encrypt_optional(updates.pop(source)))
    for field, value in updates.items():
        setattr(assessment, field, value)
    assessment.save()
    return assessment


def create_vital_sign(**data) -> VitalSign:
    encounter = _get_encounter(data.pop("encounter_id"))
    assignment = _get_practitioner_assignment(
        data.pop("recorded_by_practitioner_facility_assignment_id", None)
    )
    _validate_practitioner_assignment(assignment=assignment, encounter=encounter)
    return VitalSign.objects.create(
        encounter=encounter, recorded_by_practitioner_facility_assignment=assignment, **data
    )


def create_clinical_note(**data) -> ClinicalNote:
    encounter = _get_encounter(data.pop("encounter_id"))
    assignment = _get_practitioner_assignment(
        data.pop("practitioner_facility_assignment_id"), required=True
    )
    _validate_practitioner_assignment(assignment=assignment, encounter=encounter)
    return ClinicalNote.objects.create(
        encounter=encounter,
        practitioner_facility_assignment=assignment,
        subjective_encrypted=_encrypt_optional(data.pop("subjective", None)),
        objective_encrypted=_encrypt_optional(data.pop("objective", None)),
        assessment_encrypted=_encrypt_optional(data.pop("assessment", None)),
        plan_encrypted=_encrypt_optional(data.pop("plan", None)),
        **data,
    )


def create_diagnosis_code(**data) -> DiagnosisCode:
    data["coding_system"] = data["coding_system"].strip().upper()
    data["code"] = data["code"].strip().upper()
    return DiagnosisCode.objects.create(**data)


def update_diagnosis_code(*, code_id, **updates) -> DiagnosisCode:
    diagnosis = DiagnosisCode.objects.filter(pk=code_id).first()
    if diagnosis is None:
        raise NotFoundError("Diagnosis code not found.")
    if "coding_system" in updates:
        updates["coding_system"] = updates["coding_system"].strip().upper()
    if "code" in updates:
        updates["code"] = updates["code"].strip().upper()
    for field, value in updates.items():
        setattr(diagnosis, field, value)
    diagnosis.save()
    return diagnosis


def create_encounter_diagnosis(**data) -> EncounterDiagnosis:
    encounter = _get_encounter(data.pop("encounter_id"))
    assignment = _get_practitioner_assignment(
        data.pop("diagnosed_by_practitioner_facility_assignment_id", None)
    )
    _validate_practitioner_assignment(assignment=assignment, encounter=encounter)
    return EncounterDiagnosis.objects.create(
        encounter=encounter,
        diagnosis_code_id=data.pop("diagnosis_code_id", None),
        diagnosed_by_practitioner_facility_assignment=assignment,
        notes_encrypted=_encrypt_optional(data.pop("notes", None)),
        **data,
    )
