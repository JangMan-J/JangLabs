#!/usr/bin/env python3
"""Append compressed lessons for Convergent Arbiter."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path


DEFAULT_PATH = "~/.local/state/convergent-arbiter/lessons.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=os.environ.get("CONVERGENT_ARBITER_LESSONS_PATH", DEFAULT_PATH))
    parser.add_argument("--task-class", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--outcome", required=True)
    parser.add_argument("--note", action="append", default=[], help="Reusable lesson note. Repeatable.")
    parser.add_argument("--worker-role", action="append", default=[], help="Useful worker role. Repeatable.")
    args = parser.parse_args()

    path = Path(args.path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise SystemExit(f"{path} must contain a JSON list")
    else:
        data = []

    data.append(
        {
            "timestamp": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "taskClass": args.task_class,
            "strategy": args.strategy,
            "outcome": args.outcome,
            "usefulWorkerRoles": args.worker_role,
            "notes": args.note,
        }
    )
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
