from __future__ import annotations

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from common.db import TimeStampedModel

phone_validator = RegexValidator(
    regex=r"^\+[1-9][0-9]{7,14}$",
    message="Phone number must be in E.164 format, for example +2557656765456.",
)


class UserManager(BaseUserManager):
    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields,
    ) -> User:
        if not email:
            raise ValueError("Users must have an email address.")

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


class User(TimeStampedModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField()
    phone_number = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        validators=[phone_validator],
    )
    first_name = models.CharField(max_length=30)
    middle_name = models.CharField(max_length=30, null=True, blank=True)
    last_name = models.CharField(max_length=30)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
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
                name="uq_users_email_ci",
            ),
            models.UniqueConstraint(
                fields=["phone_number"],
                condition=Q(phone_number__isnull=False),
                name="uq_users_phone_number",
            ),
        ]
        indexes = [
            models.Index(fields=["email"], name="idx_users_email"),
            models.Index(fields=["phone_number"], name="idx_users_phone_number"),
            models.Index(fields=["is_active"], name="idx_users_is_active"),
            models.Index(fields=["is_staff"], name="idx_users_is_staff"),
        ]

    def save(self, *args, **kwargs) -> None:
        self.email = self.__class__.objects.normalize_email(self.email).lower()
        if self.phone_number == "":
            self.phone_number = None
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        names = [self.first_name, self.middle_name, self.last_name]
        return " ".join(name for name in names if name).strip()

    def get_short_name(self) -> str:
        return self.first_name

        
