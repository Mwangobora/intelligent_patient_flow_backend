from __future__ import annotations

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.accounts.models import Role
from apps.facilities.models import Facility, Organization
from common.db import ActiveModel, TimeStampedModel

phone_validator = RegexValidator(
    regex=r"^\+[1-9][0-9]{7,14}$",
    message="Phone number must be in E.164 format, for example +2557656765456.",
)
hash_validator = RegexValidator(
    regex=r"^[0-9A-Fa-f]{64}$",
    message="Hash values must be 64 hexadecimal characters.",
)


class Patient(TimeStampedModel, ActiveModel):
    class SexCode(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        INTERSEX = "intersex", "Intersex"
        UNKNOWN = "unknown", "Unknown"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="patients",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="patients",
        blank=True,
        null=True,
    )
    registered_facility = models.ForeignKey(
        Facility,
        on_delete=models.PROTECT,
        related_name="registered_patients",
        blank=True,
        null=True,
    )
    patient_number = models.CharField(max_length=50)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(blank=True, null=True)
    date_of_birth_is_estimated = models.BooleanField(default=False)
    sex_code = models.CharField(max_length=20, choices=SexCode.choices, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        validators=[phone_validator],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_patients",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "patients"
        ordering = ["organization", "last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "patient_number"],
                name="uq_patients_org_number",
            ),
            models.UniqueConstraint(
                fields=["organization", "user"],
                condition=Q(user__isnull=False),
                name="uq_patients_org_user",
            ),
            models.CheckConstraint(
                condition=Q(patient_number__regex=r".*\S.*"),
                name="ck_patients_number_not_blank",
            ),
            models.CheckConstraint(
                condition=Q(sex_code__isnull=True)
                | Q(sex_code__in=["male", "female", "intersex", "unknown"]),
                name="ck_patients_sex_code",
            ),
            models.CheckConstraint(
                condition=Q(phone_number__isnull=True) | Q(phone_number__regex=r"^\+[1-9][0-9]{7,14}$"),
                name="ck_patients_phone_e164",
            ),
        ]
        indexes = [
            models.Index(fields=["organization"], name="idx_patients_organization"),
            models.Index(fields=["registered_facility"], name="idx_patients_reg_fac"),
            models.Index(fields=["organization", "last_name", "first_name"], name="idx_patients_name"),
        ]

    def __str__(self) -> str:
        return f"{self.patient_number} - {self.last_name}, {self.first_name}"


class PatientIdentifierType(TimeStampedModel, ActiveModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="patient_identifier_types",
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=40)
    description = models.TextField(blank=True, null=True)
    is_sensitive = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_patient_identifier_types",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "patient_identifier_types"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(code=models.functions.Upper("code")),
                name="ck_patient_identifier_types_code_upper",
            ),
            models.UniqueConstraint(
                Lower("name"),
                condition=Q(organization__isnull=True),
                name="uq_patient_identifier_types_global_name",
            ),
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(organization__isnull=True),
                name="uq_patient_identifier_types_global_code",
            ),
            models.UniqueConstraint(
                Lower("name"),
                F("organization"),
                condition=Q(organization__isnull=False),
                name="uq_patient_identifier_types_org_name",
            ),
            models.UniqueConstraint(
                fields=["organization", "code"],
                condition=Q(organization__isnull=False),
                name="uq_patient_identifier_types_org_code",
            ),
        ]
        indexes = [
            models.Index(fields=["organization"], name="idx_pat_id_type_org"),
        ]

    def __str__(self) -> str:
        return self.name


