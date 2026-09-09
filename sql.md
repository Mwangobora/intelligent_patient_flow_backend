# CODEX IMPLEMENTATION BRIEF
## Upgrade `intelligent_patient_flow_database.sql` from Patient Flow / Scheduling to a Complete Hospital Management System

### Target file
`intelligent_patient_flow_database.sql`

### Current baseline
The current SQL file is a PostgreSQL 15+ production-oriented schema for the **Intelligent Patient Flow and Appointment Scheduling System**.

It currently contains **50 business tables** covering:

- organizations and facilities
- departments and specialties
- service points and consultation rooms
- users, memberships, roles and permissions
- patients and delegated access
- practitioners, professional assignments and credentials
- practitioner availability, leave and shifts
- appointments and appointment slots
- secure patient check-in
- queues, queue entries, queue transfers and queue history
- waiting-time prediction
- patient notifications
- audit logs
- report exports

The existing schema is working and is the foundation of the new system.

---

# 1. PRIMARY OBJECTIVE

Extend the existing database into a **complete Hospital Management System (HMS/HMIS)** while preserving all current patient-flow and scheduling functionality.

The upgraded system must support the complete patient journey:

```text
Patient registration
    ↓
Appointment / Walk-in
    ↓
Check-in
    ↓
Queue
    ↓
Encounter opened
    ↓
Triage
    ↓
Doctor / Practitioner consultation
    ↓
Diagnosis
    ↓
Lab / Imaging / Procedure if required
    ↓
Doctor review
    ↓
Prescription
    ↓
Pharmacy dispensing
    ↓
Charges
    ↓
Invoice
    ↓
Insurance / Payment
    ↓
Follow-up / Admission / Discharge
```

It must also support:

```text
Inventory
Procurement
Inpatient care
Ward / Bed management
Nursing
HR
Payroll
Finance / Accounting
Insurance
Reporting / Audit
```

---

# 2. ABSOLUTE RULES — DO NOT BREAK THE CURRENT SYSTEM

Codex must follow these rules before modifying anything.

## 2.1 Preserve all existing tables

Do **not**:

- drop any of the current 50 business tables
- rename current tables
- rename existing columns
- remove existing constraints
- weaken existing security rules
- destroy existing triggers
- change existing queue semantics unless strictly required for compatibility
- replace practitioner scheduling with a new scheduling system
- create another independent queue engine

The current schema must remain backward compatible.

If a current table needs to be referenced by a new module, add the relationship from the **new table** whenever possible instead of modifying the existing table.

---

## 2.2 Preserve existing design conventions

Continue using the current conventions:

- PostgreSQL 15+
- UUID primary keys using `gen_random_uuid()`
- plural `snake_case` table names
- `<entity>_id` foreign-key naming
- `TIMESTAMPTZ` for actual moments in time
- UTC database/application timestamps
- `CITEXT` where case-insensitive uniqueness is required
- explicit `CHECK` constraints
- explicit unique/partial unique indexes
- `ON DELETE RESTRICT` for operational/history data
- `ON DELETE SET NULL` only where actor history should survive user removal
- `ON DELETE CASCADE` only for true dependent configuration
- `created_at` and `updated_at`
- current `set_updated_at()` trigger pattern
- application-level encryption for sensitive `*_encrypted` values
- HMAC-SHA-256 for searchable sensitive hashes where required
- append-only lifecycle/history tables where appropriate
- database validation functions/triggers for important cross-table scope rules

Do not replace these conventions with a different style.

---

# 3. MOST IMPORTANT ARCHITECTURAL CHANGE: ENCOUNTERS

The upgraded HMS must revolve around an **encounter**, not an appointment.

Definitions:

```text
Appointment = planned visit
Patient Check-in = patient actually arrived
Queue Entry = patient waiting / receiving a specific service
Encounter = actual healthcare episode
Clinical Order = requested healthcare activity
Result / Dispense / Procedure = activity actually performed
Charge = billable event
Invoice = amount owed
Payment = amount actually paid
```

Walk-in patients may have no appointment.

Therefore, all clinical activity must be linked primarily to `encounters`.

---

# 4. ADD CLINICAL ENCOUNTER MODULE

Create the following tables.

---

## 4.1 `encounters`

Purpose:
Central record for one actual patient care episode.

Recommended columns:

```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,

patient_checkin_id UUID NOT NULL REFERENCES patient_checkins(id) ON DELETE RESTRICT,
appointment_id UUID REFERENCES appointments(id) ON DELETE RESTRICT,

department_id UUID REFERENCES departments(id) ON DELETE RESTRICT,
facility_specialty_id UUID REFERENCES facility_specialties(id) ON DELETE RESTRICT,

attending_practitioner_facility_assignment_id UUID
    REFERENCES practitioner_facility_assignments(id)
    ON DELETE RESTRICT,

encounter_number VARCHAR(50) NOT NULL,

encounter_type VARCHAR(30) NOT NULL,
status VARCHAR(30) NOT NULL DEFAULT 'opened',

opened_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
opened_by_id UUID REFERENCES users(id) ON DELETE SET NULL,

completed_at TIMESTAMPTZ,
completed_by_id UUID REFERENCES users(id) ON DELETE SET NULL,

cancelled_at TIMESTAMPTZ,
cancelled_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
cancellation_reason VARCHAR(250),

created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
```

Recommended `encounter_type` values:

```text
outpatient
emergency
inpatient
follow_up
telemedicine
```

Recommended statuses:

```text
opened
triage
waiting_practitioner
in_consultation
awaiting_lab
awaiting_imaging
awaiting_review
awaiting_pharmacy
awaiting_payment
admitted
completed
cancelled
```

Required rules:

- `encounter_number` unique within facility.
- only one active encounter per `patient_checkin_id`.
- patient check-in must belong to same patient and facility.
- appointment, if present, must belong to same patient and facility.
- department and specialty must belong to the selected facility.
- attending practitioner assignment must belong to the encounter organization/facility.
- completed encounter requires `completed_at`.
- cancelled encounter requires `cancelled_at`.
- completed/cancelled timestamps must be consistent with status.
- prevent invalid tenant/facility cross references.

Do **not** add `encounter_id` to current queue tables unless absolutely necessary. The current relationship can be:

