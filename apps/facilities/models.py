from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

from common.db import ActiveModel, TimeStampedModel

phone_validator = RegexValidator(
    regex=r"^\+[1-9][0-9]{7,14}$",
    message="Phone number must be in E.164 format, for example +2557656765456.",
)


class Organization(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=150)
    legal_name = models.CharField(max_length=200, blank=True)
    code = models.CharField(max_length=30)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        validators=[phone_validator],
    )
    registration_number = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "organizations"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["code"], name="uq_organizations_code"),
            models.CheckConstraint(
                condition=models.Q(code=models.functions.Upper("code")),
                name="ck_organizations_code_upper",
            ),
        ]
        indexes = [
            models.Index(fields=["code"], name="idx_organizations_code"),
        ]

    def save(self, *args, **kwargs) -> None:
        self.code = self.code.upper()
        if self.legal_name == "":
            self.legal_name = ""
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class FacilityType(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "facility_types"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="uq_facility_types_name"),
            models.UniqueConstraint(fields=["code"], name="uq_facility_types_code"),
            models.CheckConstraint(
                condition=models.Q(code=models.functions.Upper("code")),
                name="ck_facility_types_code_upper",
            ),
        ]

    def save(self, *args, **kwargs) -> None:
        self.code = self.code.upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Facility(TimeStampedModel, ActiveModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="facilities",
    )
    facility_type = models.ForeignKey(
        FacilityType,
        on_delete=models.PROTECT,
        related_name="facilities",
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    license_number = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        validators=[phone_validator],
    )
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    region = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    ward = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    timezone = models.CharField(max_length=64, default="Africa/Dar_es_Salaam")
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "facilities"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="uq_facilities_org_code",
            ),
            models.CheckConstraint(
                condition=models.Q(code=models.functions.Upper("code")),
                name="ck_facilities_code_upper",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(country_code="") | models.Q(country_code=models.functions.Upper("country_code"))
                ),
                name="ck_facilities_country_upper",
            ),
            models.CheckConstraint(
                condition=(
                    (models.Q(latitude__isnull=True) & models.Q(longitude__isnull=True))
                    | (models.Q(latitude__isnull=False) & models.Q(longitude__isnull=False))
                ),
                name="ck_facilities_coordinates_pair",
            ),
            models.CheckConstraint(
                condition=models.Q(latitude__isnull=True) | models.Q(latitude__gte=-90, latitude__lte=90),
                name="ck_facilities_latitude",
            ),
            models.CheckConstraint(
                condition=models.Q(longitude__isnull=True) | models.Q(longitude__gte=-180, longitude__lte=180),
                name="ck_facilities_longitude",
            ),
        ]
        indexes = [
            models.Index(fields=["organization"], name="idx_facilities_organization"),
            models.Index(fields=["facility_type"], name="idx_facilities_type"),
        ]

    def save(self, *args, **kwargs) -> None:
        self.code = self.code.upper()
        if self.country_code:
            self.country_code = self.country_code.upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"
