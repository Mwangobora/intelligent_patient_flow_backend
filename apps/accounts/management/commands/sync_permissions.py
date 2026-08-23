from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Permission
from apps.accounts.system_permissions import SYSTEM_PERMISSION_CODES, permission_name


class Command(BaseCommand):
    help = "Create or reactivate system permission records without assigning them to roles."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        reactivated = 0

        for code in SYSTEM_PERMISSION_CODES:
            module, action = code.split(".", 1)
            permission, was_created = Permission.objects.get_or_create(
                code=code,
                defaults={
                    "name": permission_name(code),
                    "module": module,
                    "action": action,
                    "description": "System capability available for dynamic role assignment.",
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
                continue

            changed_fields = []
            if not permission.is_active:
                permission.is_active = True
                changed_fields.append("is_active")
            if not permission.description:
                permission.description = "System capability available for dynamic role assignment."
                changed_fields.append("description")
            if changed_fields:
                permission.save(update_fields=[*changed_fields, "updated_at"])
                reactivated += 1

        self.stdout.write(self.style.SUCCESS(f"Permissions synced. created={created}, reactivated={reactivated}, total={len(SYSTEM_PERMISSION_CODES)}"))
