class DomainError(Exception):
    """Base exception for domain and service-layer errors."""


class ValidationError(DomainError):
    """Raised when input data or business rules are invalid."""


class ConflictError(DomainError):
    """Raised when an operation conflicts with existing state."""


class NotFoundError(DomainError):
    """Raised when an expected domain object does not exist."""
