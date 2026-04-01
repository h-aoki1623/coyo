"""Generate AI-generated test cases using Claude Opus 4.6.

Creates 20 conversation test cases with gold labels for Coyo-specific
scenarios not covered by the corpus dataset. Each scenario includes intentional
niche terms and edge cases to stress-test keyword extraction.

Usage:
    cd apps/api
    .venv/bin/python -m eval.scripts.generate_cases
    .venv/bin/python -m eval.scripts.generate_cases --validate-only
"""

from __future__ import annotations

import argparse
from typing import Any
import asyncio
import json
import sys
from pathlib import Path

import yaml

from eval.models import TestCase

GENERATED_DIR = Path(__file__).resolve().parent.parent / "data" / "cases" / "generated"

_MODEL = "claude-opus-4-20250514"

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS: list[dict[str, Any]] = [
    # --- Sports (6) ---
    {
        "id": "gen-sports-01",
        "domain": "sports",
        "instruction": (
            "Create a conversation where the user excitedly discusses watching a tennis match. "
            "The user should express genuine admiration for Carlos Alcaraz — e.g., they follow "
            "his career, are impressed by his playing style, or consider themselves a fan. "
            "The user should also naturally bring up the challenge system and hawk-eye technology "
            "as part of describing the match experience, and mention grand slam tournaments. "
            "The user's genuine interest is TENNIS and Carlos Alcaraz, not the technology."
        ),
        "gold_categories": [{"keyword": "tennis", "is_news_relevant": True}],
        "gold_entities": [{"keyword": "carlos alcaraz", "is_news_relevant": True}],
        "notes": (
            "Tests that 'challenge system', 'hawk-eye', and 'video review' are NOT extracted. "
            "These are sub-elements of tennis, not standalone interests."
        ),
    },
    {
        "id": "gen-sports-02",
        "domain": "sports",
        "instruction": (
            "Create a conversation where the user talks about watching an NBA basketball game. "
            "The user should naturally mention pick-and-roll plays and fast breaks as part of "
            "describing exciting moments. "
            "The user's interest is basketball/NBA, not specific plays."
        ),
        "gold_categories": [{"keyword": "basketball", "is_news_relevant": True}],
        "gold_entities": [{"keyword": "nba", "is_news_relevant": True}],
        "notes": "Tests that 'pick and roll' and 'fast break' are NOT extracted as keywords.",
    },
    {
        "id": "gen-sports-03",
        "domain": "sports",
        "instruction": (
            "Create a conversation where the user discusses Formula 1 racing. "
            "The user should express clear support for Max Verstappen — e.g., they root for him, "
            "follow his race results, or admire his driving skills. "
            "Red Bull Racing can be mentioned naturally in context (e.g., 'Verstappen drives for "
            "Red Bull'), but the user should NOT express interest in the team itself. "
            "Use 'F1' naturally in conversation (not 'Formula 1')."
        ),
        "gold_categories": [{"keyword": "f1", "is_news_relevant": True}],
        "gold_entities": [{"keyword": "max verstappen", "is_news_relevant": True}],
        "notes": (
            "Tests IAB normalization: 'F1' or 'auto racing'. "
            "Also tests entity extraction for drivers."
        ),
    },
    {
        "id": "gen-sports-04",
        "domain": "sports",
        "instruction": (
            "Create a conversation where a British user talks about football (meaning soccer). "
            "The user should express that they regularly watch Premier League matches — e.g., "
            "they watch every weekend, have a favorite matchday routine, or discuss recent "
            "results. "
            "A specific team like Manchester United can be mentioned in passing (e.g., 'I saw the "
            "United match'), but the user should NOT express being a fan of that team or show "
            "particular interest in it. Use British terminology naturally (football, not soccer)."
        ),
        "gold_categories": [{"keyword": "soccer", "is_news_relevant": True}],
        "gold_entities": [{"keyword": "premier league", "is_news_relevant": True}],
        "notes": (
            "Tests regional variant handling: user says 'football' "
            "but the interest category is 'soccer'."
        ),
    },
    {
        "id": "gen-sports-05",
        "domain": "sports",
        "instruction": (
            "Create a conversation where the user broadly discusses "
            "enjoying watching the Olympics. "
            "They mention several different events (swimming, athletics, gymnastics) but don't "
            "focus on any single sport. Their interest is Olympics in general."
        ),
        "gold_categories": [],
        "gold_entities": [{"keyword": "olympic games", "is_news_relevant": True}],
        "notes": (
            "Tests broad category extraction when user expresses "
            "general interest across multiple sports."
        ),
    },
    {
        "id": "gen-sports-06",
        "domain": "sports",
        "instruction": (
            "Create a conversation where the user casually mentions going to the gym and doing "
            "some yoga this morning, but the conversation is more about their daily routine than "
            "a deep interest in fitness. The yoga mention is incidental."
        ),
        "gold_categories": [{"keyword": "fitness and exercise", "is_news_relevant": False}],
        "gold_entities": [],
        "notes": (
            "Tests granularity: 'yoga' should NOT be extracted as a separate category since "
            "the user's interest scope is general fitness, not yoga specifically."
        ),
    },
    {
        "id": "gen-sports-07",
        "domain": "sports",
        "instruction": (
            "Create a conversation where the user talks about watching various sports on TV."
            "They mention enjoying soccer, basketball, and tennis, but they don't"
            "express a strong preference for any single one. The user's interest is in sports"
            "in general, not a specific sport."
        ),
        "gold_categories": [{"keyword": "sports", "is_news_relevant": True}],
        "gold_entities": [],
        "notes": (
            "Tests broad category extraction when user expresses "
            "general interest across multiple sports."
        ),
    },
    # --- Tech/AI (4) ---
    {
        "id": "gen-tech-ai-01",
        "domain": "tech-ai",
        "instruction": (
            "Create a conversation where the user is excited about generative AI. They mention "
            "using ChatGPT at work and discuss OpenAI's recent developments. They use the term "
            "'AI' frequently. The user is genuinely interested in artificial intelligence."
        ),
        "gold_categories": [{"keyword": "artificial intelligence", "is_news_relevant": True}],
        "gold_entities": [{"keyword": "openai", "is_news_relevant": True}],
        "notes": "Tests IAB normalization: 'AI' should map to 'artificial intelligence'.",
    },
    {
        "id": "gen-tech-ai-02",
        "domain": "tech-ai",
        "instruction": (
            "Create a conversation where the user talks about learning Python programming and "
            "building a personal web application. They mention frameworks but the focus is on "
            "programming as a hobby. No specific companies or products are central."
        ),
        "gold_categories": [],
        "gold_entities": [{"keyword": "python", "is_news_relevant": False}],
        "notes": "Tests that programming frameworks are not extracted as entities.",
    },
    {
        "id": "gen-tech-ai-03",
        "domain": "tech-ai",
        "instruction": (
            "Create a conversation where the user works at a tech startup and discusses their "
            "work with cloud computing. They mention AWS by name and talk about scalability "
            "challenges. The conversation mixes work and personal interest in technology."
        ),
        "gold_categories": [],
        "gold_entities": [{"keyword": "aws", "is_news_relevant": True}],
        "notes": "Tests extraction of technology category and company entity from work context.",
    },
    {
        "id": "gen-tech-ai-04",
        "domain": "tech-ai",
        "instruction": (
            "Create a conversation where the user enthusiastically discusses video games. They "
            "mention playing games by Nintendo and talk about a specific game title. The user "
            "is clearly a gaming enthusiast."
        ),
        "gold_categories": [{"keyword": "video gaming", "is_news_relevant": True}],
        "gold_entities": [{"keyword": "nintendo", "is_news_relevant": True}],
        "notes": "Tests gaming category and company entity extraction.",
    },
    # --- English Learning (2) ---
    {
        "id": "gen-english-learning-01",
        "domain": "english-learning",
        "instruction": (
            "Create a conversation where the user is practicing English grammar. They discuss "
            "the subjunctive mood and the AI helps explain it. The conversation is purely about "
            "language learning mechanics — no topical interests are expressed."
        ),
        "gold_categories": [],
        "gold_entities": [],
        "notes": (
            "Tests that grammar terms ('subjunctive mood', 'past participle') are NOT extracted. "
            "English learning activities are not user interests."
        ),
    },
    {
        "id": "gen-english-learning-02",
        "domain": "english-learning",
        "instruction": (
            "Create a conversation where the user works on pronunciation. The AI helps them "
            "practice difficult sounds. The conversation focuses on language mechanics without "
            "revealing any topical interests."
        ),
        "gold_categories": [],
        "gold_entities": [],
        "notes": "Tests that pronunciation practice is not extracted as an interest.",
    },
    # --- Multi-topic (2) ---
    {
        "id": "gen-multi-topic-01",
        "domain": "multi-topic",
        "instruction": (
            "Create a conversation where the user first talks about watching a baseball game "
            "last weekend, then transitions to talking about checking their stock portfolio. "
            "Both topics should feel natural. The user expresses genuine interest in both "
            "sports and investing."
        ),
        "gold_categories": [
            {"keyword": "baseball", "is_news_relevant": True},
            {"keyword": "personal investing", "is_news_relevant": True},
        ],
        "gold_entities": [],
        "notes": "Tests multiple categories from one conversation (max 3 rule).",
    },
    {
        "id": "gen-multi-topic-02",
        "domain": "multi-topic",
        "instruction": (
            "Create a conversation where the user describes a recent trip to Tokyo. "
            "The user should convey that they travel regularly — e.g., they go abroad a few times "
            "a year or have visited many countries. They should also express that one of the "
            "things "
            "they enjoy most about traveling is trying local cuisine in each country. "
            "Tokyo is the specific destination they visited most recently."
        ),
        "gold_categories": [
            {"keyword": "travel", "is_news_relevant": False},
            {"keyword": "world cuisines", "is_news_relevant": False},
        ],
        "gold_entities": [{"keyword": "tokyo", "is_news_relevant": False}],
        "notes": "Tests multiple categories plus entity extraction from travel context.",
    },
    # --- Edge Cases (3) ---
    {
        "id": "gen-edge-case-01",
        "domain": "edge-case",
        "instruction": (
            "Create an extremely minimal conversation: the AI asks a question, the user "
            "responds with just 'Yes, I like it.' and nothing else. No interests are expressed."
        ),
        "gold_categories": [],
        "gold_entities": [],
        "notes": "Minimal conversation — no extractable keywords.",
    },
    {
        "id": "gen-edge-case-02",
        "domain": "edge-case",
        "instruction": (
            "Create a conversation that is purely a polite greeting exchange. 'Hi, how are you?' "
            "'I'm fine, thank you.' No topical content whatsoever."
        ),
        "gold_categories": [],
        "gold_entities": [],
        "notes": "No topic discussed — extraction should return empty.",
    },
    {
        "id": "gen-edge-case-03",
        "domain": "edge-case",
        "instruction": (
            "Create a conversation where the user gives only extremely brief responses: "
            "'Yes.', 'I see.', 'Sure.', 'Maybe.' The AI tries to engage but the user "
            "never elaborates. No interests can be inferred."
        ),
        "gold_categories": [],
        "gold_entities": [],
        "notes": "Extremely brief responses — no interests expressed.",
    },
    # --- Ambiguous Proper Nouns (3) ---
    {
        "id": "gen-ambiguous-01",
        "domain": "ambiguous",
        "instruction": (
            "Create a conversation where the user talks about loving Apple products, especially "
            "the MacBook and iPhone. They discuss features and their experience. 'Apple' here "
            "clearly refers to the technology company."
        ),
        "gold_categories": [],
        "gold_entities": [{"keyword": "apple inc.", "is_news_relevant": True}],
        "notes": "Tests entity disambiguation — Apple as company, not fruit.",
    },
    {
        "id": "gen-ambiguous-02",
        "domain": "ambiguous",
        "instruction": (
            "Create a conversation where the user mentions eating an apple for lunch and it was "
            "delicious. The conversation then moves to general small talk. 'Apple' here is just "
            "a fruit, not a brand. No real interests are expressed."
        ),
        "gold_categories": [],
        "gold_entities": [],
        "notes": "Tests that common noun 'apple' (fruit) is NOT extracted as an entity.",
    },
    {
        "id": "gen-ambiguous-03",
        "domain": "ambiguous",
        "instruction": (
            "Create a conversation where the user talks about their car, mentioning it's fast "
            "and they enjoy driving on weekends. They don't name a specific make/model. The "
            "interest is in driving/automotive in general."
        ),
        "gold_categories": [{"keyword": "automotive", "is_news_relevant": False}],
        "gold_entities": [],
        "notes": (
            "Tests that generic car talk extracts a category "
            "but no entity without a specific brand."
        ),
    },
]

