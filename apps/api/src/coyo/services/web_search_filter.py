"""Filler-turn filter and citation stripping for web search gating."""

import re

FILLER_PHRASES: frozenset[str] = frozenset({
    "uh huh", "uh-huh", "mm hmm", "mm-hmm", "mhm",
    "yeah", "yep", "yup", "yes", "no", "nope",
    "okay", "ok", "sure", "right", "i see",
    "got it", "really", "wow", "nice", "cool",
    "great", "awesome", "interesting", "exactly",
    "of course", "definitely", "absolutely",
    "i know", "i agree", "me too", "same here",
})

_MAX_FILLER_WORDS = 5


def is_filler_turn(text: str) -> bool:
    """Return True if *text* is a short filler/backchannel utterance.

    A turn is classified as filler when **both** conditions hold:
    1. It contains 5 words or fewer.
    2. The normalised text matches a known filler phrase.
    """
    normalised = text.strip().lower().rstrip(".!?,")
    words = normalised.split()
    if len(words) > _MAX_FILLER_WORDS:
        return False
    return normalised in FILLER_PHRASES


# Matches markdown links: [text](url)
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]+\)")
# Matches parenthesised URLs: (https://...) or bare domain refs: (example.com)
_PAREN_URL_RE = re.compile(r"\(https?://[^)]+\)")
_PAREN_DOMAIN_RE = re.compile(r"\([a-z0-9-]+(?:\.[a-z]{2,})+\)", re.IGNORECASE)


def strip_citations(text: str) -> str:
    """Remove markdown links and parenthesised URLs from web-search responses.

    ``[label](url)`` is replaced with just ``label``.
    ``(https://…)`` is removed entirely.
    Consecutive whitespace left behind is collapsed.
    """
    # [label](url) → label
    result = _MARKDOWN_LINK_RE.sub(r"\1", text)
    # (https://...) → ""
    result = _PAREN_URL_RE.sub("", result)
    # (domain.com) → ""
    result = _PAREN_DOMAIN_RE.sub("", result)
    # Collapse runs of whitespace / blank lines
    result = re.sub(r"[ \t]+", " ", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()
