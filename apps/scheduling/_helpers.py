from __future__ import annotations

from common.exceptions import ConflictError, NotFoundError, ValidationError as DomainValidationError
from rest_framework.exceptions import NotFound, ValidationError


def translate_domain_error(exc: Exception):
    if isinstance(exc, DomainValidationError):
        raise ValidationError(str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise ValidationError({"detail": str(exc)}) from exc
    if isinstance(exc, NotFoundError):
        raise NotFound(str(exc)) from exc
    raise exc
