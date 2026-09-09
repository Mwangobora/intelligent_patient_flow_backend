from __future__ import annotations

from rest_framework.exceptions import NotFound, ValidationError

from common.exceptions import ConflictError, NotFoundError
from common.exceptions import ValidationError as DomainValidationError


def translate_domain_error(exc: Exception):
    if isinstance(exc, DomainValidationError):
        raise ValidationError(str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise ValidationError({"detail": str(exc)}) from exc
    if isinstance(exc, NotFoundError):
        raise NotFound(str(exc)) from exc
    raise exc