```text
encounters.patient_checkin_id
        ↓
patient_checkins
        ↓
queue_entries
```

---

## 4.2 `encounter_status_history`

Append-only encounter lifecycle.

Columns:

```text
id
encounter_id
from_status
to_status
change_source
changed_by_id
reason
changed_at
created_at
```

Rules:

- append-only
- initial row may have `from_status IS NULL`
- all later rows require previous status
- latest history status must match `encounters.status`
- encounter status update + history insert must occur atomically

---

# 5. TRIAGE MODULE

Create:

```text
triage_assessments
vital_signs
```

---

## 5.1 `triage_assessments`

Suggested fields:

```text
id
encounter_id
performed_by_practitioner_facility_assignment_id
triage_level
chief_complaint_encrypted
pain_score
mobility_status
consciousness_level
notes_encrypted
started_at
completed_at
created_at
updated_at
```

Recommended `triage_level`:

```text
1 routine
2 urgent
3 very_urgent
4 emergency
```

Rules:

- pain score between 0 and 10 when supplied.
- practitioner must belong to same facility.
- encounter must be active.

---

## 5.2 `vital_signs`

Vitals can be taken many times during one encounter.

Fields:

```text
id
encounter_id
recorded_by_practitioner_facility_assignment_id

temperature_c
systolic_bp
diastolic_bp
heart_rate
respiratory_rate
oxygen_saturation
weight_kg
height_cm
blood_glucose
pain_score

recorded_at
created_at
```

Validation:

- numeric physiological fields cannot be negative where impossible
- oxygen saturation between 0 and 100
- pain score between 0 and 10
- weight and height positive when supplied
- do NOT store BMI; derive it

---

# 6. PATIENT CLINICAL HISTORY

Do not add medical history columns directly to `patients`.

Create:

```text
patient_allergies
patient_conditions
```

---

## 6.1 `patient_allergies`

Suggested fields:

```text
id
patient_id
allergen
allergy_type
reaction
severity
status
recorded_by_id
recorded_at
resolved_at
created_at
updated_at
```

Status example:

```text
active
inactive
resolved
entered_in_error
```

---

## 6.2 `patient_conditions`

Suggested fields:

```text
id
patient_id
diagnosis_code_id NULL
condition_name
status
onset_date
resolved_date
notes_encrypted
recorded_by_id
created_at
updated_at
```

Used for chronic or important historical conditions.

---

# 7. CLINICAL NOTES

Create:

```text
clinical_notes
```

Suggested fields:

```text
id
encounter_id
practitioner_facility_assignment_id

note_type

subjective_encrypted
objective_encrypted
assessment_encrypted
plan_encrypted

supersedes_note_id NULL REFERENCES clinical_notes(id)

signed_at
created_at
updated_at
```

Suggested note types:

```text
consultation
progress
review
specialist
discharge_note
addendum
```

Rules:

- signed clinical notes must not be silently overwritten.
- corrections should create an addendum/new note using `supersedes_note_id`.
- preserve original signed notes.
- sensitive note content must use encrypted columns.

---

# 8. DIAGNOSIS MODULE

Create:

```text
diagnosis_codes
encounter_diagnoses
```

---

## 8.1 `diagnosis_codes`

Fields:

```text
id
coding_system
code
name
description
is_active
created_at
updated_at
```

Allow support for systems such as ICD-10 / ICD-11 without hardcoding one system.

Unique:

```text
(coding_system, code)
```

---

## 8.2 `encounter_diagnoses`

Fields:

```text
id
encounter_id
diagnosis_code_id NULL
diagnosis_text
diagnosis_type
is_primary
diagnosed_by_practitioner_facility_assignment_id
notes_encrypted
diagnosed_at
created_at
```

Diagnosis types:

```text
provisional
differential
confirmed
```

Allow historical progression such as:

```text
Provisional malaria
    ↓
Lab result
    ↓
Confirmed malaria
```

Do not overwrite prior diagnosis history.

---

# 9. LABORATORY MODULE

Create:

```text
lab_tests
lab_test_components
lab_orders
lab_order_items
lab_specimens
lab_result_values
```

---

## 9.1 `lab_tests`

Fields:

```text
id
organization_id
code
name
description
specimen_type
turnaround_minutes
billing_service_id NULL
is_active
created_at
updated_at
```

Unique:

```text
(organization_id, code)
```

---

## 9.2 `lab_test_components`

Needed for panel tests such as FBC.

Fields:

```text
id
lab_test_id
code
name
unit
reference_low
reference_high
display_order
is_active
created_at
updated_at
```

Example:

```text
FBC
 ├ WBC
 ├ RBC
 ├ Hemoglobin
 ├ Platelets
 └ Hematocrit
```

---

## 9.3 `lab_orders`

Fields:

```text
id
encounter_id
ordered_by_practitioner_facility_assignment_id
order_number
priority
clinical_notes_encrypted
status
ordered_at
cancelled_at
cancelled_by_id
cancellation_reason
created_at
updated_at
```

Priority:

```text
routine
urgent
stat
```

Status:

```text
ordered
sample_collection
processing
partially_resulted
resulted
verified
cancelled
```

---

## 9.4 `lab_order_items`

Fields:

```text
id
lab_order_id
lab_test_id
status
ordered_at
collected_at
processing_started_at
resulted_at
verified_at
created_at
updated_at
```

One order may contain several tests.

---

## 9.5 `lab_specimens`

Fields:

```text
id
lab_order_item_id
specimen_number
specimen_type
collected_by_practitioner_facility_assignment_id
collected_at
received_by_practitioner_facility_assignment_id
received_at
status
rejection_reason
created_at
updated_at
```

Status:

```text
pending
collected
received
rejected
processing
disposed
```

`specimen_number` must be traceable and suitably unique.

---

## 9.6 `lab_result_values`

Fields:

```text
id
lab_order_item_id
lab_test_component_id NULL

value_numeric NULL
value_text NULL

unit
reference_low
reference_high

abnormal_flag

entered_by_practitioner_facility_assignment_id
entered_at

verified_by_practitioner_facility_assignment_id NULL
verified_at NULL

notes_encrypted
created_at
updated_at
```

Abnormal flags:

```text
normal
low
high
critical
```

Rules:

- a result should have either a numeric or text value as appropriate.
- verified result requires verifier and verification time.
- preserve results/history.
- do not physically delete verified clinical results.

