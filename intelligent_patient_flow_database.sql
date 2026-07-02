-- Intelligent Patient Flow and Appointment Scheduling System
-- PostgreSQL 15+ database schema
-- Generated as a production-oriented baseline for Django.
--
-- Security assumptions:
--   1. Application-level encryption is used for every *_encrypted column.
--   2. *_hash columns contain keyed HMAC-SHA-256 values, never plain SHA-256.
--   3. Raw passwords, access tokens, QR tokens, push tokens, identifiers,
--      addresses, and notification content must never be logged.
--
-- IMPORTANT: Run this script using a database owner or migration role that can
-- create extensions, functions, triggers, indexes, and constraints.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;

SET search_path TO public;
SET TIME ZONE 'UTC';

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

-- ================================================================
-- ORGANIZATIONS AND FACILITIES
-- ================================================================

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    legal_name VARCHAR(200),
    code VARCHAR(30) NOT NULL,
    email CITEXT,
    phone_number VARCHAR(30),
    registration_number VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_organizations_code UNIQUE (code),
    CONSTRAINT ck_organizations_code_upper CHECK (code = UPPER(code)),
    CONSTRAINT ck_organizations_phone_e164 CHECK (
        phone_number IS NULL OR phone_number ~ '^\+[1-9][0-9]{7,14}$'
    )
);

CREATE TABLE facility_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name CITEXT NOT NULL,
    code VARCHAR(30) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_facility_types_name UNIQUE (name),
    CONSTRAINT uq_facility_types_code UNIQUE (code),
    CONSTRAINT ck_facility_types_code_upper CHECK (code = UPPER(code))
);

CREATE TABLE facilities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    facility_type_id UUID NOT NULL REFERENCES facility_types(id) ON DELETE RESTRICT,
    name VARCHAR(150) NOT NULL,
    code VARCHAR(30) NOT NULL,
    license_number VARCHAR(100),
    email CITEXT,
    phone_number VARCHAR(30),
    address_line1 VARCHAR(200),
    address_line2 VARCHAR(200),
    country_code CHAR(2),
    region VARCHAR(100),
    district VARCHAR(100),
    ward VARCHAR(100),
    postal_code VARCHAR(20),
    latitude NUMERIC(9,6),
    longitude NUMERIC(10,7),
    timezone VARCHAR(64) NOT NULL DEFAULT 'Africa/Dar_es_Salaam',
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_facilities_org_code UNIQUE (organization_id, code),
    CONSTRAINT ck_facilities_code_upper CHECK (code = UPPER(code)),
    CONSTRAINT ck_facilities_country_upper CHECK (
        country_code IS NULL OR country_code = UPPER(country_code)
    ),
    CONSTRAINT ck_facilities_phone_e164 CHECK (
        phone_number IS NULL OR phone_number ~ '^\+[1-9][0-9]{7,14}$'
    ),
    CONSTRAINT ck_facilities_coordinates_pair CHECK (
        (latitude IS NULL AND longitude IS NULL)
        OR (latitude IS NOT NULL AND longitude IS NOT NULL)
    ),
    CONSTRAINT ck_facilities_latitude CHECK (
        latitude IS NULL OR latitude BETWEEN -90 AND 90
    ),
    CONSTRAINT ck_facilities_longitude CHECK (
        longitude IS NULL OR longitude BETWEEN -180 AND 180
    )
);

CREATE UNIQUE INDEX uq_facilities_one_primary_per_org
    ON facilities (organization_id)
    WHERE is_primary AND is_active;

CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
    parent_department_id UUID REFERENCES departments(id) ON DELETE RESTRICT,
    name VARCHAR(150) NOT NULL,
    code VARCHAR(30) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_departments_facility_code UNIQUE (facility_id, code),
    CONSTRAINT ck_departments_code_upper CHECK (code = UPPER(code)),
    CONSTRAINT ck_departments_no_self_parent CHECK (parent_department_id IS NULL OR parent_department_id <> id)
);

CREATE TABLE specialties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_specialty_id UUID REFERENCES specialties(id) ON DELETE RESTRICT,
    name CITEXT NOT NULL,
    code VARCHAR(30) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_specialties_name UNIQUE (name),
    CONSTRAINT uq_specialties_code UNIQUE (code),
    CONSTRAINT ck_specialties_code_upper CHECK (code = UPPER(code)),
    CONSTRAINT ck_specialties_no_self_parent CHECK (parent_specialty_id IS NULL OR parent_specialty_id <> id)
);

CREATE TABLE facility_specialties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
    specialty_id UUID NOT NULL REFERENCES specialties(id) ON DELETE RESTRICT,
    department_id UUID REFERENCES departments(id) ON DELETE RESTRICT,
    appointment_duration_minutes SMALLINT NOT NULL,
    accepts_appointments BOOLEAN NOT NULL DEFAULT TRUE,
    accepts_walk_ins BOOLEAN NOT NULL DEFAULT FALSE,
    requires_referral BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_facility_specialties_duration CHECK (appointment_duration_minutes > 0)
);

CREATE UNIQUE INDEX uq_facility_specialties_without_department
    ON facility_specialties (facility_id, specialty_id)
    WHERE department_id IS NULL;

CREATE UNIQUE INDEX uq_facility_specialties_with_department
    ON facility_specialties (facility_id, specialty_id, department_id)
    WHERE department_id IS NOT NULL;

CREATE TABLE service_point_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name CITEXT NOT NULL,
    code VARCHAR(30) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_service_point_types_name UNIQUE (name),
    CONSTRAINT uq_service_point_types_code UNIQUE (code),
    CONSTRAINT ck_service_point_types_code_upper CHECK (code = UPPER(code))
);

CREATE TABLE service_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
    department_id UUID REFERENCES departments(id) ON DELETE RESTRICT,
    service_point_type_id UUID NOT NULL REFERENCES service_point_types(id) ON DELETE RESTRICT,
    name VARCHAR(150) NOT NULL,
    code VARCHAR(30) NOT NULL,
    location_description VARCHAR(250),
    floor VARCHAR(30),
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_service_points_facility_code UNIQUE (facility_id, code),
    CONSTRAINT ck_service_points_code_upper CHECK (code = UPPER(code)),
    CONSTRAINT ck_service_points_display_order CHECK (display_order >= 0)
);

CREATE TABLE consultation_rooms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
    department_id UUID REFERENCES departments(id) ON DELETE RESTRICT,
    name VARCHAR(150) NOT NULL,
    code VARCHAR(30) NOT NULL,
    location_description VARCHAR(250),
    floor VARCHAR(30),
    capacity SMALLINT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_consultation_rooms_facility_code UNIQUE (facility_id, code),
    CONSTRAINT ck_consultation_rooms_code_upper CHECK (code = UPPER(code)),
    CONSTRAINT ck_consultation_rooms_capacity CHECK (capacity > 0)
);

CREATE TABLE facility_operating_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    day_of_week SMALLINT NOT NULL,
    period_order SMALLINT NOT NULL DEFAULT 1,
    opens_at TIME,
    closes_at TIME,
    closes_next_day BOOLEAN NOT NULL DEFAULT FALSE,
    is_24_hours BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_facility_operating_hours_period UNIQUE (facility_id, day_of_week, period_order),
    CONSTRAINT ck_facility_operating_hours_day CHECK (day_of_week BETWEEN 1 AND 7),
    CONSTRAINT ck_facility_operating_hours_period_order CHECK (period_order > 0),
    CONSTRAINT ck_facility_operating_hours_shape CHECK (
        (is_24_hours AND opens_at IS NULL AND closes_at IS NULL AND NOT closes_next_day)
        OR
        (NOT is_24_hours AND opens_at IS NOT NULL AND closes_at IS NOT NULL
            AND opens_at <> closes_at
            AND (closes_next_day OR closes_at > opens_at))
    )
);

CREATE TABLE facility_schedule_exceptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    exception_date DATE NOT NULL,
    period_order SMALLINT NOT NULL DEFAULT 1,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    opens_at TIME,
    closes_at TIME,
    closes_next_day BOOLEAN NOT NULL DEFAULT FALSE,
    is_24_hours BOOLEAN NOT NULL DEFAULT FALSE,
    reason VARCHAR(250),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_facility_schedule_exceptions_period UNIQUE (facility_id, exception_date, period_order),
    CONSTRAINT ck_facility_schedule_exceptions_period_order CHECK (period_order > 0),
    CONSTRAINT ck_facility_schedule_exceptions_shape CHECK (
        (is_closed AND NOT is_24_hours AND opens_at IS NULL AND closes_at IS NULL AND NOT closes_next_day)
        OR
        (NOT is_closed AND is_24_hours AND opens_at IS NULL AND closes_at IS NULL AND NOT closes_next_day)
        OR
        (NOT is_closed AND NOT is_24_hours AND opens_at IS NOT NULL AND closes_at IS NOT NULL
            AND opens_at <> closes_at
            AND (closes_next_day OR closes_at > opens_at))
    )
);

-- ================================================================
-- USERS, ROLES, AND PERMISSIONS
-- ================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email CITEXT,
    phone_number VARCHAR(30),
    password VARCHAR(128) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    last_name VARCHAR(100) NOT NULL,
    email_verified_at TIMESTAMPTZ,
    phone_verified_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_staff BOOLEAN NOT NULL DEFAULT FALSE,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    last_login TIMESTAMPTZ,
    date_joined TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_users_contact_required CHECK (email IS NOT NULL OR phone_number IS NOT NULL),
    CONSTRAINT ck_users_phone_e164 CHECK (
        phone_number IS NULL OR phone_number ~ '^\+[1-9][0-9]{7,14}$'
    )
);

CREATE UNIQUE INDEX uq_users_email ON users (email) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX uq_users_phone ON users (phone_number) WHERE phone_number IS NOT NULL;

CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    facility_id UUID REFERENCES facilities(id) ON DELETE RESTRICT,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(80) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_roles_code_upper CHECK (code = UPPER(code)),
    CONSTRAINT ck_roles_scope CHECK (
        (organization_id IS NULL AND facility_id IS NULL)
        OR (organization_id IS NOT NULL AND facility_id IS NULL)
        OR (organization_id IS NOT NULL AND facility_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX uq_roles_platform_name
    ON roles (LOWER(name))
    WHERE organization_id IS NULL AND facility_id IS NULL;
CREATE UNIQUE INDEX uq_roles_platform_code
    ON roles (code)
    WHERE organization_id IS NULL AND facility_id IS NULL;
CREATE UNIQUE INDEX uq_roles_org_name
    ON roles (organization_id, LOWER(name))
    WHERE organization_id IS NOT NULL AND facility_id IS NULL;
CREATE UNIQUE INDEX uq_roles_org_code
    ON roles (organization_id, code)
    WHERE organization_id IS NOT NULL AND facility_id IS NULL;
CREATE UNIQUE INDEX uq_roles_facility_name
    ON roles (facility_id, LOWER(name))
    WHERE facility_id IS NOT NULL;
CREATE UNIQUE INDEX uq_roles_facility_code
    ON roles (facility_id, code)
    WHERE facility_id IS NOT NULL;

CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name CITEXT NOT NULL,
    code VARCHAR(120) NOT NULL,
    module VARCHAR(60) NOT NULL,
    action VARCHAR(60) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_permissions_name UNIQUE (name),
    CONSTRAINT uq_permissions_code UNIQUE (code),
    CONSTRAINT uq_permissions_module_action UNIQUE (module, action),
    CONSTRAINT ck_permissions_code_lower CHECK (code = LOWER(code)),
    CONSTRAINT ck_permissions_code_format CHECK (code ~ '^[a-z0-9_]+\.[a-z0-9_]+$'),
    CONSTRAINT ck_permissions_module_lower CHECK (module = LOWER(module)),
    CONSTRAINT ck_permissions_action_lower CHECK (action = LOWER(action))
);

CREATE TABLE role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE RESTRICT,
    granted_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_role_permissions_pair UNIQUE (role_id, permission_id)
);

CREATE TABLE user_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    facility_id UUID REFERENCES facilities(id) ON DELETE RESTRICT,
    starts_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ends_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_user_memberships_dates CHECK (ends_at IS NULL OR ends_at >= starts_at)
);

CREATE UNIQUE INDEX uq_user_memberships_org
    ON user_memberships (user_id, organization_id)
    WHERE facility_id IS NULL;
CREATE UNIQUE INDEX uq_user_memberships_facility
    ON user_memberships (user_id, facility_id)
    WHERE facility_id IS NOT NULL;

CREATE TABLE user_role_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    assigned_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    starts_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ends_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_role_assignments_pair UNIQUE (user_id, role_id),
    CONSTRAINT ck_user_role_assignments_dates CHECK (ends_at IS NULL OR ends_at >= starts_at)
);

-- ================================================================
-- PATIENTS AND PATIENT ACCESS
-- ================================================================

CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    registered_facility_id UUID REFERENCES facilities(id) ON DELETE RESTRICT,
    patient_number VARCHAR(50) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    last_name VARCHAR(100) NOT NULL,
    date_of_birth DATE,
    date_of_birth_is_estimated BOOLEAN NOT NULL DEFAULT FALSE,
    sex_code VARCHAR(20),
    email CITEXT,
    phone_number VARCHAR(30),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_patients_org_number UNIQUE (organization_id, patient_number),
    CONSTRAINT ck_patients_number_not_blank CHECK (BTRIM(patient_number) <> ''),
    CONSTRAINT ck_patients_sex_code CHECK (
        sex_code IS NULL OR sex_code IN ('male', 'female', 'intersex', 'unknown')
    ),
    CONSTRAINT ck_patients_phone_e164 CHECK (
        phone_number IS NULL OR phone_number ~ '^\+[1-9][0-9]{7,14}$'
    )
);

CREATE UNIQUE INDEX uq_patients_org_user
    ON patients (organization_id, user_id)
    WHERE user_id IS NOT NULL;

CREATE TABLE patient_identifier_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(40) NOT NULL,
    description TEXT,
    is_sensitive BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_patient_identifier_types_code_upper CHECK (code = UPPER(code))
);

CREATE UNIQUE INDEX uq_patient_identifier_types_global_name
    ON patient_identifier_types (LOWER(name))
    WHERE organization_id IS NULL;
CREATE UNIQUE INDEX uq_patient_identifier_types_global_code
    ON patient_identifier_types (code)
    WHERE organization_id IS NULL;
CREATE UNIQUE INDEX uq_patient_identifier_types_org_name
    ON patient_identifier_types (organization_id, LOWER(name))
    WHERE organization_id IS NOT NULL;
CREATE UNIQUE INDEX uq_patient_identifier_types_org_code
    ON patient_identifier_types (organization_id, code)
    WHERE organization_id IS NOT NULL;

CREATE TABLE patient_identifiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    identifier_type_id UUID NOT NULL REFERENCES patient_identifier_types(id) ON DELETE RESTRICT,
    value_encrypted TEXT NOT NULL,
    value_hash CHAR(64) NOT NULL,
    last_four VARCHAR(4),
    issuing_country_code CHAR(2),
    issuing_authority VARCHAR(150),
    issued_on DATE,
    expires_on DATE,
    verified_at TIMESTAMPTZ,
    verified_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_patient_identifiers_type_hash UNIQUE (identifier_type_id, value_hash),
    CONSTRAINT ck_patient_identifiers_hash CHECK (value_hash ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT ck_patient_identifiers_dates CHECK (
        expires_on IS NULL OR issued_on IS NULL OR expires_on >= issued_on
    ),
    CONSTRAINT ck_patient_identifiers_verification CHECK (
        (verified_at IS NULL AND verified_by_id IS NULL)
        OR (verified_at IS NOT NULL AND verified_by_id IS NOT NULL)
    ),
    CONSTRAINT ck_patient_identifiers_country_upper CHECK (
        issuing_country_code IS NULL OR issuing_country_code = UPPER(issuing_country_code)
    )
);

CREATE UNIQUE INDEX uq_patient_identifiers_primary
    ON patient_identifiers (patient_id, identifier_type_id)
    WHERE is_primary AND is_active;

CREATE TABLE patient_addresses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    label VARCHAR(50),
    address_line1_encrypted TEXT,
    address_line2_encrypted TEXT,
    country_code CHAR(2),
    region VARCHAR(100),
    district VARCHAR(100),
    ward VARCHAR(100),
    postal_code VARCHAR(20),
    latitude NUMERIC(9,6),
    longitude NUMERIC(10,7),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_patient_addresses_meaningful CHECK (
        address_line1_encrypted IS NOT NULL
        OR address_line2_encrypted IS NOT NULL
        OR region IS NOT NULL
        OR district IS NOT NULL
        OR ward IS NOT NULL
        OR postal_code IS NOT NULL
        OR latitude IS NOT NULL
    ),
    CONSTRAINT ck_patient_addresses_coordinates_pair CHECK (
        (latitude IS NULL AND longitude IS NULL)
        OR (latitude IS NOT NULL AND longitude IS NOT NULL)
    ),
    CONSTRAINT ck_patient_addresses_latitude CHECK (
        latitude IS NULL OR latitude BETWEEN -90 AND 90
    ),
    CONSTRAINT ck_patient_addresses_longitude CHECK (
        longitude IS NULL OR longitude BETWEEN -180 AND 180
    ),
    CONSTRAINT ck_patient_addresses_country_upper CHECK (
        country_code IS NULL OR country_code = UPPER(country_code)
    )
);

CREATE UNIQUE INDEX uq_patient_addresses_primary
    ON patient_addresses (patient_id)
    WHERE is_primary AND is_active;

CREATE TABLE relationship_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name CITEXT NOT NULL,
    code VARCHAR(40) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_relationship_types_name UNIQUE (name),
    CONSTRAINT uq_relationship_types_code UNIQUE (code),
    CONSTRAINT ck_relationship_types_code_upper CHECK (code = UPPER(code))
);

CREATE TABLE patient_related_persons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    relationship_type_id UUID NOT NULL REFERENCES relationship_types(id) ON DELETE RESTRICT,
    linked_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    last_name VARCHAR(100) NOT NULL,
    is_guardian BOOLEAN NOT NULL DEFAULT FALSE,
    is_caregiver BOOLEAN NOT NULL DEFAULT FALSE,
    is_next_of_kin BOOLEAN NOT NULL DEFAULT FALSE,
    is_emergency_contact BOOLEAN NOT NULL DEFAULT FALSE,
    priority_order SMALLINT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_patient_related_persons_priority CHECK (priority_order > 0)
);

CREATE UNIQUE INDEX uq_patient_related_persons_linked_user
    ON patient_related_persons (patient_id, linked_user_id)
    WHERE linked_user_id IS NOT NULL;

CREATE TABLE related_person_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    related_person_id UUID NOT NULL REFERENCES patient_related_persons(id) ON DELETE RESTRICT,
    channel VARCHAR(20) NOT NULL,
    label VARCHAR(50),
    value_encrypted TEXT NOT NULL,
    value_hash CHAR(64) NOT NULL,
    verified_at TIMESTAMPTZ,
    verified_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_related_person_contacts_value UNIQUE (related_person_id, channel, value_hash),
    CONSTRAINT ck_related_person_contacts_channel CHECK (channel IN ('phone', 'email')),
    CONSTRAINT ck_related_person_contacts_hash CHECK (value_hash ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT ck_related_person_contacts_verification CHECK (
        (verified_at IS NULL AND verified_by_id IS NULL)
        OR (verified_at IS NOT NULL AND verified_by_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX uq_related_person_contacts_primary
    ON related_person_contacts (related_person_id, channel)
    WHERE is_primary AND is_active;

CREATE TABLE patient_access_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    related_person_id UUID NOT NULL REFERENCES patient_related_persons(id) ON DELETE RESTRICT,
    grantee_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    granted_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    starts_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ends_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    revoked_at TIMESTAMPTZ,
    revoked_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    revocation_reason VARCHAR(250),
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_patient_access_grants_dates CHECK (ends_at IS NULL OR ends_at >= starts_at),
    CONSTRAINT ck_patient_access_grants_revocation CHECK (
        (revoked_at IS NULL AND revoked_by_id IS NULL AND revocation_reason IS NULL)
        OR (revoked_at IS NOT NULL AND revoked_by_id IS NOT NULL AND revocation_reason IS NOT NULL)
    ),
    CONSTRAINT ck_patient_access_grants_revoked_inactive CHECK (
        revoked_at IS NULL OR NOT is_active
    )
);

CREATE UNIQUE INDEX uq_patient_access_grants_active
    ON patient_access_grants (patient_id, grantee_user_id, role_id)
    WHERE is_active AND revoked_at IS NULL;

-- ================================================================
-- PRACTITIONERS
-- ================================================================

CREATE TABLE practitioner_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name CITEXT NOT NULL,
    code VARCHAR(40) NOT NULL,
    description TEXT,
    requires_license BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_practitioner_types_name UNIQUE (name),
    CONSTRAINT uq_practitioner_types_code UNIQUE (code),
    CONSTRAINT ck_practitioner_types_code_upper CHECK (code = UPPER(code))
);

CREATE TABLE practitioners (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    practitioner_type_id UUID NOT NULL REFERENCES practitioner_types(id) ON DELETE RESTRICT,
    practitioner_number VARCHAR(50) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    last_name VARCHAR(100) NOT NULL,
    preferred_name VARCHAR(100),
    email CITEXT,
    phone_number VARCHAR(30),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_practitioners_org_number UNIQUE (organization_id, practitioner_number),
    CONSTRAINT ck_practitioners_number_not_blank CHECK (BTRIM(practitioner_number) <> ''),
    CONSTRAINT ck_practitioners_phone_e164 CHECK (
        phone_number IS NULL OR phone_number ~ '^\+[1-9][0-9]{7,14}$'
    )
);

CREATE UNIQUE INDEX uq_practitioners_org_user
    ON practitioners (organization_id, user_id)
    WHERE user_id IS NOT NULL;

CREATE TABLE practitioner_facility_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    practitioner_id UUID NOT NULL REFERENCES practitioners(id) ON DELETE RESTRICT,
    facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
    starts_on DATE NOT NULL,
    ends_on DATE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    assigned_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_practitioner_facility_assignments_pair UNIQUE (practitioner_id, facility_id),
    CONSTRAINT ck_practitioner_facility_assignments_dates CHECK (ends_on IS NULL OR ends_on >= starts_on)
);

