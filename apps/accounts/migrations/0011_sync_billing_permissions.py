from __future__ import annotations

from django.db import migrations

BILLING_PERMISSION_CODES = [
    "billing_service.view",
    "billing_service.create",
    "billing_service.update",
    "billing_service.deactivate",
    "billing_price.view",
    "billing_price.manage",
    "billing_charge.view",
    "billing_charge.create",
    "billing_charge.void",
    "billing_invoice.view",
    "billing_invoice.create",
    "billing_invoice.cancel",
    "billing_payment.view",
    "billing_payment.create",
    "billing_refund.view",
    "billing_refund.create",
    "billing_refund.complete",
]


def permission_name(code: str) -> str:
    module, action = code.split(".", 1)
    return f"{module.replace('_', ' ').title()} {action.replace('_', ' ').title()}"


def sync_billing_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for code in BILLING_PERMISSION_CODES:
        module, action = code.split(".", 1)
        permission, created = Permission.objects.get_or_create(
            code=code,
            defaults={
                "name": permission_name(code),
                "module": module,
                "action": action,
                "description": "System capability available for dynamic role assignment.",
                "is_active": True,
            },
        )
        if created or permission.is_active:
            continue
        permission.is_active = True
        permission.save(update_fields=["is_active"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_sync_pharmacy_permissions"),
    ]

    operations = [
        migrations.RunPython(sync_billing_permissions, reverse_code=migrations.RunPython.noop),
    ]
