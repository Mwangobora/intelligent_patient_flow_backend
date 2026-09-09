from __future__ import annotations

from django.db import migrations


CLINICAL_PERMISSION_CODES = [
    "clinical_encounter.view",
    "clinical_encounter.create",
    "clinical_encounter.update",
    "clinical_encounter.complete",
    "clinical_encounter.cancel",
    "clinical_triage.manage",
    "clinical_vitals.manage",
    "clinical_note.manage",
    "clinical_diagnosis_code.manage",
    "clinical_diagnosis.manage",
    "patients_allergy.manage",
    "patients_condition.manage",
]


def permission_name(code: str) -> str:
    module, action = code.split(".", 1)
    return f"{module.replace('_', ' ').title()} {action.replace('_', ' ').title()}"


def sync_clinical_permissions(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for code in CLINICAL_PERMISSION_CODES:
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
        ("accounts", "0007_sync_user_action_permissions"),
    ]

    operations = [
        migrations.RunPython(sync_clinical_permissions, reverse_code=migrations.RunPython.noop),
    ]
