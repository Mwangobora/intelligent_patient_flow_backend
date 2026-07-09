from __future__ import annotations

import re

from apps.facilities.models import Organization
from apps.practitioners.models import Practitioner

PRACTITIONER_NUMBER_PATTERN = re.compile(r"^PRAC-(\d+)$")


def generate_practitioner_number(*, organization: Organization) -> str:
    """
    Generate the next organization-scoped practitioner number.

    This should be called from a transaction where the organization row is
    already locked with SELECT FOR UPDATE to serialize concurrent generation.
    """
    max_sequence = 0
    existing_numbers = (
        Practitioner.objects.select_for_update()
        .filter(organization=organization)
        .values_list("practitioner_number", flat=True)
    )
    for existing_number in existing_numbers:
        match = PRACTITIONER_NUMBER_PATTERN.fullmatch(existing_number or "")
        if match:
            max_sequence = max(max_sequence, int(match.group(1)))

    next_sequence = max_sequence + 1
    while True:
        candidate = f"PRAC-{next_sequence:06d}"
        if not Practitioner.objects.select_for_update().filter(
            organization=organization,
            practitioner_number=candidate,
        ).exists():
            return candidate
        next_sequence += 1
