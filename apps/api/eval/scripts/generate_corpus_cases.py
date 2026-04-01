"""Generate corpus-based test cases with gold labels annotated by Claude Opus 4.6.

Downloads the DailyDialog dataset, selects 4 conversations per domain,
and uses Claude Opus 4.6 to annotate gold labels for keyword extraction.

Usage:
    cd apps/api
    .venv/bin/python -m eval.scripts.generate_corpus_cases
    .venv/bin/python -m eval.scripts.generate_corpus_cases --validate-only
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any
import json
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import yaml

from eval.models import TestCase

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "cases" / "corpus"

_MODEL = "claude-opus-4-20250514"
# Original URL is dead; use Internet Archive mirror
_DATASET_URL = (
    "https://web.archive.org/web/20220516002703/http://yanran.li/files/ijcnlp_dailydialog.zip"
)
_API_CALL_DELAY = 1.0  # seconds between API calls

TOPIC_MAP: dict[int, str] = {
    1: "ordinary_life",
    2: "school_life",
    3: "culture_education",
    4: "attitude_emotion",
    5: "relationship",
    6: "tourism",
    7: "health",
    8: "work",
    9: "politics",
    10: "finance",
}

DOMAIN_SLUG_MAP: dict[str, str] = {
    "ordinary_life": "ordinary-life",
    "school_life": "school-life",
    "culture_education": "culture-education",
    "attitude_emotion": "attitude-emotion",
    "relationship": "relationship",
    "tourism": "tourism",
    "health": "health",
    "work": "work",
    "politics": "politics",
    "finance": "finance",
}

CONVERSATIONS_PER_DOMAIN = 4

# ---------------------------------------------------------------------------
# Dataset download and parsing
# ---------------------------------------------------------------------------


def _download_and_extract(tmp_dir: Path) -> Path:
    """Download DailyDialog zip and extract to tmp_dir. Return extracted dir."""
    zip_path = tmp_dir / "ijcnlp_dailydialog.zip"
    print("  Downloading DailyDialog from archive.org mirror...")
    # Use curl for reliable HTTPS handling (urllib has SSL issues with archive.org)
    result = subprocess.run(
        ["curl", "-L", "-o", str(zip_path), _DATASET_URL],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Download failed: {result.stderr}")
    print(f"  Downloaded {zip_path.stat().st_size / 1024:.0f} KB")

    print("  Extracting...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(tmp_dir)

    # The zip contains an ijcnlp_dailydialog/ directory with another zip inside
    inner_dir = tmp_dir / "ijcnlp_dailydialog"
    if not inner_dir.exists():
        # Try to find it
        for p in tmp_dir.iterdir():
            if p.is_dir() and p.name != "__MACOSX":
                inner_dir = p
                break

    # Check if there's a nested zip (train/validation/test structure)
    inner_zip = inner_dir / "dialogues_text.txt"
    if not inner_zip.exists():
        # May have nested zip
        for zf_path in inner_dir.glob("*.zip"):
            print(f"  Extracting inner zip: {zf_path.name}...")
            with zipfile.ZipFile(zf_path, "r") as zf:
                zf.extractall(inner_dir)

    return inner_dir


def _find_file(base_dir: Path, filename: str) -> Path:
    """Recursively find a file in base_dir."""
    for p in base_dir.rglob(filename):
        return p
    raise FileNotFoundError(f"Could not find {filename} in {base_dir}")


def _parse_dataset(
    base_dir: Path,
) -> list[tuple[list[str], int]]:
    """Parse DailyDialog dataset. Return list of (turns, topic_id)."""
    text_path = _find_file(base_dir, "dialogues_text.txt")
    topic_path = _find_file(base_dir, "dialogues_topic.txt")

    print(f"  Reading {text_path}")
    print(f"  Reading {topic_path}")

    with open(text_path, encoding="utf-8") as f:
        text_lines = f.read().strip().splitlines()

    with open(topic_path, encoding="utf-8") as f:
        topic_lines = f.read().strip().splitlines()

    if len(text_lines) != len(topic_lines):
        print(
            f"  WARNING: text lines ({len(text_lines)}) != topic lines ({len(topic_lines)})",
            file=sys.stderr,
        )

    dialogues: list[tuple[list[str], int]] = []
    for text_line, topic_line in zip(text_lines, topic_lines, strict=False):
        # Parse turns: separated by __eou__
        raw_turns = text_line.strip().split("__eou__")
        turns = [t.strip() for t in raw_turns if t.strip()]
        topic_id = int(topic_line.strip())
        if turns and 1 <= topic_id <= 10:
            dialogues.append((turns, topic_id))

    print(f"  Parsed {len(dialogues)} dialogues")
    return dialogues


# ---------------------------------------------------------------------------
# Conversation selection
# ---------------------------------------------------------------------------


def _select_conversations(
    dialogues: list[tuple[list[str], int]],
) -> dict[int, list[list[str]]]:
    """Select 4 conversations per topic. Returns {topic_id: [conversations]}."""
    # Group by topic
    by_topic: dict[int, list[list[str]]] = {i: [] for i in range(1, 11)}
    for turns, topic_id in dialogues:
        by_topic[topic_id].append(turns)

    selected: dict[int, list[list[str]]] = {}

    for topic_id in range(1, 11):
        candidates = by_topic[topic_id]
        domain = TOPIC_MAP[topic_id]

        # Filter: 4-12 turns, reasonable length
        filtered = []
        for conv in candidates:
            num_turns = len(conv)
            if num_turns < 4 or num_turns > 12:
                continue
            # Check total length is reasonable (not too short or long)
            total_chars = sum(len(t) for t in conv)
            if total_chars < 80 or total_chars > 2000:
                continue
            filtered.append(conv)

        if len(filtered) < CONVERSATIONS_PER_DOMAIN:
            print(
                f"  WARNING: Only {len(filtered)} candidates for {domain}, "
                f"need {CONVERSATIONS_PER_DOMAIN}",
                file=sys.stderr,
            )

        # Select diverse conversations by picking from different positions
        # Use stride-based selection to get diversity
        max(1, len(filtered) // (CONVERSATIONS_PER_DOMAIN + 1))
        picks: list[list[str]] = []
        seen_starts: set[str] = set()

        for conv in filtered:
            if len(picks) >= CONVERSATIONS_PER_DOMAIN:
                break
            # Skip conversations with identical first turns (dedup)
            start = conv[0][:50]
            if start in seen_starts:
                continue
            seen_starts.add(start)
            picks.append(conv)

        # If stride didn't give enough, take remaining from filtered
        if len(picks) < CONVERSATIONS_PER_DOMAIN:
            for conv in filtered:
                if len(picks) >= CONVERSATIONS_PER_DOMAIN:
                    break
                if conv not in picks:
                    picks.append(conv)

        selected[topic_id] = picks[:CONVERSATIONS_PER_DOMAIN]
        print(
            f"  Topic {topic_id} ({domain}): "
            f"{len(candidates)} total, {len(filtered)} filtered, "
            f"{len(selected[topic_id])} selected"
        )

    return selected


def _to_transcript(turns: list[str]) -> list[dict[str, str]]:
    """Convert raw turn strings to alternating user/ai transcript."""
    transcript: list[dict[str, str]] = []
    for i, text in enumerate(turns):
        role = "user" if i % 2 == 0 else "ai"
        transcript.append({"role": role, "text": text.strip()})
    return transcript


# ---------------------------------------------------------------------------
# Claude annotation
# ---------------------------------------------------------------------------

_ANNOTATION_SYSTEM_PROMPT = """\
You are annotating conversations for a keyword extraction evaluation dataset.
Given a conversation between a user and an AI in an English practice app,
determine what keywords should be extracted.

