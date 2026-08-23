-- UI demo seed data for local development.
-- Source of truth: intelligent_patient_flow_database.sql and Django models.
-- This file is idempotent for the deterministic ui_demo_* records.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION pg_temp.ui_demo_uuid(seed TEXT)
RETURNS UUID
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT (
        SUBSTR(MD5('ui-demo:' || seed), 1, 8) || '-' ||
        SUBSTR(MD5('ui-demo:' || seed), 9, 4) || '-' ||
        SUBSTR(MD5('ui-demo:' || seed), 13, 4) || '-' ||
        SUBSTR(MD5('ui-demo:' || seed), 17, 4) || '-' ||
        SUBSTR(MD5('ui-demo:' || seed), 21, 12)
    )::UUID;
$$;

CREATE OR REPLACE FUNCTION pg_temp.ui_demo_hash(seed TEXT)
RETURNS CHAR(64)
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT ENCODE(DIGEST('ui-demo:' || seed, 'sha256'), 'hex')::CHAR(64);
$$;

CREATE OR REPLACE FUNCTION pg_temp.ui_demo_local_ts(day_offset INTEGER, local_time TIME)
RETURNS TIMESTAMPTZ
LANGUAGE SQL
STABLE
AS $$
    SELECT ((CURRENT_DATE + day_offset + local_time) AT TIME ZONE 'Africa/Dar_es_Salaam');
$$;

-- Django model defaults are application-level, but the SQL schema defines
-- database-level timestamp defaults. Align local direct-SQL seeding with that
-- schema behavior so seed inserts stay constraint-safe.
DO $$
DECLARE
    seed_table TEXT;
BEGIN
    FOREACH seed_table IN ARRAY ARRAY[
        'organizations', 'facility_types', 'facilities', 'departments', 'specialties',
        'facility_specialties', 'service_point_types', 'service_points', 'consultation_rooms',
        'facility_operating_hours', 'facility_schedule_exceptions', 'users', 'roles',
        'permissions', 'role_permissions', 'user_memberships', 'user_role_assignments',
        'patients', 'patient_identifier_types', 'patient_identifiers', 'patient_addresses',
        'relationship_types', 'patient_related_persons', 'related_person_contacts',
        'patient_access_grants', 'practitioner_types', 'practitioners',
        'practitioner_facility_assignments', 'practitioner_department_assignments',
        'practitioner_specialty_assignments', 'practitioner_credential_types',
        'practitioner_credentials', 'practitioner_availability_periods',
        'practitioner_leave_requests', 'practitioner_shifts', 'appointment_slots',
        'appointments', 'patient_checkins', 'queues', 'queue_entries',
        'patient_notifications', 'user_push_devices', 'facility_flow_settings',
        'report_exports'
    ] LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = seed_table AND column_name = 'created_at'
        ) THEN
            EXECUTE FORMAT('ALTER TABLE %I ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP', seed_table);
        END IF;

        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = seed_table AND column_name = 'updated_at'
        ) THEN
            EXECUTE FORMAT('ALTER TABLE %I ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP', seed_table);
        END IF;
    END LOOP;

    FOREACH seed_table IN ARRAY ARRAY[
        'checkin_tokens', 'queue_transfers', 'queue_entry_events',
        'queue_wait_time_predictions', 'audit_logs'
    ] LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = seed_table AND column_name = 'created_at'
        ) THEN
            EXECUTE FORMAT('ALTER TABLE %I ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP', seed_table);
        END IF;
    END LOOP;
END
$$;

-- ---------------------------------------------------------------------
-- Facilities foundation
-- ---------------------------------------------------------------------

INSERT INTO organizations (id, name, legal_name, code, email, phone_number, registration_number, is_active)
SELECT
    pg_temp.ui_demo_uuid('organization-' || n),
    (ARRAY['Dar Afya Network','Kilimanjaro Care Group','Mwanza Lakeside Health','Zanzibar Wellness Trust','Dodoma Regional Care'])[n],
    (ARRAY['Dar Afya Network Ltd','Kilimanjaro Care Group Ltd','Mwanza Lakeside Health Ltd','Zanzibar Wellness Trust','Dodoma Regional Care Ltd'])[n],
    (ARRAY['UIDAR','UIKILI','UIMZA','UIZNZ','UIDOM'])[n],
    LOWER((ARRAY['info@darafya.example','hello@kilicare.example','care@mwanzahealth.example','support@znzwellness.example','info@domcare.example'])[n]),
    '+25571000000' || n,
    'UI-REG-2026-' || LPAD(n::TEXT, 3, '0'),
    TRUE
FROM GENERATE_SERIES(1, 5) AS n
ON CONFLICT DO NOTHING;

INSERT INTO facility_types (id, name, code, description, is_active)
VALUES
    (pg_temp.ui_demo_uuid('facility-type-1'), 'UI Demo Hospital', 'UIHOSP', 'Full-service hospital for UI testing.', TRUE),
    (pg_temp.ui_demo_uuid('facility-type-2'), 'UI Demo Clinic', 'UICLINIC', 'Outpatient clinic for UI testing.', TRUE),
    (pg_temp.ui_demo_uuid('facility-type-3'), 'UI Demo Health Centre', 'UIHC', 'Health centre for UI testing.', TRUE),
    (pg_temp.ui_demo_uuid('facility-type-4'), 'UI Demo Diagnostic Centre', 'UIDIAG', 'Diagnostic centre for UI testing.', TRUE)
ON CONFLICT DO NOTHING;

INSERT INTO facilities (
    id, organization_id, facility_type_id, name, code, license_number, email,
    phone_number, address_line1, country_code, region, district, ward,
    latitude, longitude, timezone, is_primary, is_active
)
SELECT
    pg_temp.ui_demo_uuid('facility-' || n),
    pg_temp.ui_demo_uuid('organization-' || (((n - 1) % 5) + 1)),
    pg_temp.ui_demo_uuid('facility-type-' || (((n - 1) % 4) + 1)),
    (ARRAY[
        'Muhimbili UI Demo Hospital','Kinondoni UI Demo Clinic','KCMC UI Demo Hospital',
        'Arusha City UI Demo Clinic','Bugando UI Demo Hospital','Nyamagana UI Demo Clinic',
        'Mnazi Mmoja UI Demo Hospital','Stone Town UI Demo Clinic','Dodoma Central UI Demo Hospital',
        'Chamwino UI Demo Health Centre'
    ])[n],
    'UIFAC' || LPAD(n::TEXT, 2, '0'),
    'UI-LIC-' || LPAD(n::TEXT, 4, '0'),
    LOWER('facility' || n || '@patientflow.example'),
    '+2557200000' || LPAD(n::TEXT, 2, '0'),
    (ARRAY['Upanga Road','Kijitonyama Road','Moshi Urban Road','Sakina Road','Bugando Hill','Nyamagana Street','Vuga Road','Forodhani Street','Nzuguni Road','Chamwino Road'])[n],
    'TZ',
    (ARRAY['Dar es Salaam','Dar es Salaam','Kilimanjaro','Arusha','Mwanza','Mwanza','Zanzibar Urban West','Zanzibar Urban West','Dodoma','Dodoma'])[n],
    (ARRAY['Ilala','Kinondoni','Moshi Urban','Arusha City','Ilemela','Nyamagana','Mjini','Mjini','Dodoma Urban','Chamwino'])[n],
    (ARRAY['Upanga','Kijitonyama','Mawenzi','Sakina','Bugando','Nyamagana','Vuga','Stone Town','Nzuguni','Chamwino'])[n],
    -6.800000 + (n::NUMERIC / 1000),
    39.2000000 + (n::NUMERIC / 1000),
    'Africa/Dar_es_Salaam',
    n <= 5,
    TRUE
