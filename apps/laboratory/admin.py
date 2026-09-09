from django.contrib import admin

from apps.laboratory.models import (
    LabOrder,
    LabOrderItem,
    LabResultValue,
    LabSpecimen,
    LabTest,
    LabTestComponent,
)


class LabTestComponentInline(admin.TabularInline):
    model = LabTestComponent
    extra = 0


@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "specimen_type", "is_active")
    list_filter = ("organization", "is_active", "specimen_type")
    search_fields = ("code", "name")
    inlines = [LabTestComponentInline]


@admin.register(LabOrder)
class LabOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "encounter", "priority", "status", "ordered_at")
    list_filter = ("priority", "status")
    search_fields = ("order_number", "encounter__encounter_number")


admin.site.register(LabOrderItem)
admin.site.register(LabSpecimen)
admin.site.register(LabResultValue)
