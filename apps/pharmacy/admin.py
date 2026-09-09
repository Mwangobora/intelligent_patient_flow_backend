from django.contrib import admin

from apps.pharmacy.models import Medication, MedicationDispense, Prescription, PrescriptionItem


class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 0


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ("code", "generic_name", "brand_name", "organization", "is_active")
    list_filter = ("organization", "is_active", "dosage_form")
    search_fields = ("code", "generic_name", "brand_name")


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ("prescription_number", "encounter", "status", "prescribed_at")
    list_filter = ("status",)
    search_fields = ("prescription_number", "encounter__encounter_number")
    inlines = [PrescriptionItemInline]


admin.site.register(MedicationDispense)