---

# 10. USE THE CURRENT QUEUE ENGINE FOR LAB / PHARMACY / RADIOLOGY

Do not create tables like:

```text
lab_queues
pharmacy_queues
radiology_queues
```

The current queue engine already supports service points, queues, queue entries and queue transfers.

Use service points such as:

```text
Triage
Doctor Consultation
Laboratory
Doctor Review
Pharmacy
Radiology
Cashier
```

Patient movement:

```text
Doctor Queue
   ↓
Lab order created
   ↓
Existing queue transfer
   ↓
Laboratory Queue
   ↓
Lab completed
   ↓
Existing queue transfer
   ↓
Doctor Review Queue
```

Keep current queue transfer rules intact.

---

# 11. IMAGING / RADIOLOGY MODULE

Create:

```text
imaging_services
imaging_orders
imaging_order_items
imaging_reports
```

---

## 11.1 `imaging_services`

Fields:

```text
id
organization_id
code
name
description
billing_service_id NULL
is_active
created_at
updated_at
```

Examples:

```text
X-Ray
Ultrasound
CT
MRI
ECG
```

---

## 11.2 `imaging_orders`

Fields:

```text
id
encounter_id
ordered_by_practitioner_facility_assignment_id
order_number
clinical_indication_encrypted
priority
status
ordered_at
cancelled_at
cancellation_reason
created_at
updated_at
```

---

## 11.3 `imaging_order_items`

Fields:

```text
id
imaging_order_id
imaging_service_id
body_site
status
performed_at
performed_by_practitioner_facility_assignment_id
created_at
updated_at
```

---

## 11.4 `imaging_reports`

Fields:

```text
id
imaging_order_item_id
findings_encrypted
impression_encrypted
reported_by_practitioner_facility_assignment_id
reported_at
verified_by_practitioner_facility_assignment_id NULL
verified_at NULL
created_at
updated_at
```

Preserve signed/verified reports.

---

# 12. PROCEDURES MODULE

Create:

```text
procedure_catalog
encounter_procedures
```

---

## 12.1 `procedure_catalog`

Fields:

```text
id
organization_id
code
name
description
billing_service_id NULL
is_active
created_at
updated_at
```

Examples:

```text
wound dressing
injection
nebulization
suturing
physiotherapy
minor surgery
dental extraction
```

---

## 12.2 `encounter_procedures`

Fields:

```text
id
encounter_id
procedure_id
ordered_by_practitioner_facility_assignment_id NULL
performed_by_practitioner_facility_assignment_id
status
performed_at
clinical_notes_encrypted
created_at
updated_at
```

---

# 13. PHARMACY / PRESCRIPTION MODULE

Create:

```text
medications
prescriptions
prescription_items
medication_dispenses
```

---

## 13.1 `medications`

Fields:

```text
id
organization_id
code
generic_name
brand_name NULL
strength
strength_unit
dosage_form
route_default NULL
is_active
created_at
updated_at
```

Unique within organization by code.

---

## 13.2 `prescriptions`

Fields:

```text
id
encounter_id
prescription_number
prescribed_by_practitioner_facility_assignment_id
status
prescribed_at
cancelled_at
cancelled_by_id
cancellation_reason
created_at
updated_at
```

Status:

```text
draft
active
partially_dispensed
dispensed
cancelled
```

---

## 13.3 `prescription_items`

Fields:

```text
id
prescription_id
medication_id
dose
dose_unit
route
frequency
duration_value
duration_unit
quantity_prescribed
instructions_encrypted
created_at
updated_at
```

---

## 13.4 `medication_dispenses`

Fields:

```text
id
prescription_item_id
stock_batch_id
quantity_dispensed
dispensed_by_practitioner_facility_assignment_id
dispensed_at
status
notes_encrypted
created_at
```

Important:

```text
quantity_prescribed != quantity_dispensed
```

Do not automatically assume the full prescription was dispensed.

Allow partial dispensing.

---

# 14. GENERIC INVENTORY MODULE

Do not build pharmacy-only inventory.

Create:

```text
inventory_categories
inventory_items
inventory_locations
stock_batches
stock_movements
```

---

## 14.1 `inventory_categories`

Fields:

```text
id
organization_id NULL
code
name
description
is_active
created_at
updated_at
```

Examples:

```text
Medicine
Lab Reagent
Medical Consumable
Surgical
Cleaning
Office
Equipment
```

---

## 14.2 `inventory_items`

Fields:

```text
id
organization_id
category_id
medication_id NULL
sku
name
description
base_unit
reorder_level
is_stock_item
is_active
created_at
updated_at
```

---

## 14.3 `inventory_locations`

Fields:

```text
id
facility_id
department_id NULL
code
name
location_type
is_active
created_at
updated_at
```

Location type examples:

```text
main_store
pharmacy
laboratory
ward
theatre
department_store
```

---

## 14.4 `stock_batches`

Fields:

```text
id
inventory_item_id
inventory_location_id
batch_number
expiry_date NULL
purchase_unit_cost
selling_unit_price NULL
quantity_on_hand
received_at
is_active
created_at
updated_at
```

Rules:

- quantity cannot be negative.
- expiry date must be meaningful when supplied.
- batch/location/item scope must be valid.
- consider uniqueness for `(inventory_item_id, inventory_location_id, batch_number)`.

---

## 14.5 `stock_movements`

Append-only inventory ledger.

Fields:

```text
id
stock_batch_id
inventory_location_id
movement_type
quantity_delta
reference_type
reference_id
performed_by_id
reason
occurred_at
created_at
```

Movement types:

```text
receipt
dispense
issue
transfer_in
transfer_out
return
adjustment
expired
damaged
```

Rules:

- append-only.
- stock movement and `quantity_on_hand` update must occur atomically.
- stock cannot become negative.
- pharmacy dispensing must create stock movement.
- goods receipt must create stock movement.
- transfers should use paired OUT/IN movements or an explicit transfer workflow with atomic enforcement.

---

# 15. BILLING SERVICE CATALOGUE

Create:

```text
services
service_prices
encounter_charges
```

---

## 15.1 `services`

Fields:

```text
id
organization_id
code
name
description
service_category
is_active
created_at
updated_at
```

Categories:

```text
consultation
laboratory
imaging
procedure
pharmacy
admission
bed
other
```

Examples:

```text
CONSULTATION_GENERAL
MALARIA_TEST
FULL_BLOOD_COUNT
CHEST_XRAY
ULTRASOUND
WARD_BED_DAY
WOUND_DRESSING
```

---

## 15.2 `service_prices`

Fields:

```text
id
service_id
facility_id NULL
amount
currency
effective_from
effective_to NULL
is_active
created_at
updated_at
```

Critical rule:

**Never overwrite historical service prices.**

A new price creates a new effective price row.

Prevent overlapping active effective date ranges for the same service/facility context.

---

## 15.3 `encounter_charges`

Fields:

```text
id
encounter_id
service_id
quantity
unit_price
amount
source_type
source_reference_id NULL
status
performed_at
created_by_id
voided_at
voided_by_id
void_reason
created_at
updated_at
```

Source types:

```text
consultation
lab
imaging
procedure
pharmacy
bed
manual
```

Status:

```text
pending
posted
voided
```

Important billing rule:

```text
ORDERED != PERFORMED != CHARGED
```

Do not automatically charge a patient merely because something was ordered.

Normally:

```text
Service ordered
    ↓
Service actually performed / medicine dispensed
    ↓
Charge posted
```

Use idempotency or a suitable unique constraint so the same performed service cannot accidentally generate the same charge twice.

---

# 16. INVOICING

Create:

```text
invoices
invoice_items
```

---

## 16.1 `invoices`

Fields:

```text
id
facility_id
patient_id
encounter_id NULL

invoice_number

status

subtotal
discount_amount
tax_amount
total_amount
paid_amount
balance_amount

issued_at
due_at NULL

created_by_id
created_at
updated_at
```

Status:

```text
draft
issued
partially_paid
paid
cancelled
```

Rules:

- invoice number unique within facility.
- monetary values non-negative.
- total/balance consistency.
- issued financial records must preserve their historical monetary snapshot.
- do not silently delete issued invoices.

---

## 16.2 `invoice_items`

Fields:

```text
id
invoice_id
encounter_charge_id NULL
service_id NULL
description
quantity
unit_price
discount_amount
tax_amount
line_total
created_at
```

Once issued, invoice item description and price are snapshots and must not change because the service catalogue price changes.

---

# 17. PAYMENTS

Create:

```text
payments
payment_allocations
payment_refunds
```

---

## 17.1 `payments`

Fields:

```text
id
facility_id
patient_id
payment_number
amount
currency
payment_method
transaction_reference NULL
status
received_by_id
received_at
created_at
updated_at
```

Methods:

```text
cash
mobile_money
card
bank
insurance
other
```

Status:

```text
pending
completed
failed
reversed
```

Payment number unique within facility.

---

## 17.2 `payment_allocations`

Fields:

```text
id
payment_id
invoice_id
amount
allocated_at
created_at
```

Must support:

- several payments against one invoice
- one payment allocated across several invoices

Rules:

- allocation amount > 0.
- total allocations cannot exceed completed payment amount.
- invoice allocations cannot exceed amount still payable unless explicit overpayment support is implemented.
- payment/invoice facility and patient context must be compatible.

---

## 17.3 `payment_refunds`

Fields:

```text
id
payment_id
amount
reason
status
requested_by_id
approved_by_id
refunded_at
transaction_reference
created_at
updated_at
```

Never delete original payment history.

---

# 18. INSURANCE MODULE

Create:

```text
insurance_providers
insurance_plans
patient_insurance_policies
insurance_claims
insurance_claim_items
```

---

## 18.1 `insurance_providers`

Fields:

```text
id
organization_id
code
name
email
phone_number
is_active
created_at
updated_at
```

---

## 18.2 `insurance_plans`

Fields:

```text
id
insurance_provider_id
plan_code
name
description
is_active
created_at
updated_at
```

---

## 18.3 `patient_insurance_policies`

Fields:

```text
id
patient_id
insurance_plan_id
membership_number_encrypted
membership_number_hash
valid_from
valid_until
is_primary
status
created_at
updated_at
```

Sensitive membership values must follow the existing encryption/HMAC conventions.

---

## 18.4 `insurance_claims`

Fields:

```text
id
patient_insurance_policy_id
invoice_id
claim_number
claimed_amount
approved_amount
rejected_amount
status
submitted_at
resolved_at
created_at
updated_at
```

Status:

```text
draft
submitted
processing
approved
partially_approved
rejected
paid
cancelled
```

---

## 18.5 `insurance_claim_items`

Fields:

```text
id
insurance_claim_id
invoice_item_id
claimed_amount
approved_amount
rejected_amount
rejection_reason
created_at
updated_at
```

---

# 19. INPATIENT / ADMISSION MODULE

Create:

```text
wards
inpatient_rooms
beds
admissions
bed_assignments
nursing_notes
medication_administrations
discharge_summaries
```

Do NOT reuse `consultation_rooms` as inpatient rooms.

---

## 19.1 `wards`

```text
id
facility_id
department_id
code
name
ward_type
is_active
created_at
updated_at
```

---

## 19.2 `inpatient_rooms`

```text
id
ward_id
room_number
room_type
is_active
created_at
updated_at
```

---

## 19.3 `beds`

```text
id
inpatient_room_id
bed_number
status
is_active
created_at
updated_at
```

Status:

```text
available
occupied
reserved
cleaning
maintenance
```

---

## 19.4 `admissions`

```text
id
encounter_id
admission_number
admitted_by_practitioner_facility_assignment_id
admitted_at
reason_encrypted
status
discharged_at NULL
created_at
updated_at
```

Status:

```text
admitted
transferred
discharged
deceased
cancelled
```

---

## 19.5 `bed_assignments`

```text
id
admission_id
bed_id
assigned_at
released_at
assigned_by_id
created_at
```

Critical:

- one bed cannot have overlapping active assignments.
- one admission cannot simultaneously occupy multiple normal beds unless explicitly designed.
- facility/ward/admission scope must match.

Use PostgreSQL exclusion constraints if appropriate.

---

## 19.6 `nursing_notes`

```text
id
encounter_id
admission_id NULL
recorded_by_practitioner_facility_assignment_id
note_type
note_encrypted
recorded_at
created_at
```