FROM GENERATE_SERIES(1, 10) AS n
ON CONFLICT DO NOTHING;

INSERT INTO departments (id, facility_id, parent_department_id, name, code, description, is_active)
SELECT
    pg_temp.ui_demo_uuid('department-' || f || '-' || d),
    pg_temp.ui_demo_uuid('facility-' || f),
    NULL,
    (ARRAY['Outpatient Department','Laboratory Department','Pharmacy Department'])[d],
    (ARRAY['OPD','LAB','PHA'])[d],
    'UI demo ' || LOWER((ARRAY['outpatient','laboratory','pharmacy'])[d]) || ' department.',
    TRUE
FROM GENERATE_SERIES(1, 10) AS f
CROSS JOIN GENERATE_SERIES(1, 3) AS d
ON CONFLICT DO NOTHING;

INSERT INTO specialties (id, parent_specialty_id, name, code, description, is_active)
SELECT
    pg_temp.ui_demo_uuid('specialty-' || n),
    NULL,
    (ARRAY['General Medicine','Paediatrics','Obstetrics and Gynaecology','Cardiology','Dental Care','Eye Clinic','ENT','Orthopaedics','Dermatology','Radiology'])[n],
    (ARRAY['GENMED','PAEDS','OBGYN','CARD','DENT','EYE','ENT','ORTHO','DERM','RAD'])[n],
    'UI demo specialty.',
    TRUE
FROM GENERATE_SERIES(1, 10) AS n
ON CONFLICT DO NOTHING;

INSERT INTO facility_specialties (
    id, facility_id, specialty_id, department_id, appointment_duration_minutes,
    accepts_appointments, accepts_walk_ins, requires_referral, is_active
)
SELECT
    pg_temp.ui_demo_uuid('facility-specialty-' || f || '-' || d),
    pg_temp.ui_demo_uuid('facility-' || f),
    pg_temp.ui_demo_uuid('specialty-' || ((((f + d - 2) % 10) + 1))),
    pg_temp.ui_demo_uuid('department-' || f || '-' || d),
    (ARRAY[30, 20, 15])[d],
    TRUE,
    d = 1,
    d IN (2, 3),
    TRUE
FROM GENERATE_SERIES(1, 10) AS f
CROSS JOIN GENERATE_SERIES(1, 3) AS d
ON CONFLICT DO NOTHING;

INSERT INTO service_point_types (id, name, code, description, is_active)
VALUES
    (pg_temp.ui_demo_uuid('service-point-type-1'), 'UI Reception Desk', 'UIRECEP', 'Reception and registration desk.', TRUE),
    (pg_temp.ui_demo_uuid('service-point-type-2'), 'UI Consultation Desk', 'UICONS', 'Clinical consultation service point.', TRUE),
    (pg_temp.ui_demo_uuid('service-point-type-3'), 'UI Laboratory Counter', 'UILAB', 'Laboratory sample and result counter.', TRUE),
    (pg_temp.ui_demo_uuid('service-point-type-4'), 'UI Pharmacy Counter', 'UIPHA', 'Pharmacy dispensing counter.', TRUE)
ON CONFLICT DO NOTHING;

INSERT INTO service_points (
    id, facility_id, department_id, service_point_type_id, name, code,
    location_description, floor, display_order, is_active
)
SELECT
    pg_temp.ui_demo_uuid('service-point-' || f || '-' || d),
    pg_temp.ui_demo_uuid('facility-' || f),
    pg_temp.ui_demo_uuid('department-' || f || '-' || d),
    pg_temp.ui_demo_uuid('service-point-type-' || CASE WHEN d = 1 THEN 2 WHEN d = 2 THEN 3 ELSE 4 END),
    (ARRAY['OPD Service Desk','Laboratory Counter','Pharmacy Counter'])[d],
    (ARRAY['OPD','LAB','PHA'])[d],
    'Main block, wing ' || d,
    CASE WHEN d = 1 THEN 'Ground' ELSE 'First' END,
    d,
    TRUE
FROM GENERATE_SERIES(1, 10) AS f
CROSS JOIN GENERATE_SERIES(1, 3) AS d
ON CONFLICT DO NOTHING;

INSERT INTO consultation_rooms (
    id, facility_id, department_id, name, code, location_description, floor, capacity, is_active
)
SELECT
    pg_temp.ui_demo_uuid('consultation-room-' || f || '-' || d),
    pg_temp.ui_demo_uuid('facility-' || f),
    pg_temp.ui_demo_uuid('department-' || f || '-' || d),
    (ARRAY['Consultation Room','Procedure Room','Review Room'])[d] || ' ' || d,
    'ROOM' || d,
    'Clinical wing room ' || d,
    CASE WHEN d = 1 THEN 'Ground' ELSE 'First' END,
    CASE WHEN d = 1 THEN 2 ELSE 1 END,
    TRUE
FROM GENERATE_SERIES(1, 10) AS f
CROSS JOIN GENERATE_SERIES(1, 3) AS d
ON CONFLICT DO NOTHING;

INSERT INTO facility_operating_hours (
    id, facility_id, day_of_week, period_order, opens_at, closes_at, closes_next_day, is_24_hours, is_active
)
SELECT
    pg_temp.ui_demo_uuid('operating-hour-' || f || '-' || d),
    pg_temp.ui_demo_uuid('facility-' || f),
    d,
    1,
    CASE WHEN d BETWEEN 1 AND 6 THEN TIME '07:30' ELSE NULL END,
    CASE WHEN d BETWEEN 1 AND 6 THEN TIME '18:00' ELSE NULL END,
    FALSE,
    d = 7,
    TRUE
FROM GENERATE_SERIES(1, 10) AS f
CROSS JOIN GENERATE_SERIES(1, 7) AS d
ON CONFLICT DO NOTHING;

INSERT INTO facility_schedule_exceptions (
    id, facility_id, exception_date, period_order, is_closed, opens_at, closes_at,
    closes_next_day, is_24_hours, reason, is_active
)
SELECT
    pg_temp.ui_demo_uuid('schedule-exception-' || f),
    pg_temp.ui_demo_uuid('facility-' || f),
    DATE '2026-08-08' + (f - 1),
    1,
    TRUE,
    NULL,
    NULL,
    FALSE,
    FALSE,
    'UI demo public holiday closure',
    TRUE
FROM GENERATE_SERIES(1, 10) AS f
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- Accounts, roles, and dynamic permissions
-- Demo password for seeded users: DemoPass123!
-- ---------------------------------------------------------------------

INSERT INTO users (
    id, email, phone_number, password, first_name, middle_name, last_name,
    email_verified_at, phone_verified_at, is_active, is_staff, is_superuser, date_joined
)
SELECT
    pg_temp.ui_demo_uuid('user-' || n),
    LOWER('demo.user' || LPAD(n::TEXT, 2, '0') || '@patientflow.local'),
    '+2557300000' || LPAD(n::TEXT, 2, '0'),
    'pbkdf2_sha256$720000$ui_demo_seed$pX9xxCR1S4l5Bz4TFlZDe2GLMvLQswhpCOZ4uRNCmAo=',
    (ARRAY['Asha','Juma','Neema','Baraka','Rehema','Hassan','Fatma','Joseph','Mariam','Godfrey'])[((n - 1) % 10) + 1],
    NULL,
    (ARRAY['Msuya','Mwakyusa','Kimaro','Mrope','Nyerere','Mwakalinga','Kassim','Mfinanga','Sanga','Mushi'])[((n - 1) % 10) + 1],
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    TRUE,
    n = 1,
    n = 1,
    CURRENT_TIMESTAMP - (n || ' days')::INTERVAL