CREATE UNIQUE INDEX uq_practitioner_primary_facility
    ON practitioner_facility_assignments (practitioner_id)
    WHERE is_primary AND is_active;

CREATE TABLE practitioner_department_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    practitioner_facility_assignment_id UUID NOT NULL REFERENCES practitioner_facility_assignments(id) ON DELETE RESTRICT,
    department_id UUID NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    starts_on DATE NOT NULL,
    ends_on DATE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    assigned_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_practitioner_department_assignments_pair UNIQUE (practitioner_facility_assignment_id, department_id),
    CONSTRAINT ck_practitioner_department_assignments_dates CHECK (ends_on IS NULL OR ends_on >= starts_on)
);

CREATE UNIQUE INDEX uq_practitioner_primary_department
    ON practitioner_department_assignments (practitioner_facility_assignment_id)
    WHERE is_primary AND is_active;

CREATE TABLE practitioner_specialty_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    practitioner_facility_assignment_id UUID NOT NULL REFERENCES practitioner_facility_assignments(id) ON DELETE RESTRICT,
    facility_specialty_id UUID NOT NULL REFERENCES facility_specialties(id) ON DELETE RESTRICT,
    starts_on DATE NOT NULL,
    ends_on DATE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    assigned_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_practitioner_specialty_assignments_pair UNIQUE (practitioner_facility_assignment_id, facility_specialty_id),
    CONSTRAINT ck_practitioner_specialty_assignments_dates CHECK (ends_on IS NULL OR ends_on >= starts_on)
);

CREATE UNIQUE INDEX uq_practitioner_primary_specialty
    ON practitioner_specialty_assignments (practitioner_facility_assignment_id)
    WHERE is_primary AND is_active;

CREATE TABLE practitioner_credential_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(40) NOT NULL,
    description TEXT,
    country_code CHAR(2),
    requires_expiry_date BOOLEAN NOT NULL DEFAULT FALSE,
    requires_verification BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_practitioner_credential_types_code_upper CHECK (code = UPPER(code)),
    CONSTRAINT ck_practitioner_credential_types_country_upper CHECK (
        country_code IS NULL OR country_code = UPPER(country_code)
    )
);

CREATE UNIQUE INDEX uq_practitioner_credential_types_global_name
    ON practitioner_credential_types (LOWER(name))
    WHERE organization_id IS NULL;
CREATE UNIQUE INDEX uq_practitioner_credential_types_global_code
    ON practitioner_credential_types (code)
    WHERE organization_id IS NULL;
CREATE UNIQUE INDEX uq_practitioner_credential_types_org_name
    ON practitioner_credential_types (organization_id, LOWER(name))
    WHERE organization_id IS NOT NULL;
CREATE UNIQUE INDEX uq_practitioner_credential_types_org_code
    ON practitioner_credential_types (organization_id, code)
    WHERE organization_id IS NOT NULL;

CREATE TABLE practitioner_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    practitioner_id UUID NOT NULL REFERENCES practitioners(id) ON DELETE RESTRICT,
    credential_type_id UUID NOT NULL REFERENCES practitioner_credential_types(id) ON DELETE RESTRICT,
    credential_number_encrypted TEXT NOT NULL,
    credential_number_hash CHAR(64) NOT NULL,
    last_four VARCHAR(4),
    issuing_authority VARCHAR(150),
    issuing_country_code CHAR(2),
    issued_on DATE,
    expires_on DATE,
    verification_status VARCHAR(20) NOT NULL DEFAULT 'unverified',
    verified_at TIMESTAMPTZ,
    verified_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_practitioner_credentials_type_hash UNIQUE (credential_type_id, credential_number_hash),
    CONSTRAINT ck_practitioner_credentials_hash CHECK (credential_number_hash ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT ck_practitioner_credentials_status CHECK (
        verification_status IN ('unverified', 'pending', 'verified', 'rejected')
    ),
    CONSTRAINT ck_practitioner_credentials_dates CHECK (
        expires_on IS NULL OR issued_on IS NULL OR expires_on >= issued_on
    ),
    CONSTRAINT ck_practitioner_credentials_country_upper CHECK (
        issuing_country_code IS NULL OR issuing_country_code = UPPER(issuing_country_code)
    ),
    CONSTRAINT ck_practitioner_credentials_verification CHECK (
        (verification_status = 'verified' AND verified_at IS NOT NULL AND verified_by_id IS NOT NULL)
        OR (verification_status <> 'verified' AND verified_at IS NULL AND verified_by_id IS NULL)
    )
);

-- ================================================================
-- SCHEDULING
-- ================================================================

CREATE TABLE practitioner_availability_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    practitioner_facility_assignment_id UUID NOT NULL REFERENCES practitioner_facility_assignments(id) ON DELETE RESTRICT,
    day_of_week SMALLINT NOT NULL,
    starts_at TIME NOT NULL,
    ends_at TIME NOT NULL,
    valid_from DATE NOT NULL,
    valid_until DATE,
    is_available_for_appointments BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_practitioner_availability_exact UNIQUE (
        practitioner_facility_assignment_id,
        day_of_week,
        starts_at,
        ends_at,
        valid_from
    ),
    CONSTRAINT ck_practitioner_availability_day CHECK (day_of_week BETWEEN 1 AND 7),
    CONSTRAINT ck_practitioner_availability_times CHECK (ends_at > starts_at),
    CONSTRAINT ck_practitioner_availability_dates CHECK (valid_until IS NULL OR valid_until >= valid_from)
);

CREATE TABLE practitioner_leave_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    practitioner_facility_assignment_id UUID NOT NULL REFERENCES practitioner_facility_assignments(id) ON DELETE RESTRICT,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    reason VARCHAR(250),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    requested_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    decided_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ,
    decision_note VARCHAR(250),
    cancelled_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    cancelled_at TIMESTAMPTZ,
    cancellation_reason VARCHAR(250),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_practitioner_leave_times CHECK (ends_at > starts_at),
    CONSTRAINT ck_practitioner_leave_status CHECK (
        status IN ('pending', 'approved', 'rejected', 'cancelled')
    ),
    CONSTRAINT ck_practitioner_leave_state CHECK (
        (status = 'pending'
            AND decided_by_id IS NULL AND decided_at IS NULL
            AND cancelled_by_id IS NULL AND cancelled_at IS NULL AND cancellation_reason IS NULL)
        OR
        (status IN ('approved', 'rejected')
            AND decided_by_id IS NOT NULL AND decided_at IS NOT NULL
            AND cancelled_by_id IS NULL AND cancelled_at IS NULL AND cancellation_reason IS NULL)
        OR
        (status = 'cancelled'
            AND cancelled_by_id IS NOT NULL AND cancelled_at IS NOT NULL AND cancellation_reason IS NOT NULL)
    )
);

ALTER TABLE practitioner_leave_requests
    ADD CONSTRAINT ex_practitioner_leave_no_overlap
    EXCLUDE USING gist (
        practitioner_facility_assignment_id WITH =,
        tstzrange(starts_at, ends_at, '[)') WITH &&
    )
    WHERE (status IN ('pending', 'approved'));

CREATE TABLE practitioner_shifts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    practitioner_facility_assignment_id UUID NOT NULL REFERENCES practitioner_facility_assignments(id) ON DELETE RESTRICT,
    practitioner_department_assignment_id UUID REFERENCES practitioner_department_assignments(id) ON DELETE RESTRICT,
    service_point_id UUID REFERENCES service_points(id) ON DELETE RESTRICT,
    consultation_room_id UUID REFERENCES consultation_rooms(id) ON DELETE RESTRICT,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    actual_started_at TIMESTAMPTZ,
    actual_ended_at TIMESTAMPTZ,
    accepts_appointments BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    notes VARCHAR(250),
    cancelled_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    cancelled_at TIMESTAMPTZ,
    cancellation_reason VARCHAR(250),
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_practitioner_shifts_times CHECK (ends_at > starts_at),
    CONSTRAINT ck_practitioner_shifts_status CHECK (
        status IN ('scheduled', 'in_progress', 'completed', 'cancelled')
    ),
    CONSTRAINT ck_practitioner_shifts_actual_times CHECK (
        actual_ended_at IS NULL
        OR (actual_started_at IS NOT NULL AND actual_ended_at > actual_started_at)
    ),
    CONSTRAINT ck_practitioner_shifts_state CHECK (
        (status = 'scheduled'
            AND actual_started_at IS NULL AND actual_ended_at IS NULL
            AND cancelled_at IS NULL AND cancelled_by_id IS NULL AND cancellation_reason IS NULL)
        OR
        (status = 'in_progress'
            AND actual_started_at IS NOT NULL AND actual_ended_at IS NULL
            AND cancelled_at IS NULL AND cancelled_by_id IS NULL AND cancellation_reason IS NULL)
        OR
        (status = 'completed'
            AND actual_started_at IS NOT NULL AND actual_ended_at IS NOT NULL
            AND cancelled_at IS NULL AND cancelled_by_id IS NULL AND cancellation_reason IS NULL)
        OR
        (status = 'cancelled'
            AND cancelled_at IS NOT NULL AND cancelled_by_id IS NOT NULL AND cancellation_reason IS NOT NULL)
    )
);

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

CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    facility_specialty_id UUID NOT NULL REFERENCES facility_specialties(id) ON DELETE RESTRICT,
    practitioner_facility_assignment_id UUID REFERENCES practitioner_facility_assignments(id) ON DELETE RESTRICT,
    practitioner_specialty_assignment_id UUID REFERENCES practitioner_specialty_assignments(id) ON DELETE RESTRICT,
    practitioner_shift_id UUID REFERENCES practitioner_shifts(id) ON DELETE RESTRICT,
    appointment_slot_id UUID,
    appointment_number VARCHAR(50) NOT NULL,
    scheduled_start TIMESTAMPTZ NOT NULL,
    scheduled_end TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    booking_channel VARCHAR(20) NOT NULL,
    reason_for_visit_encrypted TEXT,
    rescheduled_from_id UUID REFERENCES appointments(id) ON DELETE RESTRICT,
    cancelled_at TIMESTAMPTZ,
    cancelled_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    cancellation_reason VARCHAR(250),
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_appointments_facility_number UNIQUE (facility_id, appointment_number),
    CONSTRAINT ck_appointments_times CHECK (scheduled_end > scheduled_start),
    CONSTRAINT ck_appointments_status CHECK (
        status IN ('pending', 'confirmed', 'checked_in', 'queued', 'in_service', 'completed', 'cancelled', 'no_show', 'rescheduled')
    ),
    CONSTRAINT ck_appointments_booking_channel CHECK (
        booking_channel IN ('mobile', 'web', 'reception', 'api')
    ),
    CONSTRAINT ck_appointments_no_self_reschedule CHECK (rescheduled_from_id IS NULL OR rescheduled_from_id <> id),
    CONSTRAINT ck_appointments_cancellation CHECK (
        (status = 'cancelled'
            AND cancelled_at IS NOT NULL AND cancelled_by_id IS NOT NULL AND cancellation_reason IS NOT NULL)
        OR
        (status <> 'cancelled'
            AND cancelled_at IS NULL AND cancelled_by_id IS NULL AND cancellation_reason IS NULL)
    )
);

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

CREATE TABLE appointment_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE RESTRICT,
    from_status VARCHAR(20),
    to_status VARCHAR(20) NOT NULL,
    change_source VARCHAR(20) NOT NULL,
    changed_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    reason VARCHAR(250),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_appointment_history_from_status CHECK (
        from_status IS NULL OR from_status IN ('pending', 'confirmed', 'checked_in', 'queued', 'in_service', 'completed', 'cancelled', 'no_show', 'rescheduled')
    ),
    CONSTRAINT ck_appointment_history_to_status CHECK (
        to_status IN ('pending', 'confirmed', 'checked_in', 'queued', 'in_service', 'completed', 'cancelled', 'no_show', 'rescheduled')
    ),
    CONSTRAINT ck_appointment_history_source CHECK (
        change_source IN ('web', 'mobile', 'reception', 'system', 'api')
    ),
    CONSTRAINT ck_appointment_history_change CHECK (from_status IS NULL OR from_status <> to_status)
);

CREATE UNIQUE INDEX uq_appointment_history_one_initial
    ON appointment_status_history (appointment_id)
    WHERE from_status IS NULL;

CREATE TABLE appointment_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    practitioner_shift_id UUID NOT NULL REFERENCES practitioner_shifts(id) ON DELETE RESTRICT,
    facility_specialty_id UUID NOT NULL REFERENCES facility_specialties(id) ON DELETE RESTRICT,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    capacity SMALLINT NOT NULL DEFAULT 1,
    booked_count SMALLINT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'available',
    is_online_bookable BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_appointment_slots_exact UNIQUE (
        practitioner_shift_id,
        facility_specialty_id,
        starts_at,
        ends_at
    ),
    CONSTRAINT ck_appointment_slots_times CHECK (ends_at > starts_at),
    CONSTRAINT ck_appointment_slots_capacity CHECK (capacity > 0),
    CONSTRAINT ck_appointment_slots_booked_count CHECK (booked_count BETWEEN 0 AND capacity),
    CONSTRAINT ck_appointment_slots_status CHECK (status IN ('available', 'full', 'blocked', 'cancelled')),
    CONSTRAINT ck_appointment_slots_state CHECK (
        (status = 'available' AND booked_count < capacity)
        OR (status = 'full' AND booked_count = capacity)
        OR status IN ('blocked', 'cancelled')
    )
);

ALTER TABLE appointments
    ADD CONSTRAINT fk_appointments_slot
    FOREIGN KEY (appointment_slot_id)
    REFERENCES appointment_slots(id)
    ON DELETE RESTRICT;

-- ================================================================
-- CHECK-IN
-- ================================================================

CREATE TABLE patient_checkins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    appointment_id UUID REFERENCES appointments(id) ON DELETE RESTRICT,
    facility_specialty_id UUID REFERENCES facility_specialties(id) ON DELETE RESTRICT,
    checkin_method VARCHAR(20) NOT NULL,
    checked_in_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    checked_in_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    notes VARCHAR(250),
    voided_at TIMESTAMPTZ,
    voided_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    void_reason VARCHAR(250),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_patient_checkins_method CHECK (
        checkin_method IN ('reception', 'mobile', 'qr_code', 'self_service')
    ),
    CONSTRAINT ck_patient_checkins_walkin_specialty CHECK (
        appointment_id IS NOT NULL OR facility_specialty_id IS NOT NULL
    ),
    CONSTRAINT ck_patient_checkins_void CHECK (
        (voided_at IS NULL AND voided_by_id IS NULL AND void_reason IS NULL)
        OR (voided_at IS NOT NULL AND voided_by_id IS NOT NULL AND void_reason IS NOT NULL AND voided_at >= checked_in_at)
    )
);

CREATE UNIQUE INDEX uq_patient_checkins_active_appointment
    ON patient_checkins (appointment_id)
    WHERE appointment_id IS NOT NULL AND voided_at IS NULL;

CREATE TABLE checkin_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE RESTRICT,
    token_hash CHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    patient_checkin_id UUID REFERENCES patient_checkins(id) ON DELETE RESTRICT,
    revoked_at TIMESTAMPTZ,
    revoked_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    revocation_reason VARCHAR(250),
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_checkin_tokens_hash UNIQUE (token_hash),
    CONSTRAINT ck_checkin_tokens_hash CHECK (token_hash ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT ck_checkin_tokens_expiry CHECK (expires_at > created_at),
    CONSTRAINT ck_checkin_tokens_state CHECK (
        (used_at IS NULL AND patient_checkin_id IS NULL AND revoked_at IS NULL AND revoked_by_id IS NULL AND revocation_reason IS NULL)
        OR
        (used_at IS NOT NULL AND patient_checkin_id IS NOT NULL AND revoked_at IS NULL AND revoked_by_id IS NULL AND revocation_reason IS NULL
            AND used_at >= created_at AND used_at <= expires_at)
        OR
        (used_at IS NULL AND patient_checkin_id IS NULL AND revoked_at IS NOT NULL AND revoked_by_id IS NOT NULL AND revocation_reason IS NOT NULL
            AND revoked_at >= created_at)
    )
);

CREATE UNIQUE INDEX uq_checkin_tokens_active_appointment
    ON checkin_tokens (appointment_id)
    WHERE used_at IS NULL AND revoked_at IS NULL;

CREATE UNIQUE INDEX uq_checkin_tokens_checkin
    ON checkin_tokens (patient_checkin_id)
    WHERE patient_checkin_id IS NOT NULL;

-- ================================================================
-- QUEUEING
-- ================================================================

CREATE TABLE queues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_point_id UUID NOT NULL REFERENCES service_points(id) ON DELETE RESTRICT,
    facility_specialty_id UUID REFERENCES facility_specialties(id) ON DELETE RESTRICT,
    queue_date DATE NOT NULL,
    next_sequence_number INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    opened_at TIMESTAMPTZ,
    opened_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    paused_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    closed_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_queues_sequence CHECK (next_sequence_number > 0),
    CONSTRAINT ck_queues_status CHECK (status IN ('draft', 'open', 'paused', 'closed', 'cancelled')),
    CONSTRAINT ck_queues_state CHECK (
        (status = 'draft' AND opened_at IS NULL AND paused_at IS NULL AND closed_at IS NULL AND closed_by_id IS NULL)
        OR
        (status = 'open' AND opened_at IS NOT NULL AND closed_at IS NULL AND closed_by_id IS NULL)
        OR
        (status = 'paused' AND opened_at IS NOT NULL AND paused_at IS NOT NULL AND closed_at IS NULL AND closed_by_id IS NULL)
        OR
        (status = 'closed' AND opened_at IS NOT NULL AND closed_at IS NOT NULL AND closed_by_id IS NOT NULL)
        OR
        (status = 'cancelled')
    )
);

CREATE UNIQUE INDEX uq_queues_general
    ON queues (service_point_id, queue_date)
    WHERE facility_specialty_id IS NULL;

CREATE UNIQUE INDEX uq_queues_specialty
    ON queues (service_point_id, facility_specialty_id, queue_date)
    WHERE facility_specialty_id IS NOT NULL;

CREATE TABLE queue_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id UUID NOT NULL REFERENCES queues(id) ON DELETE RESTRICT,
    patient_checkin_id UUID NOT NULL REFERENCES patient_checkins(id) ON DELETE RESTRICT,
    practitioner_shift_id UUID REFERENCES practitioner_shifts(id) ON DELETE RESTRICT,
    sequence_number INTEGER NOT NULL,
    priority_level SMALLINT NOT NULL DEFAULT 0,
    priority_reason VARCHAR(250),
    status VARCHAR(20) NOT NULL DEFAULT 'waiting',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    called_at TIMESTAMPTZ,
    service_started_at TIMESTAMPTZ,
    service_completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancelled_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    cancellation_reason VARCHAR(250),
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_queue_entries_sequence UNIQUE (queue_id, sequence_number),
    CONSTRAINT uq_queue_entries_checkin UNIQUE (queue_id, patient_checkin_id),
    CONSTRAINT ck_queue_entries_sequence CHECK (sequence_number > 0),
    CONSTRAINT ck_queue_entries_priority CHECK (priority_level BETWEEN 0 AND 3),
    CONSTRAINT ck_queue_entries_priority_reason CHECK (priority_level = 0 OR priority_reason IS NOT NULL),
    CONSTRAINT ck_queue_entries_status CHECK (
        status IN ('waiting', 'called', 'in_service', 'completed', 'skipped', 'cancelled', 'transferred')
    ),
    CONSTRAINT ck_queue_entries_timeline CHECK (
        (called_at IS NULL OR called_at >= joined_at)
        AND (service_started_at IS NULL OR (called_at IS NOT NULL AND service_started_at >= called_at))
        AND (service_completed_at IS NULL OR (service_started_at IS NOT NULL AND service_completed_at >= service_started_at))
        AND (cancelled_at IS NULL OR cancelled_at >= joined_at)
    ),
    CONSTRAINT ck_queue_entries_state CHECK (
        (status = 'waiting' AND called_at IS NULL AND service_started_at IS NULL AND service_completed_at IS NULL AND cancelled_at IS NULL)
        OR
        (status = 'called' AND called_at IS NOT NULL AND service_started_at IS NULL AND service_completed_at IS NULL AND cancelled_at IS NULL)
        OR
        (status = 'in_service' AND called_at IS NOT NULL AND service_started_at IS NOT NULL AND service_completed_at IS NULL AND cancelled_at IS NULL)
        OR
        (status = 'completed' AND service_started_at IS NOT NULL AND service_completed_at IS NOT NULL AND cancelled_at IS NULL)
        OR
        (status = 'skipped' AND called_at IS NOT NULL AND service_started_at IS NULL AND service_completed_at IS NULL AND cancelled_at IS NULL)
        OR
        (status = 'cancelled' AND cancelled_at IS NOT NULL AND cancelled_by_id IS NOT NULL AND cancellation_reason IS NOT NULL)
        OR
        (status = 'transferred' AND cancelled_at IS NULL)
    )
);

