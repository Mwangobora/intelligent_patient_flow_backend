from __future__ import annotations

from django.db import migrations

PHARMACY_PERMISSION_CODES = [
    "pharmacy_medication.view",
    "pharmacy_medication.create",
    "pharmacy_medication.update",
    "pharmacy_medication.deactivate",
    "pharmacy_prescription.view",
    "pharmacy_prescription.create",
    "pharmacy_prescription.cancel",
    "pharmacy_dispense.view",
    "pharmacy_dispense.create",
]


def permission_name(code: str) -> str:
    module, action = code.split(".", 1)
    return f"{module.replace('_', ' ').title()} {action.replace('_', ' ').title()}"


def sync_pharmacy_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for code in PHARMACY_PERMISSION_CODES:
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
        ("accounts", "0009_sync_laboratory_permissions"),
    ]

    operations = [
        migrations.RunPython(sync_pharmacy_permissions, reverse_code=migrations.RunPython.noop),
    ]
