from __future__ import annotations

import re

from apps.facilities.models import Organization
from apps.patients.models import Patient

PATIENT_NUMBER_PATTERN = re.compile(r"^PAT-(\d+)$")


def generate_patient_number(*, organization: Organization) -> str:
    """
    Generate the next organization-scoped patient number.

    This should be called from a transaction where the organization row is
    already locked with SELECT FOR UPDATE to serialize concurrent generation.
    """
    max_sequence = 0
    existing_numbers = (
        Patient.objects.select_for_update()
        .filter(organization=organization)
        .values_list("patient_number", flat=True)
    )
    for existing_number in existing_numbers:
        match = PATIENT_NUMBER_PATTERN.fullmatch(existing_number or "")
        if match:
            max_sequence = max(max_sequence, int(match.group(1)))

    next_sequence = max_sequence + 1
    while True:
        candidate = f"PAT-{next_sequence:06d}"
        if not Patient.objects.select_for_update().filter(
            organization=organization,
            patient_number=candidate,
        ).exists():
            return candidate
        next_sequence += 1
