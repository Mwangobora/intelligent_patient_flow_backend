from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("facilities", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE EXTENSION IF NOT EXISTS pgcrypto;
            CREATE EXTENSION IF NOT EXISTS btree_gist;

            CREATE OR REPLACE FUNCTION prevent_history_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION '% is append-only; create a corrective event instead', TG_TABLE_NAME;
            END;
            $$;

            CREATE OR REPLACE FUNCTION validate_facility_child_scope()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                linked_facility UUID;
            BEGIN
                IF TG_TABLE_NAME = 'facility_specialties' AND NEW.department_id IS NOT NULL THEN
                    SELECT facility_id INTO linked_facility FROM departments WHERE id = NEW.department_id;
                    IF linked_facility <> NEW.facility_id THEN
                        RAISE EXCEPTION 'Facility specialty department must belong to the same facility';
                    END IF;
                ELSIF TG_TABLE_NAME = 'service_points' AND NEW.department_id IS NOT NULL THEN
                    SELECT facility_id INTO linked_facility FROM departments WHERE id = NEW.department_id;
                    IF linked_facility <> NEW.facility_id THEN
                        RAISE EXCEPTION 'Service point department must belong to the same facility';
                    END IF;
                ELSIF TG_TABLE_NAME = 'consultation_rooms' AND NEW.department_id IS NOT NULL THEN
                    SELECT facility_id INTO linked_facility FROM departments WHERE id = NEW.department_id;
                    IF linked_facility <> NEW.facility_id THEN
                        RAISE EXCEPTION 'Consultation room department must belong to the same facility';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_facility_specialties_validate_scope
            BEFORE INSERT OR UPDATE OF facility_id, department_id
            ON facility_specialties
            FOR EACH ROW EXECUTE FUNCTION validate_facility_child_scope();

            CREATE TRIGGER trg_service_points_validate_scope
            BEFORE INSERT OR UPDATE OF facility_id, department_id
            ON service_points
            FOR EACH ROW EXECUTE FUNCTION validate_facility_child_scope();

            CREATE TRIGGER trg_consultation_rooms_validate_scope
            BEFORE INSERT OR UPDATE OF facility_id, department_id
            ON consultation_rooms
            FOR EACH ROW EXECUTE FUNCTION validate_facility_child_scope();

            CREATE OR REPLACE FUNCTION validate_operating_hours()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                new_start INTEGER;
                new_end INTEGER;
                conflicting BOOLEAN;
            BEGIN
                IF NOT NEW.is_active THEN
                    RETURN NEW;
                END IF;

                IF NEW.is_24_hours THEN
                    new_start := (NEW.day_of_week - 1) * 1440;
                    new_end := new_start + 1440;
                ELSE
                    new_start := (NEW.day_of_week - 1) * 1440
                        + (EXTRACT(HOUR FROM NEW.opens_at)::INTEGER * 60)
                        + EXTRACT(MINUTE FROM NEW.opens_at)::INTEGER;
                    new_end := (NEW.day_of_week - 1) * 1440
                        + (EXTRACT(HOUR FROM NEW.closes_at)::INTEGER * 60)
                        + EXTRACT(MINUTE FROM NEW.closes_at)::INTEGER
                        + CASE WHEN NEW.closes_next_day THEN 1440 ELSE 0 END;
                END IF;

                SELECT EXISTS (
                    SELECT 1
                    FROM facility_operating_hours h
                    CROSS JOIN LATERAL (
                        SELECT
                            CASE WHEN h.is_24_hours
                                THEN (h.day_of_week - 1) * 1440
                                ELSE (h.day_of_week - 1) * 1440
                                    + EXTRACT(HOUR FROM h.opens_at)::INTEGER * 60
                                    + EXTRACT(MINUTE FROM h.opens_at)::INTEGER
                            END AS existing_start,
                            CASE WHEN h.is_24_hours
                                THEN (h.day_of_week - 1) * 1440 + 1440
                                ELSE (h.day_of_week - 1) * 1440
                                    + EXTRACT(HOUR FROM h.closes_at)::INTEGER * 60
                                    + EXTRACT(MINUTE FROM h.closes_at)::INTEGER
                                    + CASE WHEN h.closes_next_day THEN 1440 ELSE 0 END
                            END AS existing_end
                    ) x
                    WHERE h.facility_id = NEW.facility_id
                      AND h.id <> NEW.id
                      AND h.is_active
                      AND (
                          int4range(new_start, new_end, '[)') && int4range(x.existing_start, x.existing_end, '[)')
                          OR int4range(new_start, new_end, '[)') && int4range(x.existing_start + 10080, x.existing_end + 10080, '[)')
                          OR int4range(new_start, new_end, '[)') && int4range(x.existing_start - 10080, x.existing_end - 10080, '[)')
                      )
                ) INTO conflicting;

                IF conflicting THEN
                    RAISE EXCEPTION 'Facility operating hours overlap another active period';
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_facility_operating_hours_validate
            BEFORE INSERT OR UPDATE
            ON facility_operating_hours
            FOR EACH ROW EXECUTE FUNCTION validate_operating_hours();

            CREATE OR REPLACE FUNCTION validate_schedule_exception()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                new_start INTEGER;
                new_end INTEGER;
                conflicting BOOLEAN;
            BEGIN
                IF NOT NEW.is_active THEN
                    RETURN NEW;
                END IF;

                IF NEW.is_closed OR NEW.is_24_hours THEN
                    IF EXISTS (
                        SELECT 1 FROM facility_schedule_exceptions e
                        WHERE e.facility_id = NEW.facility_id
                          AND e.exception_date = NEW.exception_date
                          AND e.id <> NEW.id
                          AND e.is_active
                    ) THEN
                        RAISE EXCEPTION 'Closed or 24-hour exception cannot coexist with another active period';
                    END IF;
                    RETURN NEW;
                END IF;

                IF EXISTS (
                    SELECT 1 FROM facility_schedule_exceptions e
                    WHERE e.facility_id = NEW.facility_id
                      AND e.exception_date = NEW.exception_date
                      AND e.id <> NEW.id
                      AND e.is_active
                      AND (e.is_closed OR e.is_24_hours)
                ) THEN
                    RAISE EXCEPTION 'Normal exception period cannot coexist with a closed or 24-hour exception';
                END IF;

                new_start := EXTRACT(HOUR FROM NEW.opens_at)::INTEGER * 60
                    + EXTRACT(MINUTE FROM NEW.opens_at)::INTEGER;
                new_end := EXTRACT(HOUR FROM NEW.closes_at)::INTEGER * 60
                    + EXTRACT(MINUTE FROM NEW.closes_at)::INTEGER
                    + CASE WHEN NEW.closes_next_day THEN 1440 ELSE 0 END;

                SELECT EXISTS (
                    SELECT 1
                    FROM facility_schedule_exceptions e
                    WHERE e.facility_id = NEW.facility_id
                      AND e.exception_date = NEW.exception_date
                      AND e.id <> NEW.id
                      AND e.is_active
                      AND NOT e.is_closed
                      AND NOT e.is_24_hours
                      AND int4range(new_start, new_end, '[)') && int4range(
                            EXTRACT(HOUR FROM e.opens_at)::INTEGER * 60 + EXTRACT(MINUTE FROM e.opens_at)::INTEGER,
                            EXTRACT(HOUR FROM e.closes_at)::INTEGER * 60 + EXTRACT(MINUTE FROM e.closes_at)::INTEGER
                                + CASE WHEN e.closes_next_day THEN 1440 ELSE 0 END,
                            '[)'
                          )
                ) INTO conflicting;

                IF conflicting THEN
                    RAISE EXCEPTION 'Facility schedule exception overlaps another active period';
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_facility_schedule_exceptions_validate
            BEFORE INSERT OR UPDATE
            ON facility_schedule_exceptions
            FOR EACH ROW EXECUTE FUNCTION validate_schedule_exception();

            CREATE OR REPLACE FUNCTION validate_org_facility_pair()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                facility_org UUID;
            BEGIN
                IF NEW.facility_id IS NOT NULL THEN
                    SELECT organization_id INTO facility_org FROM facilities WHERE id = NEW.facility_id;
                    IF NEW.organization_id IS NULL OR facility_org <> NEW.organization_id THEN
                        RAISE EXCEPTION 'Facility must belong to the selected organization';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$;
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_facility_schedule_exceptions_validate ON facility_schedule_exceptions;
            DROP TRIGGER IF EXISTS trg_facility_operating_hours_validate ON facility_operating_hours;
            DROP TRIGGER IF EXISTS trg_consultation_rooms_validate_scope ON consultation_rooms;
            DROP TRIGGER IF EXISTS trg_service_points_validate_scope ON service_points;
            DROP TRIGGER IF EXISTS trg_facility_specialties_validate_scope ON facility_specialties;

            DROP FUNCTION IF EXISTS validate_org_facility_pair();
            DROP FUNCTION IF EXISTS validate_schedule_exception();
            DROP FUNCTION IF EXISTS validate_operating_hours();
            DROP FUNCTION IF EXISTS validate_facility_child_scope();
            DROP FUNCTION IF EXISTS prevent_history_mutation();

            DROP EXTENSION IF EXISTS btree_gist;
            DROP EXTENSION IF EXISTS pgcrypto;
            """,
        ),
    ]
