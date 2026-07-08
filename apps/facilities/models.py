from __future__ import annotations

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
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
            models.Index(fields=["is_active"], name="idx_facilities_active"),
        ]

    def save(self, *args, **kwargs) -> None:
        self.code = self.code.upper()
        if self.country_code:
            self.country_code = self.country_code.upper()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Department(TimeStampedModel, ActiveModel):
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="departments")
    parent_department = models.ForeignKey(
        "self", on_delete=models.PROTECT, related_name="child_departments", blank=True, null=True
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "departments"
        constraints = [
            models.UniqueConstraint(fields=["facility", "code"], name="uq_departments_facility_code"),
            models.CheckConstraint(
                condition=Q(code=models.functions.Upper("code")),
                name="ck_departments_code_upper",
            ),
            models.CheckConstraint(
                condition=Q(parent_department__isnull=True) | ~Q(parent_department=F("id")),
                name="ck_departments_no_self_parent",
            ),
        ]
        indexes = [models.Index(fields=["facility"], name="idx_departments_facility")]

    # TODO: enforce department hierarchy validation trigger from the SQL file in a custom migration.


class Specialty(TimeStampedModel, ActiveModel):
    parent_specialty = models.ForeignKey(
        "self", on_delete=models.PROTECT, related_name="child_specialties", blank=True, null=True
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "specialties"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="uq_specialties_name"),
            models.UniqueConstraint(fields=["code"], name="uq_specialties_code"),
            models.CheckConstraint(
                condition=Q(code=models.functions.Upper("code")),
                name="ck_specialties_code_upper",
            ),
            models.CheckConstraint(
                condition=Q(parent_specialty__isnull=True) | ~Q(parent_specialty=F("id")),
                name="ck_specialties_no_self_parent",
            ),
        ]


class FacilitySpecialty(TimeStampedModel, ActiveModel):
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="facility_specialties")
    specialty = models.ForeignKey(Specialty, on_delete=models.PROTECT, related_name="facility_specialties")
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="facility_specialties", blank=True, null=True
    )
    appointment_duration_minutes = models.SmallIntegerField()
    accepts_appointments = models.BooleanField(default=True)
    accepts_walk_ins = models.BooleanField(default=False)
    requires_referral = models.BooleanField(default=False)

    class Meta:
        db_table = "facility_specialties"
        constraints = [
            models.CheckConstraint(
                condition=Q(appointment_duration_minutes__gt=0),
                name="ck_facility_specialties_duration",
            ),
            models.UniqueConstraint(
                fields=["facility", "specialty"],
                condition=Q(department__isnull=True),
                name="uq_facility_specialties_without_department",
            ),
            models.UniqueConstraint(
                fields=["facility", "specialty", "department"],
                condition=Q(department__isnull=False),
                name="uq_facility_specialties_with_department",
            ),
        ]
        indexes = [
            models.Index(fields=["facility"], name="idx_facility_specialties_facility"),
            models.Index(fields=["specialty"], name="idx_facility_specialties_specialty"),
            models.Index(fields=["department"], name="idx_facility_specialties_department"),
        ]

    # TODO: enforce facility child scope validation trigger from the SQL file in a custom migration.


class ServicePointType(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "service_point_types"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="uq_service_point_types_name"),
            models.UniqueConstraint(fields=["code"], name="uq_service_point_types_code"),
            models.CheckConstraint(
                condition=Q(code=models.functions.Upper("code")),
                name="ck_service_point_types_code_upper",
            ),
        ]


