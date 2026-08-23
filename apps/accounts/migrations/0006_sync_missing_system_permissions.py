from __future__ import annotations

from django.db import migrations


MISSING_PERMISSION_CODES = [
    "accounts_role_permission.revoke",
    "accounts_membership.end",
    "facilities_facility_type.view",
    "facilities_facility_type.create",
    "facilities_facility_type.update",
    "facilities_facility_type.deactivate",
    "facilities_flow_settings.manage",
]


def permission_name(code: str) -> str:
    module, action = code.split(".", 1)
    return f"{module.replace('_', ' ').title()} {action.replace('_', ' ').title()}"


def sync_missing_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for code in MISSING_PERMISSION_CODES:
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
        ("accounts", "0005_sync_system_permissions"),
    ]

    operations = [
        migrations.RunPython(sync_missing_permissions, reverse_code=migrations.RunPython.noop),
    ]
