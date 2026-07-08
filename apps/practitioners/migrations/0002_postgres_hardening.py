from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("facilities", "0002_postgres_hardening"),
        ("practitioners", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION validate_practitioner_facility_assignment()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                practitioner_org UUID;
                facility_org UUID;
            BEGIN
                SELECT organization_id INTO practitioner_org FROM practitioners WHERE id = NEW.practitioner_id;
                SELECT organization_id INTO facility_org FROM facilities WHERE id = NEW.facility_id;

                IF practitioner_org <> facility_org THEN
                    RAISE EXCEPTION 'Practitioner and facility must belong to the same organization';
                END IF;
                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_practitioner_facility_assignments_validate
            BEFORE INSERT OR UPDATE OF practitioner_id, facility_id
            ON practitioner_facility_assignments
            FOR EACH ROW EXECUTE FUNCTION validate_practitioner_facility_assignment();

            CREATE OR REPLACE FUNCTION validate_practitioner_department_assignment()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                assignment_facility UUID;
                assignment_start DATE;
                assignment_end DATE;
                department_facility UUID;
            BEGIN
                SELECT facility_id, starts_on, ends_on
                  INTO assignment_facility, assignment_start, assignment_end
                FROM practitioner_facility_assignments
                WHERE id = NEW.practitioner_facility_assignment_id;

                SELECT facility_id INTO department_facility FROM departments WHERE id = NEW.department_id;

                IF assignment_facility <> department_facility THEN
                    RAISE EXCEPTION 'Practitioner department must belong to assigned facility';
                END IF;

                IF NEW.starts_on < assignment_start
                   OR (assignment_end IS NOT NULL AND (NEW.ends_on IS NULL OR NEW.ends_on > assignment_end)) THEN
                    RAISE EXCEPTION 'Department assignment must remain within facility assignment dates';
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_practitioner_department_assignments_validate
            BEFORE INSERT OR UPDATE
            ON practitioner_department_assignments
            FOR EACH ROW EXECUTE FUNCTION validate_practitioner_department_assignment();

            CREATE OR REPLACE FUNCTION validate_practitioner_specialty_assignment()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                assignment_facility UUID;
                assignment_start DATE;
                assignment_end DATE;
                specialty_facility UUID;
                specialty_department UUID;
                has_department_assignment BOOLEAN;
            BEGIN
                SELECT facility_id, starts_on, ends_on
                  INTO assignment_facility, assignment_start, assignment_end
                FROM practitioner_facility_assignments
                WHERE id = NEW.practitioner_facility_assignment_id;

                SELECT facility_id, department_id
                  INTO specialty_facility, specialty_department
                FROM facility_specialties
                WHERE id = NEW.facility_specialty_id;

                IF assignment_facility <> specialty_facility THEN
                    RAISE EXCEPTION 'Practitioner specialty must belong to assigned facility';
                END IF;

                IF NEW.starts_on < assignment_start
                   OR (assignment_end IS NOT NULL AND (NEW.ends_on IS NULL OR NEW.ends_on > assignment_end)) THEN
                    RAISE EXCEPTION 'Specialty assignment must remain within facility assignment dates';
                END IF;

                IF specialty_department IS NOT NULL THEN
                    SELECT EXISTS (
                        SELECT 1
                        FROM practitioner_department_assignments pda
                        WHERE pda.practitioner_facility_assignment_id = NEW.practitioner_facility_assignment_id
                          AND pda.department_id = specialty_department
                          AND pda.is_active
                          AND pda.starts_on <= NEW.starts_on
                          AND (pda.ends_on IS NULL OR pda.ends_on >= COALESCE(NEW.ends_on, NEW.starts_on))
                    ) INTO has_department_assignment;

                    IF NOT has_department_assignment THEN
                        RAISE EXCEPTION 'Department-specific specialty requires an active matching department assignment';
                    END IF;
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_practitioner_specialty_assignments_validate
            BEFORE INSERT OR UPDATE
            ON practitioner_specialty_assignments
            FOR EACH ROW EXECUTE FUNCTION validate_practitioner_specialty_assignment();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_practitioner_specialty_assignments_validate ON practitioner_specialty_assignments;
            DROP TRIGGER IF EXISTS trg_practitioner_department_assignments_validate ON practitioner_department_assignments;
            DROP TRIGGER IF EXISTS trg_practitioner_facility_assignments_validate ON practitioner_facility_assignments;

            DROP FUNCTION IF EXISTS validate_practitioner_specialty_assignment();
            DROP FUNCTION IF EXISTS validate_practitioner_department_assignment();
            DROP FUNCTION IF EXISTS validate_practitioner_facility_assignment();
            """,
        ),
    ]
