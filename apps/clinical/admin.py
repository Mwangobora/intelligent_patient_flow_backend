from django.contrib import admin

from apps.clinical.models import (
    ClinicalNote,
    DiagnosisCode,
    Encounter,
    EncounterDiagnosis,
    EncounterStatusHistory,
    TriageAssessment,
    VitalSign,
)


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = (
        "encounter_number",
        "facility",
        "patient",
        "encounter_type",
        "status",
        "opened_at",
    )
    list_filter = ("encounter_type", "status", "facility")
    search_fields = (
        "encounter_number",
        "patient__patient_number",
        "patient__first_name",
        "patient__last_name",
    )


@admin.register(EncounterStatusHistory)
class EncounterStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("encounter", "from_status", "to_status", "change_source", "changed_at")
    list_filter = ("to_status", "change_source")


admin.site.register(TriageAssessment)
admin.site.register(VitalSign)
admin.site.register(ClinicalNote)
admin.site.register(DiagnosisCode)
admin.site.register(EncounterDiagnosis)
