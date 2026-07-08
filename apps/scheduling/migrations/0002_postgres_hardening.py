from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("facilities", "0002_postgres_hardening"),
        ("patients", "0001_initial"),
        ("practitioners", "0002_postgres_hardening"),
        ("scheduling", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION validate_practitioner_leave()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                assignment_start DATE;
                assignment_end DATE;
                facility_tz TEXT;
                local_start DATE;
                local_end DATE;
            BEGIN
                SELECT pfa.starts_on, pfa.ends_on, f.timezone
                  INTO assignment_start, assignment_end, facility_tz
                FROM practitioner_facility_assignments pfa
                JOIN facilities f ON f.id = pfa.facility_id
                WHERE pfa.id = NEW.practitioner_facility_assignment_id;

                local_start := (NEW.starts_at AT TIME ZONE facility_tz)::DATE;
                local_end := (NEW.ends_at AT TIME ZONE facility_tz)::DATE;

                IF local_start < assignment_start
                   OR (assignment_end IS NOT NULL AND local_end > assignment_end) THEN
                    RAISE EXCEPTION 'Leave must remain within practitioner facility assignment dates';
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_practitioner_leave_validate
            BEFORE INSERT OR UPDATE
            ON practitioner_leave_requests
            FOR EACH ROW EXECUTE FUNCTION validate_practitioner_leave();

            ALTER TABLE practitioner_leave_requests
                ADD CONSTRAINT ex_practitioner_leave_no_overlap
                EXCLUDE USING gist (
                    practitioner_facility_assignment_id WITH =,
                    tstzrange(starts_at, ends_at, '[)') WITH &&
                )
                WHERE (status IN ('pending', 'approved'));

            CREATE OR REPLACE FUNCTION validate_practitioner_shift()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                shift_facility UUID;
                assignment_start DATE;
                assignment_end DATE;
                facility_tz TEXT;
                local_start DATE;
                local_end DATE;
                department_assignment_pfa UUID;
                department_id UUID;
                service_facility UUID;
                service_department UUID;
                room_facility UUID;
                room_department UUID;
                room_active BOOLEAN;
            BEGIN
                SELECT pfa.facility_id, pfa.starts_on, pfa.ends_on, f.timezone
                  INTO shift_facility, assignment_start, assignment_end, facility_tz
                FROM practitioner_facility_assignments pfa
                JOIN facilities f ON f.id = pfa.facility_id
                WHERE pfa.id = NEW.practitioner_facility_assignment_id;

                local_start := (NEW.starts_at AT TIME ZONE facility_tz)::DATE;
                local_end := (NEW.ends_at AT TIME ZONE facility_tz)::DATE;

                IF local_start < assignment_start
                   OR (assignment_end IS NOT NULL AND local_end > assignment_end) THEN
                    RAISE EXCEPTION 'Shift must remain within practitioner facility assignment dates';
                END IF;

                IF NEW.practitioner_department_assignment_id IS NOT NULL THEN
                    SELECT practitioner_facility_assignment_id, department_id
                      INTO department_assignment_pfa, department_id
                    FROM practitioner_department_assignments
                    WHERE id = NEW.practitioner_department_assignment_id
                      AND is_active
                      AND starts_on <= local_start
                      AND (ends_on IS NULL OR ends_on >= local_end);

                    IF department_assignment_pfa IS NULL OR department_assignment_pfa <> NEW.practitioner_facility_assignment_id THEN
                        RAISE EXCEPTION 'Shift department assignment is invalid for practitioner, facility, or date';
                    END IF;
                END IF;

                IF NEW.service_point_id IS NOT NULL THEN
                    SELECT facility_id, department_id INTO service_facility, service_department
                    FROM service_points WHERE id = NEW.service_point_id AND is_active;

                    IF service_facility IS NULL OR service_facility <> shift_facility THEN
                        RAISE EXCEPTION 'Shift service point must be active and belong to the same facility';
                    END IF;

                    IF department_id IS NOT NULL AND service_department IS NOT NULL AND department_id <> service_department THEN
                        RAISE EXCEPTION 'Shift service point department must match practitioner department assignment';
                    END IF;
                END IF;

                IF NEW.consultation_room_id IS NOT NULL THEN
                    SELECT facility_id, department_id, is_active
                      INTO room_facility, room_department, room_active
                    FROM consultation_rooms WHERE id = NEW.consultation_room_id;

                    IF room_facility IS NULL OR room_facility <> shift_facility OR NOT room_active THEN
                        RAISE EXCEPTION 'Consultation room must be active and belong to the same facility';
                    END IF;

                    IF department_id IS NOT NULL AND room_department IS NOT NULL AND department_id <> room_department THEN
                        RAISE EXCEPTION 'Consultation room department must match practitioner department assignment';
                    END IF;
                END IF;

                IF NEW.status <> 'cancelled' AND EXISTS (
                    SELECT 1
                    FROM practitioner_leave_requests l
                    WHERE l.practitioner_facility_assignment_id = NEW.practitioner_facility_assignment_id
                      AND l.status = 'approved'
                      AND tstzrange(l.starts_at, l.ends_at, '[)') && tstzrange(NEW.starts_at, NEW.ends_at, '[)')
                ) THEN
                    RAISE EXCEPTION 'Shift overlaps approved practitioner leave';
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_practitioner_shifts_validate
            BEFORE INSERT OR UPDATE
            ON practitioner_shifts
            FOR EACH ROW EXECUTE FUNCTION validate_practitioner_shift();

            ALTER TABLE practitioner_shifts
                ADD CONSTRAINT ex_practitioner_shifts_no_overlap
                EXCLUDE USING gist (
                    practitioner_facility_assignment_id WITH =,
                    tstzrange(starts_at, ends_at, '[)') WITH &&
                )
                WHERE (status <> 'cancelled');

            ALTER TABLE practitioner_shifts
                ADD CONSTRAINT ex_consultation_room_shifts_no_overlap
                EXCLUDE USING gist (
                    consultation_room_id WITH =,
                    tstzrange(starts_at, ends_at, '[)') WITH &&
                )
                WHERE (consultation_room_id IS NOT NULL AND status <> 'cancelled');

            CREATE OR REPLACE FUNCTION prevent_practitioner_shift_overlap_across_facilities()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                practitioner UUID;
            BEGIN
                IF NEW.status = 'cancelled' THEN
                    RETURN NEW;
                END IF;

                SELECT practitioner_id INTO practitioner
                FROM practitioner_facility_assignments
                WHERE id = NEW.practitioner_facility_assignment_id;

                PERFORM pg_advisory_xact_lock(hashtextextended(practitioner::TEXT, 0));

                IF EXISTS (
                    SELECT 1
                    FROM practitioner_shifts s
                    JOIN practitioner_facility_assignments pfa
                      ON pfa.id = s.practitioner_facility_assignment_id
                    WHERE pfa.practitioner_id = practitioner
                      AND s.id <> NEW.id
                      AND s.status <> 'cancelled'
                      AND tstzrange(s.starts_at, s.ends_at, '[)')
                          && tstzrange(NEW.starts_at, NEW.ends_at, '[)')
                ) THEN
                    RAISE EXCEPTION 'Practitioner cannot have overlapping shifts across facilities';
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_practitioner_shifts_global_overlap
            BEFORE INSERT OR UPDATE OF practitioner_facility_assignment_id, starts_at, ends_at, status
            ON practitioner_shifts
            FOR EACH ROW EXECUTE FUNCTION prevent_practitioner_shift_overlap_across_facilities();

            CREATE OR REPLACE FUNCTION validate_appointment()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                facility_org UUID;
                facility_tz TEXT;
                patient_org UUID;
                specialty_facility UUID;
                pfa_facility UUID;
                psa_pfa UUID;
                psa_specialty UUID;
                shift_pfa UUID;
                shift_start TIMESTAMPTZ;
                shift_end TIMESTAMPTZ;
                shift_status VARCHAR(20);
                shift_accepts BOOLEAN;
                slot_shift UUID;
                slot_specialty UUID;
                slot_start TIMESTAMPTZ;
                slot_end TIMESTAMPTZ;
                slot_status VARCHAR(20);
                local_date DATE;
                creates_cycle BOOLEAN;
            BEGIN
                SELECT organization_id, timezone INTO facility_org, facility_tz
                FROM facilities WHERE id = NEW.facility_id AND is_active;

                IF facility_org IS NULL THEN
                    RAISE EXCEPTION 'Appointment facility must be active';
                END IF;

                SELECT organization_id INTO patient_org FROM patients WHERE id = NEW.patient_id AND is_active;
                IF patient_org IS NULL OR patient_org <> facility_org THEN
                    RAISE EXCEPTION 'Appointment patient must be active and belong to facility organization';
                END IF;

                SELECT facility_id INTO specialty_facility
                FROM facility_specialties WHERE id = NEW.facility_specialty_id AND is_active;
                IF specialty_facility IS NULL OR specialty_facility <> NEW.facility_id THEN
                    RAISE EXCEPTION 'Appointment specialty must be active at the selected facility';
                END IF;

                local_date := (NEW.scheduled_start AT TIME ZONE facility_tz)::DATE;

                IF NEW.practitioner_facility_assignment_id IS NOT NULL THEN
                    SELECT facility_id INTO pfa_facility
                    FROM practitioner_facility_assignments
                    WHERE id = NEW.practitioner_facility_assignment_id
                      AND is_active
                      AND starts_on <= local_date
                      AND (ends_on IS NULL OR ends_on >= local_date);

                    IF pfa_facility IS NULL OR pfa_facility <> NEW.facility_id THEN
                        RAISE EXCEPTION 'Practitioner facility assignment is invalid for appointment';
                    END IF;
                END IF;

                IF NEW.practitioner_specialty_assignment_id IS NOT NULL THEN
                    IF NEW.practitioner_facility_assignment_id IS NULL THEN
                        RAISE EXCEPTION 'Practitioner specialty assignment requires practitioner facility assignment';
                    END IF;

                    SELECT practitioner_facility_assignment_id, facility_specialty_id
                      INTO psa_pfa, psa_specialty
                    FROM practitioner_specialty_assignments
                    WHERE id = NEW.practitioner_specialty_assignment_id
                      AND is_active
                      AND starts_on <= local_date
                      AND (ends_on IS NULL OR ends_on >= local_date);

                    IF psa_pfa IS NULL
                       OR psa_pfa <> NEW.practitioner_facility_assignment_id
                       OR psa_specialty <> NEW.facility_specialty_id THEN
                        RAISE EXCEPTION 'Practitioner specialty assignment does not match appointment';
                    END IF;
                END IF;

                IF NEW.practitioner_shift_id IS NOT NULL THEN
                    IF NEW.practitioner_facility_assignment_id IS NULL THEN
                        RAISE EXCEPTION 'Practitioner shift requires practitioner facility assignment';
                    END IF;

                    SELECT practitioner_facility_assignment_id, starts_at, ends_at, status, accepts_appointments
                      INTO shift_pfa, shift_start, shift_end, shift_status, shift_accepts
                    FROM practitioner_shifts
                    WHERE id = NEW.practitioner_shift_id;

                    IF shift_pfa <> NEW.practitioner_facility_assignment_id
                       OR shift_status = 'cancelled'
                       OR NOT shift_accepts
                       OR NEW.scheduled_start < shift_start
                       OR NEW.scheduled_end > shift_end THEN
                        RAISE EXCEPTION 'Appointment must fit an active appointment-accepting practitioner shift';
                    END IF;
                END IF;

                IF NEW.appointment_slot_id IS NOT NULL THEN
                    SELECT practitioner_shift_id, facility_specialty_id, starts_at, ends_at, status
                      INTO slot_shift, slot_specialty, slot_start, slot_end, slot_status
                    FROM appointment_slots
                    WHERE id = NEW.appointment_slot_id;

                    IF slot_shift IS NULL
                       OR NEW.practitioner_shift_id IS DISTINCT FROM slot_shift
                       OR NEW.facility_specialty_id <> slot_specialty
                       OR NEW.scheduled_start <> slot_start
                       OR NEW.scheduled_end <> slot_end
                       OR slot_status IN ('blocked', 'cancelled') THEN
                        RAISE EXCEPTION 'Appointment does not match selected appointment slot';
                    END IF;
                END IF;

                IF NEW.rescheduled_from_id IS NOT NULL THEN
                    WITH RECURSIVE chain AS (
                        SELECT id, rescheduled_from_id
                        FROM appointments
                        WHERE id = NEW.rescheduled_from_id
                        UNION ALL
                        SELECT a.id, a.rescheduled_from_id
                        FROM appointments a
                        JOIN chain c ON a.id = c.rescheduled_from_id
                    )
                    SELECT EXISTS (SELECT 1 FROM chain WHERE id = NEW.id)
                    INTO creates_cycle;

                    IF creates_cycle THEN
                        RAISE EXCEPTION 'Appointment reschedule cycle detected';
                    END IF;
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_appointments_validate
            BEFORE INSERT OR UPDATE
            ON appointments
            FOR EACH ROW EXECUTE FUNCTION validate_appointment();

            ALTER TABLE appointments
                ADD CONSTRAINT ex_appointments_practitioner_no_overlap
                EXCLUDE USING gist (
                    practitioner_facility_assignment_id WITH =,
                    tstzrange(scheduled_start, scheduled_end, '[)') WITH &&
                )
                WHERE (
                    practitioner_facility_assignment_id IS NOT NULL
                    AND status IN ('pending', 'confirmed', 'checked_in', 'queued', 'in_service')
                );

            ALTER TABLE appointments
                ADD CONSTRAINT ex_appointments_patient_no_overlap
                EXCLUDE USING gist (
                    patient_id WITH =,
                    tstzrange(scheduled_start, scheduled_end, '[)') WITH &&
                )
                WHERE (status IN ('pending', 'confirmed', 'checked_in', 'queued', 'in_service'));

            CREATE OR REPLACE FUNCTION prevent_practitioner_appointment_overlap_across_facilities()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                practitioner UUID;
            BEGIN
                IF NEW.practitioner_facility_assignment_id IS NULL
                   OR NEW.status NOT IN ('pending', 'confirmed', 'checked_in', 'queued', 'in_service') THEN
                    RETURN NEW;
                END IF;

                SELECT practitioner_id INTO practitioner
                FROM practitioner_facility_assignments
                WHERE id = NEW.practitioner_facility_assignment_id;

                PERFORM pg_advisory_xact_lock(hashtextextended(practitioner::TEXT, 1));

                IF EXISTS (
                    SELECT 1
                    FROM appointments a
                    JOIN practitioner_facility_assignments pfa
                      ON pfa.id = a.practitioner_facility_assignment_id
                    WHERE pfa.practitioner_id = practitioner
                      AND a.id <> NEW.id
                      AND a.status IN ('pending', 'confirmed', 'checked_in', 'queued', 'in_service')
                      AND tstzrange(a.scheduled_start, a.scheduled_end, '[)')
                          && tstzrange(NEW.scheduled_start, NEW.scheduled_end, '[)')
                ) THEN
                    RAISE EXCEPTION 'Practitioner cannot have overlapping appointments across facilities';
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_appointments_global_practitioner_overlap
            BEFORE INSERT OR UPDATE OF practitioner_facility_assignment_id, scheduled_start, scheduled_end, status
            ON appointments
            FOR EACH ROW EXECUTE FUNCTION prevent_practitioner_appointment_overlap_across_facilities();

            CREATE OR REPLACE FUNCTION validate_appointment_slot()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                shift_pfa UUID;
                shift_start TIMESTAMPTZ;
                shift_end TIMESTAMPTZ;
                shift_facility UUID;
                specialty_facility UUID;
                has_specialty BOOLEAN;
            BEGIN
                SELECT s.practitioner_facility_assignment_id, s.starts_at, s.ends_at, pfa.facility_id
                  INTO shift_pfa, shift_start, shift_end, shift_facility
                FROM practitioner_shifts s
                JOIN practitioner_facility_assignments pfa ON pfa.id = s.practitioner_facility_assignment_id
                WHERE s.id = NEW.practitioner_shift_id
                  AND s.status <> 'cancelled'
                  AND s.accepts_appointments;

                IF shift_pfa IS NULL OR NEW.starts_at < shift_start OR NEW.ends_at > shift_end THEN
                    RAISE EXCEPTION 'Appointment slot must fit within an active appointment-accepting shift';
                END IF;

                SELECT facility_id INTO specialty_facility
                FROM facility_specialties WHERE id = NEW.facility_specialty_id AND is_active;

                IF specialty_facility IS NULL OR specialty_facility <> shift_facility THEN
                    RAISE EXCEPTION 'Appointment slot specialty must belong to the shift facility';
                END IF;

                SELECT EXISTS (
                    SELECT 1 FROM practitioner_specialty_assignments psa
                    WHERE psa.practitioner_facility_assignment_id = shift_pfa
                      AND psa.facility_specialty_id = NEW.facility_specialty_id
                      AND psa.is_active
                      AND psa.starts_on <= (NEW.starts_at AT TIME ZONE (SELECT timezone FROM facilities WHERE id = shift_facility))::DATE
                      AND (psa.ends_on IS NULL OR psa.ends_on >= (NEW.ends_at AT TIME ZONE (SELECT timezone FROM facilities WHERE id = shift_facility))::DATE)
                ) INTO has_specialty;

                IF NOT has_specialty THEN
                    RAISE EXCEPTION 'Practitioner does not have an active specialty assignment for this slot';
                END IF;

                RETURN NEW;
            END;
            $$;

            CREATE TRIGGER trg_appointment_slots_validate
            BEFORE INSERT OR UPDATE
            ON appointment_slots
            FOR EACH ROW EXECUTE FUNCTION validate_appointment_slot();

            CREATE TRIGGER trg_appointment_status_history_append_only
            BEFORE UPDATE OR DELETE ON appointment_status_history
            FOR EACH ROW EXECUTE FUNCTION prevent_history_mutation();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_appointment_status_history_append_only ON appointment_status_history;
            DROP TRIGGER IF EXISTS trg_appointment_slots_validate ON appointment_slots;
            DROP TRIGGER IF EXISTS trg_appointments_global_practitioner_overlap ON appointments;
            DROP TRIGGER IF EXISTS trg_appointments_validate ON appointments;
            DROP TRIGGER IF EXISTS trg_practitioner_shifts_global_overlap ON practitioner_shifts;
            DROP TRIGGER IF EXISTS trg_practitioner_shifts_validate ON practitioner_shifts;
            DROP TRIGGER IF EXISTS trg_practitioner_leave_validate ON practitioner_leave_requests;

            ALTER TABLE appointments DROP CONSTRAINT IF EXISTS ex_appointments_patient_no_overlap;
            ALTER TABLE appointments DROP CONSTRAINT IF EXISTS ex_appointments_practitioner_no_overlap;
            ALTER TABLE practitioner_shifts DROP CONSTRAINT IF EXISTS ex_consultation_room_shifts_no_overlap;
            ALTER TABLE practitioner_shifts DROP CONSTRAINT IF EXISTS ex_practitioner_shifts_no_overlap;
            ALTER TABLE practitioner_leave_requests DROP CONSTRAINT IF EXISTS ex_practitioner_leave_no_overlap;

            DROP FUNCTION IF EXISTS validate_appointment_slot();
            DROP FUNCTION IF EXISTS prevent_practitioner_appointment_overlap_across_facilities();
            DROP FUNCTION IF EXISTS validate_appointment();
            DROP FUNCTION IF EXISTS prevent_practitioner_shift_overlap_across_facilities();
            DROP FUNCTION IF EXISTS validate_practitioner_shift();
            DROP FUNCTION IF EXISTS validate_practitioner_leave();
            """,
        ),
    ]
