from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("checkins", "0002_postgres_hardening"),
        ("facilities", "0002_postgres_hardening"),
        ("queueing", "0001_initial"),
        ("scheduling", "0002_postgres_hardening"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION validate_queue()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                queue_facility UUID;
                service_department UUID;
                specialty_facility UUID;
                specialty_department UUID;
            BEGIN
                SELECT facility_id, department_id INTO queue_facility, service_department
                FROM service_points WHERE id = NEW.service_point_id AND is_active;

                IF queue_facility IS NULL THEN
                    RAISE EXCEPTION 'Queue service point must be active';
                END IF;

                IF NEW.facility_specialty_id IS NOT NULL THEN
                    SELECT facility_id, department_id INTO specialty_facility, specialty_department
                    FROM facility_specialties WHERE id = NEW.facility_specialty_id AND is_active;

                    IF specialty_facility IS NULL OR specialty_facility <> queue_facility THEN
                        RAISE EXCEPTION 'Queue specialty must be active and belong to service-point facility';
                    END IF;

                    IF service_department IS NOT NULL AND specialty_department IS NOT NULL
                       AND service_department <> specialty_department THEN
                        RAISE EXCEPTION 'Queue service point and specialty departments must match';
                    END IF;
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_queues_validate
            BEFORE INSERT OR UPDATE
            ON queues
            FOR EACH ROW EXECUTE FUNCTION validate_queue();

            CREATE OR REPLACE FUNCTION validate_queue_entry()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                queue_status VARCHAR(20);
                queue_service_point UUID;
                queue_specialty UUID;
                queue_facility UUID;
                checkin_facility UUID;
                checkin_specialty UUID;
                checkin_appointment UUID;
                appointment_specialty UUID;
                shift_service_point UUID;
                shift_facility UUID;
                shift_status VARCHAR(20);
            BEGIN
                SELECT q.status, q.service_point_id, q.facility_specialty_id, sp.facility_id
                  INTO queue_status, queue_service_point, queue_specialty, queue_facility
                FROM queues q
                JOIN service_points sp ON sp.id = q.service_point_id
                WHERE q.id = NEW.queue_id;

                IF TG_OP = 'INSERT' AND queue_status <> 'open' THEN
                    RAISE EXCEPTION 'New queue entries require an open queue';
                END IF;

                SELECT facility_id, facility_specialty_id, appointment_id
                  INTO checkin_facility, checkin_specialty, checkin_appointment
                FROM patient_checkins
                WHERE id = NEW.patient_checkin_id AND voided_at IS NULL;

                IF checkin_facility IS NULL OR checkin_facility <> queue_facility THEN
                    RAISE EXCEPTION 'Queue entry check-in must be active and belong to queue facility';
                END IF;

                IF checkin_appointment IS NOT NULL THEN
                    SELECT facility_specialty_id INTO appointment_specialty
                    FROM appointments WHERE id = checkin_appointment;
                END IF;

                IF queue_specialty IS NOT NULL
                   AND queue_specialty <> COALESCE(checkin_specialty, appointment_specialty) THEN
                    RAISE EXCEPTION 'Queue entry specialty does not match check-in or appointment specialty';
                END IF;

                IF NEW.practitioner_shift_id IS NOT NULL THEN
                    SELECT s.service_point_id, pfa.facility_id, s.status
                      INTO shift_service_point, shift_facility, shift_status
                    FROM practitioner_shifts s
                    JOIN practitioner_facility_assignments pfa ON pfa.id = s.practitioner_facility_assignment_id
                    WHERE s.id = NEW.practitioner_shift_id;

                    IF shift_facility <> queue_facility
                       OR shift_service_point IS DISTINCT FROM queue_service_point
                       OR shift_status = 'cancelled' THEN
                        RAISE EXCEPTION 'Queue entry practitioner shift must match queue facility and service point';
                    END IF;
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_queue_entries_validate
            BEFORE INSERT OR UPDATE
            ON queue_entries
            FOR EACH ROW EXECUTE FUNCTION validate_queue_entry();

            CREATE OR REPLACE FUNCTION validate_queue_transfer()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                source_checkin UUID;
                destination_checkin UUID;
                source_queue UUID;
                destination_queue UUID;
                source_facility UUID;
                destination_facility UUID;
                source_status VARCHAR(20);
                destination_status VARCHAR(20);
                source_joined TIMESTAMPTZ;
                destination_joined TIMESTAMPTZ;
                destination_queue_status VARCHAR(20);
            BEGIN
                SELECT qe.patient_checkin_id, qe.queue_id, sp.facility_id, qe.status, qe.joined_at
                  INTO source_checkin, source_queue, source_facility, source_status, source_joined
                FROM queue_entries qe
                JOIN queues q ON q.id = qe.queue_id
                JOIN service_points sp ON sp.id = q.service_point_id
                WHERE qe.id = NEW.source_queue_entry_id;

                SELECT qe.patient_checkin_id, qe.queue_id, sp.facility_id, qe.status, qe.joined_at, q.status
                  INTO destination_checkin, destination_queue, destination_facility, destination_status, destination_joined, destination_queue_status
                FROM queue_entries qe
                JOIN queues q ON q.id = qe.queue_id
                JOIN service_points sp ON sp.id = q.service_point_id
                WHERE qe.id = NEW.destination_queue_entry_id;

                IF source_checkin <> destination_checkin THEN
                    RAISE EXCEPTION 'Queue transfer source and destination must use the same check-in';
                END IF;
                IF source_queue = destination_queue THEN
                    RAISE EXCEPTION 'Queue transfer destination must be a different queue';
                END IF;
                IF source_facility <> destination_facility THEN
                    RAISE EXCEPTION 'Queue transfer must remain within the same facility';
                END IF;
                IF source_status <> 'transferred' OR destination_status <> 'waiting' THEN
                    RAISE EXCEPTION 'Transfer requires transferred source and waiting destination entries';
                END IF;
                IF destination_queue_status <> 'open' THEN
                    RAISE EXCEPTION 'Transfer destination queue must be open';
                END IF;
                IF NEW.transferred_at < source_joined OR destination_joined < NEW.transferred_at THEN
                    RAISE EXCEPTION 'Queue transfer timestamps are inconsistent';
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_queue_transfers_validate
            BEFORE INSERT OR UPDATE
            ON queue_transfers
            FOR EACH ROW EXECUTE FUNCTION validate_queue_transfer();

            CREATE OR REPLACE FUNCTION validate_queue_entry_event()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                entry_joined TIMESTAMPTZ;
            BEGIN
                SELECT joined_at INTO entry_joined FROM queue_entries WHERE id = NEW.queue_entry_id;
                IF NEW.occurred_at < entry_joined THEN
                    RAISE EXCEPTION 'Queue event cannot occur before queue entry joined_at';
                END IF;

                IF NEW.event_type = 'joined'
                   AND NOT (NEW.from_status IS NULL AND NEW.to_status = 'waiting') THEN
                    RAISE EXCEPTION 'Joined event must transition from NULL to waiting';
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_queue_entry_events_validate
            BEFORE INSERT OR UPDATE
            ON queue_entry_events
            FOR EACH ROW EXECUTE FUNCTION validate_queue_entry_event();

            CREATE TRIGGER trg_queue_entry_events_append_only
            BEFORE UPDATE OR DELETE ON queue_entry_events
            FOR EACH ROW EXECUTE FUNCTION prevent_history_mutation();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_queue_entry_events_append_only ON queue_entry_events;
            DROP TRIGGER IF EXISTS trg_queue_entry_events_validate ON queue_entry_events;
            DROP TRIGGER IF EXISTS trg_queue_transfers_validate ON queue_transfers;
            DROP TRIGGER IF EXISTS trg_queue_entries_validate ON queue_entries;
            DROP TRIGGER IF EXISTS trg_queues_validate ON queues;

            DROP FUNCTION IF EXISTS validate_queue_entry_event();
            DROP FUNCTION IF EXISTS validate_queue_transfer();
            DROP FUNCTION IF EXISTS validate_queue_entry();
            DROP FUNCTION IF EXISTS validate_queue();
            """,
        ),
    ]