FROM GENERATE_SERIES(1, 30) AS n
ON CONFLICT DO NOTHING;

INSERT INTO permissions (id, name, code, module, action, description, is_active, created_by_id)
SELECT
    pg_temp.ui_demo_uuid('permission-' || code),
    INITCAP(REPLACE(REPLACE(code, '_', ' '), '.', ' ')),
    code,
    SPLIT_PART(code, '.', 1),
    SPLIT_PART(code, '.', 2),
    'UI demo permission.',
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM (
    VALUES
    ('accounts_user.view'), ('accounts_user.create'), ('accounts_user.update'), ('accounts_user.deactivate'),
    ('accounts_role.view'), ('accounts_role.manage'), ('accounts_permission.view'), ('accounts_permission.manage'),
    ('facilities_organization.view'), ('facilities_organization.create'), ('facilities_organization.update'), ('facilities_organization.deactivate'),
    ('facilities_facility.view'), ('facilities_facility.create'), ('facilities_facility.update'), ('facilities_facility.deactivate'),
    ('facilities_department.manage'), ('facilities_specialty.manage'), ('facilities_service_point.manage'), ('facilities_room.manage'), ('facilities_schedule.manage'), ('facilities_settings.manage'),
    ('patients_patient.view'), ('patients_patient.create'), ('patients_patient.update'), ('patients_patient.deactivate'),
    ('patients_identifier_type.manage'), ('patients_identifier.manage'), ('patients_address.manage'), ('patients_relationship_type.manage'), ('patients_related_person.manage'), ('patients_related_person_contact.manage'), ('patients_access_grant.manage'),
    ('practitioners_type.view'), ('practitioners_type.manage'), ('practitioners_practitioner.view'), ('practitioners_practitioner.create'), ('practitioners_practitioner.update'), ('practitioners_practitioner.deactivate'), ('practitioners_assignment.manage'), ('practitioners_credential_type.manage'), ('practitioners_credential.manage'), ('practitioners_credential.verify'),
    ('scheduling_availability.manage'), ('scheduling_leave.manage'), ('scheduling_shift.manage'), ('scheduling_slot.manage'), ('scheduling_appointment.view'), ('scheduling_appointment.create'), ('scheduling_appointment.update'), ('scheduling_appointment.cancel'), ('scheduling_appointment.reschedule'), ('scheduling_appointment.assign'),
    ('checkins_checkin.view'), ('checkins_checkin.create'), ('checkins_checkin.void'), ('checkins_token.create'), ('checkins_token.revoke'), ('checkins_token.consume'),
    ('queueing_queue.view'), ('queueing_queue.manage'), ('queueing_entry.view'), ('queueing_entry.create'), ('queueing_entry.call'), ('queueing_entry.skip'), ('queueing_entry.start_service'), ('queueing_entry.complete_service'), ('queueing_entry.cancel'), ('queueing_entry.transfer'), ('queueing_priority.manage'),
    ('intelligence_prediction.view'), ('intelligence_prediction.create'), ('intelligence_prediction.evaluate'), ('intelligence_forecast.view'), ('intelligence_slot_suggestion.view'),
    ('notifications_notification.view'), ('notifications_notification.create'), ('notifications_notification.send'), ('notifications_notification.cancel'), ('notifications_device.view'), ('notifications_device.manage'),
    ('reporting_report.view'), ('reporting_report.generate'), ('reporting_report.download'), ('reporting_report.cancel'), ('reporting_analytics.view'),
    ('audit_log.view'), ('audit_log.create'), ('audit_log.export'), ('audit_log.summary')
) AS permission_codes(code)
ON CONFLICT DO NOTHING;

INSERT INTO roles (id, organization_id, facility_id, name, code, description, is_active, created_by_id)
SELECT pg_temp.ui_demo_uuid('role-platform-admin'), NULL, NULL, 'UI Demo Platform Admin', 'UI_PLATFORM_ADMIN', 'Demo platform role with all UI permissions.', TRUE, pg_temp.ui_demo_uuid('user-1')
ON CONFLICT DO NOTHING;

INSERT INTO roles (id, organization_id, facility_id, name, code, description, is_active, created_by_id)
SELECT
    pg_temp.ui_demo_uuid('role-org-admin-' || n),
    pg_temp.ui_demo_uuid('organization-' || n),
    NULL,
    'UI Demo Organization Admin',
    'UI_ORG_ADMIN',
    'Demo organization administrator role.',
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 5) AS n
ON CONFLICT DO NOTHING;

INSERT INTO roles (id, organization_id, facility_id, name, code, description, is_active, created_by_id)
SELECT
    pg_temp.ui_demo_uuid('role-facility-operator-' || f),
    pg_temp.ui_demo_uuid('organization-' || (((f - 1) % 5) + 1)),
    pg_temp.ui_demo_uuid('facility-' || f),
    'UI Demo Facility Operator',
    'UI_FACILITY_OPERATOR',
    'Demo facility operator role.',
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 10) AS f
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (id, role_id, permission_id, granted_by_id, is_active)
SELECT
    pg_temp.ui_demo_uuid('role-permission-' || r.id || '-' || p.id),
    r.id,
    p.id,
    pg_temp.ui_demo_uuid('user-1'),
    TRUE
FROM roles r
CROSS JOIN permissions p
WHERE r.code IN ('UI_PLATFORM_ADMIN', 'UI_ORG_ADMIN', 'UI_FACILITY_OPERATOR')
ON CONFLICT DO NOTHING;

INSERT INTO user_memberships (id, user_id, organization_id, facility_id, starts_at, is_active, created_by_id)
SELECT
    pg_temp.ui_demo_uuid('membership-' || n),
    pg_temp.ui_demo_uuid('user-' || n),
    pg_temp.ui_demo_uuid('organization-' || (((((n - 1) % 10) + 1 - 1) % 5) + 1)),
    pg_temp.ui_demo_uuid('facility-' || (((n - 1) % 10) + 1)),
    CURRENT_TIMESTAMP - INTERVAL '30 days',
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 30) AS n
ON CONFLICT DO NOTHING;

INSERT INTO user_role_assignments (id, user_id, role_id, assigned_by_id, starts_at, is_active)
SELECT pg_temp.ui_demo_uuid('user-role-1'), pg_temp.ui_demo_uuid('user-1'), pg_temp.ui_demo_uuid('role-platform-admin'), pg_temp.ui_demo_uuid('user-1'), CURRENT_TIMESTAMP - INTERVAL '30 days', TRUE
ON CONFLICT DO NOTHING;

INSERT INTO user_role_assignments (id, user_id, role_id, assigned_by_id, starts_at, is_active)
SELECT
    pg_temp.ui_demo_uuid('user-org-role-' || n),
    pg_temp.ui_demo_uuid('user-' || (n + 1)),
    pg_temp.ui_demo_uuid('role-org-admin-' || n),
    pg_temp.ui_demo_uuid('user-1'),
    CURRENT_TIMESTAMP - INTERVAL '30 days',
    TRUE