---

## 19.7 `medication_administrations`

This is separate from pharmacy dispensing.

Fields:

```text
id
admission_id
prescription_item_id
scheduled_at
administered_at NULL
status
dose_given
administered_by_practitioner_facility_assignment_id NULL
reason NULL
created_at
updated_at
```

Status:

```text
scheduled
given
refused
missed
held
cancelled
```

Remember:

```text
Doctor prescribes
    ↓
Pharmacy dispenses
    ↓
Nurse administers
```

These are three different business events.

---

## 19.8 `discharge_summaries`

Fields:

```text
id
admission_id
encounter_id
prepared_by_practitioner_facility_assignment_id
admission_reason_encrypted
final_diagnosis_encrypted
treatment_summary_encrypted
discharge_medications_encrypted
follow_up_instructions_encrypted
condition_at_discharge
discharged_at
signed_at
created_at
updated_at
```

Signed discharge summaries should preserve history.

---

# 20. FOLLOW-UP MODULE

Create:

```text
follow_up_plans
```

Fields:

```text
id
encounter_id
practitioner_facility_assignment_id
follow_up_date
reason_encrypted
specialty_id NULL
appointment_id NULL
status
created_at
updated_at
```

Status:

```text
planned
booked
completed
cancelled
```

This should integrate with the existing appointment system rather than duplicate it.

---

# 21. REFERRALS

Create:

```text
patient_referrals
```

Fields:

```text
id
encounter_id
referred_by_practitioner_facility_assignment_id
referral_type
destination_facility_id NULL
destination_department_id NULL
destination_specialty_id NULL
external_facility_name NULL
reason_encrypted
clinical_summary_encrypted
status
created_at
updated_at
```

Referral type:

```text
internal
external
```

Do **not** use current `queue_transfers` for external referrals.

Queue transfers remain operational movement within the current facility/check-in.

---

# 22. HR MODULE

Do not convert `practitioners` into employees.

A practitioner represents a healthcare professional.

An employee represents an employment relationship.

Create:

```text
employees
employment_contracts
employee_facility_assignments
employee_department_assignments
employee_attendance
employee_leave_requests
employee_shifts
```

A doctor may be:

```text
users
  ↕
employees
  ↕
practitioners
```

A receptionist may be:

```text
users
  ↕
employees
```

with no practitioner row.

---

## 22.1 `employees`

Suggested fields:

```text
id
organization_id
user_id NULL
practitioner_id NULL
employee_number
first_name
middle_name
last_name
phone_number
email
employment_status
hire_date
termination_date NULL
created_at
updated_at
```

Status:

```text
active
suspended
terminated
retired
```

Unique employee number within organization.

---

## 22.2 `employment_contracts`

```text
id
employee_id
contract_type
starts_on
ends_on NULL
basic_salary
currency
status
created_at
updated_at
```

Contract types:

```text
permanent
temporary
part_time
consultant
intern
```

Protect salary information through RBAC at the application layer.

---

## 22.3 `employee_facility_assignments`

```text
id
employee_id
facility_id
starts_on
ends_on NULL
is_primary
is_active
created_at
updated_at
```

---

## 22.4 `employee_department_assignments`

```text
id
employee_facility_assignment_id
department_id
job_title
starts_on
ends_on NULL
is_primary
is_active
created_at
updated_at
```

---

## 22.5 `employee_attendance`

```text
id
employee_id
facility_id
clock_in
clock_out NULL
attendance_source
recorded_by_id NULL
created_at
updated_at
```

Sources:

```text
manual
biometric
mobile
system
```

---

## 22.6 `employee_leave_requests`

```text
id
employee_id
leave_type
starts_on
ends_on
reason
status
approved_by_id
approved_at
created_at
updated_at
```

Leave types:

```text
annual
sick
maternity
paternity
study
unpaid
other
```

Status:

```text
pending
approved
rejected
cancelled
```

For employees linked to practitioners, application services may synchronize approved HR leave with practitioner scheduling, but do not destroy the current practitioner leave model.

---

## 22.7 `employee_shifts`

Keep this separate from practitioner clinical shifts.

Fields:

```text
id
employee_id
facility_id
department_id NULL
starts_at
ends_at
status
created_by_id
created_at
updated_at
```

Use this for general employee rosters.

Clinical practitioner scheduling remains in existing `practitioner_shifts`.

---

# 23. PAYROLL MODULE

Create:

```text
payroll_periods
payroll_entries
payroll_entry_components
```

---

## 23.1 `payroll_periods`

```text
id
organization_id
period_name
starts_on
ends_on
status
created_at
updated_at
```

Status:

```text
open
processing
approved
paid
closed
```

Prevent overlapping payroll periods if appropriate for the organization.

---

## 23.2 `payroll_entries`

```text
id
payroll_period_id
employee_id
basic_salary
gross_pay
total_deductions
net_pay
status
created_at
updated_at
```

---

## 23.3 `payroll_entry_components`

```text
id
payroll_entry_id
component_type
description
amount
created_at
```

Types:

```text
allowance
overtime
bonus
tax
pension
loan
deduction
other
```

---

# 24. PROCUREMENT MODULE

Create:

```text
suppliers
purchase_orders
purchase_order_items
goods_receipts
goods_receipt_items
```

---

## 24.1 `suppliers`

```text
id
organization_id
supplier_code
name
email
phone_number
address_encrypted NULL
tax_number_encrypted NULL
tax_number_hash NULL
is_active
created_at
updated_at
```

---

## 24.2 `purchase_orders`

```text
id
organization_id
facility_id
supplier_id
purchase_order_number
status
ordered_at
expected_at NULL
approved_by_id NULL
approved_at NULL
created_by_id
created_at
updated_at
```

Status:

```text
draft
pending_approval
approved
sent
partially_received
received
cancelled
```

---

## 24.3 `purchase_order_items`

```text
id
purchase_order_id
inventory_item_id
quantity_ordered
unit_cost
quantity_received
created_at
updated_at
```

---

## 24.4 `goods_receipts`

```text
id
purchase_order_id
receipt_number
received_by_id
received_at
status
notes
created_at
updated_at
```

---

## 24.5 `goods_receipt_items`