CREATE TABLE queue_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_queue_entry_id UUID NOT NULL REFERENCES queue_entries(id) ON DELETE RESTRICT,
    destination_queue_entry_id UUID NOT NULL REFERENCES queue_entries(id) ON DELETE RESTRICT,
    transferred_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    transfer_reason VARCHAR(250) NOT NULL,
    transferred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_queue_transfers_source UNIQUE (source_queue_entry_id),
    CONSTRAINT uq_queue_transfers_destination UNIQUE (destination_queue_entry_id),
    CONSTRAINT ck_queue_transfers_distinct CHECK (source_queue_entry_id <> destination_queue_entry_id)
);

CREATE TABLE queue_entry_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_entry_id UUID NOT NULL REFERENCES queue_entries(id) ON DELETE RESTRICT,
    event_type VARCHAR(30) NOT NULL,
    from_status VARCHAR(20),
    to_status VARCHAR(20),
    performed_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    reason VARCHAR(250),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_queue_entry_events_type CHECK (
        event_type IN ('joined', 'called', 'recalled', 'skipped', 'service_started', 'service_completed', 'cancelled', 'transferred', 'priority_changed')
    ),
    CONSTRAINT ck_queue_entry_events_from_status CHECK (
        from_status IS NULL OR from_status IN ('waiting', 'called', 'in_service', 'completed', 'skipped', 'cancelled', 'transferred')
    ),
    CONSTRAINT ck_queue_entry_events_to_status CHECK (
        to_status IS NULL OR to_status IN ('waiting', 'called', 'in_service', 'completed', 'skipped', 'cancelled', 'transferred')
    ),
    CONSTRAINT ck_queue_entry_events_reason CHECK (
        event_type NOT IN ('cancelled', 'transferred', 'priority_changed') OR reason IS NOT NULL
    )
);

CREATE UNIQUE INDEX uq_queue_entry_events_one_joined
    ON queue_entry_events (queue_entry_id)
    WHERE event_type = 'joined';

-- ================================================================
-- INTELLIGENCE
-- ================================================================

CREATE TABLE queue_wait_time_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_entry_id UUID NOT NULL REFERENCES queue_entries(id) ON DELETE RESTRICT,
    predicted_wait_minutes INTEGER NOT NULL,
    prediction_method VARCHAR(30) NOT NULL,
    model_version VARCHAR(100),
    confidence_score NUMERIC(5,4),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_queue_predictions_minutes CHECK (predicted_wait_minutes >= 0),
    CONSTRAINT ck_queue_predictions_method CHECK (prediction_method IN ('rule_based', 'machine_learning')),
    CONSTRAINT ck_queue_predictions_model CHECK (
        prediction_method <> 'machine_learning' OR model_version IS NOT NULL
    ),
    CONSTRAINT ck_queue_predictions_confidence CHECK (
        confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1
    )
);

-- ================================================================
-- NOTIFICATIONS
-- ================================================================

CREATE TABLE patient_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    appointment_id UUID REFERENCES appointments(id) ON DELETE RESTRICT,
    queue_entry_id UUID REFERENCES queue_entries(id) ON DELETE RESTRICT,
    notification_type VARCHAR(40) NOT NULL,
    channel VARCHAR(20) NOT NULL,
    recipient_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    destination_encrypted TEXT,
    subject_encrypted TEXT,
    body_encrypted TEXT NOT NULL,
    scheduled_for TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_count SMALLINT NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    failure_reason VARCHAR(250),
    provider_message_id VARCHAR(150),
    idempotency_key VARCHAR(100),
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_patient_notifications_type CHECK (
        notification_type IN (
            'appointment_confirmation',
            'appointment_reminder',
            'appointment_rescheduled',
            'appointment_cancelled',
            'queue_joined',
            'queue_updated',
            'queue_called',
            'general'
        )
    ),
    CONSTRAINT ck_patient_notifications_channel CHECK (channel IN ('sms', 'email', 'push', 'in_app')),
    CONSTRAINT ck_patient_notifications_status CHECK (
        status IN ('pending', 'processing', 'sent', 'delivered', 'failed', 'cancelled')
    ),
    CONSTRAINT ck_patient_notifications_attempts CHECK (attempt_count >= 0),
    CONSTRAINT ck_patient_notifications_destination CHECK (
        channel = 'in_app' OR destination_encrypted IS NOT NULL
    ),
    CONSTRAINT ck_patient_notifications_recipient CHECK (
        channel NOT IN ('push', 'in_app') OR recipient_user_id IS NOT NULL
    ),
    CONSTRAINT ck_patient_notifications_single_source CHECK (
        NOT (appointment_id IS NOT NULL AND queue_entry_id IS NOT NULL)
    ),
    CONSTRAINT ck_patient_notifications_timeline CHECK (
        (last_attempt_at IS NULL OR last_attempt_at >= created_at)
        AND (sent_at IS NULL OR (last_attempt_at IS NOT NULL AND sent_at >= last_attempt_at))
        AND (delivered_at IS NULL OR (sent_at IS NOT NULL AND delivered_at >= sent_at))
        AND (failed_at IS NULL OR (last_attempt_at IS NOT NULL AND failed_at >= last_attempt_at))
        AND (read_at IS NULL OR (channel = 'in_app' AND delivered_at IS NOT NULL AND read_at >= delivered_at))
    ),
    CONSTRAINT ck_patient_notifications_outcome CHECK (
        NOT (delivered_at IS NOT NULL AND failed_at IS NOT NULL)
    ),
    CONSTRAINT ck_patient_notifications_state CHECK (
        (status = 'pending' AND attempt_count = 0 AND sent_at IS NULL AND delivered_at IS NULL AND failed_at IS NULL)
        OR
        (status = 'processing' AND delivered_at IS NULL AND failed_at IS NULL)
        OR
        (status = 'sent' AND attempt_count > 0 AND sent_at IS NOT NULL AND delivered_at IS NULL AND failed_at IS NULL)
        OR
        (status = 'delivered' AND sent_at IS NOT NULL AND delivered_at IS NOT NULL AND failed_at IS NULL)
        OR
        (status = 'failed' AND attempt_count > 0 AND failed_at IS NOT NULL AND failure_reason IS NOT NULL AND delivered_at IS NULL)
        OR
        (status = 'cancelled' AND delivered_at IS NULL)
    )
);

CREATE UNIQUE INDEX uq_patient_notifications_idempotency
    ON patient_notifications (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TABLE user_push_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    platform VARCHAR(15) NOT NULL,
    token_encrypted TEXT NOT NULL,
    token_hash CHAR(64) NOT NULL,
    device_name VARCHAR(100),
    app_version VARCHAR(30),
    last_seen_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_push_devices_hash UNIQUE (token_hash),
    CONSTRAINT ck_user_push_devices_platform CHECK (platform IN ('android', 'ios', 'web')),
    CONSTRAINT ck_user_push_devices_hash CHECK (token_hash ~ '^[0-9A-Fa-f]{64}$'),
    CONSTRAINT ck_user_push_devices_revocation CHECK (
        (revoked_at IS NULL)
        OR (revoked_at IS NOT NULL AND NOT is_active)
    )
);

-- ================================================================
-- FACILITY FLOW CONFIGURATION
-- ================================================================

CREATE TABLE facility_flow_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID NOT NULL UNIQUE REFERENCES facilities(id) ON DELETE CASCADE,
    max_advance_booking_days SMALLINT NOT NULL DEFAULT 30,
    minimum_booking_notice_minutes INTEGER NOT NULL DEFAULT 0,
    cancellation_cutoff_minutes INTEGER NOT NULL DEFAULT 60,
    reschedule_cutoff_minutes INTEGER NOT NULL DEFAULT 60,
    early_checkin_minutes INTEGER NOT NULL DEFAULT 30,
    late_checkin_grace_minutes INTEGER NOT NULL DEFAULT 15,
    no_show_after_minutes INTEGER NOT NULL DEFAULT 15,
    default_reminder_minutes_before INTEGER DEFAULT 1440,
    queue_number_padding SMALLINT NOT NULL DEFAULT 3,
    auto_create_daily_queues BOOLEAN NOT NULL DEFAULT FALSE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_facility_flow_settings_nonnegative CHECK (
        max_advance_booking_days >= 0
        AND minimum_booking_notice_minutes >= 0
        AND cancellation_cutoff_minutes >= 0
        AND reschedule_cutoff_minutes >= 0
        AND early_checkin_minutes >= 0
        AND late_checkin_grace_minutes >= 0
        AND no_show_after_minutes >= 0
        AND (default_reminder_minutes_before IS NULL OR default_reminder_minutes_before >= 0)
    ),
    CONSTRAINT ck_facility_flow_settings_padding CHECK (queue_number_padding BETWEEN 1 AND 6)
);

-- ================================================================
-- AUDIT AND REPORTING
-- ================================================================

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE RESTRICT,
    facility_id UUID REFERENCES facilities(id) ON DELETE RESTRICT,
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID,
    source VARCHAR(20) NOT NULL,
    request_id UUID,
    ip_address INET,
    user_agent VARCHAR(500),
    changes JSONB,
    metadata JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_audit_logs_source CHECK (source IN ('web', 'mobile', 'api', 'system', 'admin')),
    CONSTRAINT ck_audit_logs_action_not_blank CHECK (BTRIM(action) <> ''),
    CONSTRAINT ck_audit_logs_entity_type_not_blank CHECK (BTRIM(entity_type) <> '')
);

