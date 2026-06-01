#!/usr/bin/env python3
"""Append a checkpoint to a Convergent Arbiter run."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path


def parse_json_list(value: str) -> list:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise argparse.ArgumentTypeError("value must be a JSON list")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("--json-file", help="Checkpoint JSON file to append")
    parser.add_argument("--phase")
    parser.add_argument("--worker")
    parser.add_argument("--role")
    parser.add_argument("--summary")
    parser.add_argument("--next-action", default="continue")
    parser.add_argument("--evidence", default="[]", type=parse_json_list)
    parser.add_argument("--tests-run", default="[]", type=parse_json_list)
    parser.add_argument("--test-results", default="[]", type=parse_json_list)
    parser.add_argument("--validated-discoveries", default="[]", type=parse_json_list)
    parser.add_argument("--risks", default="[]", type=parse_json_list)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    checkpoints_path = run_dir / "checkpoints.json"
    checkpoints = json.loads(checkpoints_path.read_text(encoding="utf-8"))
    if not isinstance(checkpoints, list):
        raise SystemExit(f"{checkpoints_path} does not contain a JSON list")

    if args.json_file:
        checkpoint = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
        if not isinstance(checkpoint, dict):
            raise SystemExit("--json-file must contain a JSON object")
    else:
        missing = [name for name in ("phase", "worker", "role", "summary") if getattr(args, name.replace("-", "_")) is None]
        if missing:
            raise SystemExit(f"missing required fields without --json-file: {', '.join(missing)}")
        checkpoint = {
            "phase": args.phase,
            "worker": args.worker,
            "role": args.role,
            "summary": args.summary,
            "nextAction": args.next_action,
            "evidence": args.evidence,
            "testsRun": args.tests_run,
            "testResults": args.test_results,
            "validatedDiscoveries": args.validated_discoveries,
            "risks": args.risks,
        }

    checkpoint.setdefault("timestamp", dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat())
    checkpoint.setdefault("checkpointId", f"cp-{len(checkpoints) + 1:03d}")
    checkpoints.append(checkpoint)
    checkpoints_path.write_text(json.dumps(checkpoints, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(checkpoint["checkpointId"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
