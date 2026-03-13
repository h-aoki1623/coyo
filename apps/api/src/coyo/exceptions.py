"""Application-level exceptions for the Coyo API.

All domain errors inherit from CoyoError so they can be caught
by a single centralized exception handler in middleware.
"""


class CoyoError(Exception):
    """Base exception for all Coyo application errors.

    Attributes:
        message: Internal message for server-side logging (may contain
            sensitive details such as resource IDs or service names).
        client_message: Sanitized message safe to return to API clients.
            Defaults to ``message`` when not explicitly overridden.
        code: Machine-readable error code (e.g. "NOT_FOUND").
        status_code: HTTP status code for the error response.
    """

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 500,
        *,
        client_message: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.client_message = client_message if client_message is not None else message
        self.code = code
        self.status_code = status_code


class NotFoundError(CoyoError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, id: str) -> None:
        super().__init__(
            f"{resource} not found: {id}",
            "NOT_FOUND",
            404,
            client_message="The requested resource was not found",
        )


class ValidationError(CoyoError):
    """Raised when input data fails business-rule validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "VALIDATION_ERROR", 422)


class ConversationStateError(CoyoError):
    """Raised when an operation is invalid for the current conversation state."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            "INVALID_STATE",
            409,
            client_message="This operation is not allowed for the current conversation state",
        )


class AuthenticationError(CoyoError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            message,
            "AUTHENTICATION_ERROR",
            401,
            client_message="Authentication required",
        )


class ExternalServiceError(CoyoError):
    """Raised when an external service (LLM, TTS, GCS) fails."""

    def __init__(self, service: str, detail: str) -> None:
        super().__init__(
            f"{service} error: {detail}",
            "EXTERNAL_ERROR",
            502,
            client_message="An external service error occurred",
        )


class STTRecognitionError(CoyoError):
    """Raised when speech-to-text fails to recognize audio content."""

    def __init__(self) -> None:
        super().__init__("Speech not recognized", "STT_RECOGNITION_FAILED", 422)
