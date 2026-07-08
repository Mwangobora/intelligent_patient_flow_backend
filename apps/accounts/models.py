from __future__ import annotations

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.facilities.models import Facility, Organization
from common.db import ActiveModel, TimeStampedModel

phone_validator = RegexValidator(
    regex=r"^\+[1-9][0-9]{7,14}$",
    message="Phone number must be in E.164 format, for example +2557656765456.",
)
permission_code_validator = RegexValidator(
    regex=r"^[a-z0-9_]+\.[a-z0-9_]+$",
    message="Permission code must use module.action format in lowercase.",
)


class UserManager(BaseUserManager):
    def create_user(
        self,
        email: str | None = None,
        password: str | None = None,
        **extra_fields,
    ) -> User:
        phone_number = extra_fields.get("phone_number")
        if not email and not phone_number:
            raise ValueError("Users must have an email address or phone number.")

        if email:
            email = self.normalize_email(email).lower()
        user = self.model(
            email=email,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str,
        **extra_fields,
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("email_verified_at", timezone.now())

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(
            email=email,
            password=password,
            **extra_fields,
        )


class User(TimeStampedModel, AbstractBaseUser):
    email = models.EmailField(null=True, blank=True)
    phone_number = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        validators=[phone_validator],
    )
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "users"
        ordering = ["email"]
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                condition=Q(email__isnull=False),
                name="uq_users_email",
            ),
            models.UniqueConstraint(
                fields=["phone_number"],
                condition=Q(phone_number__isnull=False),
                name="uq_users_phone",
            ),
            models.CheckConstraint(
                condition=Q(email__isnull=False) | Q(phone_number__isnull=False),
                name="ck_users_contact_required",
            ),
            models.CheckConstraint(
                condition=Q(phone_number__isnull=True) | Q(phone_number__regex=r"^\+[1-9][0-9]{7,14}$"),
                name="ck_users_phone_e164",
            ),
            models.CheckConstraint(
                condition=Q(email_verified_at__isnull=True) | Q(email__isnull=False),
                name="ck_users_email_verification_target",
            ),
            models.CheckConstraint(
                condition=Q(phone_verified_at__isnull=True) | Q(phone_number__isnull=False),
                name="ck_users_phone_verification_target",
            ),
        ]

    def save(self, *args, **kwargs) -> None:
        if self.email:
            self.email = self.__class__.objects.normalize_email(self.email).lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email or self.phone_number or str(self.pk)

    def get_full_name(self) -> str:
        names = [self.first_name, self.middle_name, self.last_name]
        return " ".join(name for name in names if name).strip()

    def get_short_name(self) -> str:
        return self.first_name

    def has_perm(self, perm: str, obj=None) -> bool:
        return bool(self.is_active and (self.is_superuser or self.is_staff))

    def has_module_perms(self, app_label: str) -> bool:
        return bool(self.is_active and (self.is_superuser or self.is_staff))


class Role(TimeStampedModel, ActiveModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="roles",
        blank=True,
        null=True,
    )
    facility = models.ForeignKey(
        Facility,
        on_delete=models.PROTECT,
        related_name="roles",
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=80)
    description = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_roles",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "roles"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(code=models.functions.Upper("code")),
                name="ck_roles_code_upper",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(organization__isnull=True) & Q(facility__isnull=True))
                    | (Q(organization__isnull=False) & Q(facility__isnull=True))
                    | (Q(organization__isnull=False) & Q(facility__isnull=False))
                ),
                name="ck_roles_scope",
            ),
            models.UniqueConstraint(
                Lower("name"),
                condition=Q(organization__isnull=True, facility__isnull=True),
                name="uq_roles_platform_name",
            ),
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(organization__isnull=True, facility__isnull=True),
                name="uq_roles_platform_code",
            ),
            models.UniqueConstraint(
                Lower("name"),
                F("organization"),
                condition=Q(organization__isnull=False, facility__isnull=True),
                name="uq_roles_org_name",
            ),
            models.UniqueConstraint(
                fields=["organization", "code"],
                condition=Q(organization__isnull=False, facility__isnull=True),
                name="uq_roles_org_code",
            ),
            models.UniqueConstraint(
                Lower("name"),
                F("facility"),
                condition=Q(facility__isnull=False),
                name="uq_roles_facility_name",
            ),
            models.UniqueConstraint(
                fields=["facility", "code"],
                condition=Q(facility__isnull=False),
                name="uq_roles_facility_code",
            ),
        ]
        indexes = [
            models.Index(fields=["organization"], name="idx_roles_organization"),
            models.Index(fields=["facility"], name="idx_roles_facility"),
        ]

    def __str__(self) -> str:
        return self.name

    # TODO: enforce the SQL trigger `trg_roles_validate_scope` in a custom migration.


