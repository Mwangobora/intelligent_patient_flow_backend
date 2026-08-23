from __future__ import annotations

from django.db import migrations


USER_ACTION_PERMISSION_CODES = [
    "accounts_user.activate",
    "accounts_user.verify_email",
    "accounts_user.verify_phone",
]


def permission_name(code: str) -> str:
    module, action = code.split(".", 1)
    return f"{module.replace('_', ' ').title()} {action.replace('_', ' ').title()}"


def sync_user_action_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for code in USER_ACTION_PERMISSION_CODES:
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
        ("accounts", "0006_sync_missing_system_permissions"),
    ]

    operations = [
        migrations.RunPython(sync_user_action_permissions, reverse_code=migrations.RunPython.noop),
    ]
