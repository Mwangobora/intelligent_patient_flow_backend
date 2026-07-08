from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
        ("patients", "0001_initial"),
        ("queueing", "0002_postgres_hardening"),
        ("scheduling", "0002_postgres_hardening"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION validate_patient_notification()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                patient_user UUID;
                appointment_patient UUID;
                queue_patient UUID;
            BEGIN
                SELECT user_id INTO patient_user FROM patients WHERE id = NEW.patient_id;

                IF NEW.recipient_user_id IS NOT NULL
                   AND patient_user IS DISTINCT FROM NEW.recipient_user_id THEN
                    RAISE EXCEPTION 'Notification recipient user must be linked to the patient';
                END IF;

                IF NEW.appointment_id IS NOT NULL THEN
                    SELECT patient_id INTO appointment_patient FROM appointments WHERE id = NEW.appointment_id;
                    IF appointment_patient <> NEW.patient_id THEN
                        RAISE EXCEPTION 'Notification appointment does not belong to the patient';
                    END IF;
                END IF;

                IF NEW.queue_entry_id IS NOT NULL THEN
                    SELECT pc.patient_id INTO queue_patient
                    FROM queue_entries qe
                    JOIN patient_checkins pc ON pc.id = qe.patient_checkin_id
                    WHERE qe.id = NEW.queue_entry_id;

                    IF queue_patient <> NEW.patient_id THEN
                        RAISE EXCEPTION 'Notification queue entry does not belong to the patient';
                    END IF;
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_patient_notifications_validate
            BEFORE INSERT OR UPDATE
            ON patient_notifications
            FOR EACH ROW EXECUTE FUNCTION validate_patient_notification();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_patient_notifications_validate ON patient_notifications;
            DROP FUNCTION IF EXISTS validate_patient_notification();
            """,
        ),
    ]