class PatientIdentifier(TimeStampedModel, ActiveModel):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="identifiers",
    )
    identifier_type = models.ForeignKey(
        PatientIdentifierType,
        on_delete=models.PROTECT,
        related_name="patient_identifiers",
    )
    value_encrypted = models.TextField()
    value_hash = models.CharField(max_length=64, validators=[hash_validator])
    last_four = models.CharField(max_length=4, blank=True, null=True)
    issuing_country_code = models.CharField(max_length=2, blank=True, null=True)
    issuing_authority = models.CharField(max_length=150, blank=True, null=True)
    issued_on = models.DateField(blank=True, null=True)
    expires_on = models.DateField(blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="verified_patient_identifiers",
        blank=True,
        null=True,
    )
    is_primary = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_patient_identifiers",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "patient_identifiers"
        constraints = [
            models.UniqueConstraint(
                fields=["identifier_type", "value_hash"],
                name="uq_patient_identifiers_type_hash",
            ),
            models.UniqueConstraint(
                fields=["patient", "identifier_type"],
                condition=Q(is_primary=True, is_active=True),
                name="uq_patient_identifiers_primary",
            ),
            models.CheckConstraint(
                condition=Q(value_hash__regex=r"^[0-9A-Fa-f]{64}$"),
                name="ck_patient_identifiers_hash",
            ),
            models.CheckConstraint(
                condition=Q(expires_on__isnull=True)
                | Q(issued_on__isnull=True)
                | Q(expires_on__gte=F("issued_on")),
                name="ck_patient_identifiers_dates",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(verified_at__isnull=True) & Q(verified_by__isnull=True))
                    | (Q(verified_at__isnull=False) & Q(verified_by__isnull=False))
                ),
                name="ck_patient_identifiers_verification",
            ),
            models.CheckConstraint(
                condition=Q(issuing_country_code__isnull=True)
                | Q(issuing_country_code=models.functions.Upper("issuing_country_code")),
                name="ck_patient_identifiers_country_upper",
            ),
        ]
        indexes = [
            models.Index(fields=["patient"], name="idx_pat_ident_patient"),
            models.Index(fields=["identifier_type"], name="idx_patient_identifiers_type"),
        ]


class PatientAddress(TimeStampedModel, ActiveModel):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="addresses",
    )
    label = models.CharField(max_length=50, blank=True, null=True)
    address_line1_encrypted = models.TextField(blank=True, null=True)
    address_line2_encrypted = models.TextField(blank=True, null=True)
    country_code = models.CharField(max_length=2, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    ward = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_patient_addresses",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "patient_addresses"
        constraints = [
            models.UniqueConstraint(
                fields=["patient"],
                condition=Q(is_primary=True, is_active=True),
                name="uq_patient_addresses_primary",
            ),
            models.CheckConstraint(
                condition=Q(address_line1_encrypted__isnull=False)
                | Q(address_line2_encrypted__isnull=False)
                | Q(region__isnull=False)
                | Q(district__isnull=False)
                | Q(ward__isnull=False)
                | Q(postal_code__isnull=False)
                | Q(latitude__isnull=False),
                name="ck_patient_addresses_meaningful",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(latitude__isnull=True) & Q(longitude__isnull=True))
                    | (Q(latitude__isnull=False) & Q(longitude__isnull=False))
                ),
                name="ck_patient_addresses_coordinates_pair",
            ),
            models.CheckConstraint(
                condition=Q(latitude__isnull=True) | Q(latitude__gte=-90, latitude__lte=90),
                name="ck_patient_addresses_latitude",
            ),
            models.CheckConstraint(
                condition=Q(longitude__isnull=True) | Q(longitude__gte=-180, longitude__lte=180),
                name="ck_patient_addresses_longitude",
            ),
            models.CheckConstraint(
                condition=Q(country_code__isnull=True)
                | Q(country_code=models.functions.Upper("country_code")),
                name="ck_patient_addresses_country_upper",
            ),
        ]
        indexes = [
            models.Index(fields=["patient"], name="idx_patient_addresses_patient"),
        ]


