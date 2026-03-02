"""Application-level exceptions for the Coto API.

All domain errors inherit from CotoError so they can be caught
by a single centralized exception handler in middleware.
"""


class CotoError(Exception):
    """Base exception for all Coto application errors."""

    def __init__(self, message: str, code: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(CotoError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, id: str) -> None:
        super().__init__(f"{resource} not found: {id}", "NOT_FOUND", 404)


class ValidationError(CotoError):
    """Raised when input data fails business-rule validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "VALIDATION_ERROR", 422)


class ConversationStateError(CotoError):
    """Raised when an operation is invalid for the current conversation state."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "INVALID_STATE", 409)


class ExternalServiceError(CotoError):
    """Raised when an external service (LLM, TTS, GCS) fails."""

    def __init__(self, service: str, detail: str) -> None:
        super().__init__(f"{service} error: {detail}", "EXTERNAL_ERROR", 502)


class STTRecognitionError(CotoError):
    """Raised when speech-to-text fails to recognize audio content."""

    def __init__(self) -> None:
        super().__init__("Speech not recognized", "STT_RECOGNITION_FAILED", 422)