class ServicePoint(TimeStampedModel, ActiveModel):
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="service_points")
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="service_points", blank=True, null=True
    )
    service_point_type = models.ForeignKey(
        ServicePointType, on_delete=models.PROTECT, related_name="service_points"
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    location_description = models.CharField(max_length=250, blank=True, null=True)
    floor = models.CharField(max_length=30, blank=True, null=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        db_table = "service_points"
        constraints = [
            models.UniqueConstraint(fields=["facility", "code"], name="uq_service_points_facility_code"),
            models.CheckConstraint(
                condition=Q(code=models.functions.Upper("code")),
                name="ck_service_points_code_upper",
            ),
            models.CheckConstraint(condition=Q(display_order__gte=0), name="ck_service_points_display_order"),
        ]
        indexes = [models.Index(fields=["facility"], name="idx_service_points_facility")]

    # TODO: enforce facility child scope validation trigger from the SQL file in a custom migration.


class ConsultationRoom(TimeStampedModel, ActiveModel):
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="consultation_rooms")
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="consultation_rooms", blank=True, null=True
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    location_description = models.CharField(max_length=250, blank=True, null=True)
    floor = models.CharField(max_length=30, blank=True, null=True)
    capacity = models.SmallIntegerField(default=1)

    class Meta:
        db_table = "consultation_rooms"
        constraints = [
            models.UniqueConstraint(fields=["facility", "code"], name="uq_consultation_rooms_facility_code"),
            models.CheckConstraint(
                condition=Q(code=models.functions.Upper("code")),
                name="ck_consultation_rooms_code_upper",
            ),
            models.CheckConstraint(condition=Q(capacity__gt=0), name="ck_consultation_rooms_capacity"),
        ]
        indexes = [models.Index(fields=["facility"], name="idx_consultation_rooms_facility")]

    # TODO: enforce facility child scope validation trigger from the SQL file in a custom migration.


class FacilityOperatingHour(TimeStampedModel, ActiveModel):
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="operating_hours")
    day_of_week = models.SmallIntegerField()
    period_order = models.SmallIntegerField(default=1)
    opens_at = models.TimeField(blank=True, null=True)
    closes_at = models.TimeField(blank=True, null=True)
    closes_next_day = models.BooleanField(default=False)
    is_24_hours = models.BooleanField(default=False)

    class Meta:
        db_table = "facility_operating_hours"
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "day_of_week", "period_order"],
                name="uq_facility_operating_hours_period",
            ),
            models.CheckConstraint(condition=Q(day_of_week__gte=1, day_of_week__lte=7), name="ck_facility_operating_hours_day"),
            models.CheckConstraint(condition=Q(period_order__gt=0), name="ck_facility_operating_hours_period_order"),
            models.CheckConstraint(
                condition=(
                    (Q(is_24_hours=True) & Q(opens_at__isnull=True) & Q(closes_at__isnull=True) & Q(closes_next_day=False))
                    | (
                        Q(is_24_hours=False)
                        & Q(opens_at__isnull=False)
                        & Q(closes_at__isnull=False)
                        & ~Q(opens_at=F("closes_at"))
                        & (Q(closes_next_day=True) | Q(closes_at__gt=F("opens_at")))
                    )
                ),
                name="ck_facility_operating_hours_shape",
            ),
        ]
        indexes = [models.Index(fields=["facility", "day_of_week", "is_active"], name="idx_facility_operating_hours_lookup")]

    # TODO: enforce operating hours overlap trigger from the SQL file in a custom migration.


class FacilityScheduleException(TimeStampedModel, ActiveModel):
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="schedule_exceptions")
    exception_date = models.DateField()
    period_order = models.SmallIntegerField(default=1)
    is_closed = models.BooleanField(default=False)
    opens_at = models.TimeField(blank=True, null=True)
    closes_at = models.TimeField(blank=True, null=True)
    closes_next_day = models.BooleanField(default=False)
    is_24_hours = models.BooleanField(default=False)
    reason = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        db_table = "facility_schedule_exceptions"
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "exception_date", "period_order"],
                name="uq_facility_schedule_exceptions_period",
            ),
            models.CheckConstraint(condition=Q(period_order__gt=0), name="ck_facility_schedule_exceptions_period_order"),
            models.CheckConstraint(
                condition=(
                    (Q(is_closed=True) & Q(is_24_hours=False) & Q(opens_at__isnull=True) & Q(closes_at__isnull=True) & Q(closes_next_day=False))
                    | (Q(is_closed=False) & Q(is_24_hours=True) & Q(opens_at__isnull=True) & Q(closes_at__isnull=True) & Q(closes_next_day=False))
                    | (
                        Q(is_closed=False) & Q(is_24_hours=False) & Q(opens_at__isnull=False) & Q(closes_at__isnull=False)
                        & ~Q(opens_at=F("closes_at")) & (Q(closes_next_day=True) | Q(closes_at__gt=F("opens_at")))
                    )
                ),
                name="ck_facility_schedule_exceptions_shape",
            ),
        ]
        indexes = [models.Index(fields=["facility", "exception_date", "is_active"], name="idx_facility_schedule_exceptions_lookup")]

    # TODO: enforce schedule exception trigger from the SQL file in a custom migration.


class FacilityFlowSetting(TimeStampedModel):
    facility = models.OneToOneField(Facility, on_delete=models.CASCADE, related_name="flow_settings")
    max_advance_booking_days = models.SmallIntegerField(default=30)
    minimum_booking_notice_minutes = models.IntegerField(default=0)
    cancellation_cutoff_minutes = models.IntegerField(default=60)
    reschedule_cutoff_minutes = models.IntegerField(default=60)
    early_checkin_minutes = models.IntegerField(default=30)
    late_checkin_grace_minutes = models.IntegerField(default=15)
    no_show_after_minutes = models.IntegerField(default=15)
    default_reminder_minutes_before = models.IntegerField(blank=True, null=True, default=1440)
    queue_number_padding = models.SmallIntegerField(default=3)
    auto_create_daily_queues = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_facility_flow_settings", blank=True, null=True
    )

    class Meta:
        db_table = "facility_flow_settings"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(max_advance_booking_days__gte=0)
                    & Q(minimum_booking_notice_minutes__gte=0)
                    & Q(cancellation_cutoff_minutes__gte=0)
                    & Q(reschedule_cutoff_minutes__gte=0)
                    & Q(early_checkin_minutes__gte=0)
                    & Q(late_checkin_grace_minutes__gte=0)
                    & Q(no_show_after_minutes__gte=0)
                    & (Q(default_reminder_minutes_before__isnull=True) | Q(default_reminder_minutes_before__gte=0))
                ),
                name="ck_facility_flow_settings_nonnegative",
            ),
            models.CheckConstraint(condition=Q(queue_number_padding__gte=1, queue_number_padding__lte=6), name="ck_facility_flow_settings_padding"),
        ]