# ---------------------------------------------------------------------------
# System prompt for Claude Opus 4.6
# ---------------------------------------------------------------------------

_GENERATION_SYSTEM_PROMPT = """\
You are generating test conversations for an AI English conversation practice app called Coyo.

Each conversation has two speakers:
- "user": An English learner (slightly informal, natural speech, occasional hesitation)
- "ai": A friendly conversation partner (natural, encouraging)

RULES:
1. Generate 4-8 turns (2-4 per speaker).
2. The conversation must feel natural — not scripted or stiff.
3. Follow the scenario instruction carefully. If it says to include niche terms \
(like "challenge system" or "pick and roll"), include them naturally in the user's speech.
4. Edge case conversations (minimal/greeting-only) can be 2-4 turns.
5. The user is practicing English, so their language should be natural but not perfectly formal.

Return ONLY a JSON array of turns, nothing else:
[
  {"role": "user", "text": "..."},
  {"role": "ai", "text": "..."},
  ...
]"""


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


async def _generate_conversation(
    scenario: dict[str, Any],
    client: object,
) -> list[dict[str, str]]:
    """Generate a single conversation transcript using Claude Opus 4.6."""
    import anthropic

    assert isinstance(client, anthropic.AsyncAnthropic)

    response = await client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=_GENERATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": str(scenario["instruction"])}],
    )

    from anthropic.types import TextBlock

    raw_text = ""
    for block in response.content:
        if isinstance(block, TextBlock):
            raw_text = block.text
            break

    if not raw_text:
        raise ValueError(f"No text in response for {scenario['id']}")

    # Strip markdown code fences if present
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    text = text.strip()

    turns: list[dict[str, str]] = json.loads(text)
    if not isinstance(turns, list) or len(turns) < 2:
        raise ValueError(f"Invalid turns for {scenario['id']}: expected list of 2+ turns")
    return turns