```text
id
goods_receipt_id
purchase_order_item_id
quantity_received
batch_number NULL
expiry_date NULL
unit_cost
stock_batch_id NULL
created_at
```

Receiving stock must atomically:

```text
create/update stock batch
+
create stock movement
+
update received quantity
```

---

# 25. ACCOUNTING / FINANCE MODULE

Create:

```text
chart_of_accounts
fiscal_periods
cost_centers
journal_entries
journal_lines
expenses
supplier_invoices
```

---

## 25.1 `chart_of_accounts`

```text
id
organization_id
account_code
account_name
account_type
parent_account_id NULL
is_active
created_at
updated_at
```

Types:

```text
asset
liability
equity
revenue
expense
```

---

## 25.2 `fiscal_periods`

```text
id
organization_id
name
starts_on
ends_on
status
created_at
updated_at
```

Status:

```text
open
closed
locked
```

---

## 25.3 `cost_centers`

```text
id
organization_id
facility_id NULL
department_id NULL
code
name
is_active
created_at
updated_at
```

---

## 25.4 `journal_entries`

```text
id
organization_id
facility_id NULL
journal_number
entry_date
description
source_type
source_id NULL
status
posted_by_id NULL
posted_at NULL
created_at
updated_at
```

Status:

```text
draft
posted
reversed
```

---

## 25.5 `journal_lines`

```text
id
journal_entry_id
account_id
cost_center_id NULL
debit
credit
description
created_at
```

Critical constraint:

```text
for every posted journal entry:
SUM(debit) = SUM(credit)
```

Each line should normally have either debit or credit, not both.

---

## 25.6 `expenses`

```text
id
organization_id
facility_id NULL
expense_number
expense_date
description
amount
currency
account_id
supplier_id NULL
status
created_by_id
approved_by_id NULL
created_at
updated_at
```

---

## 25.7 `supplier_invoices`

```text
id
supplier_id
purchase_order_id NULL
invoice_number
invoice_date
due_date NULL
subtotal
tax_amount
total_amount
paid_amount
status
created_at
updated_at
```

---

# 26. BILLING → ACCOUNTING INTEGRATION

Do not place accounting logic directly into clinical rows.

Use application/service-layer transactions.

Examples:

### Patient payment

```text
Payment completed
   ↓
Journal Entry
   ↓
Debit: Cash / Bank
Credit: Patient Service Revenue / Accounts Receivable
```

### Supplier invoice

```text
Supplier invoice
   ↓
Debit: Inventory / Expense
Credit: Accounts Payable
```

### Payroll

```text
Approved payroll
   ↓
Debit: Salary Expense
Credit: Payroll Payable / Bank
```

Database must provide strong integrity structures, but accounting orchestration may remain in the Django service layer.

---

# 27. ROLE-BASED ACCESS

Do not create a new permissions system.

Use the current:

```text
users
roles
permissions
role_permissions
user_memberships
user_role_assignments
```

The application should create default roles such as:

```text
Receptionist
Nurse
Doctor
Clinical Officer
Lab Technician
Pharmacist
Radiologist
Cashier
Storekeeper
Procurement Officer
HR Officer
Payroll Officer
Accountant
Hospital Manager
System Administrator
```

The SQL schema should remain role-configurable instead of hardcoding business permissions into tables.

---

# 28. AUDIT REQUIREMENTS

The current `audit_logs` table remains the platform-wide audit trail.

New clinical/financial modules must additionally preserve their own domain history when current state alone is insufficient.

Examples of records that should not be silently deleted:

```text
signed clinical notes
verified lab results
verified imaging reports
diagnoses
dispensing records
stock movements
issued invoices
completed payments
refunds
posted journal entries
payroll history
bed assignment history
encounter status history
```

Use void/reversal/superseding semantics instead of destructive deletion.

---

# 29. SECURITY REQUIREMENTS

Follow all existing security assumptions.

Sensitive data should use application encryption, for example:

```text
chief_complaint_encrypted
clinical_notes_encrypted
subjective_encrypted
objective_encrypted
assessment_encrypted
plan_encrypted
lab_notes_encrypted
imaging_findings_encrypted
insurance_membership_number_encrypted
```

Where exact lookup of encrypted values is required, use a paired HMAC hash such as:

```text
membership_number_encrypted
membership_number_hash
```

Never store raw:

- authentication secrets
- QR tokens
- payment credentials
- mobile-money PINs
- card numbers/CVV
- encryption keys
- raw sensitive national identifiers where encryption is required

Do not log sensitive clinical payloads into `audit_logs.metadata` or `audit_logs.changes`.

---

# 30. TENANT / FACILITY INTEGRITY

This database is multi-organization and multi-facility.

Every new cross-table relationship must be checked for scope consistency.

Examples:

- encounter patient organization must match facility organization.
- practitioner assignment must match encounter facility.
- department must belong to encounter facility.
- lab order's encounter and lab test organization must be compatible.
- pharmacy inventory location must belong to the same facility where dispensing occurs.
- invoice patient/encounter/facility must match.
- payment and invoice allocations must be organization/facility compatible.
- employee facility assignment must belong to employee organization.
- purchase orders must use suppliers belonging to the same organization.
- accounting entries must never mix organizations.

Where a normal FK is insufficient, create validation trigger functions consistent with the style already used in the SQL file.

---

# 31. INDEXING REQUIREMENTS

Add indexes intentionally for real access paths.

At minimum consider indexes for:

```text
encounters(patient_id, opened_at DESC)
encounters(facility_id, status, opened_at)
encounters(patient_checkin_id)

vital_signs(encounter_id, recorded_at DESC)

clinical_notes(encounter_id, created_at DESC)

encounter_diagnoses(encounter_id, diagnosed_at DESC)

lab_orders(encounter_id, ordered_at DESC)
lab_orders(status, ordered_at)
lab_order_items(lab_order_id)
lab_specimens(specimen_number)
lab_result_values(lab_order_item_id)

prescriptions(encounter_id, prescribed_at DESC)
prescription_items(prescription_id)
medication_dispenses(prescription_item_id)

stock_batches(inventory_item_id, inventory_location_id)
stock_batches(expiry_date)
stock_movements(stock_batch_id, occurred_at DESC)

encounter_charges(encounter_id, status)
invoices(patient_id, issued_at DESC)
invoices(facility_id, status, issued_at)
payments(patient_id, received_at DESC)
payment_allocations(invoice_id)

admissions(encounter_id)
admissions(status, admitted_at)
bed_assignments(bed_id, assigned_at)

employees(organization_id, employee_number)
employee_attendance(employee_id, clock_in DESC)

purchase_orders(facility_id, status, ordered_at)
journal_entries(organization_id, entry_date, status)
```