FROM GENERATE_SERIES(1, 5) AS n
ON CONFLICT DO NOTHING;

INSERT INTO user_role_assignments (id, user_id, role_id, assigned_by_id, starts_at, is_active)
SELECT
    pg_temp.ui_demo_uuid('user-facility-role-' || n),
    pg_temp.ui_demo_uuid('user-' || n),
    pg_temp.ui_demo_uuid('role-facility-operator-' || (((n - 1) % 10) + 1)),
    pg_temp.ui_demo_uuid('user-1'),
    CURRENT_TIMESTAMP - INTERVAL '30 days',
    TRUE
FROM GENERATE_SERIES(7, 30) AS n
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- Patients
-- ---------------------------------------------------------------------

INSERT INTO patients (
    id, organization_id, user_id, registered_facility_id, patient_number,
    first_name, middle_name, last_name, date_of_birth, date_of_birth_is_estimated,
    sex_code, email, phone_number, is_active, created_by_id
)
SELECT
    pg_temp.ui_demo_uuid('patient-' || n),
    pg_temp.ui_demo_uuid('organization-' || (((n - 1) % 5) + 1)),
    CASE WHEN n <= 10 THEN pg_temp.ui_demo_uuid('user-' || (n + 10)) ELSE NULL END,
    pg_temp.ui_demo_uuid('facility-' || (((n - 1) % 5) + 1)),
    'UIPAT-' || LPAD(n::TEXT, 5, '0'),
    (ARRAY['Amina','Zawadi','Halima','Upendo','Jasiri','Tumaini','Faraja','Saidi','Bahati','Tunu'])[((n - 1) % 10) + 1],
    NULL,
    (ARRAY['Mrema','Ngowi','Massawe','Komba','Macha','Lema','Mwakasege','Mboya','Kileo','Komba'])[((n - 1) % 10) + 1],
    DATE '1970-01-01' + ((n * 137) % 15000),
    FALSE,
    (ARRAY['female','male','female','male','unknown'])[((n - 1) % 5) + 1],
    LOWER('patient' || LPAD(n::TEXT, 3, '0') || '@example.test'),
    '+2557400000' || LPAD(n::TEXT, 2, '0'),
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 60) AS n
ON CONFLICT DO NOTHING;

INSERT INTO patient_identifier_types (id, organization_id, name, code, description, is_sensitive, is_active, created_by_id)
VALUES
    (pg_temp.ui_demo_uuid('patient-identifier-type-nida'), NULL, 'UI Demo National ID', 'UINIDA', 'Demo national identifier type.', TRUE, TRUE, pg_temp.ui_demo_uuid('user-1')),
    (pg_temp.ui_demo_uuid('patient-identifier-type-insurance'), NULL, 'UI Demo Insurance Number', 'UIINS', 'Demo insurance identifier type.', TRUE, TRUE, pg_temp.ui_demo_uuid('user-1'))
ON CONFLICT DO NOTHING;

INSERT INTO patient_identifiers (
    id, patient_id, identifier_type_id, value_encrypted, value_hash, last_four,
    issuing_country_code, issuing_authority, issued_on, expires_on, verified_at,
    verified_by_id, is_primary, is_active, created_by_id
)
SELECT
    pg_temp.ui_demo_uuid('patient-identifier-' || n),
    pg_temp.ui_demo_uuid('patient-' || n),
    pg_temp.ui_demo_uuid('patient-identifier-type-nida'),
    'enc:ui-demo-patient-identifier-' || n,
    pg_temp.ui_demo_hash('patient-identifier-' || n),
    LPAD((1000 + n)::TEXT, 4, '0'),
    'TZ',
    'UI Demo Registry',
    DATE '2018-01-01',
    DATE '2030-12-31',
    CURRENT_TIMESTAMP - INTERVAL '10 days',
    pg_temp.ui_demo_uuid('user-1'),
    TRUE,
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 50) AS n
ON CONFLICT DO NOTHING;

INSERT INTO patient_addresses (
    id, patient_id, label, address_line1_encrypted, country_code, region,
    district, ward, postal_code, latitude, longitude, is_primary, is_active, created_by_id
)
SELECT
    pg_temp.ui_demo_uuid('patient-address-' || n),
    pg_temp.ui_demo_uuid('patient-' || n),
    'Home',
    'enc:ui-demo-address-line-1-' || n,
    'TZ',
    (ARRAY['Dar es Salaam','Kilimanjaro','Mwanza','Zanzibar Urban West','Dodoma'])[((n - 1) % 5) + 1],
    (ARRAY['Ilala','Moshi Urban','Nyamagana','Mjini','Dodoma Urban'])[((n - 1) % 5) + 1],
    (ARRAY['Upanga','Mawenzi','Nyamagana','Vuga','Nzuguni'])[((n - 1) % 5) + 1],
    NULL,
    -6.80 + (n::NUMERIC / 1000),
    39.20 + (n::NUMERIC / 1000),
    TRUE,
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 50) AS n
ON CONFLICT DO NOTHING;

INSERT INTO relationship_types (id, name, code, description, is_active, created_by_id)
VALUES
    (pg_temp.ui_demo_uuid('relationship-type-spouse'), 'UI Demo Spouse', 'UISPOUSE', 'Demo relationship type.', TRUE, pg_temp.ui_demo_uuid('user-1')),
    (pg_temp.ui_demo_uuid('relationship-type-parent'), 'UI Demo Parent', 'UIPARENT', 'Demo relationship type.', TRUE, pg_temp.ui_demo_uuid('user-1')),
    (pg_temp.ui_demo_uuid('relationship-type-sibling'), 'UI Demo Sibling', 'UISIBLING', 'Demo relationship type.', TRUE, pg_temp.ui_demo_uuid('user-1'))
ON CONFLICT DO NOTHING;

INSERT INTO patient_related_persons (
    id, patient_id, relationship_type_id, linked_user_id, first_name, middle_name, last_name,
    is_guardian, is_caregiver, is_next_of_kin, is_emergency_contact, priority_order,
    is_active, created_by_id
)
SELECT
    pg_temp.ui_demo_uuid('patient-related-person-' || n),
    pg_temp.ui_demo_uuid('patient-' || n),
    pg_temp.ui_demo_uuid('relationship-type-' || (ARRAY['spouse','parent','sibling'])[((n - 1) % 3) + 1]),
    NULL,
    (ARRAY['Salma','Yusuph','Rose','Peter','Hadija'])[((n - 1) % 5) + 1],
    NULL,
    (ARRAY['Msuya','Mwakyusa','Kassim','Macha','Mushi'])[((n - 1) % 5) + 1],
    n % 3 = 0,
    n % 4 = 0,
    TRUE,
    TRUE,
    1,
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 30) AS n
ON CONFLICT DO NOTHING;

INSERT INTO related_person_contacts (
    id, related_person_id, channel, label, value_encrypted, value_hash,
    verified_at, verified_by_id, is_primary, is_active, created_by_id
)
SELECT
    pg_temp.ui_demo_uuid('related-person-contact-' || n),
    pg_temp.ui_demo_uuid('patient-related-person-' || n),
    'phone',
    'Mobile',
    'enc:ui-demo-related-contact-' || n,
    pg_temp.ui_demo_hash('related-person-contact-' || n),
    CURRENT_TIMESTAMP - INTERVAL '5 days',
    pg_temp.ui_demo_uuid('user-1'),
    TRUE,
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 30) AS n
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- Practitioners and scheduling foundation
-- ---------------------------------------------------------------------