def _build_yaml_data(
    scenario: dict[str, Any],
    turns: list[dict[str, str]],
) -> dict[str, Any]:
    """Build a YAML-serializable dict matching TestCase schema."""
    gold_labels: dict[str, list[dict[str, Any]]] = {
        "categories": [
            {
                "keyword": c["keyword"],
                "is_news_relevant": c["is_news_relevant"],
                "keyword_type": "category",
            }
            for c in scenario.get("gold_categories", [])
        ],
        "entities": [
            {
                "keyword": e["keyword"],
                "is_news_relevant": e["is_news_relevant"],
                "keyword_type": "entity",
            }
            for e in scenario.get("gold_entities", [])
        ],
    }

    return {
        "id": scenario["id"],
        "source": "generated",
        "domain": scenario["domain"],
        "transcript": turns,
        "gold_labels": gold_labels,
        "notes": scenario.get("notes"),
    }


async def generate_all(
    output_dir: Path,
    *,
    only: list[str] | None = None,
    missing_only: bool = False,
) -> list[TestCase]:
    """Generate test cases and write to YAML files.

    Args:
        output_dir: Directory to write YAML files to.
        only: If set, only generate scenarios whose IDs are in this list.
        missing_only: If True, skip scenarios that already have a YAML file.
    """
    import anthropic

    api_key = _get_anthropic_key()
    client = anthropic.AsyncAnthropic(api_key=api_key)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine which scenarios to generate
    targets = list(SCENARIOS)
    if only:
        only_set = set(only)
        targets = [s for s in targets if str(s["id"]) in only_set]
        unknown = only_set - {str(s["id"]) for s in targets}
        if unknown:
            print(f"WARNING: Unknown scenario IDs: {', '.join(sorted(unknown))}", file=sys.stderr)
    if missing_only:
        targets = [s for s in targets if not (output_dir / f"{s['id']}.yaml").exists()]

    if not targets:
        print("  No scenarios to generate.")
        return []

    cases: list[TestCase] = []
    errors: list[str] = []

    for i, scenario in enumerate(targets):
        scenario_id = str(scenario["id"])
        print(f"  [{i + 1}/{len(targets)}] Generating {scenario_id}...")

        try:
            turns = await _generate_conversation(scenario, client)
            data = _build_yaml_data(scenario, turns)

            # Validate before writing
            case = TestCase.model_validate(data)
            cases.append(case)

            # Write YAML
            yaml_path = output_dir / f"{scenario_id}.yaml"
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            print(f"    ✓ {len(turns)} turns")

        except Exception as exc:
            errors.append(f"{scenario_id}: {exc}")
            print(f"    ✗ {exc}")

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
# Validation (for already-generated files)
# ---------------------------------------------------------------------------


