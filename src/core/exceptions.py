"""Domain Core Exceptions."""

class DomainError(Exception):
    """Base domain exception."""

class SessionNotFoundError(DomainError):
    pass

class AudioProcessingError(DomainError):
    pass

class GuardrailViolationError(DomainError):
    pass