INSERT INTO practitioner_types (id, name, code, description, requires_license, is_active, created_by_id)
VALUES
    (pg_temp.ui_demo_uuid('practitioner-type-doctor'), 'UI Demo Doctor', 'UIDOCTOR', 'Demo doctor type.', TRUE, TRUE, pg_temp.ui_demo_uuid('user-1')),
    (pg_temp.ui_demo_uuid('practitioner-type-nurse'), 'UI Demo Nurse', 'UINURSE', 'Demo nurse type.', TRUE, TRUE, pg_temp.ui_demo_uuid('user-1')),
    (pg_temp.ui_demo_uuid('practitioner-type-clinical-officer'), 'UI Demo Clinical Officer', 'UICO', 'Demo clinical officer type.', TRUE, TRUE, pg_temp.ui_demo_uuid('user-1')),
    (pg_temp.ui_demo_uuid('practitioner-type-lab-tech'), 'UI Demo Lab Technologist', 'UILABTECH', 'Demo lab technologist type.', TRUE, TRUE, pg_temp.ui_demo_uuid('user-1')),
    (pg_temp.ui_demo_uuid('practitioner-type-pharmacist'), 'UI Demo Pharmacist', 'UIPHARMA', 'Demo pharmacist type.', TRUE, TRUE, pg_temp.ui_demo_uuid('user-1'))
ON CONFLICT DO NOTHING;

INSERT INTO practitioners (
    id, organization_id, user_id, practitioner_type_id, practitioner_number,
    first_name, middle_name, last_name, preferred_name, email, phone_number,
    is_active, created_by_id
)
SELECT
    pg_temp.ui_demo_uuid('practitioner-' || n),
    pg_temp.ui_demo_uuid('organization-' || (((n - 1) % 5) + 1)),
    pg_temp.ui_demo_uuid('user-' || n),
    pg_temp.ui_demo_uuid('practitioner-type-' || (ARRAY['doctor','nurse','clinical-officer','lab-tech','pharmacist'])[((n - 1) % 5) + 1]),
    'UIPRAC-' || LPAD(n::TEXT, 5, '0'),
    (ARRAY['Dkt. Asha','Dkt. Juma','Dkt. Neema','Dkt. Hassan','Dkt. Fatma'])[((n - 1) % 5) + 1],
    NULL,
    (ARRAY['Moshi','Mlay','Sanga','Mrope','Kimaro'])[((n - 1) % 5) + 1],
    NULL,
    LOWER('practitioner' || LPAD(n::TEXT, 2, '0') || '@patientflow.local'),
    '+2557500000' || LPAD(n::TEXT, 2, '0'),
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 30) AS n
ON CONFLICT DO NOTHING;

INSERT INTO practitioner_facility_assignments (
    id, practitioner_id, facility_id, starts_on, ends_on, is_primary, is_active, assigned_by_id
)
SELECT
    pg_temp.ui_demo_uuid('practitioner-facility-assignment-' || n),
    pg_temp.ui_demo_uuid('practitioner-' || n),
    pg_temp.ui_demo_uuid('facility-' || (((n - 1) % 5) + 1)),
    DATE '2026-01-01',
    NULL,
    TRUE,
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 30) AS n
ON CONFLICT DO NOTHING;

INSERT INTO practitioner_department_assignments (
    id, practitioner_facility_assignment_id, department_id, starts_on, ends_on, is_primary, is_active, assigned_by_id
)
SELECT
    pg_temp.ui_demo_uuid('practitioner-department-assignment-' || n),
    pg_temp.ui_demo_uuid('practitioner-facility-assignment-' || n),
    pg_temp.ui_demo_uuid('department-' || (((n - 1) % 5) + 1) || '-1'),
    DATE '2026-01-01',
    NULL,
    TRUE,
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 30) AS n
ON CONFLICT DO NOTHING;

INSERT INTO practitioner_specialty_assignments (
    id, practitioner_facility_assignment_id, facility_specialty_id, starts_on, ends_on, is_primary, is_active, assigned_by_id
)
SELECT
    pg_temp.ui_demo_uuid('practitioner-specialty-assignment-' || n),
    pg_temp.ui_demo_uuid('practitioner-facility-assignment-' || n),
    pg_temp.ui_demo_uuid('facility-specialty-' || (((n - 1) % 5) + 1) || '-1'),
    DATE '2026-01-01',
    NULL,
    TRUE,
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 30) AS n
ON CONFLICT DO NOTHING;

INSERT INTO practitioner_credential_types (
    id, organization_id, name, code, description, country_code,
    requires_expiry_date, requires_verification, is_active, created_by_id
)
VALUES
    (pg_temp.ui_demo_uuid('practitioner-credential-type-license'), NULL, 'UI Demo Medical License', 'UIMEDLIC', 'Demo license credential.', 'TZ', TRUE, TRUE, TRUE, pg_temp.ui_demo_uuid('user-1'))
ON CONFLICT DO NOTHING;

INSERT INTO practitioner_credentials (
    id, practitioner_id, credential_type_id, credential_number_encrypted, credential_number_hash,
    last_four, issuing_authority, issuing_country_code, issued_on, expires_on,
    verification_status, verified_at, verified_by_id, is_active, created_by_id
)
SELECT
    pg_temp.ui_demo_uuid('practitioner-credential-' || n),
    pg_temp.ui_demo_uuid('practitioner-' || n),
    pg_temp.ui_demo_uuid('practitioner-credential-type-license'),
    'enc:ui-demo-practitioner-credential-' || n,
    pg_temp.ui_demo_hash('practitioner-credential-' || n),
    LPAD((2000 + n)::TEXT, 4, '0'),
    'Tanganyika Medical Council UI Demo',
    'TZ',
    DATE '2020-01-01',
    DATE '2030-01-01',
    'verified',
    CURRENT_TIMESTAMP - INTERVAL '20 days',
    pg_temp.ui_demo_uuid('user-1'),
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 30) AS n
ON CONFLICT DO NOTHING;

INSERT INTO practitioner_availability_periods (
    id, practitioner_facility_assignment_id, day_of_week, starts_at, ends_at,
    valid_from, valid_until, is_available_for_appointments, is_active, created_by_id
)
SELECT
    pg_temp.ui_demo_uuid('practitioner-availability-' || n),
    pg_temp.ui_demo_uuid('practitioner-facility-assignment-' || n),
    ((n - 1) % 7) + 1,
    TIME '08:00',
    TIME '16:00',
    DATE '2026-01-01',
    NULL,
    TRUE,
    TRUE,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 30) AS n
ON CONFLICT DO NOTHING;

INSERT INTO practitioner_shifts (
    id, practitioner_facility_assignment_id, practitioner_department_assignment_id,
    service_point_id, consultation_room_id, starts_at, ends_at, actual_started_at,
    actual_ended_at, accepts_appointments, status, notes, created_by_id
)
SELECT
    pg_temp.ui_demo_uuid('practitioner-shift-' || n),
    pg_temp.ui_demo_uuid('practitioner-facility-assignment-' || n),
    pg_temp.ui_demo_uuid('practitioner-department-assignment-' || n),
    pg_temp.ui_demo_uuid('service-point-' || (((n - 1) % 5) + 1) || '-1'),
    pg_temp.ui_demo_uuid('consultation-room-' || (((n - 1) % 5) + 1) || '-1'),
    pg_temp.ui_demo_local_ts(((((n - 1) / 5) + 1))::INTEGER, TIME '08:00'),
    pg_temp.ui_demo_local_ts(((((n - 1) / 5) + 1))::INTEGER, TIME '12:00'),
    NULL,
    NULL,
    TRUE,
    'scheduled',
    'UI demo scheduled shift',
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 30) AS n
ON CONFLICT DO NOTHING;

