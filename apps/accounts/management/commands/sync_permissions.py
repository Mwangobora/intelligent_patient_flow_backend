from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Permission


PERMISSION_CODES = [
    "accounts_user.view",
    "accounts_user.create",
    "accounts_user.update",
    "accounts_user.deactivate",
    "accounts_role.view",
    "accounts_role.create",
    "accounts_role.update",
    "accounts_role.deactivate",
    "accounts_role.manage",
    "accounts_role_permission.grant",
    "accounts_permission.view",
    "accounts_permission.create",
    "accounts_permission.update",
    "accounts_permission.deactivate",
    "accounts_permission.manage",
    "accounts_membership.create",
    "accounts_membership.update",
    "accounts_membership.deactivate",
    "accounts_role_assignment.create",
    "accounts_role_assignment.revoke",
    "facilities_organization.view",
    "facilities_organization.create",
    "facilities_organization.update",
    "facilities_organization.deactivate",
    "facilities_facility.view",
    "facilities_facility.create",
    "facilities_facility.update",
    "facilities_facility.deactivate",
    "facilities_department.manage",
    "facilities_specialty.manage",
    "facilities_service_point.manage",
    "facilities_room.manage",
    "facilities_schedule.manage",
    "facilities_settings.manage",
    "patients_patient.view",
    "patients_patient.create",
    "patients_patient.update",
    "patients_patient.deactivate",
    "patients_identifier_type.manage",
    "patients_identifier.manage",
    "patients_address.manage",
    "patients_relationship_type.manage",
    "patients_related_person.manage",
    "patients_related_person_contact.manage",
    "patients_access_grant.manage",
    "practitioners_type.view",
    "practitioners_type.manage",
    "practitioners_practitioner.view",
    "practitioners_practitioner.create",
    "practitioners_practitioner.update",
    "practitioners_practitioner.deactivate",
    "practitioners_assignment.manage",
    "practitioners_credential_type.manage",
    "practitioners_credential.manage",
    "practitioners_credential.verify",
    "scheduling_availability.manage",
    "scheduling_leave.manage",
    "scheduling_shift.manage",
    "scheduling_slot.manage",
    "scheduling_appointment.view",
    "scheduling_appointment.create",
    "scheduling_appointment.update",
    "scheduling_appointment.cancel",
    "scheduling_appointment.reschedule",
    "scheduling_appointment.assign",
    "checkins_checkin.view",
    "checkins_checkin.create",
    "checkins_checkin.void",
    "checkins_token.create",
    "checkins_token.revoke",
    "checkins_token.consume",
    "queueing_queue.view",
    "queueing_queue.manage",
    "queueing_entry.view",
    "queueing_entry.create",
    "queueing_entry.call",
    "queueing_entry.skip",
    "queueing_entry.start_service",
    "queueing_entry.complete_service",
    "queueing_entry.cancel",
    "queueing_entry.transfer",
    "queueing_priority.manage",
    "intelligence_prediction.view",
    "intelligence_prediction.create",
    "intelligence_prediction.evaluate",
    "intelligence_forecast.view",
    "intelligence_slot_suggestion.view",
    "notifications_notification.view",
    "notifications_notification.create",
    "notifications_notification.send",
    "notifications_notification.cancel",
    "notifications_device.view",
    "notifications_device.manage",
    "reporting_report.view",
    "reporting_report.generate",
    "reporting_report.download",
    "reporting_report.cancel",
    "reporting_analytics.view",
    "audit_log.view",
    "audit_log.create",
    "audit_log.export",
    "audit_log.summary",
]


def permission_name(code: str) -> str:
    module, action = code.split(".", 1)
    return f"{module.replace('_', ' ').title()} {action.replace('_', ' ').title()}"


class Command(BaseCommand):
    help = "Create or reactivate system permission records without assigning them to roles."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        reactivated = 0

        for code in PERMISSION_CODES:
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

        self.stdout.write(self.style.SUCCESS(f"Permissions synced. created={created}, reactivated={reactivated}, total={len(PERMISSION_CODES)}"))
