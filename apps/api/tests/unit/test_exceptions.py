"""Unit tests for custom exception classes."""

import pytest

from coyo.exceptions import (
    ConversationStateError,
    CoyoError,
    ExternalServiceError,
    NotFoundError,
    STTRecognitionError,
    ValidationError,
)


class TestCoyoError:
    """Tests for the base CoyoError exception."""

    @pytest.mark.unit
    def test_coyo_error_attributes(self):
        error = CoyoError("Something went wrong", "GENERIC_ERROR", 500)
        assert error.message == "Something went wrong"
        assert error.code == "GENERIC_ERROR"
        assert error.status_code == 500
        assert str(error) == "Something went wrong"

    @pytest.mark.unit
    def test_coyo_error_default_status_code(self):
        error = CoyoError("test", "TEST")
        assert error.status_code == 500

    @pytest.mark.unit
    def test_coyo_error_custom_status_code(self):
        error = CoyoError("test", "TEST", 418)
        assert error.status_code == 418

    @pytest.mark.unit
    def test_coyo_error_is_exception(self):
        error = CoyoError("test", "TEST")
        assert isinstance(error, Exception)


class TestNotFoundError:
    """Tests for the NotFoundError exception."""

    @pytest.mark.unit
    def test_not_found_error_format(self):
        error = NotFoundError("Conversation", "abc-123")
        assert error.message == "Conversation not found: abc-123"
        assert error.code == "NOT_FOUND"
        assert error.status_code == 404

    @pytest.mark.unit
    def test_not_found_error_inheritance(self):
        error = NotFoundError("User", "xyz")
        assert isinstance(error, CoyoError)
        assert isinstance(error, Exception)

    @pytest.mark.unit
    def test_not_found_error_different_resources(self):
        conv_error = NotFoundError("Conversation", "conv-id")
        user_error = NotFoundError("User", "user-id")
        assert "Conversation" in conv_error.message
        assert "User" in user_error.message

    @pytest.mark.unit
    def test_not_found_error_with_uuid(self):
        import uuid

        id_str = str(uuid.uuid4())
        error = NotFoundError("Conversation", id_str)
        assert id_str in error.message


class TestValidationError:
    """Tests for the ValidationError exception."""

    @pytest.mark.unit
    def test_validation_error_attributes(self):
        error = ValidationError("Invalid email format")
        assert error.message == "Invalid email format"
        assert error.code == "VALIDATION_ERROR"
        assert error.status_code == 422

    @pytest.mark.unit
    def test_validation_error_inheritance(self):
        error = ValidationError("test")
        assert isinstance(error, CoyoError)

    @pytest.mark.unit
    def test_validation_error_empty_message(self):
        error = ValidationError("")
        assert error.message == ""
        assert error.code == "VALIDATION_ERROR"


class TestConversationStateError:
    """Tests for the ConversationStateError exception."""

    @pytest.mark.unit
    def test_conversation_state_error_attributes(self):
        error = ConversationStateError("Cannot end a completed conversation")
        assert error.message == "Cannot end a completed conversation"
        assert error.code == "INVALID_STATE"
        assert error.status_code == 409

    @pytest.mark.unit
    def test_conversation_state_error_inheritance(self):
        error = ConversationStateError("test")
        assert isinstance(error, CoyoError)


class TestExternalServiceError:
    """Tests for the ExternalServiceError exception."""

    @pytest.mark.unit
    def test_external_service_error_format(self):
        error = ExternalServiceError("STT", "Connection timeout")
        assert error.message == "STT error: Connection timeout"
        assert error.code == "EXTERNAL_ERROR"
        assert error.status_code == 502

    @pytest.mark.unit
    def test_external_service_error_different_services(self):
        stt_error = ExternalServiceError("STT", "failed")
        tts_error = ExternalServiceError("TTS", "timeout")
        llm_error = ExternalServiceError("OpenAI", "rate limited")
        assert "STT" in stt_error.message
        assert "TTS" in tts_error.message
        assert "OpenAI" in llm_error.message

    @pytest.mark.unit
    def test_external_service_error_inheritance(self):
        error = ExternalServiceError("STT", "test")
        assert isinstance(error, CoyoError)


class TestSTTRecognitionError:
    """Tests for the STTRecognitionError exception."""

    @pytest.mark.unit
    def test_stt_recognition_error_attributes(self):
        error = STTRecognitionError()
        assert error.message == "Speech not recognized"
        assert error.code == "STT_RECOGNITION_FAILED"
        assert error.status_code == 422

    @pytest.mark.unit
    def test_stt_recognition_error_no_args(self):
        """STTRecognitionError requires no arguments to instantiate."""
        error = STTRecognitionError()
        assert isinstance(error, CoyoError)

    @pytest.mark.unit
    def test_stt_recognition_error_str(self):
        error = STTRecognitionError()
        assert str(error) == "Speech not recognized"
