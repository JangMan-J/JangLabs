---
name: convergent-arbiter
description: Use Convergent Arbiter for software tasks that benefit from independent attempts or perspectives, evidence-based comparison, controlled resynchronization, validation, and final synthesis into one result. Use when the user wants an arbiter to coordinate workers, teammates, subagents, manual sessions, or harness-backed agents rather than relying on one linear implementation path.
---

# Convergent Arbiter

## Core Idea

Convergent Arbiter is an evidence-based coordination pattern for software work.

Given one objective, preserve useful independent thinking long enough to surface distinct diagnoses or solution paths, then converge deliberately through validation, comparison, resynchronization, and final synthesis.

The arbiter may coordinate Claude Agent Teams, ACP agents, ordinary subagents, manual sessions, or a single-session fallback. The execution surface is secondary. The invariant is controlled convergence from independent evidence.

## When To Use

Use this skill when the task has one or more of these properties:

- multiple plausible root causes or solution paths
- high cost of choosing the wrong fix
- useful separation between diagnosis, implementation, tests, and review
- security, permissions, concurrency, migration, or data-loss risk
- a user explicitly asks for arbitration, competing approaches, red-team review, or agent coordination

Do not use it for tiny edits where coordination overhead exceeds the value.

## Operating Contract

The user-facing input can stay small:

```json
{
  "objective": "string",
  "strategy": "auto",
  "autonomy": "standard",
  "budget": "normal"
}
```

Defaults:

- `strategy`: `auto`
- `autonomy`: `standard`
- `budget`: `normal`

## Preflight

Before creating workers or making edits:

1. Inspect the current repository state.
2. Restate the objective as acceptance criteria.
3. Infer validation commands from project context.
4. Select a strategy.
5. Choose worker roles and ownership boundaries.
6. Decide whether work needs file ownership, worktree isolation, or a single implementer with reviewers.
7. Ask one concise clarification only when missing information would materially change the run.

If the task is small or the environment cannot support multiple workers, run the same arbitration loop in a single session: independent analysis first, implementation second, review/validation last.

## Strategy Selection

Use `scripts/select_strategy.py` for a quick local suggestion when useful:

```text
python scripts/select_strategy.py --objective "<objective>"
```

Core strategies:

- `checkpointed_convergence`: default for medium bugs/features where independent diagnosis helps.
- `primary_with_reviewers`: safest for tightly coupled edits or shared files.
- `test_first_competition`: best for failing tests, regressions, compile failures, and behavior bugs.
- `debate_then_execute`: best for architecture, API design, migrations, and unclear direction.
- `red_team_validation`: best for security, permissions, filesystem-sensitive, data-loss, or concurrency risk.
- `parallel_best_of_n`: use only with real file/worktree isolation or naturally disjoint file ownership.
- `tree_search`: high-budget exploration where solution branches are meaningfully different.

Read `references/strategies.md` when strategy choice is non-obvious or when running a multi-round strategy.

## Worker Design

Workers are any bounded execution surface: teammates, subagents, ACP sessions, human/manual sessions, or the current agent acting through staged passes.

Useful roles:

- `diagnostician`: root cause, relevant files, repro steps, constraints.
- `test_engineer`: failing tests, validation targets, coverage gaps.
- `implementer`: a bounded patch or file set.
- `reviewer`: correctness, maintainability, project conventions, missing tests.
- `red_team`: failure modes, regressions, security, unsafe assumptions.
- `architect`: design options, API boundaries, migration plan.
- `specialist`: performance, accessibility, database behavior, packaging, or another domain lens.

Give each worker a task packet with objective, role, phase, repo/worktree path, owned files, acceptance criteria, validation target, constraints, and expected deliverable. Read `references/worker-contracts.md` for packet templates.

## Isolation Rule

No two implementation workers should edit the same file set at the same time unless they are in separate worktrees from the same base.

Use:

- file ownership when work partitions naturally
- one implementer plus reviewers for tightly coupled edits
- explicit worktrees for competing implementations

## Core Loop

1. Set up a run record when the task is non-trivial:

   ```text
   python scripts/init_run.py --objective "<objective>" --strategy "<strategy>"
   ```

2. Assign independent diagnosis or role-specific research.
3. Checkpoint worker findings with evidence.
4. Compare claims against files, diffs, logs, tests, and repros.
5. Share only validated facts when resynchronization would improve worker output.
6. Implement through owned files, a primary implementer, or isolated worktrees.
7. Validate candidate results.
8. Cross-review when risk or ambiguity remains.
9. Synthesize one final result.
10. Run final validation.
11. Report what won, why it won, what was validated, and what risk remains.
12. Update persistent lessons only when a lessons file exists or the user requested learning.

Read `references/evidence-and-synthesis.md` before comparing candidate patches or merging multiple contributions.

## Checkpoints

For non-trivial runs, append checkpoints using:

```text
python scripts/append_checkpoint.py <run-dir> --phase diagnosis --worker worker-1 --role diagnostician --summary "..."
```

Checkpoint only phase boundaries or material discoveries. Do not checkpoint every hunch.

Read `references/artifacts.md` for checkpoint, run artifact, resync, and final report formats.

## Resynchronization

Resynchronize workers only with validated information that should change behavior:

- confirmed root cause
- accepted repro or test
- edge case
- ownership change
- failed approach to avoid
- high-level direction
- patch fragment only when clearly useful

Preserve independence until evidence justifies convergence.

## Final Response

Lead with result and validation. Include:

- objective
- selected strategy
- workers/roles used
- changed files or final artifact path
- validation commands and results
- what each worker contributed
- why the final approach won
- remaining risks
- recommended next step, if any

## Additional References

- `references/runner-adapters.md`: how to map the arbiter to Agent Teams, ACP, subagents, manual sessions, or single-session fallback.
- `references/artifacts.md`: schemas, run directory layout, resync template, final report template.
- `references/evidence-and-synthesis.md`: comparison rules and synthesis workflow.
- `references/strategies.md`: full strategy definitions.
- `references/worker-contracts.md`: role and task packet templates.
