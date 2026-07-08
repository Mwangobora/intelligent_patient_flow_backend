from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Permission, Role, RolePermission, User, UserMembership, UserRoleAssignment


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = (
        "email",
        "first_name",
        "last_name",
        "phone_number",
        "is_active",
        "is_staff",
        "is_superuser",
    )
    search_fields = ("email", "first_name", "last_name", "phone_number")
    list_filter = ("is_active", "is_staff", "is_superuser")
    filter_horizontal = ()
    readonly_fields = ("last_login", "date_joined", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {
                "fields": (
                    "first_name",
                    "middle_name",
                    "last_name",
                    "phone_number",
                    "email_verified_at",
                    "phone_verified_at",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "password1", "password2"),
            },
        ),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "organization", "facility", "is_active", "created_at")
    list_filter = ("is_active", "organization", "facility")
    search_fields = ("name", "code", "description")


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "module", "action", "is_active", "created_at")
    list_filter = ("is_active", "module", "action")
    search_fields = ("name", "code", "module", "action")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission", "granted_by", "is_active", "created_at")
    list_filter = ("is_active", "role")
    search_fields = ("role__name", "permission__code")


@admin.register(UserMembership)
class UserMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "facility", "starts_at", "ends_at", "is_active")
    list_filter = ("is_active", "organization", "facility")
    search_fields = ("user__email", "organization__name", "facility__name")


@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "assigned_by", "starts_at", "ends_at", "is_active")
    list_filter = ("is_active", "role")
    search_fields = ("user__email", "role__name", "role__code")
