# Runner Adapters

Convergent Arbiter is runner-agnostic. Pick the execution surface that fits the task and environment.

## Claude Agent Teams

Use when the work benefits from a team lead, shared task list, direct teammate messages, and natural-language coordination.

Best for:

- diagnosis plus review
- debate then execute
- red-team validation
- partitioned features

Risks:

- token usage scales with teammates
- same-file edits need explicit ownership
- feature availability depends on Claude Code settings

## ACP Harness

Use when the work needs provider/model diversity, capability probing, explicit session lifecycle, or deterministic control.

Best for:

- comparing different coding agents
- repeated benchmark-like runs
- automated worktree setup
- inventory-driven model/agent selection

Risks:

- more implementation work
- protocol and agent capability variability
- orchestration bugs can contaminate results

## Subagents

Use when a side task would flood the main context but does not need peer-to-peer coordination.

Best for:

- isolated research
- log/file scanning
- quick independent review

Risks:

- subagents report back only to the parent
- less useful for multi-round collaboration

## Manual Sessions

Use when automation is unavailable but the arbiter structure is still useful.

Best for:

- controlled human/agent comparison
- early experiments
- one-off validation

Risks:

- more manual bookkeeping
- weaker repeatability

## Single-Session Fallback

Use when the task is small or no worker mechanism is available.

Perform staged passes:

1. independent diagnosis
2. plan
3. implementation
4. adversarial review
5. validation
6. synthesis

The fallback still follows the evidence and convergence rules.
