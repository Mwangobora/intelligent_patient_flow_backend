from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("checkins", "0001_initial"),
        ("facilities", "0002_postgres_hardening"),
        ("patients", "0001_initial"),
        ("scheduling", "0002_postgres_hardening"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION validate_patient_checkin()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                facility_org UUID;
                patient_org UUID;
                appointment_patient UUID;
                appointment_facility UUID;
                appointment_specialty UUID;
                appointment_status VARCHAR(20);
                walkin_facility UUID;
                walkin_allowed BOOLEAN;
            BEGIN
                SELECT organization_id INTO facility_org FROM facilities WHERE id = NEW.facility_id AND is_active;
                SELECT organization_id INTO patient_org FROM patients WHERE id = NEW.patient_id AND is_active;

                IF facility_org IS NULL OR patient_org IS NULL OR facility_org <> patient_org THEN
                    RAISE EXCEPTION 'Check-in patient and facility must be active and in the same organization';
                END IF;

                IF NEW.appointment_id IS NOT NULL THEN
                    SELECT patient_id, facility_id, facility_specialty_id, status
                      INTO appointment_patient, appointment_facility, appointment_specialty, appointment_status
                    FROM appointments WHERE id = NEW.appointment_id;

                    IF appointment_patient <> NEW.patient_id OR appointment_facility <> NEW.facility_id THEN
                        RAISE EXCEPTION 'Check-in appointment does not match patient or facility';
                    END IF;

                    IF appointment_status IN ('cancelled', 'completed', 'no_show', 'rescheduled') THEN
                        RAISE EXCEPTION 'Appointment status is not eligible for check-in';
                    END IF;

                    IF NEW.facility_specialty_id IS NOT NULL AND NEW.facility_specialty_id <> appointment_specialty THEN
                        RAISE EXCEPTION 'Check-in specialty does not match appointment specialty';
                    END IF;
                ELSE
                    SELECT facility_id, accepts_walk_ins
                      INTO walkin_facility, walkin_allowed
                    FROM facility_specialties
                    WHERE id = NEW.facility_specialty_id AND is_active;

                    IF walkin_facility IS NULL OR walkin_facility <> NEW.facility_id OR NOT walkin_allowed THEN
                        RAISE EXCEPTION 'Walk-in specialty must be active, accept walk-ins, and belong to the facility';
                    END IF;
                END IF;

                IF NEW.checkin_method = 'reception' AND NEW.checked_in_by_id IS NULL THEN
                    RAISE EXCEPTION 'Reception check-in requires checked_in_by_id';
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_patient_checkins_validate
            BEFORE INSERT OR UPDATE
            ON patient_checkins
            FOR EACH ROW EXECUTE FUNCTION validate_patient_checkin();

            CREATE OR REPLACE FUNCTION validate_checkin_token()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                checkin_appointment UUID;
            BEGIN
                IF NEW.patient_checkin_id IS NOT NULL THEN
                    SELECT appointment_id INTO checkin_appointment
                    FROM patient_checkins WHERE id = NEW.patient_checkin_id AND voided_at IS NULL;

                    IF checkin_appointment IS NULL OR checkin_appointment <> NEW.appointment_id THEN
                        RAISE EXCEPTION 'Used check-in token must reference a valid check-in for the same appointment';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_checkin_tokens_validate
            BEFORE INSERT OR UPDATE
            ON checkin_tokens
            FOR EACH ROW EXECUTE FUNCTION validate_checkin_token();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_checkin_tokens_validate ON checkin_tokens;
            DROP TRIGGER IF EXISTS trg_patient_checkins_validate ON patient_checkins;

            DROP FUNCTION IF EXISTS validate_checkin_token();
            DROP FUNCTION IF EXISTS validate_patient_checkin();
            """,
        ),
    ]
