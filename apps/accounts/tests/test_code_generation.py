from __future__ import annotations

import re

import pytest

from apps.accounts.serializers import RoleCreateSerializer
from apps.accounts.services import create_permission, create_role, update_role
from apps.facilities.serializers import OrganizationCreateSerializer
from apps.facilities.services import create_facility, create_facility_type, create_organization, update_organization
from common.exceptions import ValidationError


pytestmark = pytest.mark.django_db


def test_create_organization_without_code_generates_org_code():
    organization = create_organization(name="Muhimbili Health Network")

    assert re.fullmatch(r"ORG\d{4}", organization.code)


def test_create_facility_without_code_generates_fac_code():
    organization = create_organization(name="Afya Tanzania")
    facility_type = create_facility_type(name="Hospital")

    facility = create_facility(
        organization_id=organization.id,
        facility_type_id=facility_type.id,
        name="Kijitonyama Hospital",
    )

    assert re.fullmatch(r"FAC\d{4}", facility.code)


def test_generated_codes_are_unique():
    first = create_organization(name="First Organization")
    second = create_organization(name="Second Organization")

    assert first.code != second.code
    assert first.code == "ORG0001"
    assert second.code == "ORG0002"


def test_code_is_not_changed_on_update():
    organization = create_organization(name="Original Organization")
    original_code = organization.code

    updated = update_organization(organization_id=organization.id, name="Renamed Organization")

    assert updated.code == original_code


def test_client_provided_code_cannot_override_backend_generation():
    organization = create_organization(name="Backend Owned Code", code="DIRTY")
    role = create_role(name="Operations Manager", code="CUSTOM_ROLE")

    assert organization.code == "ORG0001"
    assert role.code == "ROLE0001"

    with pytest.raises(ValidationError):
        update_role(role_id=role.id, code="OTHER_ROLE")


def test_generated_code_is_not_in_write_serializers():
    organization_serializer = OrganizationCreateSerializer(
        data={"name": "Serializer Organization", "code": "MANUAL"}
    )
    role_serializer = RoleCreateSerializer(data={"name": "Serializer Role", "code": "MANUAL_ROLE"})

    assert organization_serializer.is_valid(), organization_serializer.errors
    assert role_serializer.is_valid(), role_serializer.errors
    assert "code" not in organization_serializer.validated_data
    assert "code" not in role_serializer.validated_data


def test_permissions_keep_semantic_code_format():
    permission = create_permission(
        name="View Demo Capability",
        module="demo_capability",
        action="view",
    )

    assert permission.code == "demo_capability.view"
