# Artifacts

Use artifacts for non-trivial runs. Keep them separate from durable lessons.

## Run Directory

Suggested layout:

```text
runs/<run-id>/
  task.json
  checkpoints.json
  summary.md
  worker-001-summary.md
  worker-002-summary.md
  worker-001.diff
  worker-002.diff
  final.diff
  validation.log
```

Use `scripts/init_run.py` to create the initial files.

## Checkpoint

Minimum checkpoint shape:

```json
{
  "checkpointId": "cp-001",
  "timestamp": "...",
  "phase": "diagnosis",
  "worker": "worker-001",
  "role": "diagnostician",
  "summary": "...",
  "evidence": [],
  "testsRun": [],
  "testResults": [],
  "validatedDiscoveries": [],
  "risks": [],
  "nextAction": "continue"
}
```

Use `scripts/append_checkpoint.py` to append structured checkpoints.

## Resync Message

```text
Checkpoint update:

Validated discovery:
- ...

Evidence:
- ...

Required adjustment:
- ...

Continue within your assigned files/worktree unless told otherwise.
Keep the patch focused on the objective.
Run validation again when ready.
```

## Final Report

```text
Result:
  success | partial | blocked

Objective:
  ...

Strategy:
  ...

Workers:
  - worker/role summary

Final output:
  branch, worktree, patch path, or changed files

Validation:
  command(s) and result(s)

Comparison:
  what each worker contributed
  which approach won and why

Key discoveries:
  ...

Remaining risks:
  ...

Next step:
  ...
```

## Lessons

Persistent lessons should be compressed patterns only:

```json
{
  "taskClass": "compile_fix",
  "strategy": "test_first_competition",
  "outcome": "success",
  "notes": [
    "Test-first found the root cause fastest.",
    "Primary-with-reviewers is safer for shared parser files."
  ]
}
```

Use `scripts/update_lessons.py` only when the user requested persistence or an existing lessons file is part of the workflow.
