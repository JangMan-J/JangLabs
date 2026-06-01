# Strategy Reference

Use this file when strategy selection is non-obvious or the run needs more than one phase.

## `checkpointed_convergence`

Default for medium bugs and features.

1. Workers diagnose independently.
2. Arbiter compares diagnoses and extracts validated facts.
3. Arbiter sends a concise convergence update.
4. Workers implement partitioned work, or one implementer owns the patch while others review.
5. Arbiter validates, resynchronizes if needed, and synthesizes the final result.

Use when there are multiple plausible explanations but the final result is likely one coherent patch.

## `primary_with_reviewers`

Safest default for tightly coupled code.

1. One implementer owns all edits.
2. Reviewers investigate, test, or critique independently.
3. Arbiter validates reviewer findings.
4. Implementer revises.
5. Arbiter runs final validation and synthesis.

Use when parallel edits would collide or obscure responsibility.

## `test_first_competition`

Best for failing tests, compile errors, regressions, and behavior bugs.

1. One worker finds or writes a useful failing test/repro.
2. Arbiter validates the test target.
3. Implementer(s) fix against the accepted test.
4. Arbiter chooses by correctness, minimality, and validation.

Do not accept a test just because a worker is confident. Run it or inspect it.

## `debate_then_execute`

Best for architecture, API design, migrations, or unclear direction.

1. Workers propose independent plans.
2. Arbiter compares tradeoffs and risks.
3. Optional critique round.
4. Arbiter selects or synthesizes a plan.
5. Selected worker(s) implement.
6. Remaining workers review.

Keep debate bounded. The output must be a decision, not a transcript.

## `red_team_validation`

Best for security, permissions, data loss, concurrency, filesystem-sensitive changes, or high-risk correctness work.

1. Implementer creates a candidate.
2. Red-team/reviewer workers search for failures and missing cases.
3. Arbiter validates findings.
4. Implementer revises.
5. Repeat while risk remains and budget allows.

The red team should attack assumptions, not style.

## `parallel_best_of_n`

Use only when isolation is real.

1. Workers receive the same objective.
2. Workers solve independently in separate worktrees or non-overlapping file sets.
3. Arbiter compares diffs, validation, maintainability, and drift.
4. Arbiter selects the best candidate or synthesizes final work.

Without worktree or file isolation, switch to `primary_with_reviewers`.

## `tree_search`

Use only for high-budget complex tasks with meaningfully different solution branches.

1. Workers explore distinct approaches.
2. Arbiter checkpoints each branch.
3. Weak branches are retired.
4. Strong branches are refined or forked.
5. Final candidate receives cross-review.
6. Arbiter synthesizes the result.

Tree search is expensive. Use it when exploration is more valuable than fast convergence.
