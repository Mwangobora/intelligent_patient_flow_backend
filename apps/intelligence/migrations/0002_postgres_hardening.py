from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("facilities", "0002_postgres_hardening"),
        ("intelligence", "0001_initial"),
        ("queueing", "0002_postgres_hardening"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION validate_queue_prediction()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                entry_status VARCHAR(20);
                entry_joined TIMESTAMPTZ;
                service_started TIMESTAMPTZ;
            BEGIN
                SELECT status, joined_at, service_started_at
                  INTO entry_status, entry_joined, service_started
                FROM queue_entries WHERE id = NEW.queue_entry_id;

                IF entry_status NOT IN ('waiting', 'called', 'skipped') THEN
                    RAISE EXCEPTION 'Waiting-time prediction is not allowed for this queue-entry status';
                END IF;
                IF NEW.generated_at < entry_joined THEN
                    RAISE EXCEPTION 'Prediction cannot be generated before queue entry joined_at';
                END IF;
                IF service_started IS NOT NULL AND NEW.generated_at >= service_started THEN
                    RAISE EXCEPTION 'Prediction must be generated before service starts';
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_queue_wait_time_predictions_validate
            BEFORE INSERT OR UPDATE
            ON queue_wait_time_predictions
            FOR EACH ROW EXECUTE FUNCTION validate_queue_prediction();

            CREATE TRIGGER trg_queue_wait_time_predictions_append_only
            BEFORE UPDATE OR DELETE ON queue_wait_time_predictions
            FOR EACH ROW EXECUTE FUNCTION prevent_history_mutation();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_queue_wait_time_predictions_append_only ON queue_wait_time_predictions;
            DROP TRIGGER IF EXISTS trg_queue_wait_time_predictions_validate ON queue_wait_time_predictions;

            DROP FUNCTION IF EXISTS validate_queue_prediction();
            """,
        ),
    ]
