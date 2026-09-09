from __future__ import annotations

from django.db.models import Q

from apps.patients.models import PatientAllergy, PatientCondition


def list_patient_allergies(*, patient_id=None, status=None, search=None):
    queryset = PatientAllergy.objects.select_related("patient", "recorded_by")
    if patient_id:
        queryset = queryset.filter(patient_id=patient_id)
    if status:
        queryset = queryset.filter(status=status)
    if search:
        queryset = queryset.filter(
            Q(allergen__icontains=search)
            | Q(reaction__icontains=search)
            | Q(allergy_type__icontains=search)
        )
    return queryset.order_by("-recorded_at")


def get_patient_allergy_by_id(allergy_id):
    return list_patient_allergies().filter(pk=allergy_id).first()


def list_patient_conditions(*, patient_id=None, status=None, search=None):
    queryset = PatientCondition.objects.select_related("patient", "diagnosis_code", "recorded_by")
    if patient_id:
        queryset = queryset.filter(patient_id=patient_id)
    if status:
        queryset = queryset.filter(status=status)
    if search:
        queryset = queryset.filter(
            Q(condition_name__icontains=search)
            | Q(diagnosis_code__code__icontains=search)
            | Q(diagnosis_code__name__icontains=search)
        )
    return queryset.order_by("-created_at")


def get_patient_condition_by_id(condition_id):
    return list_patient_conditions().filter(pk=condition_id).first()
