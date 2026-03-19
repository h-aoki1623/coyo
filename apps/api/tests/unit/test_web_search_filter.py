"""Unit tests for the web search filler-turn filter."""

import pytest

from coyo.services.web_search_filter import (
    FILLER_PHRASES,
    _MAX_FILLER_WORDS,
    is_filler_turn,
    strip_citations,
)


class TestIsFillerTurn:
    """Tests for is_filler_turn()."""

    # -- Known fillers (exact matches) --------------------------------------

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "text",
        ["yeah", "uh huh", "ok", "i see", "of course"],
    )
    def test_known_fillers_return_true(self, text: str):
        assert is_filler_turn(text) is True

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "text",
        ["yep", "yup", "nope", "sure", "right", "got it", "really",
         "wow", "nice", "cool", "great", "awesome", "interesting",
         "exactly", "definitely", "absolutely", "i know", "i agree",
         "me too", "same here", "mhm", "mm hmm", "mm-hmm", "uh-huh",
         "okay", "yes", "no"],
    )
    def test_all_filler_phrases_return_true(self, text: str):
        assert is_filler_turn(text) is True

    # -- Non-fillers (substantive questions) --------------------------------

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "text",
        [
            "What happened in the election?",
            "Tell me about the weather",
            "Who won the Champions League?",
        ],
    )
    def test_substantive_questions_return_false(self, text: str):
        assert is_filler_turn(text) is False

    # -- Edge cases: empty and whitespace -----------------------------------

    @pytest.mark.unit
    def test_empty_string_returns_false(self):
        assert is_filler_turn("") is False

    @pytest.mark.unit
    def test_whitespace_only_returns_false(self):
        assert is_filler_turn("   ") is False

    @pytest.mark.unit
    def test_tabs_and_newlines_returns_false(self):
        assert is_filler_turn("\t\n") is False

    # -- Edge cases: trailing punctuation -----------------------------------

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "text",
        ["yeah!", "ok.", "sure?", "right,"],
    )
    def test_trailing_punctuation_stripped(self, text: str):
        assert is_filler_turn(text) is True

    @pytest.mark.unit
    def test_multiple_trailing_punctuation(self):
        assert is_filler_turn("yeah!!!") is True

    # -- Edge cases: mixed case ---------------------------------------------

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "text",
        ["Yeah", "OK", "Of Course", "I SEE", "Uh Huh"],
    )
    def test_mixed_case_returns_true(self, text: str):
        assert is_filler_turn(text) is True

    # -- Edge cases: leading/trailing whitespace ----------------------------

    @pytest.mark.unit
    def test_leading_whitespace_stripped(self):
        assert is_filler_turn("  yeah") is True

    @pytest.mark.unit
    def test_trailing_whitespace_stripped(self):
        assert is_filler_turn("yeah  ") is True

    @pytest.mark.unit
    def test_both_whitespace_stripped(self):
        assert is_filler_turn("  yeah  ") is True

    # -- Word count boundary ------------------------------------------------

    @pytest.mark.unit
    def test_five_word_filler_matches(self):
        # "same here" is 2 words and in the list; check a known 3-word phrase
        # "of course" is 2 words; the longest are 2 words
        # 5 words exact but NOT in list -> False
        assert is_filler_turn("this is five words here") is False

    @pytest.mark.unit
    def test_six_words_always_returns_false(self):
        assert is_filler_turn("this is definitely more than five words") is False

    @pytest.mark.unit
    def test_max_filler_words_constant_is_five(self):
        assert _MAX_FILLER_WORDS == 5

    # -- Phrases not in the list --------------------------------------------

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "text",
        ["hello", "goodbye", "thanks", "please", "sorry"],
    )
    def test_short_non_filler_phrases_return_false(self, text: str):
        assert is_filler_turn(text) is False

    # -- Verify FILLER_PHRASES is a frozenset (immutable) -------------------

    @pytest.mark.unit
    def test_filler_phrases_is_frozenset(self):
        assert isinstance(FILLER_PHRASES, frozenset)


class TestStripCitations:
    """Tests for strip_citations()."""

    @pytest.mark.unit
    def test_markdown_link_replaced_with_label(self):
        text = "See [Wikipedia](https://en.wikipedia.org/wiki/Test) for details."
        assert strip_citations(text) == "See Wikipedia for details."

    @pytest.mark.unit
    def test_parenthesised_url_removed(self):
        text = "Grand Slam in singles. (https://en.wikipedia.org/wiki/Test?utm_source=openai)"
        assert strip_citations(text) == "Grand Slam in singles."

    @pytest.mark.unit
    def test_complex_citation_from_responses_api(self):
        text = (
            "Carlos Alcaraz won the 2026 Australian Open. "
            "([en.wikipedia.org](https://en.wikipedia.org/wiki/2026_Australian_Open))"
        )
        result = strip_citations(text)
        assert "https://" not in result
        assert "Carlos Alcaraz won the 2026 Australian Open." in result

    @pytest.mark.unit
    def test_multiple_citations_stripped(self):
        text = (
            "Fact one [source](https://a.com). "
            "Fact two [source](https://b.com)."
        )
        result = strip_citations(text)
        assert result == "Fact one source. Fact two source."

    @pytest.mark.unit
    def test_bare_domain_in_parens_removed(self):
        text = "He won the title. (apnews.com) It was historic."
        result = strip_citations(text)
        assert "apnews.com" not in result
        assert "He won the title." in result

    @pytest.mark.unit
    def test_no_citations_returns_unchanged(self):
        text = "A simple response with no links."
        assert strip_citations(text) == text

    @pytest.mark.unit
    def test_empty_string(self):
        assert strip_citations("") == ""

    @pytest.mark.unit
    def test_whitespace_collapsed(self):
        text = "Hello  ([en.wikipedia.org](https://example.com))  world"
        result = strip_citations(text)
        # Should not have double spaces
        assert "  " not in result
