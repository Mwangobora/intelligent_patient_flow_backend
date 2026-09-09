from django.contrib import admin

from apps.billing.models import (
    EncounterCharge,
    Invoice,
    InvoiceItem,
    Payment,
    PaymentRefund,
    Service,
    ServicePrice,
)


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "service_category", "is_active")
    list_filter = ("organization", "service_category", "is_active")
    search_fields = ("code", "name")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "facility",
        "patient",
        "status",
        "total_amount",
        "balance_amount",
    )
    list_filter = ("status", "facility")
    search_fields = ("invoice_number", "patient__patient_number")
    inlines = [InvoiceItemInline]


admin.site.register(ServicePrice)
admin.site.register(EncounterCharge)
admin.site.register(Payment)
admin.site.register(PaymentRefund)
