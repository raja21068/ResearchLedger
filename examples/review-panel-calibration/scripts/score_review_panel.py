#!/usr/bin/env python3
"""Score a review-tool's output against the review-panel-calibration fixture's known flaws.

This is a coarse, deterministic proxy grader -- not a semantic judge. It checks whether ANY of a
flaw's trigger phrases appear (case-insensitive substring match) anywhere in the review text you
give it. That means:

  - A hit is fairly reliable evidence the reviewer caught the flaw.
  - A miss is NOT reliable evidence the reviewer missed it -- the reviewer may have described the
    same problem in different words. Always read the flagged misses in the actual review text
    before concluding a tool failed a flaw.

Usage:
    python3 score_review_panel.py <path-to-review-output.md> [--flaws flaws.json]

Exit status is always 0; this prints a scorecard, it does not gate anything.
"""
import argparse
import json
import sys
from pathlib import Path


def load_flaws(flaws_path: Path) -> dict:
    with open(flaws_path, "r", encoding="utf-8") as f:
        return json.load(f)


def score(review_text: str, flaws: list[dict]) -> list[dict]:
    lowered = review_text.lower()
    results = []
    for flaw in flaws:
        hit_phrases = [p for p in flaw["trigger_phrases"] if p.lower() in lowered]
        results.append({
            "id": flaw["id"],
            "persona": flaw["persona"],
            "description": flaw["description"],
            "hit": bool(hit_phrases),
            "matched_on": hit_phrases,
        })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("review_path", type=Path, help="Path to the review tool's output (markdown or plain text)")
    parser.add_argument("--flaws", type=Path, default=Path(__file__).parent.parent / "flaws.json",
                         help="Path to flaws.json (default: sibling flaws.json in this fixture)")
    parser.add_argument("--label", type=str, default=None,
                         help="Optional label for this run (e.g. 'researchledger-panel', 'ars-reviewer') for the printed header")
    args = parser.parse_args()

    if not args.review_path.exists():
        print(f"error: review file not found: {args.review_path}", file=sys.stderr)
        return 1
    if not args.flaws.exists():
        print(f"error: flaws file not found: {args.flaws}", file=sys.stderr)
        return 1

    review_text = args.review_path.read_text(encoding="utf-8")
    data = load_flaws(args.flaws)
    results = score(review_text, data["flaws"])

    label = args.label or args.review_path.name
    hits = sum(1 for r in results if r["hit"])
    total = len(results)

    print(f"=== Calibration scorecard: {label} ===")
    print(f"Flaws caught: {hits}/{total}\n")
    for r in results:
        mark = "HIT " if r["hit"] else "MISS"
        print(f"[{mark}] {r['id']} ({r['persona']})")
        print(f"        {r['description']}")
        if r["hit"]:
            print(f"        matched on: {', '.join(r['matched_on'])}")
        print()

    print("Note: MISS means the fixture's expected phrasing wasn't found -- re-read the review")
    print("text for that flaw before concluding the tool actually missed it. This scorer is a")
    print("floor check for a single synthetic fixture (n=1), not a validated benchmark. Run the")
    print("same review text through this script for any competing tool's output to compare on")
    print("the same yardstick.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
