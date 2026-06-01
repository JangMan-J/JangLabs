# Worker Contracts

Workers are bounded contributors. A worker can be a Claude teammate, subagent, ACP session, manual terminal session, or the current agent performing a staged pass.

## Task Packet

Every worker receives:

```text
Objective:
  ...

Role:
  diagnostician | test_engineer | implementer | reviewer | red_team | architect | specialist

Phase:
  diagnosis | plan | implementation | review | validation | synthesis

Workspace:
  repo path or worktree path

Ownership:
  files/directories this worker may edit, or "read-only"

Acceptance Criteria:
  ...

Validation Target:
  command(s), repro steps, or "infer and report"

Constraints:
  user constraints, style constraints, safety constraints

Deliverable:
  summary, test, patch, review findings, or validation result
```

## Role Prompts

### Diagnostician

Find the root cause, relevant files, repro steps, constraints, and likely validation target. Do not edit files unless explicitly assigned. Report evidence, not confidence.

### Test Engineer

Find or create the smallest useful repro/test. Explain why it fails before the fix and what passing means. Avoid broad unrelated coverage changes.

### Implementer

Own only the assigned files or worktree. Keep the patch focused on the objective. Run assigned validation and summarize diff, tests, and risks.

### Reviewer

Review the candidate for correctness, maintainability, project conventions, missing tests, and drift from objective. Prefer concrete file/line evidence.

### Red Team

Search for failures, regressions, unsafe assumptions, security issues, race conditions, and data-loss paths. Do not nitpick style unless it hides a real defect.

### Architect

Compare design options, API boundaries, migration path, reversibility, and long-term maintainability. Produce a decision-ready recommendation.

## Ownership Rules

- Implementation workers need explicit edit boundaries.
- Reviewer and diagnostician workers are read-only unless assigned otherwise.
- Competing implementations need separate worktrees or non-overlapping file ownership.
- If ownership becomes ambiguous, pause and resynchronize before editing.