INSERT INTO appointment_slots (
    id, practitioner_shift_id, facility_specialty_id, starts_at, ends_at,
    capacity, booked_count, status, is_online_bookable
)
SELECT
    pg_temp.ui_demo_uuid('appointment-slot-' || n),
    pg_temp.ui_demo_uuid('practitioner-shift-' || (((n - 1) / 2) + 1)),
    pg_temp.ui_demo_uuid('facility-specialty-' || (((((n - 1) / 2) % 5) + 1)::TEXT) || '-1'),
    pg_temp.ui_demo_local_ts(((((((n - 1) / 2) + 1 - 1) / 5) + 1))::INTEGER, TIME '08:00')
        + ((((n - 1) % 2) * 30) || ' minutes')::INTERVAL,
    pg_temp.ui_demo_local_ts(((((((n - 1) / 2) + 1 - 1) / 5) + 1))::INTEGER, TIME '08:30')
        + ((((n - 1) % 2) * 30) || ' minutes')::INTERVAL,
    2,
    CASE WHEN n <= 50 THEN 1 ELSE 0 END,
    'available',
    TRUE
FROM GENERATE_SERIES(1, 60) AS n
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- Appointments, check-ins, queues, and intelligence
-- ---------------------------------------------------------------------

INSERT INTO appointments (
    id, facility_id, patient_id, facility_specialty_id, practitioner_facility_assignment_id,
    practitioner_specialty_assignment_id, practitioner_shift_id, appointment_slot_id,
    appointment_number, scheduled_start, scheduled_end, status, booking_channel,
    reason_for_visit_encrypted, cancelled_at, cancelled_by_id, cancellation_reason, created_by_id
)
SELECT
    pg_temp.ui_demo_uuid('appointment-' || n),
    pfa.facility_id,
    pg_temp.ui_demo_uuid('patient-' || (((n - 1) % 12) * 5 + CAST(SUBSTR(f.code, 6) AS INTEGER))),
    aps.facility_specialty_id,
    ps.practitioner_facility_assignment_id,
    pg_temp.ui_demo_uuid('practitioner-specialty-assignment-' || ps_n),
    ps.id,
    aps.id,
    'UIAPT-202607-' || LPAD(n::TEXT, 4, '0'),
    aps.starts_at,
    aps.ends_at,
    CASE
        WHEN n <= 10 THEN 'checked_in'
        WHEN n <= 25 THEN 'queued'
        WHEN n <= 35 THEN 'in_service'
        WHEN n <= 40 THEN 'confirmed'
        WHEN n <= 45 THEN 'completed'
        WHEN n <= 48 THEN 'cancelled'
        ELSE 'pending'
    END,
    'reception',
    'enc:ui-demo-reason-for-visit-' || n,
    CASE WHEN n BETWEEN 46 AND 48 THEN aps.starts_at - INTERVAL '1 day' ELSE NULL END,
    CASE WHEN n BETWEEN 46 AND 48 THEN pg_temp.ui_demo_uuid('user-1') ELSE NULL END,
    CASE WHEN n BETWEEN 46 AND 48 THEN 'Patient requested cancellation in UI demo.' ELSE NULL END,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 50) AS n
CROSS JOIN LATERAL (SELECT (((n - 1) / 2) + 1) AS ps_n) AS derived
JOIN appointment_slots aps ON aps.id = pg_temp.ui_demo_uuid('appointment-slot-' || n)
JOIN practitioner_shifts ps ON ps.id = pg_temp.ui_demo_uuid('practitioner-shift-' || ps_n)
JOIN practitioner_facility_assignments pfa ON pfa.id = ps.practitioner_facility_assignment_id
JOIN facilities f ON f.id = pfa.facility_id
ON CONFLICT DO NOTHING;

INSERT INTO appointment_status_history (
    id, appointment_id, from_status, to_status, change_source, changed_by_id, reason, changed_at
)
SELECT
    pg_temp.ui_demo_uuid('appointment-history-initial-' || n),
    pg_temp.ui_demo_uuid('appointment-' || n),
    NULL,
    'pending',
    'system',
    pg_temp.ui_demo_uuid('user-1'),
    'Initial UI demo appointment state.',
    a.created_at
FROM GENERATE_SERIES(1, 50) AS n
JOIN appointments a ON a.id = pg_temp.ui_demo_uuid('appointment-' || n)
ON CONFLICT DO NOTHING;

INSERT INTO appointment_status_history (
    id, appointment_id, from_status, to_status, change_source, changed_by_id, reason, changed_at
)
SELECT
    pg_temp.ui_demo_uuid('appointment-history-current-' || n),
    pg_temp.ui_demo_uuid('appointment-' || n),
    'pending',
    a.status,
    'reception',
    pg_temp.ui_demo_uuid('user-1'),
    'UI demo workflow status.',
    a.created_at + INTERVAL '10 minutes'
FROM GENERATE_SERIES(1, 50) AS n
JOIN appointments a ON a.id = pg_temp.ui_demo_uuid('appointment-' || n)
WHERE a.status <> 'pending'
ON CONFLICT DO NOTHING;

INSERT INTO patient_checkins (
    id, facility_id, patient_id, appointment_id, facility_specialty_id, checkin_method,
    checked_in_at, checked_in_by_id, notes
)
SELECT
    pg_temp.ui_demo_uuid('patient-checkin-' || n),
    a.facility_id,
    a.patient_id,
    a.id,
    a.facility_specialty_id,
    (ARRAY['reception','qr_code','mobile','self_service'])[((n - 1) % 4) + 1],
    a.scheduled_start - INTERVAL '5 minutes',
    CASE WHEN ((n - 1) % 4) + 1 = 1 THEN pg_temp.ui_demo_uuid('user-1') ELSE NULL END,
    'UI demo appointment check-in.'
FROM GENERATE_SERIES(1, 40) AS n
JOIN appointments a ON a.id = pg_temp.ui_demo_uuid('appointment-' || n)
ON CONFLICT DO NOTHING;

INSERT INTO checkin_tokens (
    id, appointment_id, token_hash, expires_at, used_at, patient_checkin_id,
    revoked_at, revoked_by_id, revocation_reason, created_by_id, created_at
)
SELECT
    pg_temp.ui_demo_uuid('checkin-token-' || n),
    pg_temp.ui_demo_uuid('appointment-' || n),
    pg_temp.ui_demo_hash('checkin-token-' || n),
    a.scheduled_start + INTERVAL '2 hours',
    CASE WHEN n <= 10 THEN pc.checked_in_at ELSE NULL END,
    CASE WHEN n <= 10 THEN pc.id ELSE NULL END,
    CASE WHEN n BETWEEN 11 AND 15 THEN a.scheduled_start - INTERVAL '2 hours' ELSE NULL END,
    CASE WHEN n BETWEEN 11 AND 15 THEN pg_temp.ui_demo_uuid('user-1') ELSE NULL END,
    CASE WHEN n BETWEEN 11 AND 15 THEN 'Reissued for UI demo.' ELSE NULL END,
    pg_temp.ui_demo_uuid('user-1'),
    a.scheduled_start - INTERVAL '3 hours'
