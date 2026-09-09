# HMS Database V2 Changelog

## Scope

`intelligent_patient_flow_database.sql` has been expanded from the Intelligent Patient Flow and Appointment Scheduling baseline into a broader Hospital Management System schema while preserving the existing business tables and table semantics.

## Table Count

- Existing baseline tables preserved: 50
- New HMS tables added: 75
- Total business tables after update: 125

## New Modules Added

- Clinical encounters: encounter headers and append-only status history.
- Triage and vitals: triage assessments and point-in-time vital signs.
- Patient clinical history: allergies and conditions.
- Clinical documentation: notes, diagnosis codes, and encounter diagnoses.
- Billing service catalogue: services, prices, and encounter charges.
- Laboratory: tests, test components, orders, order items, specimens, and result values.
- Imaging: imaging services, orders, order items, and reports.
- Procedures: procedure catalogue and encounter procedures.
- Pharmacy: medications, prescriptions, prescription items, and dispenses.
- Inventory: categories, items, locations, batches, and append-only stock movements.
- Billing and payments: invoices, invoice items, payments, allocations, refunds.
- Insurance: providers, plans, patient policies, claims, and claim items.
- Inpatient and nursing: wards, rooms, beds, admissions, bed assignments, nursing notes, medication administrations, and discharge summaries.
- Follow-up and referrals: follow-up plans and patient referrals.
- HR: employees, contracts, facility assignments, department assignments, attendance, leave, and shifts.
- Payroll: payroll periods, payroll entries, and payroll components.
- Procurement: suppliers, purchase orders, purchase order items, goods receipts, and receipt items.
- Accounting and finance: chart of accounts, fiscal periods, cost centers, journal entries, journal lines, expenses, and supplier invoices.

## Integrity Additions

- UUID primary keys and PostgreSQL defaults are used consistently.
- `created_at` and `updated_at` timestamps are used on mutable tables.
- New mutable tables are registered with the existing `set_updated_at()` trigger.
- Domain status values are constrained with `CHECK` constraints.
- Money, quantity, date, time, and status transition rules are constrained where practical.
- Cross-table scope validation was added for encounters, practitioners, service catalogue links, inventory, billing, beds, and accounting.
- Append-only protection was extended to encounter status history and stock movements.
- Posted journal entries must balance debit and credit lines.
- Posted journal lines cannot be updated or deleted.

## Security And Privacy Notes

- Sensitive clinical, address, tax, and note fields use `*_encrypted` columns.
- Lookup-only sensitive identifiers use `*_hash` columns.
- Raw tokens, passwords, QR tokens, push tokens, and plaintext sensitive values are still expected to be handled by the application layer and never logged.
- The SQL schema stores structural support only; encryption and HMAC generation remain application responsibilities.

## Backward Compatibility

- Existing table names were not renamed.
- Existing table semantics were not intentionally changed.
- Existing report export tables and export-related fields were preserved.
- New tables reference existing organizations, facilities, patients, users, practitioners, appointments, check-ins, and queue entities instead of replacing them.

