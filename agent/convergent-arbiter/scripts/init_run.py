#!/usr/bin/env python3
"""Create a Convergent Arbiter run directory."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path


def slugify(value: str, max_len: int = 48) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return (value or "run")[:max_len].strip("-") or "run"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--strategy", default="auto")
    parser.add_argument("--autonomy", default="standard")
    parser.add_argument("--budget", default="normal")
    parser.add_argument("--root", default="runs", help="Directory that will contain run directories")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    run_id = args.run_id or f"{now.strftime('%Y%m%dT%H%M%SZ')}-{slugify(args.objective)}"
    run_dir = Path(args.root).expanduser().resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    task = {
        "runId": run_id,
        "createdAt": now.isoformat(),
        "objective": args.objective,
        "strategy": args.strategy,
        "autonomy": args.autonomy,
        "budget": args.budget,
        "status": "active",
    }
    (run_dir / "task.json").write_text(json.dumps(task, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "checkpoints.json").write_text("[]\n", encoding="utf-8")
    (run_dir / "summary.md").write_text(
        f"# Convergent Arbiter Run\n\n"
        f"- Run ID: `{run_id}`\n"
        f"- Objective: {args.objective}\n"
        f"- Strategy: `{args.strategy}`\n"
        f"- Status: active\n",
        encoding="utf-8",
    )
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
