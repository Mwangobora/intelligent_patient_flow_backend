from __future__ import annotations

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

from apps.facilities.models import Department, Facility, FacilitySpecialty, Organization
from common.db import ActiveModel, TimeStampedModel

phone_validator = RegexValidator(regex=r"^\+[1-9][0-9]{7,14}$", message="Phone number must be in E.164 format.")
hash_validator = RegexValidator(regex=r"^[0-9A-Fa-f]{64}$", message="Hash values must be 64 hexadecimal characters.")


class PractitionerType(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=40)
    description = models.TextField(blank=True, null=True)
    requires_license = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_practitioner_types", blank=True, null=True)

    class Meta:
        db_table = "practitioner_types"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="uq_practitioner_types_name"),
            models.UniqueConstraint(fields=["code"], name="uq_practitioner_types_code"),
            models.CheckConstraint(condition=Q(code=models.functions.Upper("code")), name="ck_practitioner_types_code_upper"),
        ]


class Practitioner(TimeStampedModel, ActiveModel):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="practitioners")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="practitioner_profiles", blank=True, null=True)
    practitioner_type = models.ForeignKey(PractitionerType, on_delete=models.PROTECT, related_name="practitioners")
    practitioner_number = models.CharField(max_length=50)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    preferred_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=30, blank=True, null=True, validators=[phone_validator])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_practitioners", blank=True, null=True)

    class Meta:
        db_table = "practitioners"
        constraints = [
            models.UniqueConstraint(fields=["organization", "practitioner_number"], name="uq_practitioners_org_number"),
            models.UniqueConstraint(fields=["organization", "user"], condition=Q(user__isnull=False), name="uq_practitioners_org_user"),
            models.CheckConstraint(condition=Q(practitioner_number__regex=r".*\S.*"), name="ck_practitioners_number_not_blank"),
            models.CheckConstraint(condition=Q(phone_number__isnull=True) | Q(phone_number__regex=r"^\+[1-9][0-9]{7,14}$"), name="ck_practitioners_phone_e164"),
        ]
        indexes = [
            models.Index(fields=["organization"], name="idx_practitioners_organization"),
            models.Index(fields=["practitioner_type"], name="idx_practitioners_type"),
            models.Index(fields=["organization", "last_name", "first_name"], name="idx_practitioners_name"),
        ]


class PractitionerFacilityAssignment(TimeStampedModel, ActiveModel):
    practitioner = models.ForeignKey(Practitioner, on_delete=models.PROTECT, related_name="facility_assignments")
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="practitioner_assignments")
    starts_on = models.DateField()
    ends_on = models.DateField(blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="assigned_practitioner_facilities", blank=True, null=True)

    class Meta:
        db_table = "practitioner_facility_assignments"
        constraints = [
            models.UniqueConstraint(fields=["practitioner", "facility"], name="uq_practitioner_facility_assignments_pair"),
            models.UniqueConstraint(fields=["practitioner"], condition=Q(is_primary=True, is_active=True), name="uq_practitioner_primary_facility"),
            models.CheckConstraint(condition=Q(ends_on__isnull=True) | Q(ends_on__gte=F("starts_on")), name="ck_practitioner_facility_assignments_dates"),
            models.CheckConstraint(condition=Q(is_primary=False) | Q(is_active=True), name="ck_practitioner_facility_primary_active"),
        ]
        indexes = [
            models.Index(fields=["practitioner", "is_active"], name="idx_prac_fac_asn_prac"),
            models.Index(fields=["facility", "is_active"], name="idx_prac_fac_asn_fac"),
        ]

    # TODO: enforce practitioner facility assignment validation trigger from the SQL file in a custom migration.


class PractitionerDepartmentAssignment(TimeStampedModel, ActiveModel):
    practitioner_facility_assignment = models.ForeignKey(PractitionerFacilityAssignment, on_delete=models.PROTECT, related_name="department_assignments")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="practitioner_assignments")
    starts_on = models.DateField()
    ends_on = models.DateField(blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="assigned_practitioner_departments", blank=True, null=True)

    class Meta:
        db_table = "practitioner_department_assignments"
        constraints = [
            models.UniqueConstraint(fields=["practitioner_facility_assignment", "department"], name="uq_practitioner_department_assignments_pair"),
            models.UniqueConstraint(fields=["practitioner_facility_assignment"], condition=Q(is_primary=True, is_active=True), name="uq_practitioner_primary_department"),
            models.CheckConstraint(condition=Q(ends_on__isnull=True) | Q(ends_on__gte=F("starts_on")), name="ck_practitioner_department_assignments_dates"),
            models.CheckConstraint(condition=Q(is_primary=False) | Q(is_active=True), name="ck_practitioner_department_primary_active"),
        ]
        indexes = [
            models.Index(fields=["practitioner_facility_assignment", "is_active"], name="idx_prac_dept_asn_pfa"),
            models.Index(fields=["department"], name="idx_prac_dept_asn_dept"),
        ]

    # TODO: enforce practitioner department assignment validation trigger from the SQL file in a custom migration.