Do not create indexes blindly. Avoid redundant indexes already implied by unique constraints.

---

# 32. UPDATED_AT TRIGGERS

Every mutable table containing `updated_at` must use the current `set_updated_at()` trigger.

Do not create duplicate timestamp functions.

Reuse the existing function.

---

# 33. APPEND-ONLY PROTECTION

Use trigger protection where appropriate to prevent UPDATE/DELETE after finalization for history/ledger records.

Candidates include:

```text
encounter_status_history
stock_movements
verified lab result history where applicable
payment/refund history after completion
posted journal entries / lines
```

If strict append-only behavior would make legitimate correction impossible, implement:

```text
void
reverse
supersede
addendum
```

instead of destructive modification.

---

# 34. MONEY DATA TYPES

Use a consistent exact numeric type for money.

Recommended:

```sql
NUMERIC(18,2)
```

unless the existing schema establishes another monetary convention.

Do not use floating point for money.

Currency:

```text
CHAR(3)
```

using ISO-style currency codes such as:

```text
TZS
USD
```

Default may be `TZS` only where appropriate, but do not hardcode Tanzania-specific assumptions into reusable global catalogue tables unless the existing product requires it.

---

# 35. STATUS CHECK CONSTRAINTS

Where practical, add CHECK constraints for controlled statuses.

Do not leave important workflow statuses completely unrestricted.

Examples:

```sql
CHECK (status IN (...))
```

Use this for:

- encounter status/type
- lab order statuses
- specimen statuses
- prescription statuses
- payment statuses
- invoice statuses
- admission statuses
- bed statuses
- employment statuses
- purchase-order statuses
- accounting statuses

Keep values consistent and lowercase in SQL.

---

# 36. DO NOT STORE DERIVED DATA UNLESS IT IS A TRANSACTIONAL SNAPSHOT

Continue the current design principle.

Do not store:

```text
queue position
actual waiting time
BMI
dashboard totals
doctor workload totals
available bed count
daily patient totals
stock dashboard totals
```

These are derived.

However, storing historical transaction snapshots is valid where necessary, for example:

```text
invoice unit price
invoice line total
payment amount
payroll amounts
purchase-order unit cost
stock batch purchase cost
journal debit/credit
```

---

# 37. IMPLEMENTATION ORDER

Modify the SQL file in this order so FK dependencies remain clean.

Recommended section ordering after the existing queue/reporting sections, or inserted in logically appropriate positions:

```text
1. Clinical Encounters
2. Triage and Vitals
3. Patient Clinical History
4. Clinical Notes and Diagnoses
5. Billing Service Catalogue
6. Laboratory
7. Imaging
8. Procedures
9. Pharmacy
10. Inventory
11. Billing / Invoices / Payments
12. Insurance
13. Inpatient / Nursing
14. Follow-up / Referrals
15. HR
16. Payroll
17. Procurement
18. Accounting / Finance
19. New indexes
20. New validation functions
21. New triggers
22. updated_at triggers
23. append-only protections
```

If a table dependency requires a different exact SQL ordering, change the physical order while preserving this conceptual grouping.

---

# 38. IMPORTANT DEPENDENCY NOTE

Several catalogue tables may reference `services.billing_service_id`.

Therefore create the billing service catalogue before tables that reference it, or:

- create catalogues first without the FK and add FK constraints afterward, OR
- order the CREATE TABLE statements so dependencies resolve cleanly.

Prefer clean CREATE order rather than deferred ad-hoc fixes.

---

# 39. TRANSACTIONAL WORKFLOWS TO SUPPORT

The schema must support these service-layer transactions safely.

### 39.1 Open encounter

```text
Check-in exists
    ↓
Validate patient/facility
    ↓
Create encounter
    ↓
Create initial encounter status history
```

---

### 39.2 Triage to doctor

```text
Record triage
+
Record vitals
+
Update encounter status
+
Transfer/create existing queue entry as required
```

---

### 39.3 Doctor orders laboratory test

```text
Create lab order
+
Create lab order items
+
Update encounter status
+
Transfer patient through existing queue engine
```

---

### 39.4 Lab result completed

```text
Enter result
+
Verify result
+
Update lab status
+
Notify doctor/patient where appropriate
+
Transfer patient to doctor-review queue if workflow requires
```

---

### 39.5 Prescription dispensing

```text
Lock stock batch
+
Validate available quantity
+
Create medication dispense
+
Create stock movement
+
Decrease batch quantity
+
Create encounter charge if billable
```

All inside a transaction.

---

### 39.6 Service charge

```text
Service actually performed
+
Resolve effective service price
+
Create one idempotent encounter charge
```

---

### 39.7 Invoice generation

```text
Select posted unbilled charges
+
Create invoice
+
Create invoice item snapshots
+
Mark/link charges appropriately
```

Prevent double invoicing.

---

### 39.8 Payment

```text
Create payment
+
Allocate payment
+
Update invoice paid/balance/status transactionally
```

Use row locking where concurrency can over-allocate.

---

### 39.9 Goods receipt

```text
Lock purchase order
+
Create goods receipt
+
Create/update stock batch
+
Create stock movement
+
Update PO quantities
```

---

### 39.10 Admission / bed assignment

```text
Create admission
+
Lock selected bed
+
Ensure bed available
+
Create bed assignment
+
Set bed occupied
+
Update encounter status
```

---

# 40. DJANGO COMPATIBILITY

The current SQL file is designed as a Django modular-monolith baseline.

Keep compatibility.

Do not use database designs that are unnecessarily hostile to Django ORM.

Continue to use:

```text
UUID PKs
explicit FK relationships
explicit db table names
clean junction tables
database constraints for final integrity
service-layer transactions for multi-step workflows
```

Complex PostgreSQL constraints/triggers are acceptable and expected when required.

---

# 41. COMMENTS AND DOCUMENTATION INSIDE SQL

Maintain clear SQL section comments matching the current style, for example:

