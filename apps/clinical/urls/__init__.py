from django.urls import include, path
from rest_framework.routers import SimpleRouter

from apps.clinical.views import (
    ClinicalNoteViewSet,
    DiagnosisCodeViewSet,
    EncounterDiagnosisViewSet,
    EncounterViewSet,
    TriageAssessmentViewSet,
    VitalSignViewSet,
)

router = SimpleRouter()
router.register(r"clinical/encounters", EncounterViewSet, basename="clinical-encounters")
router.register(
    r"clinical/triage-assessments", TriageAssessmentViewSet, basename="clinical-triage-assessments"
)
router.register(r"clinical/vital-signs", VitalSignViewSet, basename="clinical-vital-signs")
router.register(r"clinical/notes", ClinicalNoteViewSet, basename="clinical-notes")
router.register(
    r"clinical/diagnosis-codes", DiagnosisCodeViewSet, basename="clinical-diagnosis-codes"
)
router.register(
    r"clinical/encounter-diagnoses",
    EncounterDiagnosisViewSet,
    basename="clinical-encounter-diagnoses",
)

urlpatterns = [
    path("", include(router.urls)),
]