CREATE TABLE report_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    facility_id UUID REFERENCES facilities(id) ON DELETE RESTRICT,
    report_type VARCHAR(50) NOT NULL,
    export_format VARCHAR(10) NOT NULL,
    parameters JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    requested_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    storage_key VARCHAR(500),
    row_count INTEGER,
    generated_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    failure_reason VARCHAR(250),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_report_exports_format CHECK (export_format IN ('csv', 'xlsx', 'pdf')),
    CONSTRAINT ck_report_exports_status CHECK (
        status IN ('pending', 'processing', 'completed', 'failed', 'expired', 'cancelled')
    ),
    CONSTRAINT ck_report_exports_row_count CHECK (row_count IS NULL OR row_count >= 0),
    CONSTRAINT ck_report_exports_completion CHECK (
        status <> 'completed' OR (storage_key IS NOT NULL AND generated_at IS NOT NULL)
    ),
    CONSTRAINT ck_report_exports_failure CHECK (
        status <> 'failed' OR (failed_at IS NOT NULL AND failure_reason IS NOT NULL)
    ),
    CONSTRAINT ck_report_exports_expiry CHECK (
        expires_at IS NULL OR (generated_at IS NOT NULL AND expires_at > generated_at)
    )
);

-- ================================================================
-- CROSS-TABLE VALIDATION FUNCTIONS AND TRIGGERS
-- ================================================================

CREATE OR REPLACE FUNCTION validate_department_hierarchy()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_facility UUID;
    creates_cycle BOOLEAN;
BEGIN
    IF NEW.parent_department_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT facility_id INTO parent_facility
    FROM departments
    WHERE id = NEW.parent_department_id;

    IF parent_facility IS NULL OR parent_facility <> NEW.facility_id THEN
        RAISE EXCEPTION 'Parent department must belong to the same facility';
    END IF;

    WITH RECURSIVE ancestors AS (
        SELECT id, parent_department_id
        FROM departments
        WHERE id = NEW.parent_department_id
        UNION ALL
        SELECT d.id, d.parent_department_id
        FROM departments d
        JOIN ancestors a ON d.id = a.parent_department_id
    )
    SELECT EXISTS (SELECT 1 FROM ancestors WHERE id = NEW.id)
    INTO creates_cycle;

    IF creates_cycle THEN
        RAISE EXCEPTION 'Department hierarchy cycle detected';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_departments_validate_hierarchy
BEFORE INSERT OR UPDATE OF facility_id, parent_department_id
ON departments
FOR EACH ROW EXECUTE FUNCTION validate_department_hierarchy();

CREATE OR REPLACE FUNCTION validate_specialty_hierarchy()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    creates_cycle BOOLEAN;
BEGIN
    IF NEW.parent_specialty_id IS NULL THEN
        RETURN NEW;
    END IF;

    WITH RECURSIVE ancestors AS (
        SELECT id, parent_specialty_id
        FROM specialties
        WHERE id = NEW.parent_specialty_id
        UNION ALL
        SELECT s.id, s.parent_specialty_id
        FROM specialties s
        JOIN ancestors a ON s.id = a.parent_specialty_id
    )
    SELECT EXISTS (SELECT 1 FROM ancestors WHERE id = NEW.id)
    INTO creates_cycle;

    IF creates_cycle THEN
        RAISE EXCEPTION 'Specialty hierarchy cycle detected';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_specialties_validate_hierarchy
BEFORE INSERT OR UPDATE OF parent_specialty_id
ON specialties
FOR EACH ROW EXECUTE FUNCTION validate_specialty_hierarchy();

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

CREATE OR REPLACE FUNCTION validate_role_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    facility_org UUID;
BEGIN
    IF NEW.facility_id IS NOT NULL THEN
        SELECT organization_id INTO facility_org FROM facilities WHERE id = NEW.facility_id;
        IF facility_org <> NEW.organization_id THEN
            RAISE EXCEPTION 'Role facility must belong to role organization';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_roles_validate_scope
BEFORE INSERT OR UPDATE OF organization_id, facility_id
ON roles
FOR EACH ROW EXECUTE FUNCTION validate_role_scope();

CREATE OR REPLACE FUNCTION validate_membership_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    facility_org UUID;
BEGIN
    IF NEW.facility_id IS NOT NULL THEN
        SELECT organization_id INTO facility_org FROM facilities WHERE id = NEW.facility_id;
        IF facility_org <> NEW.organization_id THEN
            RAISE EXCEPTION 'Membership facility must belong to membership organization';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_user_memberships_validate_scope
BEFORE INSERT OR UPDATE OF organization_id, facility_id
ON user_memberships
FOR EACH ROW EXECUTE FUNCTION validate_membership_scope();

CREATE OR REPLACE FUNCTION validate_user_role_assignment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    role_org UUID;
    role_facility UUID;
    has_membership BOOLEAN;
BEGIN
    SELECT organization_id, facility_id
      INTO role_org, role_facility
    FROM roles
    WHERE id = NEW.role_id AND is_active;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Assigned role must exist and be active';
    END IF;

    IF role_org IS NULL AND role_facility IS NULL THEN
        RETURN NEW;
    END IF;

    IF role_facility IS NULL THEN
        SELECT EXISTS (
            SELECT 1
            FROM user_memberships
            WHERE user_id = NEW.user_id
              AND organization_id = role_org
              AND facility_id IS NULL
              AND is_active
              AND starts_at <= NEW.starts_at
              AND (ends_at IS NULL OR ends_at >= NEW.starts_at)
        ) INTO has_membership;
    ELSE
        SELECT EXISTS (
            SELECT 1
            FROM user_memberships
            WHERE user_id = NEW.user_id
              AND organization_id = role_org
              AND facility_id = role_facility
              AND is_active
              AND starts_at <= NEW.starts_at
              AND (ends_at IS NULL OR ends_at >= NEW.starts_at)
        ) INTO has_membership;
    END IF;

    IF NOT has_membership THEN
        RAISE EXCEPTION 'User requires an active membership matching the role scope';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_user_role_assignments_validate
BEFORE INSERT OR UPDATE OF user_id, role_id, starts_at, ends_at, is_active
ON user_role_assignments
FOR EACH ROW EXECUTE FUNCTION validate_user_role_assignment();

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

CREATE OR REPLACE FUNCTION validate_patient_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    facility_org UUID;
BEGIN
    IF NEW.registered_facility_id IS NOT NULL THEN
        SELECT organization_id INTO facility_org FROM facilities WHERE id = NEW.registered_facility_id;
        IF facility_org <> NEW.organization_id THEN
            RAISE EXCEPTION 'Patient registered facility must belong to patient organization';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_patients_validate_scope
BEFORE INSERT OR UPDATE OF organization_id, registered_facility_id
ON patients
FOR EACH ROW EXECUTE FUNCTION validate_patient_scope();

CREATE OR REPLACE FUNCTION validate_patient_identifier_scope()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    patient_org UUID;
    type_org UUID;
BEGIN
    SELECT organization_id INTO patient_org FROM patients WHERE id = NEW.patient_id;
    SELECT organization_id INTO type_org FROM patient_identifier_types WHERE id = NEW.identifier_type_id;

    IF type_org IS NOT NULL AND type_org <> patient_org THEN
        RAISE EXCEPTION 'Patient identifier type is outside the patient organization';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_patient_identifiers_validate_scope
BEFORE INSERT OR UPDATE OF patient_id, identifier_type_id
ON patient_identifiers
FOR EACH ROW EXECUTE FUNCTION validate_patient_identifier_scope();

CREATE OR REPLACE FUNCTION validate_patient_access_grant()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    patient_org UUID;
    patient_user UUID;
    related_patient UUID;
    related_user UUID;
    role_org UUID;
    role_active BOOLEAN;
BEGIN
    SELECT organization_id, user_id INTO patient_org, patient_user
    FROM patients WHERE id = NEW.patient_id;

    SELECT patient_id, linked_user_id INTO related_patient, related_user
    FROM patient_related_persons WHERE id = NEW.related_person_id;

    SELECT organization_id, is_active INTO role_org, role_active
    FROM roles WHERE id = NEW.role_id;

    IF related_patient <> NEW.patient_id THEN
        RAISE EXCEPTION 'Related person does not belong to the selected patient';
    END IF;

    IF related_user IS NULL OR related_user <> NEW.grantee_user_id THEN
        RAISE EXCEPTION 'Related person linked user must match grantee user';
    END IF;

    IF patient_user IS NOT NULL AND patient_user = NEW.grantee_user_id THEN
        RAISE EXCEPTION 'Patient cannot receive a related-person access grant to their own record';
    END IF;

    IF NOT role_active OR role_org IS DISTINCT FROM patient_org THEN
        RAISE EXCEPTION 'Patient access role must be active and scoped to the patient organization';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_patient_access_grants_validate
BEFORE INSERT OR UPDATE OF patient_id, related_person_id, grantee_user_id, role_id
ON patient_access_grants
FOR EACH ROW EXECUTE FUNCTION validate_patient_access_grant();

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

CREATE OR REPLACE FUNCTION validate_practitioner_credential()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    practitioner_org UUID;
    type_org UUID;
    expiry_required BOOLEAN;
    verification_required BOOLEAN;
BEGIN
    SELECT organization_id INTO practitioner_org FROM practitioners WHERE id = NEW.practitioner_id;
    SELECT organization_id, requires_expiry_date, requires_verification
      INTO type_org, expiry_required, verification_required
    FROM practitioner_credential_types
    WHERE id = NEW.credential_type_id;

    IF type_org IS NOT NULL AND type_org <> practitioner_org THEN
        RAISE EXCEPTION 'Credential type is outside practitioner organization';
    END IF;

    IF expiry_required AND NEW.expires_on IS NULL THEN
        RAISE EXCEPTION 'Credential type requires an expiry date';
    END IF;

    IF verification_required AND NEW.verification_status = 'unverified' AND NEW.is_active THEN
        -- Allowed while onboarding; service authorization must still reject it.
        NULL;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_practitioner_credentials_validate
BEFORE INSERT OR UPDATE
ON practitioner_credentials
FOR EACH ROW EXECUTE FUNCTION validate_practitioner_credential();

CREATE OR REPLACE FUNCTION validate_practitioner_availability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    assignment_start DATE;
    assignment_end DATE;
    conflicting BOOLEAN;