FROM GENERATE_SERIES(1, 20) AS n
JOIN appointments a ON a.id = pg_temp.ui_demo_uuid('appointment-' || n)
LEFT JOIN patient_checkins pc ON pc.id = pg_temp.ui_demo_uuid('patient-checkin-' || n)
ON CONFLICT DO NOTHING;

INSERT INTO queues (
    id, service_point_id, facility_specialty_id, queue_date, next_sequence_number,
    status, opened_at, opened_by_id, created_by_id
)
SELECT
    pg_temp.ui_demo_uuid('queue-' || f),
    pg_temp.ui_demo_uuid('service-point-' || f || '-1'),
    NULL,
    DATE '2026-07-20',
    20,
    'open',
    TIMESTAMPTZ '2026-07-20 07:30:00+03',
    pg_temp.ui_demo_uuid('user-1'),
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 10) AS f
ON CONFLICT DO NOTHING;

INSERT INTO queue_entries (
    id, queue_id, patient_checkin_id, practitioner_shift_id, sequence_number,
    priority_level, priority_reason, status, joined_at, called_at,
    service_started_at, service_completed_at, created_by_id
)
SELECT
    pg_temp.ui_demo_uuid('queue-entry-' || n),
    pg_temp.ui_demo_uuid('queue-' || fac_num),
    pg_temp.ui_demo_uuid('patient-checkin-' || n),
    CASE WHEN n > 30 THEN a.practitioner_shift_id ELSE NULL END,
    ROW_NUMBER() OVER (PARTITION BY fac_num ORDER BY n),
    CASE WHEN n % 10 = 0 THEN 3 WHEN n % 7 = 0 THEN 2 WHEN n % 5 = 0 THEN 1 ELSE 0 END,
    CASE WHEN n % 10 = 0 THEN 'Emergency UI demo priority'
         WHEN n % 7 = 0 THEN 'Urgent UI demo priority'
         WHEN n % 5 = 0 THEN 'Priority UI demo patient'
         ELSE NULL END,
    CASE
        WHEN n <= 15 THEN 'waiting'
        WHEN n <= 25 THEN 'called'
        WHEN n <= 30 THEN 'skipped'
        WHEN n <= 35 THEN 'in_service'
        ELSE 'completed'
    END,
    pc.checked_in_at + INTERVAL '3 minutes',
    CASE WHEN n > 15 THEN pc.checked_in_at + INTERVAL '8 minutes' ELSE NULL END,
    CASE WHEN n > 30 THEN pc.checked_in_at + INTERVAL '15 minutes' ELSE NULL END,
    CASE WHEN n > 35 THEN pc.checked_in_at + INTERVAL '35 minutes' ELSE NULL END,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 40) AS n
JOIN patient_checkins pc ON pc.id = pg_temp.ui_demo_uuid('patient-checkin-' || n)
JOIN appointments a ON a.id = pc.appointment_id
CROSS JOIN LATERAL (
    SELECT CAST(REPLACE(SUBSTR(f.code, 6), '0', '') AS INTEGER) AS fac_num
    FROM facilities f
    WHERE f.id = pc.facility_id
) facility_number
ON CONFLICT DO NOTHING;

INSERT INTO queue_entry_events (
    id, queue_entry_id, event_type, from_status, to_status, performed_by_id, reason, occurred_at
)
SELECT
    pg_temp.ui_demo_uuid('queue-entry-event-joined-' || n),
    pg_temp.ui_demo_uuid('queue-entry-' || n),
    'joined',
    NULL,
    'waiting',
    pg_temp.ui_demo_uuid('user-1'),
    NULL,
    qe.joined_at
FROM GENERATE_SERIES(1, 40) AS n
JOIN queue_entries qe ON qe.id = pg_temp.ui_demo_uuid('queue-entry-' || n)
ON CONFLICT DO NOTHING;

INSERT INTO queue_entry_events (id, queue_entry_id, event_type, from_status, to_status, performed_by_id, reason, occurred_at)
SELECT pg_temp.ui_demo_uuid('queue-entry-event-called-' || n), pg_temp.ui_demo_uuid('queue-entry-' || n), 'called', 'waiting', 'called', pg_temp.ui_demo_uuid('user-1'), NULL, qe.called_at
FROM GENERATE_SERIES(16, 40) AS n
JOIN queue_entries qe ON qe.id = pg_temp.ui_demo_uuid('queue-entry-' || n)
ON CONFLICT DO NOTHING;

INSERT INTO queue_entry_events (id, queue_entry_id, event_type, from_status, to_status, performed_by_id, reason, occurred_at)
SELECT pg_temp.ui_demo_uuid('queue-entry-event-skipped-' || n), pg_temp.ui_demo_uuid('queue-entry-' || n), 'skipped', 'called', 'skipped', pg_temp.ui_demo_uuid('user-1'), NULL, qe.called_at + INTERVAL '4 minutes'
FROM GENERATE_SERIES(26, 30) AS n
JOIN queue_entries qe ON qe.id = pg_temp.ui_demo_uuid('queue-entry-' || n)
ON CONFLICT DO NOTHING;

INSERT INTO queue_entry_events (id, queue_entry_id, event_type, from_status, to_status, performed_by_id, reason, occurred_at)
SELECT pg_temp.ui_demo_uuid('queue-entry-event-service-started-' || n), pg_temp.ui_demo_uuid('queue-entry-' || n), 'service_started', 'called', 'in_service', pg_temp.ui_demo_uuid('user-1'), NULL, qe.service_started_at
FROM GENERATE_SERIES(31, 40) AS n
JOIN queue_entries qe ON qe.id = pg_temp.ui_demo_uuid('queue-entry-' || n)
ON CONFLICT DO NOTHING;

INSERT INTO queue_entry_events (id, queue_entry_id, event_type, from_status, to_status, performed_by_id, reason, occurred_at)
SELECT pg_temp.ui_demo_uuid('queue-entry-event-service-completed-' || n), pg_temp.ui_demo_uuid('queue-entry-' || n), 'service_completed', 'in_service', 'completed', pg_temp.ui_demo_uuid('user-1'), NULL, qe.service_completed_at
FROM GENERATE_SERIES(36, 40) AS n
JOIN queue_entries qe ON qe.id = pg_temp.ui_demo_uuid('queue-entry-' || n)
ON CONFLICT DO NOTHING;

INSERT INTO queue_wait_time_predictions (
    id, queue_entry_id, predicted_wait_minutes, prediction_method, model_version,
    confidence_score, generated_at, created_at
)
SELECT
    pg_temp.ui_demo_uuid('queue-wait-time-prediction-' || n),
    pg_temp.ui_demo_uuid('queue-entry-' || (((n - 1) % 30) + 1)),
    5 + ((n * 3) % 45),
    CASE WHEN n % 12 = 0 THEN 'machine_learning' ELSE 'rule_based' END,
    CASE WHEN n % 12 = 0 THEN 'ui-demo-ml-v0.1' ELSE NULL END,
    CASE WHEN n % 12 = 0 THEN 0.6500 ELSE NULL END,
    qe.joined_at + INTERVAL '1 minute',
    qe.joined_at + INTERVAL '1 minute'
FROM GENERATE_SERIES(1, 50) AS n
JOIN queue_entries qe ON qe.id = pg_temp.ui_demo_uuid('queue-entry-' || (((n - 1) % 30) + 1))
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- Notifications, reporting, and audit
-- ---------------------------------------------------------------------

