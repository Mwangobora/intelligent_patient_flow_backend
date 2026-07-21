from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.accounts.models import Role, User
from apps.facilities.models import Facility, Organization
from common.exceptions import ConflictError, NotFoundError, ValidationError
from common.services.code_generation import generate_code


def _get_role_for_update(role_id) -> Role:
    try:
        return Role.objects.select_for_update().get(pk=role_id)
    except Role.DoesNotExist as exc:
        raise NotFoundError("Role not found.") from exc


def _get_user(user_id, *, field_label: str) -> User:
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError(f"{field_label} user not found.") from exc


def _get_organization(organization_id) -> Organization:
    try:
        return Organization.objects.select_for_update().get(pk=organization_id)
    except Organization.DoesNotExist as exc:
        raise NotFoundError("Organization not found.") from exc


def _get_facility(facility_id) -> Facility:
    try:
        return Facility.objects.select_for_update().select_related("organization").get(pk=facility_id)
    except Facility.DoesNotExist as exc:
        raise NotFoundError("Facility not found.") from exc


def _resolve_role_scope(*, organization_id, facility_id) -> tuple[Organization | None, Facility | None]:
    organization = _get_organization(organization_id) if organization_id is not None else None
    facility = _get_facility(facility_id) if facility_id is not None else None

    if facility is not None and organization is None:
        raise ValidationError("Facility-scoped roles require an organization.")
    if facility is not None and facility.organization_id != organization.id:
        raise ValidationError("Facility must belong to the selected organization.")

    return organization, facility


def _get_scope_queryset(*, organization: Organization | None, facility: Facility | None):
    if facility is not None:
        return Role.objects.filter(facility=facility)
    if organization is not None:
        return Role.objects.filter(organization=organization, facility__isnull=True)
    return Role.objects.filter(organization__isnull=True, facility__isnull=True)


def _ensure_unique_role_scope_values(
    *,
    name: str,
    code: str,
    organization: Organization | None,
    facility: Facility | None,
    exclude_id=None,
) -> None:
    queryset = _get_scope_queryset(organization=organization, facility=facility).select_for_update()
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)

    if queryset.filter(name__iexact=name).exists():
        raise ConflictError("Role name already exists in this scope.")
    if queryset.filter(code=code).exists():
        raise ConflictError("Role code already exists in this scope.")


@transaction.atomic
def create_role(
    *,
    name: str,
    organization_id=None,
    facility_id=None,
    description: str | None = None,
    code: str | None = None,
    created_by_id=None,
) -> Role:
    if not name or not name.strip():
        raise ValidationError("Role name is required.")

    cleaned_name = name.strip()
    organization, facility = _resolve_role_scope(organization_id=organization_id, facility_id=facility_id)

    normalized_code = generate_code("role")

    _ensure_unique_role_scope_values(
        name=cleaned_name,
        code=normalized_code,
        organization=organization,
        facility=facility,
    )

    created_by = _get_user(created_by_id, field_label="Creator") if created_by_id is not None else None

    try:
        return Role.objects.create(
            organization=organization,
            facility=facility,
            name=cleaned_name,
            code=normalized_code,
            description=description.strip() if description else None,
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Role could not be created because a unique value already exists in this scope.") from exc


@transaction.atomic
def update_role(
    *,
    role_id,
    regenerate_code: bool = False,
    **updates,
) -> Role:
    role = _get_role_for_update(role_id)

    allowed_fields = {"name", "description", "organization_id", "facility_id"}
    unexpected_fields = set(updates) - allowed_fields
    if unexpected_fields:
        unexpected = ", ".join(sorted(unexpected_fields))
        raise ValidationError(f"Unsupported role update fields: {unexpected}.")

    next_name = role.name
    if "name" in updates:
        if not updates["name"] or not updates["name"].strip():
            raise ValidationError("Role name is required.")
        next_name = updates["name"].strip()

    next_organization_id = updates["organization_id"] if "organization_id" in updates else role.organization_id
    next_facility_id = updates["facility_id"] if "facility_id" in updates else role.facility_id
    next_organization, next_facility = _resolve_role_scope(
        organization_id=next_organization_id,
        facility_id=next_facility_id,
    )

    next_code = role.code

    _ensure_unique_role_scope_values(
        name=next_name,
        code=next_code,
        organization=next_organization,
        facility=next_facility,
        exclude_id=role.pk,
    )

    role.organization = next_organization
    role.facility = next_facility
    role.name = next_name
    role.code = next_code

    if "description" in updates:
        role.description = updates["description"].strip() if updates["description"] else None

    try:
        role.save()
    except IntegrityError as exc:
        raise ConflictError("Role could not be updated because a unique value already exists in this scope.") from exc
    return role


@transaction.atomic
def deactivate_role(*, role_id) -> Role:
    role = _get_role_for_update(role_id)
    if not role.is_active:
        return role

    role.is_active = False
    role.save(update_fields=["is_active", "updated_at"])
    return role
