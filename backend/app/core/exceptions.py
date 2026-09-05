class TruthScopeError(Exception):
    """Base class for expected application failures."""


class GonkaUnavailableError(TruthScopeError):
    """Raised when Gonka cannot complete an inference request."""


class InvalidModelOutputError(TruthScopeError):
    """Raised when provider output fails strict schema validation."""

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        validationPaths: tuple[str, ...] = (),
        outputLength: int | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.validationPaths = validationPaths
        self.outputLength = outputLength


class RetrievalError(TruthScopeError):
    """Raised when an evidence adapter cannot safely retrieve content."""


class UnsafeUrlError(RetrievalError):
    """Raised when a URL could target a non-public network address."""


class VerificationNotFoundError(TruthScopeError):
    """Raised when a verification does not exist."""


class VerificationAccessError(TruthScopeError):
    """Raised when a user cannot access a stored verification."""


class AuthenticationError(TruthScopeError):
    """Raised when a Supabase access token is missing or invalid."""


class PersistenceUnavailableError(TruthScopeError):
    """Raised when the configured persistence boundary is unavailable."""