class PractitionerSpecialtyAssignment(TimeStampedModel, ActiveModel):
    practitioner_facility_assignment = models.ForeignKey(PractitionerFacilityAssignment, on_delete=models.PROTECT, related_name="specialty_assignments")
    facility_specialty = models.ForeignKey(FacilitySpecialty, on_delete=models.PROTECT, related_name="practitioner_assignments")
    starts_on = models.DateField()
    ends_on = models.DateField(blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="assigned_practitioner_specialties", blank=True, null=True)

    class Meta:
        db_table = "practitioner_specialty_assignments"
        constraints = [
            models.UniqueConstraint(fields=["practitioner_facility_assignment", "facility_specialty"], name="uq_practitioner_specialty_assignments_pair"),
            models.UniqueConstraint(fields=["practitioner_facility_assignment"], condition=Q(is_primary=True, is_active=True), name="uq_practitioner_primary_specialty"),
            models.CheckConstraint(condition=Q(ends_on__isnull=True) | Q(ends_on__gte=F("starts_on")), name="ck_practitioner_specialty_assignments_dates"),
            models.CheckConstraint(condition=Q(is_primary=False) | Q(is_active=True), name="ck_practitioner_specialty_primary_active"),
        ]
        indexes = [
            models.Index(fields=["practitioner_facility_assignment", "is_active"], name="idx_prac_spec_asn_pfa"),
            models.Index(fields=["facility_specialty"], name="idx_prac_spec_asn_spec"),
        ]

    # TODO: enforce practitioner specialty assignment triggers from the SQL file in a custom migration.


class PractitionerCredentialType(TimeStampedModel, ActiveModel):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="practitioner_credential_types", blank=True, null=True)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=40)
    description = models.TextField(blank=True, null=True)
    country_code = models.CharField(max_length=2, blank=True, null=True)
    requires_expiry_date = models.BooleanField(default=False)
    requires_verification = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_practitioner_credential_types", blank=True, null=True)

    class Meta:
        db_table = "practitioner_credential_types"
        constraints = [
            models.CheckConstraint(condition=Q(code=models.functions.Upper("code")), name="ck_practitioner_credential_types_code_upper"),
            models.CheckConstraint(condition=Q(country_code__isnull=True) | Q(country_code=models.functions.Upper("country_code")), name="ck_practitioner_credential_types_country_upper"),
            models.UniqueConstraint(Lower("name"), condition=Q(organization__isnull=True), name="uq_practitioner_credential_types_global_name"),
            models.UniqueConstraint(fields=["code"], condition=Q(organization__isnull=True), name="uq_practitioner_credential_types_global_code"),
            models.UniqueConstraint(Lower("name"), F("organization"), condition=Q(organization__isnull=False), name="uq_practitioner_credential_types_org_name"),
            models.UniqueConstraint(fields=["organization", "code"], condition=Q(organization__isnull=False), name="uq_practitioner_credential_types_org_code"),
        ]
        indexes = [models.Index(fields=["organization"], name="idx_prac_cred_type_org")]


class PractitionerCredential(TimeStampedModel, ActiveModel):
    class VerificationStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    practitioner = models.ForeignKey(Practitioner, on_delete=models.PROTECT, related_name="credentials")
    credential_type = models.ForeignKey(PractitionerCredentialType, on_delete=models.PROTECT, related_name="credentials")
    credential_number_encrypted = models.TextField()
    credential_number_hash = models.CharField(max_length=64, validators=[hash_validator])
    last_four = models.CharField(max_length=4, blank=True, null=True)
    issuing_authority = models.CharField(max_length=150, blank=True, null=True)
    issuing_country_code = models.CharField(max_length=2, blank=True, null=True)
    issued_on = models.DateField(blank=True, null=True)
    expires_on = models.DateField(blank=True, null=True)
    verification_status = models.CharField(max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.UNVERIFIED)
    verified_at = models.DateTimeField(blank=True, null=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="verified_practitioner_credentials", blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_practitioner_credentials", blank=True, null=True)

    class Meta:
        db_table = "practitioner_credentials"
        constraints = [
            models.UniqueConstraint(fields=["credential_type", "credential_number_hash"], name="uq_practitioner_credentials_type_hash"),
            models.CheckConstraint(condition=Q(credential_number_hash__regex=r"^[0-9A-Fa-f]{64}$"), name="ck_practitioner_credentials_hash"),
            models.CheckConstraint(condition=Q(verification_status__in=["unverified", "pending", "verified", "rejected"]), name="ck_practitioner_credentials_status"),
            models.CheckConstraint(condition=Q(expires_on__isnull=True) | Q(issued_on__isnull=True) | Q(expires_on__gte=F("issued_on")), name="ck_practitioner_credentials_dates"),
            models.CheckConstraint(condition=Q(issuing_country_code__isnull=True) | Q(issuing_country_code=models.functions.Upper("issuing_country_code")), name="ck_practitioner_credentials_country_upper"),
        ]
        indexes = [
            models.Index(fields=["practitioner", "is_active"], name="idx_prac_cred_prac"),
            models.Index(fields=["credential_type"], name="idx_prac_cred_type"),
        ]

    # TODO: enforce practitioner credential validation trigger and final verification-state semantics from the SQL file in a custom migration.