CRITICAL: Extract interests from the USER's turns ONLY.
The AI's turns provide context but must NOT be a source of extracted interests.
For example, if the AI says "I'm interested in basketball" but the user never
mentions basketball, do NOT extract "basketball".

Rules:
- categories: broad interest subjects that correspond to IAB Content Taxonomy (lowercase)
  Only extract if the USER expresses genuine interest or engagement in their own turns
  Do NOT extract: generic mentions, grammar terms, emotion words, relationship terms
- entities: proper nouns with real-world identity (lowercase)
  Must be mentioned by the USER (not just the AI) as something they care about
  Must be a person, organization, product, event, or specific place
- is_news_relevant: Would "{keyword} news" return fresh articles regularly?
  true: sports, politics, economy, tech companies, current events
  false: cooking, hobbies, daily life, education, general wellness
- Return empty lists if no genuine interests are expressed by the USER
- Be conservative: only extract clear, unambiguous interests from USER turns

Return JSON only:
{
  "categories": [{"keyword": "...", "is_news_relevant": true/false}],
  "entities": [{"keyword": "...", "is_news_relevant": true/false}],
  "notes": "Brief explanation of labeling decisions"
}"""


async def _annotate_conversation(
    transcript: list[dict[str, str]],
    case_id: str,
    client: object,
) -> dict[str, Any]:
    """Annotate a single conversation using Claude Opus 4.6."""
    import anthropic
    from anthropic.types import TextBlock

    assert isinstance(client, anthropic.AsyncAnthropic)

    # Format conversation for the prompt
    conv_text = "\n".join(f"[{t['role'].upper()}]: {t['text']}" for t in transcript)

    response = await client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=_ANNOTATION_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (f"Annotate this conversation:\n\n{conv_text}"),
            }
        ],
    )

    raw_text = ""
    for block in response.content:
        if isinstance(block, TextBlock):
            raw_text = block.text
            break

    if not raw_text:
        raise ValueError(f"No text in response for {case_id}")

    # Strip markdown code fences if present
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    text = text.strip()

    result: dict[str, Any] = json.loads(text)
    return result


def _build_yaml_data(
    case_id: str,
    domain: str,
    transcript: list[dict[str, str]],
    annotation: dict[str, Any],
) -> dict[str, Any]:
    """Build a YAML-serializable dict matching TestCase schema."""
    categories_raw = annotation.get("categories", [])
    entities_raw = annotation.get("entities", [])
    notes = annotation.get("notes", "")

    gold_labels: dict[str, list[dict[str, Any]]] = {
        "categories": [
            {
                "keyword": c["keyword"],
                "is_news_relevant": c["is_news_relevant"],
                "keyword_type": "category",
            }
            for c in categories_raw
        ],
        "entities": [
            {
                "keyword": e["keyword"],
                "is_news_relevant": e["is_news_relevant"],
                "keyword_type": "entity",
            }
            for e in entities_raw
        ],
    }

    return {
        "id": case_id,
        "source": "corpus",
        "domain": domain,
        "transcript": transcript,
        "gold_labels": gold_labels,
        "notes": notes if notes else None,
    }


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------


async def generate_all(output_dir: Path) -> list[TestCase]:
    """Download dataset, select conversations, annotate, and write YAML."""
    import anthropic

    api_key = _get_anthropic_key()
    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Step 1: Download and parse dataset
    print("Step 1: Downloading DailyDialog dataset...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        base_dir = _download_and_extract(tmp_path)
        dialogues = _parse_dataset(base_dir)

    # Step 2: Select conversations
    print("\nStep 2: Selecting conversations...")
    selected = _select_conversations(dialogues)

    # Step 3: Delete existing cp-*.yaml files
    print("\nStep 3: Cleaning existing files...")
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = list(output_dir.glob("cp-*.yaml"))
    for ef in existing:
        ef.unlink()
    print(f"  Deleted {len(existing)} existing files")

    # Step 4: Annotate and write
    print(f"\nStep 4: Annotating with {_MODEL}...")
    cases: list[TestCase] = []
    errors: list[str] = []
    total = sum(len(convs) for convs in selected.values())
    count = 0

    for topic_id in range(1, 11):
        domain = TOPIC_MAP[topic_id]
        slug = DOMAIN_SLUG_MAP[domain]
        convs = selected[topic_id]

        for idx, turns in enumerate(convs, start=1):
            case_id = f"cp-{slug}-{idx:02d}"
            count += 1
            print(f"  [{count}/{total}] Annotating {case_id}...")

            transcript = _to_transcript(turns)

            try:
                annotation = await _annotate_conversation(transcript, case_id, client)
                data = _build_yaml_data(case_id, domain, transcript, annotation)

                # Validate before writing
                case = TestCase.model_validate(data)
                cases.append(case)

                # Write YAML
                yaml_path = output_dir / f"{case_id}.yaml"
                with open(yaml_path, "w", encoding="utf-8") as f:
                    yaml.dump(
                        data,
                        f,
                        default_flow_style=False,
                        allow_unicode=True,
                        sort_keys=False,
                    )

                cat_count = len(annotation.get("categories", []))
                ent_count = len(annotation.get("entities", []))
                print(f"    OK: {len(turns)} turns, {cat_count} categories, {ent_count} entities")

            except Exception as exc:
                errors.append(f"{case_id}: {exc}")
                print(f"    FAILED: {exc}")

            # Rate limit delay
            if count < total:
                time.sleep(_API_CALL_DELAY)

    if errors:
        print(f"\n{len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)

    return cases


def _get_anthropic_key() -> str:
    """Load Anthropic API key from environment."""
    import os

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        # Try loading from .env
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip("\"'")
                    break
    if not key:
        print("ERROR: ANTHROPIC_API_KEY not found in environment or .env", file=sys.stderr)
        sys.exit(1)
    return key


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_corpus_cases(data_dir: Path | None = None) -> list[TestCase]:
    """Load and validate all DailyDialog test case YAML files."""
    target_dir = data_dir or CORPUS_DIR
    yaml_files = sorted(target_dir.glob("cp-*.yaml"))

    if not yaml_files:
        print(f"ERROR: No cp-*.yaml files found in {target_dir}", file=sys.stderr)
        sys.exit(1)

    expected_count = len(TOPIC_MAP) * CONVERSATIONS_PER_DOMAIN
    if len(yaml_files) != expected_count:
        print(
            f"WARNING: Expected {expected_count} files, found {len(yaml_files)}",
            file=sys.stderr,
        )

    cases: list[TestCase] = []
    errors: list[str] = []

    for yaml_path in yaml_files:
        try:
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            case = TestCase.model_validate(data)
            cases.append(case)
        except Exception as exc:
            errors.append(f"{yaml_path.name}: {exc}")

    if errors:
        print("Validation errors:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    return cases


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Generate or validate DailyDialog test cases using Claude Opus 4.6.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing YAML files, do not regenerate.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=CORPUS_DIR,
        help=f"Output directory (default: {CORPUS_DIR})",
    )
    args = parser.parse_args()

    if args.validate_only:
        cases = validate_corpus_cases(args.output_dir)
        print(f"Validated {len(cases)} DailyDialog test cases successfully.")
        return

    print(f"Generating DailyDialog test cases with {_MODEL}...")
    cases = asyncio.run(generate_all(args.output_dir))
    print(f"\nGenerated {len(cases)} / {len(TOPIC_MAP) * CONVERSATIONS_PER_DOMAIN} test cases.")

    # Validate the generated files
    print("\nValidating generated files...")
    validated = validate_corpus_cases(args.output_dir)
    print(f"Validated {len(validated)} DailyDialog test cases successfully.")


if __name__ == "__main__":
    main()