INSERT INTO patient_notifications (
    id, patient_id, appointment_id, queue_entry_id, notification_type, channel,
    recipient_user_id, destination_encrypted, subject_encrypted, body_encrypted,
    scheduled_for, status, attempt_count, last_attempt_at, sent_at, delivered_at,
    read_at, failed_at, failure_reason, provider_message_id, idempotency_key, created_by_id
)
SELECT
    pg_temp.ui_demo_uuid('patient-notification-' || n),
    pg_temp.ui_demo_uuid('patient-' || n),
    NULL,
    NULL,
    (ARRAY['appointment_confirmation','appointment_reminder','queue_joined','queue_called','general'])[((n - 1) % 5) + 1],
    'sms',
    NULL,
    'enc:ui-demo-notification-destination-' || n,
    NULL,
    'enc:ui-demo-notification-body-' || n,
    CURRENT_TIMESTAMP - (n || ' minutes')::INTERVAL,
    CASE WHEN n % 5 = 1 THEN 'pending' WHEN n % 5 = 2 THEN 'sent' WHEN n % 5 = 3 THEN 'delivered' WHEN n % 5 = 4 THEN 'failed' ELSE 'cancelled' END,
    CASE WHEN n % 5 IN (2, 3, 4) THEN 1 ELSE 0 END,
    CASE WHEN n % 5 IN (2, 3, 4) THEN CURRENT_TIMESTAMP - (n || ' minutes')::INTERVAL ELSE NULL END,
    CASE WHEN n % 5 IN (2, 3) THEN CURRENT_TIMESTAMP - ((n - 1) || ' minutes')::INTERVAL ELSE NULL END,
    CASE WHEN n % 5 = 3 THEN CURRENT_TIMESTAMP - ((n - 2) || ' minutes')::INTERVAL ELSE NULL END,
    NULL,
    CASE WHEN n % 5 = 4 THEN CURRENT_TIMESTAMP - ((n - 1) || ' minutes')::INTERVAL ELSE NULL END,
    CASE WHEN n % 5 = 4 THEN 'Provider not configured in UI demo.' ELSE NULL END,
    CASE WHEN n % 5 IN (2, 3) THEN 'ui-demo-provider-' || n ELSE NULL END,
    'ui-demo-notification-' || n,
    pg_temp.ui_demo_uuid('user-1')
FROM GENERATE_SERIES(1, 50) AS n
ON CONFLICT DO NOTHING;

INSERT INTO user_push_devices (
    id, user_id, platform, token_encrypted, token_hash, device_name,
    app_version, last_seen_at, is_active, revoked_at
)
SELECT
    pg_temp.ui_demo_uuid('push-device-' || n),
    pg_temp.ui_demo_uuid('user-' || n),
    (ARRAY['android','ios','web'])[((n - 1) % 3) + 1],
    'enc:ui-demo-push-token-' || n,
    pg_temp.ui_demo_hash('push-device-token-' || n),
    'UI Demo Device ' || n,
    '1.0.' || n,
    CURRENT_TIMESTAMP - (n || ' hours')::INTERVAL,
    n <= 20,
    CASE WHEN n > 20 THEN CURRENT_TIMESTAMP - INTERVAL '1 day' ELSE NULL END
FROM GENERATE_SERIES(1, 30) AS n
ON CONFLICT DO NOTHING;

INSERT INTO report_exports (
    id, organization_id, facility_id, report_type, export_format, parameters,
    status, requested_by_id, storage_key, row_count, generated_at, expires_at,
    failed_at, failure_reason
)
SELECT
    pg_temp.ui_demo_uuid('report-export-' || n),
    pg_temp.ui_demo_uuid('organization-' || (((n - 1) % 5) + 1)),
    pg_temp.ui_demo_uuid('facility-' || (((n - 1) % 10) + 1)),
    (ARRAY['patient_waiting_time','appointment_utilization','doctor_workload','daily_attendance','prediction_accuracy'])[((n - 1) % 5) + 1],
    (ARRAY['csv','xlsx','pdf'])[((n - 1) % 3) + 1],
    JSONB_BUILD_OBJECT('date_from', '2026-07-20', 'date_to', '2026-07-31', 'ui_demo', TRUE),
    (ARRAY['pending','processing','completed','failed','expired','cancelled'])[((n - 1) % 6) + 1],
    pg_temp.ui_demo_uuid('user-1'),
    CASE WHEN ((n - 1) % 6) + 1 IN (3, 5) THEN 'reports/ui-demo/' || pg_temp.ui_demo_uuid('report-export-' || n)::TEXT || '.' || (ARRAY['csv','xlsx','pdf'])[((n - 1) % 3) + 1] ELSE NULL END,
    CASE WHEN ((n - 1) % 6) + 1 IN (3, 5) THEN 25 + n ELSE NULL END,
    CASE WHEN ((n - 1) % 6) + 1 IN (3, 5) THEN CURRENT_TIMESTAMP - (n || ' hours')::INTERVAL ELSE NULL END,
    CASE WHEN ((n - 1) % 6) + 1 = 5 THEN CURRENT_TIMESTAMP - ((n - 1) || ' hours')::INTERVAL
         WHEN ((n - 1) % 6) + 1 = 3 THEN CURRENT_TIMESTAMP + INTERVAL '7 days'
         ELSE NULL END,
    CASE WHEN ((n - 1) % 6) + 1 = 4 THEN CURRENT_TIMESTAMP - (n || ' hours')::INTERVAL ELSE NULL END,
    CASE WHEN ((n - 1) % 6) + 1 = 4 THEN 'UI demo export adapter not configured.' ELSE NULL END
FROM GENERATE_SERIES(1, 30) AS n
ON CONFLICT DO NOTHING;

INSERT INTO audit_logs (
    id, organization_id, facility_id, actor_user_id, action, entity_type, entity_id,
    source, request_id, ip_address, user_agent, changes, metadata, occurred_at, created_at
)
SELECT
    pg_temp.ui_demo_uuid('audit-log-' || n),
    pg_temp.ui_demo_uuid('organization-' || (((n - 1) % 5) + 1)),
    pg_temp.ui_demo_uuid('facility-' || (((n - 1) % 10) + 1)),
    pg_temp.ui_demo_uuid('user-' || (((n - 1) % 30) + 1)),
    (ARRAY['created','updated','viewed','cancelled','permission_denied','login_success'])[((n - 1) % 6) + 1],
    (ARRAY['appointment','queue_entry','patient','report_export','notification','auth_session'])[((n - 1) % 6) + 1],
    pg_temp.ui_demo_uuid('audit-entity-' || n),
    (ARRAY['web','api','system','admin'])[((n - 1) % 4) + 1],
    pg_temp.ui_demo_uuid('request-' || n),
    ('10.20.0.' || (((n - 1) % 200) + 1))::INET,
    'Mozilla/5.0 UI Demo Staff Console',
    JSONB_BUILD_OBJECT('before', JSONB_BUILD_OBJECT('status', 'pending'), 'after', JSONB_BUILD_OBJECT('status', 'confirmed')),
    JSONB_BUILD_OBJECT('ui_demo', TRUE, 'outcome', CASE WHEN n % 7 = 0 THEN 'denied' WHEN n % 5 = 0 THEN 'failure' ELSE 'success' END),
    CURRENT_TIMESTAMP - (n || ' minutes')::INTERVAL,
    CURRENT_TIMESTAMP - (n || ' minutes')::INTERVAL
FROM GENERATE_SERIES(1, 60) AS n
ON CONFLICT DO NOTHING;

COMMIT;
