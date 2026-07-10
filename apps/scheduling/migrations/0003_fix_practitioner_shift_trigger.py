from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0002_postgres_hardening"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
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
                department_assignment_department_id UUID;
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
                    SELECT pda.practitioner_facility_assignment_id, pda.department_id
                      INTO department_assignment_pfa, department_assignment_department_id
                    FROM practitioner_department_assignments pda
                    WHERE pda.id = NEW.practitioner_department_assignment_id
                      AND pda.is_active
                      AND pda.starts_on <= local_start
                      AND (pda.ends_on IS NULL OR pda.ends_on >= local_end);

                    IF department_assignment_pfa IS NULL OR department_assignment_pfa <> NEW.practitioner_facility_assignment_id THEN
                        RAISE EXCEPTION 'Shift department assignment is invalid for practitioner, facility, or date';
                    END IF;
                END IF;

                IF NEW.service_point_id IS NOT NULL THEN
                    SELECT sp.facility_id, sp.department_id
                      INTO service_facility, service_department
                    FROM service_points sp
                    WHERE sp.id = NEW.service_point_id
                      AND sp.is_active;

                    IF service_facility IS NULL OR service_facility <> shift_facility THEN
                        RAISE EXCEPTION 'Shift service point must be active and belong to the same facility';
                    END IF;

                    IF department_assignment_department_id IS NOT NULL
                       AND service_department IS NOT NULL
                       AND department_assignment_department_id <> service_department THEN
                        RAISE EXCEPTION 'Shift service point department must match practitioner department assignment';
                    END IF;
                END IF;

                IF NEW.consultation_room_id IS NOT NULL THEN
                    SELECT cr.facility_id, cr.department_id, cr.is_active
                      INTO room_facility, room_department, room_active
                    FROM consultation_rooms cr
                    WHERE cr.id = NEW.consultation_room_id;

                    IF room_facility IS NULL OR room_facility <> shift_facility OR NOT room_active THEN
                        RAISE EXCEPTION 'Consultation room must be active and belong to the same facility';
                    END IF;

                    IF department_assignment_department_id IS NOT NULL
                       AND room_department IS NOT NULL
                       AND department_assignment_department_id <> room_department THEN
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
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
