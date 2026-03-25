"""Unit tests for the STT prompt building logic in TurnOrchestrator."""

from types import SimpleNamespace

import pytest

from coyo.services.turn_orchestrator import TurnOrchestrator


def _make_turn(text: str) -> SimpleNamespace:
    """Create a minimal turn-like object with a text attribute."""
    return SimpleNamespace(text=text)


class TestFormatSttPrompt:
    """Tests for TurnOrchestrator._format_stt_prompt static method."""

    @pytest.mark.unit
    def test_empty_conversation(self):
        """Verify prompt contains only topic when no turns exist."""
        result = TurnOrchestrator._format_stt_prompt([], "tennis")
        assert result == "Topic: tennis."

    @pytest.mark.unit
    def test_fewer_than_four_turns(self):
        """Verify all turns are included when fewer than 4 exist."""
        turns = [_make_turn("Hello"), _make_turn("Hi there")]
        result = TurnOrchestrator._format_stt_prompt(turns, "tennis")
        assert result == "Topic: tennis. Hello Hi there"

    @pytest.mark.unit
    def test_more_than_four_turns_uses_last_four(self):
        """Verify only the last 4 turns are included."""
        turns = [
            _make_turn("Turn 1"),
            _make_turn("Turn 2"),
            _make_turn("Turn 3"),
            _make_turn("Turn 4"),
            _make_turn("Turn 5"),
            _make_turn("Turn 6"),
        ]
        result = TurnOrchestrator._format_stt_prompt(turns, "sports")
        assert "Turn 1" not in result
        assert "Turn 2" not in result
        assert "Turn 3" in result
        assert "Turn 4" in result
        assert "Turn 5" in result
        assert "Turn 6" in result

    @pytest.mark.unit
    def test_suggested_topic_label_substitution(self):
        """Verify 'suggested' topic is replaced with descriptive label."""
        result = TurnOrchestrator._format_stt_prompt([], "suggested")
        assert result == "Topic: a trending news topic."

    @pytest.mark.unit
    def test_standard_topic_passthrough(self):
        """Verify standard topics are passed through unchanged."""
        result = TurnOrchestrator._format_stt_prompt([], "cooking")
        assert result == "Topic: cooking."

    @pytest.mark.unit
    def test_prompt_truncated_to_max_length(self):
        """Verify prompt is truncated when it exceeds the max character limit."""
        long_text = "x" * 500
        turns = [_make_turn(long_text) for _ in range(4)]
        result = TurnOrchestrator._format_stt_prompt(turns, "tennis")
        assert len(result) <= 800
