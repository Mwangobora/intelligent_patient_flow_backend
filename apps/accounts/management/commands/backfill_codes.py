from __future__ import annotations

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from common.services.code_generation import CODE_SEQUENCE_DEFINITIONS, generate_code_for_sequence


class Command(BaseCommand):
    help = "Backfill missing backend-managed code values without overwriting existing codes."

    def handle(self, *args, **options):
        total_backfilled = 0

        for definition in CODE_SEQUENCE_DEFINITIONS.values():
            app_label, model_name = definition.model_label.split(".", 1)
            model = apps.get_model(app_label, model_name)
            missing_filter = Q(**{f"{definition.field_name}__isnull": True}) | Q(**{definition.field_name: ""})

            backfilled = 0
            with transaction.atomic():
                queryset = model._default_manager.select_for_update().filter(missing_filter).order_by("created_at", "id")
                for record in queryset:
                    setattr(record, definition.field_name, generate_code_for_sequence(definition=definition))
                    record.save(update_fields=[definition.field_name, "updated_at"])
                    backfilled += 1

            total_backfilled += backfilled
            self.stdout.write(f"{model._meta.db_table}: {backfilled} code(s) backfilled")

        self.stdout.write(self.style.SUCCESS(f"Backfill complete. Total codes backfilled: {total_backfilled}"))
