"""Annotate test case YAML files with gold IAB category IDs.

For each test case, takes gold category keywords and matches them against
the IAB Content Taxonomy via embedding similarity. If similarity >= NORMALIZE_THRESHOLD,
the IAB ID is assigned to the keyword. Otherwise, iab_category_id is set to null.

Usage:
    cd apps/api
    .venv/bin/python -m eval.scripts.annotate_iab_ids
    .venv/bin/python -m eval.scripts.annotate_iab_ids --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import yaml

from eval.models import TestCase

_CASES_DIR = Path(__file__).resolve().parent.parent / "data" / "cases"


async def annotate_all(cases_dir: Path, *, dry_run: bool = False) -> None:
    """Annotate all YAML test cases with gold IAB category IDs."""
    from coyo.services.embedding import EmbeddingService
    from coyo.services.iab_taxonomy import get_iab_taxonomy_service

    embedding_service = EmbeddingService()
    iab_service = get_iab_taxonomy_service()

    await iab_service.ensure_embeddings(embedding_service)

    # Build case-insensitive label -> IAB category lookup for string matching
    # Also index normalized variants (& -> and) to handle notation differences
    iab_name_map: dict[str, str] = {}  # normalized lowercase name -> iab_id
    for cat in iab_service._ordered_categories:
        key = cat.name.lower()
        iab_name_map[key] = cat.id
        if " and " in key:
            iab_name_map[key.replace(" and ", " & ")] = cat.id

    yaml_files = sorted(cases_dir.rglob("*.yaml"))
    if not yaml_files:
        print(f"No YAML files found in {cases_dir}")
        return

    updated_count = 0
    skipped_count = 0

    for yaml_path in yaml_files:
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            continue

        case = TestCase.model_validate(data)
        gold_cats = case.gold_labels.categories
        if not gold_cats:
            skipped_count += 1
            continue

        # Remove legacy top-level field if present
        had_legacy = "gold_iab_category_ids" in data
        if had_legacy:
            del data["gold_iab_category_ids"]

        # Embed gold category keywords and match against IAB
        keywords = [gk.keyword for gk in gold_cats]
        embeddings = await embedding_service.embed(keywords)

        changed = had_legacy
        details: list[str] = []
        cat_entries = data["gold_labels"]["categories"]

        for i, (keyword, emb) in enumerate(
            zip(keywords, embeddings, strict=True),
        ):
            has_field = "iab_category_id" in cat_entries[i]
            old_id = cat_entries[i].get("iab_category_id")

            # Step 1: case-insensitive string match against IAB labels
            string_match_id = iab_name_map.get(keyword.lower())
            if string_match_id is not None:
                iab_cat = iab_service.get_category(string_match_id)
                iab_name = iab_cat.name if iab_cat else keyword
                new_id = string_match_id
                details.append(f"    {keyword} -> {iab_name} (id={new_id}, string match)")
            else:
                # Step 2: embedding similarity match
                match = iab_service.match(emb)
                if match.action == "normalize" and match.iab_id is not None:
                    new_id = match.iab_id
                    details.append(
                        f"    {keyword} -> {match.iab_name} "
                        f"(id={new_id}, sim={match.similarity:.3f})"
                    )
                else:
                    new_id = None
                    best_sim = match.similarity
                    details.append(f"    {keyword} -> null (best={best_sim:.3f})")

            if not has_field or old_id != new_id:
                changed = True
            cat_entries[i]["iab_category_id"] = new_id

        if not changed:
            print(f"  {case.id}: unchanged")
            for d in details:
                print(d)
            skipped_count += 1
            continue

        if dry_run:
            print(f"  {case.id}: would update")
            for d in details:
                print(d)
            updated_count += 1
            continue

        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

        print(f"  {case.id}: updated")
        for d in details:
            print(d)
        updated_count += 1

    action = "would update" if dry_run else "updated"
    print(f"\nDone: {action} {updated_count}, skipped {skipped_count}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Annotate test cases with gold IAB category IDs.",
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=_CASES_DIR,
        help=f"Test cases directory (default: {_CASES_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without writing files.",
    )
    args = parser.parse_args()

    print(f"Annotating IAB IDs for test cases in {args.cases_dir}...")
    print(f"  Mode: {'dry-run' if args.dry_run else 'write'}")
    asyncio.run(annotate_all(args.cases_dir, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
