"""Service for analyzing user text and generating corrections.

Uses the LLM with structured JSON output to identify grammar,
expression, and vocabulary errors in the user's English text.
Explanations are generated in the user's preferred language.
"""

import uuid

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.config import get_settings
from coyo.models.correction import CorrectionItem, TurnCorrection
from coyo.models.turn import Turn
from coyo.services.llm.base import ChatMessage, ChatOptions
from coyo.services.llm.openai_client import OpenAIClient

logger = structlog.get_logger()


# -- LLM structured output schemas (internal, not API response) --------


class CorrectionItemAnalysis(BaseModel):
    """A single correction identified by the LLM."""

    original: str
    corrected: str
    original_sentence: str
    corrected_sentence: str
    type: str  # "grammar" | "expression" | "vocabulary"
    explanation: str


class CorrectionAnalysis(BaseModel):
    """LLM output schema for correction analysis."""

    has_errors: bool
    corrected_text: str
    explanation: str
    items: list[CorrectionItemAnalysis]


# -- System prompt template ---------------------------------------------

# The prompt is split into a byte-stable static prefix and a dynamic suffix
# (language + user_text) so OpenAI's prompt-prefix cache can reuse the prefix
# across calls. Do NOT interpolate dynamic values into the prefix.

_CORRECTION_SYSTEM_PROMPT_PREFIX = """\
You are an English language correction assistant. \
The input text is transcribed from a spoken English conversation, not written text. \
Analyze it for genuine spoken-English errors only.

Rules:
- The input is speech-to-text output. Judge it by spoken/colloquial norms, \
NOT formal written-English standards.
- Accept natural spoken patterns — do NOT flag these:
  - Sentence fragments or incomplete thoughts (normal in conversation)
  - Filler words and discourse markers ("um", "uh", "like", "you know", \
"well", "so", "I mean")
  - Informal contractions ("gonna", "wanna", "gotta", "kinda")
  - Casual sentence structures and informal grammar that native speakers use
  - Missing punctuation or capitalization (these are transcription artifacts)
  - Repetitions or self-corrections ("I went to the — I went to the store")
- Only flag errors that would sound wrong in spoken conversation:
  - Incorrect verb tenses ("I goed" instead of "I went")
  - Wrong prepositions ("interested for" instead of "interested in")
  - Subject-verb agreement errors ("he don't" instead of "he doesn't")
  - Vocabulary misuse (wrong word choice that changes meaning)
  - Word order errors that sound unnatural in speech
- Each error MUST be a separate item. Never combine multiple errors into one \
item, even if they appear in the same sentence.
- "original" and "corrected" must be the minimal fragment around the single \
error, not the entire sentence. Include only 1-2 surrounding words for context.
- For each item, also provide the full original sentence and the full corrected \
sentence (with ALL corrections for that sentence applied).
- Classify each error as one of: "grammar", "expression", "vocabulary".
- Write all explanations in the language specified below \
(see "Explanation language").
- If the text has no errors, set has_errors to false, corrected_text to the \
original text, explanation to an empty string, and items to an empty list.

You MUST respond with valid JSON matching this exact schema:
{
  "has_errors": <boolean>,
  "corrected_text": "<string>",
  "explanation": "<string — overall explanation of corrections>",
  "items": [
    {
      "original": "<string>",
      "corrected": "<string>",
      "original_sentence": "<string>",
      "corrected_sentence": "<string>",
      "type": "<grammar|expression|vocabulary>",
      "explanation": "<string>"
    }
  ]
}\
"""


def _build_correction_system_prompt(
    correction_language_name: str,
    user_text: str,
) -> str:
    """Compose the correction prompt: static prefix + dynamic suffix."""
    return (
        f"{_CORRECTION_SYSTEM_PROMPT_PREFIX}\n\n"
        f"Explanation language: {correction_language_name}\n\n"
        f'User text to analyze:\n"""{user_text}"""'
    )


_LANGUAGE_NAMES: dict[str, str] = {
    "ja": "Japanese",
    "en": "English",
    "ko": "Korean",
    "zh": "Chinese",
    "es": "Spanish",
    "fr": "French",
}


class CorrectionService:
    """Analyzes user turns for grammar, expression, and vocabulary errors.

    Uses the LLM with structured output to identify corrections
    and generates explanations in the user's preferred language.
    Persists results to the database.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        settings = get_settings()
        self._llm = OpenAIClient(model=settings.llm_correction_model)

    async def analyze_turn(
        self,
        *,
        turn_id: uuid.UUID,
        user_id: uuid.UUID,
        user_text: str,
        correction_language: str = "ja",
    ) -> TurnCorrection | None:
        """Analyze a user turn for corrections.

        On success with corrections: creates TurnCorrection and CorrectionItem
        rows, updates the turn's correction_status to 'has_corrections'.

        On success with no errors: updates the turn's correction_status
        to 'clean' and returns None.

        Args:
            turn_id: The turn to analyze.
            user_id: The user who submitted the turn.
            user_text: The transcribed user text.
            correction_language: ISO 639-1 code for explanation language.

        Returns:
            The TurnCorrection ORM object if corrections were found,
            or None if the text is clean.
        """
        logger.info(
            "correction_analyze_start",
            turn_id=str(turn_id),
            text_length=len(user_text),
            language=correction_language,
        )

        language_name = _LANGUAGE_NAMES.get(correction_language, correction_language)
        system_content = _build_correction_system_prompt(
            correction_language_name=language_name,
            user_text=user_text,
        )

        messages = [ChatMessage(role="system", content=system_content)]
        analysis = await self._llm.structured(
            messages,
            response_model=CorrectionAnalysis,
            options=ChatOptions(temperature=0.3, max_tokens=1024),
        )

        # Fetch the turn to update its correction_status
        turn = await self._session.get(Turn, turn_id)
        if turn is None:
            logger.error("correction_turn_not_found", turn_id=str(turn_id))
            return None

        if not analysis.has_errors or not analysis.items:
            turn.correction_status = "clean"
            await self._session.flush()
            logger.info("correction_clean", turn_id=str(turn_id))
            return None

        # Persist TurnCorrection
        turn_correction = TurnCorrection(
            turn_id=turn_id,
            corrected_text=analysis.corrected_text,
            explanation=analysis.explanation,
        )
        self._session.add(turn_correction)
        await self._session.flush()

        # Persist CorrectionItems
        for item in analysis.items:
            correction_item = CorrectionItem(
                turn_correction_id=turn_correction.id,
                user_id=user_id,
                original=item.original,
                corrected=item.corrected,
                original_sentence=item.original_sentence,
                corrected_sentence=item.corrected_sentence,
                type=item.type,
                explanation=item.explanation,
            )
            self._session.add(correction_item)

        turn.correction_status = "has_corrections"
        await self._session.flush()

        logger.info(
            "correction_analyze_done",
            turn_id=str(turn_id),
            correction_count=len(analysis.items),
        )
        return turn_correction