class Permission(TimeStampedModel, ActiveModel):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=120, validators=[permission_code_validator])
    module = models.CharField(max_length=60)
    action = models.CharField(max_length=60)
    description = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_permissions",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "permissions"
        ordering = ["module", "action"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="uq_permissions_name"),
            models.UniqueConstraint(fields=["code"], name="uq_permissions_code"),
            models.UniqueConstraint(fields=["module", "action"], name="uq_permissions_module_action"),
            models.CheckConstraint(
                condition=Q(code=Lower("code")),
                name="ck_permissions_code_lower",
            ),
            models.CheckConstraint(
                condition=Q(code__regex=r"^[a-z0-9_]+\.[a-z0-9_]+$"),
                name="ck_permissions_code_format",
            ),
            models.CheckConstraint(
                condition=Q(module=Lower("module")),
                name="ck_permissions_module_lower",
            ),
            models.CheckConstraint(
                condition=Q(action=Lower("action")),
                name="ck_permissions_action_lower",
            ),
        ]

    def __str__(self) -> str:
        return self.code


class RolePermission(TimeStampedModel, ActiveModel):
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="role_permissions",
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.PROTECT,
        related_name="role_permissions",
    )
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="granted_role_permissions",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "role_permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="uq_role_permissions_pair",
            )
        ]
        indexes = [
            models.Index(fields=["role", "is_active"], name="idx_role_permissions_role_active"),
            models.Index(fields=["permission"], name="idx_role_permissions_permission"),
        ]

    def __str__(self) -> str:
        return f"{self.role} -> {self.permission}"


class UserMembership(TimeStampedModel, ActiveModel):
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="user_memberships",
    )
    facility = models.ForeignKey(
        Facility,
        on_delete=models.PROTECT,
        related_name="user_memberships",
        blank=True,
        null=True,
    )
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_memberships",
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "user_memberships"
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(ends_at__gte=F("starts_at")),
                name="ck_user_memberships_dates",
            ),
            models.UniqueConstraint(
                fields=["user", "organization"],
                condition=Q(facility__isnull=True),
                name="uq_user_memberships_org",
            ),
            models.UniqueConstraint(
                fields=["user", "facility"],
                condition=Q(facility__isnull=False),
                name="uq_user_memberships_facility",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_active"], name="idx_user_memberships_user_active"),
            models.Index(fields=["organization"], name="idx_user_memberships_org"),
            models.Index(fields=["facility"], name="idx_user_memberships_facility"),
        ]

    def __str__(self) -> str:
        scope = self.facility.name if self.facility else self.organization.name
        return f"{self.user} @ {scope}"

    # TODO: enforce the SQL trigger `trg_user_memberships_validate_scope` in a custom migration.


class UserRoleAssignment(TimeStampedModel, ActiveModel):
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="role_assignments",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="user_assignments",
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="assigned_roles",
        blank=True,
        null=True,
    )
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "user_role_assignments"
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="uq_user_role_assignments_pair"),
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(ends_at__gte=F("starts_at")),
                name="ck_user_role_assignments_dates",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "is_active"], name="idx_user_role_assignments_user_active"),
            models.Index(fields=["role"], name="idx_user_role_assignments_role"),
        ]

    def __str__(self) -> str:
        return f"{self.user} -> {self.role}"

    # TODO: enforce the SQL trigger `trg_user_role_assignments_validate` in a custom migration.

        