BEGIN
    SELECT starts_on, ends_on INTO assignment_start, assignment_end
    FROM practitioner_facility_assignments
    WHERE id = NEW.practitioner_facility_assignment_id;

    IF NEW.valid_from < assignment_start
       OR (assignment_end IS NOT NULL AND (NEW.valid_until IS NULL OR NEW.valid_until > assignment_end)) THEN
        RAISE EXCEPTION 'Availability period must remain within facility assignment dates';
    END IF;

    IF NEW.is_active THEN
        SELECT EXISTS (
            SELECT 1
            FROM practitioner_availability_periods p
            WHERE p.practitioner_facility_assignment_id = NEW.practitioner_facility_assignment_id
              AND p.day_of_week = NEW.day_of_week
              AND p.id <> NEW.id
              AND p.is_active
              AND daterange(p.valid_from, COALESCE(p.valid_until, 'infinity'::date), '[]')
                  && daterange(NEW.valid_from, COALESCE(NEW.valid_until, 'infinity'::date), '[]')
              AND int4range(
                    EXTRACT(EPOCH FROM p.starts_at)::INTEGER,
                    EXTRACT(EPOCH FROM p.ends_at)::INTEGER,
                    '[)'
                  ) && int4range(
                    EXTRACT(EPOCH FROM NEW.starts_at)::INTEGER,
                    EXTRACT(EPOCH FROM NEW.ends_at)::INTEGER,
                    '[)'
                  )
        ) INTO conflicting;

        IF conflicting THEN
            RAISE EXCEPTION 'Practitioner availability overlaps another active period';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_practitioner_availability_validate
BEFORE INSERT OR UPDATE
ON practitioner_availability_periods
FOR EACH ROW EXECUTE FUNCTION validate_practitioner_availability();

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

CREATE TRIGGER trg_audit_logs_validate_scope
BEFORE INSERT OR UPDATE OF organization_id, facility_id
ON audit_logs
FOR EACH ROW EXECUTE FUNCTION validate_org_facility_pair();

CREATE TRIGGER trg_report_exports_validate_scope
BEFORE INSERT OR UPDATE OF organization_id, facility_id
ON report_exports
FOR EACH ROW EXECUTE FUNCTION validate_org_facility_pair();

-- Correct credential decision semantics: both verified and rejected are reviewed outcomes.
ALTER TABLE practitioner_credentials
    DROP CONSTRAINT ck_practitioner_credentials_verification;

ALTER TABLE practitioner_credentials
    ADD CONSTRAINT ck_practitioner_credentials_verification CHECK (
        (verification_status IN ('verified', 'rejected') AND verified_at IS NOT NULL AND verified_by_id IS NOT NULL)
        OR
        (verification_status IN ('unverified', 'pending') AND verified_at IS NULL AND verified_by_id IS NULL)
    );

-- Appointment creation must never consume an already full slot.
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
           OR slot_status IN ('full', 'blocked', 'cancelled') THEN
            RAISE EXCEPTION 'Appointment does not match an available appointment slot';
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

-- ================================================================
-- APPEND-ONLY PROTECTION FOR DOMAIN HISTORY TABLES
-- ================================================================

CREATE OR REPLACE FUNCTION prevent_history_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only; create a corrective event instead', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER trg_appointment_status_history_append_only
BEFORE UPDATE OR DELETE ON appointment_status_history
FOR EACH ROW EXECUTE FUNCTION prevent_history_mutation();

CREATE TRIGGER trg_queue_entry_events_append_only
BEFORE UPDATE OR DELETE ON queue_entry_events
FOR EACH ROW EXECUTE FUNCTION prevent_history_mutation();

CREATE TRIGGER trg_queue_wait_time_predictions_append_only
BEFORE UPDATE OR DELETE ON queue_wait_time_predictions
FOR EACH ROW EXECUTE FUNCTION prevent_history_mutation();

CREATE TRIGGER trg_audit_logs_append_only
BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION prevent_history_mutation();

-- ================================================================
-- PERFORMANCE INDEXES
-- PostgreSQL does not automatically index foreign-key columns.
-- ================================================================

CREATE INDEX idx_facilities_organization ON facilities (organization_id);
CREATE INDEX idx_facilities_type ON facilities (facility_type_id);
CREATE INDEX idx_facilities_active ON facilities (is_active);

CREATE INDEX idx_departments_facility ON departments (facility_id);
CREATE INDEX idx_departments_parent ON departments (parent_department_id);
CREATE INDEX idx_specialties_parent ON specialties (parent_specialty_id);
CREATE INDEX idx_facility_specialties_facility ON facility_specialties (facility_id);
CREATE INDEX idx_facility_specialties_specialty ON facility_specialties (specialty_id);
CREATE INDEX idx_facility_specialties_department ON facility_specialties (department_id);
CREATE INDEX idx_service_points_facility ON service_points (facility_id);
CREATE INDEX idx_service_points_department ON service_points (department_id);
CREATE INDEX idx_service_points_type ON service_points (service_point_type_id);
CREATE INDEX idx_consultation_rooms_facility ON consultation_rooms (facility_id);
CREATE INDEX idx_consultation_rooms_department ON consultation_rooms (department_id);
CREATE INDEX idx_facility_operating_hours_lookup ON facility_operating_hours (facility_id, day_of_week, is_active);
CREATE INDEX idx_facility_schedule_exceptions_lookup ON facility_schedule_exceptions (facility_id, exception_date, is_active);

CREATE INDEX idx_roles_organization ON roles (organization_id);
CREATE INDEX idx_roles_facility ON roles (facility_id);
CREATE INDEX idx_role_permissions_role_active ON role_permissions (role_id, is_active);
CREATE INDEX idx_role_permissions_permission ON role_permissions (permission_id);
CREATE INDEX idx_user_memberships_user_active ON user_memberships (user_id, is_active);
CREATE INDEX idx_user_memberships_org ON user_memberships (organization_id);
CREATE INDEX idx_user_memberships_facility ON user_memberships (facility_id);
CREATE INDEX idx_user_role_assignments_user_active ON user_role_assignments (user_id, is_active);
CREATE INDEX idx_user_role_assignments_role ON user_role_assignments (role_id);

CREATE INDEX idx_patients_organization ON patients (organization_id);
CREATE INDEX idx_patients_registered_facility ON patients (registered_facility_id);
CREATE INDEX idx_patients_name ON patients (organization_id, last_name, first_name);
CREATE INDEX idx_patient_identifier_types_org ON patient_identifier_types (organization_id);
CREATE INDEX idx_patient_identifiers_patient ON patient_identifiers (patient_id);
CREATE INDEX idx_patient_identifiers_type ON patient_identifiers (identifier_type_id);
CREATE INDEX idx_patient_addresses_patient ON patient_addresses (patient_id);
CREATE INDEX idx_patient_related_persons_patient ON patient_related_persons (patient_id);
CREATE INDEX idx_patient_related_persons_relationship ON patient_related_persons (relationship_type_id);
CREATE INDEX idx_related_person_contacts_person ON related_person_contacts (related_person_id);
CREATE INDEX idx_patient_access_grants_patient_active ON patient_access_grants (patient_id, is_active);
CREATE INDEX idx_patient_access_grants_grantee_active ON patient_access_grants (grantee_user_id, is_active);
CREATE INDEX idx_patient_access_grants_role ON patient_access_grants (role_id);

CREATE INDEX idx_practitioners_organization ON practitioners (organization_id);
CREATE INDEX idx_practitioners_type ON practitioners (practitioner_type_id);
CREATE INDEX idx_practitioners_name ON practitioners (organization_id, last_name, first_name);
CREATE INDEX idx_practitioner_facility_assignments_practitioner ON practitioner_facility_assignments (practitioner_id, is_active);
CREATE INDEX idx_practitioner_facility_assignments_facility ON practitioner_facility_assignments (facility_id, is_active);
CREATE INDEX idx_practitioner_department_assignments_pfa ON practitioner_department_assignments (practitioner_facility_assignment_id, is_active);
CREATE INDEX idx_practitioner_department_assignments_department ON practitioner_department_assignments (department_id);
CREATE INDEX idx_practitioner_specialty_assignments_pfa ON practitioner_specialty_assignments (practitioner_facility_assignment_id, is_active);
CREATE INDEX idx_practitioner_specialty_assignments_specialty ON practitioner_specialty_assignments (facility_specialty_id);
CREATE INDEX idx_practitioner_credential_types_org ON practitioner_credential_types (organization_id);
CREATE INDEX idx_practitioner_credentials_practitioner ON practitioner_credentials (practitioner_id, is_active);
CREATE INDEX idx_practitioner_credentials_type ON practitioner_credentials (credential_type_id);

CREATE INDEX idx_practitioner_availability_lookup
    ON practitioner_availability_periods (practitioner_facility_assignment_id, day_of_week, is_active);
CREATE INDEX idx_practitioner_availability_dates
    ON practitioner_availability_periods (valid_from, valid_until);
CREATE INDEX idx_practitioner_leave_lookup
    ON practitioner_leave_requests (practitioner_facility_assignment_id, status, starts_at, ends_at);
CREATE INDEX idx_practitioner_shifts_practitioner_time
    ON practitioner_shifts (practitioner_facility_assignment_id, starts_at, ends_at);
CREATE INDEX idx_practitioner_shifts_department
    ON practitioner_shifts (practitioner_department_assignment_id);
CREATE INDEX idx_practitioner_shifts_service_point_time
    ON practitioner_shifts (service_point_id, starts_at, ends_at);
CREATE INDEX idx_practitioner_shifts_room_time
    ON practitioner_shifts (consultation_room_id, starts_at, ends_at);
CREATE INDEX idx_practitioner_shifts_status ON practitioner_shifts (status);

CREATE INDEX idx_appointments_facility_time ON appointments (facility_id, scheduled_start);
CREATE INDEX idx_appointments_patient_time ON appointments (patient_id, scheduled_start);
CREATE INDEX idx_appointments_specialty_time ON appointments (facility_specialty_id, scheduled_start);
CREATE INDEX idx_appointments_practitioner_time ON appointments (practitioner_facility_assignment_id, scheduled_start);
CREATE INDEX idx_appointments_shift ON appointments (practitioner_shift_id);
CREATE INDEX idx_appointments_slot ON appointments (appointment_slot_id);
CREATE INDEX idx_appointments_status_time ON appointments (status, scheduled_start);
CREATE INDEX idx_appointments_rescheduled_from ON appointments (rescheduled_from_id);
CREATE INDEX idx_appointment_history_appointment_time ON appointment_status_history (appointment_id, changed_at);
CREATE INDEX idx_appointment_history_status_time ON appointment_status_history (to_status, changed_at);
CREATE INDEX idx_appointment_slots_shift_time ON appointment_slots (practitioner_shift_id, starts_at);
CREATE INDEX idx_appointment_slots_specialty_time ON appointment_slots (facility_specialty_id, starts_at);
CREATE INDEX idx_appointment_slots_available ON appointment_slots (starts_at)
    WHERE status = 'available' AND is_online_bookable;