def validate_generated_cases() -> list[TestCase]:
    """Load and validate all generated test case YAML files."""
    yaml_files = sorted(GENERATED_DIR.glob("*.yaml"))

    if not yaml_files:
        print(f"ERROR: No YAML files found in {GENERATED_DIR}", file=sys.stderr)
        sys.exit(1)

    expected_count = len(SCENARIOS)
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
        description="Generate or validate generated test cases using Claude Opus 4.6.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing YAML files, do not regenerate.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=GENERATED_DIR,
        help=f"Output directory (default: {GENERATED_DIR})",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="ID",
        help="Generate only these scenario IDs (e.g., --only gen-sports-01 gen-ambiguous-01)",
    )
    parser.add_argument(
        "--missing",
        action="store_true",
        help="Only generate scenarios that don't have a YAML file yet.",
    )
    args = parser.parse_args()

    if args.validate_only:
        cases = validate_generated_cases()
        print(f"Validated {len(cases)} generated test cases successfully.")
        return

    if args.only:
        print(f"Generating {len(args.only)} specified scenario(s) with {_MODEL}...")
    elif args.missing:
        print(f"Generating missing test cases with {_MODEL}...")
    else:
        print(f"Generating all {len(SCENARIOS)} test cases with {_MODEL}...")

    cases = asyncio.run(generate_all(args.output_dir, only=args.only, missing_only=args.missing))
    print(f"\nGenerated {len(cases)} test case(s).")

    # Validate the generated files
    print("\nValidating generated files...")
    validated = validate_generated_cases()
    print(f"Validated {len(validated)} generated test cases successfully.")


if __name__ == "__main__":
    main()
