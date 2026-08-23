from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User, UserMembership
from apps.facilities.models import Facility, Organization
from common.exceptions import ConflictError, NotFoundError, ValidationError


def _get_user(user_id) -> User:
    try:
        user = User.objects.select_for_update().get(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError("User not found.") from exc

    if not user.is_active:
        raise ValidationError("User must be active.")
    return user


def _get_creator_user(user_id) -> User:
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist as exc:
        raise NotFoundError("Creator user not found.") from exc


def _get_organization(organization_id) -> Organization:
    try:
        organization = Organization.objects.select_for_update().get(pk=organization_id)
    except Organization.DoesNotExist as exc:
        raise NotFoundError("Organization not found.") from exc

    if not organization.is_active:
        raise ValidationError("Organization must be active.")
    return organization


def _get_facility(facility_id) -> Facility:
    try:
        facility = Facility.objects.select_for_update().select_related("organization").get(pk=facility_id)
    except Facility.DoesNotExist as exc:
        raise NotFoundError("Facility not found.") from exc

    if not facility.is_active:
        raise ValidationError("Facility must be active.")
    return facility


def _get_membership_for_update(membership_id) -> UserMembership:
    try:
        return UserMembership.objects.select_for_update().get(pk=membership_id)
    except UserMembership.DoesNotExist as exc:
        raise NotFoundError("User membership not found.") from exc


def _resolve_membership_dates(*, starts_at, ends_at) -> tuple:
    resolved_starts_at = starts_at or timezone.now()
    if ends_at is not None and ends_at < resolved_starts_at:
        raise ValidationError("Membership ends_at must be greater than or equal to starts_at.")
    return resolved_starts_at, ends_at


def _get_existing_org_membership(*, user: User, organization: Organization) -> UserMembership | None:
    return UserMembership.objects.select_for_update().filter(
        user=user,
        organization=organization,
        facility__isnull=True,
    ).first()


def _get_existing_facility_membership(*, user: User, facility: Facility) -> UserMembership | None:
    return UserMembership.objects.select_for_update().filter(
        user=user,
        facility=facility,
    ).first()


def _membership_is_effective(*, membership: UserMembership, effective_at) -> bool:
    return (
        membership.is_active
        and membership.starts_at <= effective_at
        and (membership.ends_at is None or membership.ends_at >= effective_at)
    )


def _reuse_or_refresh_membership(
    *,
    membership: UserMembership,
    starts_at,
    ends_at,
    created_by: User | None,
) -> UserMembership:
    if _membership_is_effective(membership=membership, effective_at=starts_at):
        return membership

    membership.starts_at = starts_at
    membership.ends_at = ends_at
    membership.is_active = True
    update_fields = ["starts_at", "ends_at", "is_active", "updated_at"]
    if created_by is not None:
        membership.created_by = created_by
        update_fields.append("created_by")
    membership.save(update_fields=update_fields)
    return membership


@transaction.atomic
def create_organization_membership(
    *,
    user_id,
    organization_id,
    starts_at=None,
    ends_at=None,
    created_by_id=None,
) -> UserMembership:
    user = _get_user(user_id)
    organization = _get_organization(organization_id)
    resolved_starts_at, resolved_ends_at = _resolve_membership_dates(starts_at=starts_at, ends_at=ends_at)
    created_by = _get_creator_user(created_by_id) if created_by_id is not None else None
    existing = _get_existing_org_membership(user=user, organization=organization)
    if existing is not None:
        return _reuse_or_refresh_membership(
            membership=existing,
            starts_at=resolved_starts_at,
            ends_at=resolved_ends_at,
            created_by=created_by,
        )

    try:
        return UserMembership.objects.create(
            user=user,
            organization=organization,
            facility=None,
            starts_at=resolved_starts_at,
            ends_at=resolved_ends_at,
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Organization membership could not be created because it already exists.") from exc


@transaction.atomic
def create_facility_membership(
    *,
    user_id,
    organization_id,
    facility_id,
    starts_at=None,
    ends_at=None,
    created_by_id=None,
) -> UserMembership:
    user = _get_user(user_id)
    organization = _get_organization(organization_id)
    facility = _get_facility(facility_id)
    if facility.organization_id != organization.id:
        raise ValidationError("Facility must belong to the selected organization.")

    resolved_starts_at, resolved_ends_at = _resolve_membership_dates(starts_at=starts_at, ends_at=ends_at)
    created_by = _get_creator_user(created_by_id) if created_by_id is not None else None
    existing = _get_existing_facility_membership(user=user, facility=facility)
    if existing is not None:
        return _reuse_or_refresh_membership(
            membership=existing,
            starts_at=resolved_starts_at,
            ends_at=resolved_ends_at,
            created_by=created_by,
        )

    try:
        return UserMembership.objects.create(
            user=user,
            organization=organization,
            facility=facility,
            starts_at=resolved_starts_at,
            ends_at=resolved_ends_at,
            created_by=created_by,
        )
    except IntegrityError as exc:
        raise ConflictError("Facility membership could not be created because it already exists.") from exc


@transaction.atomic
def end_membership(
    *,
    membership_id,
    ends_at=None,
) -> UserMembership:
    membership = _get_membership_for_update(membership_id)
    now = timezone.now()
    resolved_ends_at = ends_at or now
    if resolved_ends_at < membership.starts_at:
        raise ValidationError("Membership ends_at must be greater than or equal to starts_at.")

    membership.ends_at = resolved_ends_at
    if resolved_ends_at <= now:
        membership.is_active = False
        membership.save(update_fields=["ends_at", "is_active", "updated_at"])
    else:
        membership.save(update_fields=["ends_at", "updated_at"])
    return membership


@transaction.atomic
def deactivate_membership(
    *,
    membership_id,
) -> UserMembership:
    membership = _get_membership_for_update(membership_id)
    if not membership.is_active:
        return membership

    membership.is_active = False
    membership.save(update_fields=["is_active", "updated_at"])
    return membership


@transaction.atomic
def reactivate_membership(
    *,
    membership_id,
) -> UserMembership:
    membership = _get_membership_for_update(membership_id)
    if membership.is_active:
        return membership

    if not membership.user.is_active:
        raise ValidationError("User must be active.")
    if not membership.organization.is_active:
        raise ValidationError("Organization must be active.")
    if membership.facility_id is not None and not membership.facility.is_active:
        raise ValidationError("Facility must be active.")
    if membership.ends_at is not None and membership.ends_at < timezone.now():
        raise ValidationError("Ended memberships cannot be reactivated; create a new membership instead.")

    membership.is_active = True
    membership.save(update_fields=["is_active", "updated_at"])
    return membership