```sql
-- ================================================================
-- CLINICAL ENCOUNTERS
-- ================================================================
```

Every module should have a clearly labeled section.

For complex functions/triggers add concise comments explaining:

- what it validates
- why normal FK constraints are insufficient

Do not flood the SQL with unnecessary prose.

---

# 42. FINAL VALIDATION — CODEX MUST DO THIS

After editing the SQL file:

## 42.1 Syntax validation

Run the SQL against PostgreSQL 15+ if a PostgreSQL environment is available.

The entire script must complete successfully from an empty database.

Because the file uses:

```sql
BEGIN;
...
COMMIT;
```

one failure must not leave a half-created schema.

---

## 42.2 Table count

Report:

```text
existing tables preserved: 50
new tables added: N
total tables: 50 + N
```

Do not claim 50 tables remain if new tables were added.

---

## 42.3 Existing schema regression

Confirm all original 50 tables still exist.

Confirm important current capabilities still work structurally:

```text
appointment booking
appointment rescheduling
secure QR check-in
walk-in check-in
practitioner shifts
appointment slots
queue creation
queue entry
queue transfer
queue history
waiting-time prediction
notifications
RBAC
audit
report exports
```

---

## 42.4 Foreign-key validation

Check for:

- missing referenced tables
- circular create-order failures
- cross-organization relationships
- cross-facility relationships
- nullable relationships accidentally made mandatory
- accidental cascades on historical records

---

## 42.5 Constraint validation

Test examples that MUST fail:

```text
encounter patient belongs to another organization
encounter check-in belongs to another patient
lab practitioner belongs to another facility
negative payment
negative invoice amount
negative stock after dispensing
duplicate active encounter for one check-in
two patients occupying the same bed at the same time
overlapping service price periods
duplicate billing charge for the same performed source
payment allocations larger than payment amount
cross-organization accounting journal
```

---

## 42.6 Valid workflow seed/test

Create a minimal test scenario:

```text
Organization
Facility
Department
Specialty
Doctor
Nurse
Lab Technician
Pharmacist
Patient

Appointment
Check-in
Encounter
Triage
Vitals
Doctor consultation
Provisional diagnosis
Lab order
Lab result
Confirmed diagnosis
Prescription
Dispensing
Charge
Invoice
Payment
Encounter completion
```

The complete scenario must succeed without violating constraints.

---

# 43. OUTPUT REQUIRED FROM CODEX

Codex must provide:

### A. Updated SQL file

Modify:

```text
intelligent_patient_flow_database.sql
```

Do not create a completely separate unrelated schema.

---

### B. Change summary

Create:

```text
HMS_DATABASE_V2_CHANGELOG.md
```

Include:

```text
original table count
new table count
new tables by module
new functions
new triggers
new indexes
important decisions
backward-compatibility notes
known application-layer responsibilities
```

---

### C. Validation report

Create:

```text
HMS_DATABASE_V2_VALIDATION.md
```

Include:

```text
SQL parse/execution result
PostgreSQL version used
table count
constraint tests
workflow test
any unresolved issues
```

Do not say validation passed unless it was actually executed.

If PostgreSQL is unavailable, explicitly state:

```text
Not executed against PostgreSQL.
Static validation only.
```

---

# 44. DO NOT IMPLEMENT THESE AS SHORTCUTS

Do not:

- put all clinical data in a JSONB `encounter_data` column
- put lab results directly on `lab_orders`
- put multiple medications into one prescription text field
- put multiple invoice items into JSON
- use free-text employee role instead of existing RBAC
- make nurses a separate identity table
- replace practitioners with employees
- store all inventory only in `medications`
- use consultation rooms as hospital beds
- use appointments as encounters
- use queue transfers as external referrals
- use payment rows as accounting journal entries
- delete financial or clinical history to “correct” records
- use FLOAT/REAL for money
- duplicate the existing queue system
- duplicate the existing authentication/permissions system

---

# 45. CORE RELATIONSHIP MAP

Use this as the final conceptual relationship.

```text
organizations
   │
facilities
   │
   ├── departments
   ├── service_points
   ├── consultation_rooms
   ├── wards
   ├── inventory_locations
   └── cost_centers
         │
patients ───────── appointments
   │                  │
   └──── patient_checkins
             │
          encounters
             │
     ┌───────┼─────────────────────────────┐
     │       │        │        │           │
   triage  notes   diagnoses   lab      imaging
     │                          │           │
   vitals                     results     reports

encounters
   │
   ├── procedures
   ├── prescriptions
   │      └── prescription_items
   │             └── medication_dispenses
   │                        │
   │                    stock_batches
   │                        │
   │                    stock_movements
   │
   ├── encounter_charges
   │          │
   │       invoice_items
   │          │
   └────── invoices
               │
       payment_allocations
               │
            payments
               │
            refunds

encounters
   │
 admissions
   │
 bed_assignments
   │
 beds
   │
 inpatient_rooms
   │
 wards

users
 │
 ├── practitioners
 │       └── professional assignments
 │
 └── employees
         ├── contracts
         ├── attendance
         ├── HR leave
         ├── shifts
         └── payroll

suppliers
   │
purchase_orders
   │
goods_receipts
   │
stock_batches / stock_movements

billing / payroll / procurement
             │
       journal_entries
             │
         journal_lines
             │
      chart_of_accounts
```

---

# 46. FINAL DESIGN PRINCIPLE

The existing system remains the **patient-flow engine**.

The new system adds the **clinical and hospital business layers** around it.

The final architecture should be understood as:

```text
CURRENT SYSTEM
────────────────────────────────────
Facilities
Patients
Practitioners
Scheduling
Appointments
Check-in
Queues
Prediction
Notifications
RBAC
Audit
Reporting

                +

NEW HMS V2
────────────────────────────────────
Encounters
Triage
Vitals
Clinical Notes
Diagnoses
Laboratory
Imaging
Procedures
Pharmacy
Inventory
Billing
Payments
Insurance
Admissions
Wards
Beds
Nursing
Discharge
Referrals
HR
Payroll
Procurement
Accounting
```

Do not rewrite a good existing subsystem merely because the project scope has expanded.

Extend it cleanly, enforce tenant/facility integrity, preserve history, and keep clinical, operational, HR and financial lifecycles separated.
