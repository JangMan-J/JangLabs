#!/usr/bin/env python3
"""Suggest a Convergent Arbiter strategy from an objective string."""

from __future__ import annotations

import argparse
import json
import re


RULES = [
    (
        "red_team_validation",
        [
            r"\bsecurity\b",
            r"\bauth\b",
            r"\bpermission",
            r"\bconcurren",
            r"\brace\b",
            r"\bdata loss\b",
            r"\bfilesystem\b",
            r"\bdelete\b",
            r"\bdestructive\b",
        ],
        "risk-sensitive objective",
    ),
    (
        "test_first_competition",
        [
            r"\bfailing test",
            r"\bregression\b",
            r"\bcompile\b",
            r"\bbuild fail",
            r"\berror\b",
            r"\brepro\b",
            r"\bbug\b",
        ],
        "bug, failure, or repro language",
    ),
    (
        "debate_then_execute",
        [
            r"\barchitecture\b",
            r"\bdesign\b",
            r"\bmigration\b",
            r"\bapi\b",
            r"\bapproach\b",
            r"\bplan\b",
        ],
        "design or planning language",
    ),
    (
        "primary_with_reviewers",
        [
            r"\brefactor\b",
            r"\blarge\b",
            r"\bshared\b",
            r"\bcoupled\b",
            r"\bminimal patch\b",
        ],
        "likely shared or controlled edit",
    ),
]


def suggest(objective: str) -> dict:
    text = objective.lower()
    for strategy, patterns, reason in RULES:
        if any(re.search(pattern, text) for pattern in patterns):
            return {
                "strategy": strategy,
                "reason": reason,
                "confidence": "medium",
            }
    return {
        "strategy": "checkpointed_convergence",
        "reason": "default for general software tasks where independent diagnosis may help",
        "confidence": "low",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objective", required=True, help="User objective to classify")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args()

    result = suggest(args.objective)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"strategy: {result['strategy']}")
        print(f"reason: {result['reason']}")
        print(f"confidence: {result['confidence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