class RelationshipType(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=40)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_relationship_types",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "relationship_types"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="uq_relationship_types_name"),
            models.UniqueConstraint(fields=["code"], name="uq_relationship_types_code"),
            models.CheckConstraint(
                condition=Q(code=models.functions.Upper("code")),
                name="ck_relationship_types_code_upper",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class PatientRelatedPerson(TimeStampedModel, ActiveModel):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="related_persons",
    )
    relationship_type = models.ForeignKey(
        RelationshipType,
        on_delete=models.PROTECT,
        related_name="patient_related_persons",
    )
    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="linked_related_person_records",
        blank=True,
        null=True,
    )
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    is_guardian = models.BooleanField(default=False)
    is_caregiver = models.BooleanField(default=False)
    is_next_of_kin = models.BooleanField(default=False)
    is_emergency_contact = models.BooleanField(default=False)
    priority_order = models.SmallIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_patient_related_persons",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "patient_related_persons"
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "linked_user"],
                condition=Q(linked_user__isnull=False),
                name="uq_patient_related_persons_linked_user",
            ),
            models.CheckConstraint(
                condition=Q(priority_order__gt=0),
                name="ck_patient_related_persons_priority",
            ),
        ]
        indexes = [
            models.Index(fields=["patient"], name="idx_pat_rel_person_pat"),
            models.Index(fields=["relationship_type"], name="idx_pat_rel_person_rel"),
        ]


class RelatedPersonContact(TimeStampedModel, ActiveModel):
    class Channel(models.TextChoices):
        PHONE = "phone", "Phone"
        EMAIL = "email", "Email"

    related_person = models.ForeignKey(
        PatientRelatedPerson,
        on_delete=models.PROTECT,
        related_name="contacts",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    label = models.CharField(max_length=50, blank=True, null=True)
    value_encrypted = models.TextField()
    value_hash = models.CharField(max_length=64, validators=[hash_validator])
    verified_at = models.DateTimeField(blank=True, null=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="verified_related_person_contacts",
        blank=True,
        null=True,
    )
    is_primary = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_related_person_contacts",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "related_person_contacts"
        constraints = [
            models.UniqueConstraint(
                fields=["related_person", "channel", "value_hash"],
                name="uq_related_person_contacts_value",
            ),
            models.UniqueConstraint(
                fields=["related_person", "channel"],
                condition=Q(is_primary=True, is_active=True),
                name="uq_related_person_contacts_primary",
            ),
            models.CheckConstraint(
                condition=Q(channel__in=["phone", "email"]),
                name="ck_related_person_contacts_channel",
            ),
            models.CheckConstraint(
                condition=Q(value_hash__regex=r"^[0-9A-Fa-f]{64}$"),
                name="ck_related_person_contacts_hash",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(verified_at__isnull=True) & Q(verified_by__isnull=True))
                    | (Q(verified_at__isnull=False) & Q(verified_by__isnull=False))
                ),
                name="ck_related_person_contacts_verification",
            ),
        ]
        indexes = [
            models.Index(fields=["related_person"], name="idx_rel_person_ctc"),
        ]


class PatientAccessGrant(TimeStampedModel, ActiveModel):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="access_grants",
    )
    related_person = models.ForeignKey(
        PatientRelatedPerson,
        on_delete=models.PROTECT,
        related_name="access_grants",
    )
    grantee_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="patient_access_grants",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="patient_access_grants",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="granted_patient_access",
        blank=True,
        null=True,
    )
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="revoked_patient_access",
        blank=True,
        null=True,
    )
    revocation_reason = models.CharField(max_length=250, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_patient_access_grants",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "patient_access_grants"
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "grantee_user", "role"],
                condition=Q(is_active=True, revoked_at__isnull=True),
                name="uq_patient_access_grants_active",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(ends_at__gte=F("starts_at")),
                name="ck_patient_access_grants_dates",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(revoked_at__isnull=True) & Q(revoked_by__isnull=True) & Q(revocation_reason__isnull=True))
                    | (
                        Q(revoked_at__isnull=False)
                        & Q(revoked_by__isnull=False)
                        & Q(revocation_reason__isnull=False)
                    )
                ),
                name="ck_patient_access_grants_revocation",
            ),
            models.CheckConstraint(
                condition=Q(revoked_at__isnull=True) | Q(is_active=False),
                name="ck_patient_access_grants_revoked_inactive",
            ),
        ]
        indexes = [
            models.Index(fields=["patient", "is_active"], name="idx_pat_access_pat_act"),
            models.Index(fields=["grantee_user", "is_active"], name="idx_pat_access_grant_act"),
            models.Index(fields=["role"], name="idx_patient_access_grants_role"),
        ]

    