CREATE INDEX idx_patient_checkins_facility_time ON patient_checkins (facility_id, checked_in_at);
CREATE INDEX idx_patient_checkins_patient_time ON patient_checkins (patient_id, checked_in_at);
CREATE INDEX idx_patient_checkins_specialty ON patient_checkins (facility_specialty_id);
CREATE INDEX idx_checkin_tokens_appointment ON checkin_tokens (appointment_id);
CREATE INDEX idx_checkin_tokens_expiry ON checkin_tokens (expires_at)
    WHERE used_at IS NULL AND revoked_at IS NULL;

CREATE INDEX idx_queues_date_status ON queues (queue_date, status);
CREATE INDEX idx_queues_service_point_status ON queues (service_point_id, status);
CREATE INDEX idx_queue_entries_queue_status ON queue_entries (queue_id, status);
CREATE INDEX idx_queue_entries_order ON queue_entries (queue_id, priority_level DESC, joined_at, sequence_number);
CREATE INDEX idx_queue_entries_checkin ON queue_entries (patient_checkin_id);
CREATE INDEX idx_queue_entries_shift ON queue_entries (practitioner_shift_id);
CREATE INDEX idx_queue_transfers_time ON queue_transfers (transferred_at);
CREATE INDEX idx_queue_entry_events_entry_time ON queue_entry_events (queue_entry_id, occurred_at);
CREATE INDEX idx_queue_entry_events_type_time ON queue_entry_events (event_type, occurred_at);
CREATE INDEX idx_queue_predictions_entry_time ON queue_wait_time_predictions (queue_entry_id, generated_at DESC);
CREATE INDEX idx_queue_predictions_model_time ON queue_wait_time_predictions (model_version, generated_at);

CREATE INDEX idx_patient_notifications_dispatch
    ON patient_notifications (status, scheduled_for)
    WHERE status IN ('pending', 'processing');
CREATE INDEX idx_patient_notifications_patient_time ON patient_notifications (patient_id, created_at DESC);
CREATE INDEX idx_patient_notifications_appointment ON patient_notifications (appointment_id);
CREATE INDEX idx_patient_notifications_queue_entry ON patient_notifications (queue_entry_id);
CREATE INDEX idx_patient_notifications_recipient ON patient_notifications (recipient_user_id);
CREATE INDEX idx_user_push_devices_user_active ON user_push_devices (user_id, is_active);

CREATE INDEX idx_audit_logs_org_time ON audit_logs (organization_id, occurred_at DESC);
CREATE INDEX idx_audit_logs_facility_time ON audit_logs (facility_id, occurred_at DESC);
CREATE INDEX idx_audit_logs_actor_time ON audit_logs (actor_user_id, occurred_at DESC);
CREATE INDEX idx_audit_logs_entity ON audit_logs (entity_type, entity_id, occurred_at DESC);
CREATE INDEX idx_audit_logs_request ON audit_logs (request_id) WHERE request_id IS NOT NULL;
CREATE INDEX idx_report_exports_requester_time ON report_exports (requested_by_id, created_at DESC);
CREATE INDEX idx_report_exports_org_status ON report_exports (organization_id, status, created_at DESC);
CREATE INDEX idx_report_exports_facility ON report_exports (facility_id);

-- ================================================================
-- AUTOMATIC updated_at TRIGGERS
-- ================================================================

DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'organizations',
        'facility_types',
        'facilities',
        'departments',
        'specialties',
        'facility_specialties',
        'service_point_types',
        'service_points',
        'consultation_rooms',
        'facility_operating_hours',
        'facility_schedule_exceptions',
        'users',
        'roles',
        'permissions',
        'role_permissions',
        'user_memberships',
        'user_role_assignments',
        'patients',
        'patient_identifier_types',
        'patient_identifiers',
        'patient_addresses',
        'relationship_types',
        'patient_related_persons',
        'related_person_contacts',
        'patient_access_grants',
        'practitioner_types',
        'practitioners',
        'practitioner_facility_assignments',
        'practitioner_department_assignments',
        'practitioner_specialty_assignments',
        'practitioner_credential_types',
        'practitioner_credentials',
        'practitioner_availability_periods',
        'practitioner_leave_requests',
        'practitioner_shifts',
        'appointments',
        'appointment_slots',
        'patient_checkins',
        'queues',
        'queue_entries',
        'patient_notifications',
        'user_push_devices',
        'facility_flow_settings',
        'report_exports'
    ]
    LOOP
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION set_updated_at()',
            'trg_' || table_name || '_set_updated_at',
            table_name
        );
    END LOOP;
END;
$$;

-- ================================================================
-- DATABASE DOCUMENTATION
-- ================================================================

COMMENT ON TABLE appointment_status_history IS
'Append-only appointment lifecycle history. Current state remains in appointments.status.';

COMMENT ON TABLE queue_entry_events IS
'Append-only operational queue history including repeated call attempts.';

COMMENT ON TABLE queue_wait_time_predictions IS
'Append-only prediction history used to show estimates and evaluate prediction accuracy.';

COMMENT ON TABLE audit_logs IS
'Append-only security and administrative audit trail. Sensitive values must be redacted before insertion.';

COMMENT ON COLUMN appointments.reason_for_visit_encrypted IS
'Application-encrypted sensitive visit reason. Never log or expose without authorization.';

COMMENT ON COLUMN patient_identifiers.value_hash IS
'Keyed HMAC-SHA-256 of the normalized identifier, used for equality lookup without plaintext storage.';

COMMENT ON COLUMN practitioner_credentials.credential_number_hash IS
'Keyed HMAC-SHA-256 of the normalized credential number.';

COMMENT ON COLUMN checkin_tokens.token_hash IS
'Keyed HMAC-SHA-256 of the random QR check-in token. The raw token is never stored.';

COMMENT ON COLUMN user_push_devices.token_hash IS
'Keyed HMAC-SHA-256 of the push token. The raw token is stored only in encrypted form.';


-- ================================================================
-- FINAL INTEGRITY HARDENING
-- ================================================================

ALTER TABLE users
    ADD CONSTRAINT ck_users_email_verification_target CHECK (
        email_verified_at IS NULL OR email IS NOT NULL
    ),
    ADD CONSTRAINT ck_users_phone_verification_target CHECK (
        phone_verified_at IS NULL OR phone_number IS NOT NULL
    );

ALTER TABLE patients
    ADD CONSTRAINT ck_patients_estimated_dob CHECK (
        NOT date_of_birth_is_estimated OR date_of_birth IS NOT NULL
    );

ALTER TABLE patient_identifiers
    ADD CONSTRAINT ck_patient_identifiers_primary_active CHECK (NOT is_primary OR is_active);

ALTER TABLE patient_addresses
    ADD CONSTRAINT ck_patient_addresses_primary_active CHECK (NOT is_primary OR is_active);

ALTER TABLE related_person_contacts
    ADD CONSTRAINT ck_related_person_contacts_primary_active CHECK (NOT is_primary OR is_active);

ALTER TABLE practitioner_facility_assignments
    ADD CONSTRAINT ck_practitioner_facility_primary_active CHECK (NOT is_primary OR is_active);

ALTER TABLE practitioner_department_assignments
    ADD CONSTRAINT ck_practitioner_department_primary_active CHECK (NOT is_primary OR is_active);

ALTER TABLE practitioner_specialty_assignments
    ADD CONSTRAINT ck_practitioner_specialty_primary_active CHECK (NOT is_primary OR is_active);

ALTER TABLE appointments
    ADD CONSTRAINT ck_appointments_practitioner_assignment_bundle CHECK (
        (
            practitioner_facility_assignment_id IS NULL
            AND practitioner_specialty_assignment_id IS NULL
            AND practitioner_shift_id IS NULL
            AND appointment_slot_id IS NULL
        )
        OR
        (
            practitioner_facility_assignment_id IS NOT NULL
            AND practitioner_specialty_assignment_id IS NOT NULL
        )
    );

CREATE OR REPLACE FUNCTION validate_patient_date_of_birth()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.date_of_birth IS NOT NULL AND NEW.date_of_birth > CURRENT_DATE THEN
        RAISE EXCEPTION 'Patient date of birth cannot be in the future';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_patients_validate_date_of_birth
BEFORE INSERT OR UPDATE OF date_of_birth
ON patients
FOR EACH ROW EXECUTE FUNCTION validate_patient_date_of_birth();

CREATE OR REPLACE FUNCTION validate_user_role_assignment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    role_org UUID;
    role_facility UUID;
    has_membership BOOLEAN;
BEGIN
    SELECT organization_id, facility_id
      INTO role_org, role_facility
    FROM roles
    WHERE id = NEW.role_id AND is_active;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Assigned role must exist and be active';
    END IF;

    IF role_org IS NULL AND role_facility IS NULL THEN
        RETURN NEW;
    END IF;

    IF role_facility IS NULL THEN
        SELECT EXISTS (
            SELECT 1
            FROM user_memberships
            WHERE user_id = NEW.user_id
              AND organization_id = role_org
              AND facility_id IS NULL
              AND is_active
              AND starts_at <= NEW.starts_at
              AND (
                    ends_at IS NULL
                    OR (NEW.ends_at IS NOT NULL AND ends_at >= NEW.ends_at)
                  )
        ) INTO has_membership;
    ELSE
        SELECT EXISTS (
            SELECT 1
            FROM user_memberships
            WHERE user_id = NEW.user_id
              AND organization_id = role_org
              AND facility_id = role_facility
              AND is_active
              AND starts_at <= NEW.starts_at
              AND (
                    ends_at IS NULL
                    OR (NEW.ends_at IS NOT NULL AND ends_at >= NEW.ends_at)
                  )
        ) INTO has_membership;
    END IF;

    IF NOT has_membership THEN
        RAISE EXCEPTION 'User requires an active membership covering the full role-assignment period';
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION validate_specialty_department_coverage()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    specialty_department UUID;
    has_department_assignment BOOLEAN;
BEGIN
    SELECT department_id INTO specialty_department
    FROM facility_specialties
    WHERE id = NEW.facility_specialty_id;

    IF specialty_department IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM practitioner_department_assignments pda
        WHERE pda.practitioner_facility_assignment_id = NEW.practitioner_facility_assignment_id
          AND pda.department_id = specialty_department
          AND pda.is_active
          AND pda.starts_on <= NEW.starts_on
          AND (
                pda.ends_on IS NULL
                OR (NEW.ends_on IS NOT NULL AND pda.ends_on >= NEW.ends_on)
              )
    ) INTO has_department_assignment;

    IF NOT has_department_assignment THEN
        RAISE EXCEPTION 'Department assignment must cover the full specialty-assignment period';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_practitioner_specialty_department_coverage
BEFORE INSERT OR UPDATE OF practitioner_facility_assignment_id, facility_specialty_id, starts_on, ends_on, is_active
ON practitioner_specialty_assignments
FOR EACH ROW EXECUTE FUNCTION validate_specialty_department_coverage();

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

COMMIT;
