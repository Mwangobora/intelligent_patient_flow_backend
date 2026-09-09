from __future__ import annotations

from django.db import migrations

LABORATORY_PERMISSION_CODES = [
    "laboratory_test.view",
    "laboratory_test.create",
    "laboratory_test.update",
    "laboratory_test.deactivate",
    "laboratory_order.view",
    "laboratory_order.create",
    "laboratory_order.update",
    "laboratory_order.cancel",
    "laboratory_specimen.view",
    "laboratory_specimen.manage",
    "laboratory_result.view",
    "laboratory_result.create",
    "laboratory_result.verify",
]


def permission_name(code: str) -> str:
    module, action = code.split(".", 1)
    return f"{module.replace('_', ' ').title()} {action.replace('_', ' ').title()}"


def sync_laboratory_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for code in LABORATORY_PERMISSION_CODES:
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
        ("accounts", "0008_sync_clinical_permissions"),
    ]

    operations = [
        migrations.RunPython(sync_laboratory_permissions, reverse_code=migrations.RunPython.noop),
    ]
