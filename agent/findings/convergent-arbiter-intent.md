# Convergent Arbiter Intent

## Thesis

Convergent Arbiter is not primarily a "multi-agent" project. It is an evidence-based arbitration project for software work.

The central claim is:

> Independent attempts are valuable only when they produce evidence that can be compared, validated, and synthesized into one result.

The project should therefore optimize for controlled convergence, not parallelism for its own sake.

## Problem

Single-pass agent work often fails in predictable ways:

- it commits to a root cause too early
- it writes a plausible patch before validating the problem
- it hides uncertainty behind confident prose
- it overfits to the first path explored
- it reviews its own work too gently
- it treats tests as a closing ritual instead of a decision surface

Multiple agents can help, but only if their independence is preserved long enough to produce different evidence. Without arbitration, multiple agents can also make things worse by creating redundant diffs, same-file conflicts, noisy summaries, and unvalidated disagreement.

## Intended Shape

Convergent Arbiter should become a small kernel plus runner adapters.

The kernel owns:

- objective intake
- strategy selection
- worker roles
- task packets
- checkpoints
- evidence comparison
- resynchronization discipline
- final synthesis
- validation and reporting

Runner adapters own:

- how workers are launched
- whether workers are Claude teammates, ACP agents, subagents, manual sessions, or local staged passes
- how workspaces are isolated
- how logs and diffs are captured

The kernel should not care which agent framework executes the work. It should care whether the work produces usable evidence.

## Product Standard

The system is working when it can take an ordinary coding objective and produce:

1. a clear strategy choice
2. bounded worker assignments
3. evidence-bearing checkpoints
4. a defensible comparison
5. one final validated patch or plan
6. a report explaining what won and why

If the final answer cannot explain why the selected result beat alternatives, the arbiter did not do its job.

## Non-Goals

Convergent Arbiter should not become:

- a giant prompt that tries to describe every runtime detail
- a benchmark harness first and a useful workflow second
- a framework locked to one vendor
- a swarm manager that maximizes worker count
- a transcript summarizer that treats all worker claims equally
- an autonomous system that hides risk from the user

## Design Biases

- Prefer evidence over confidence.
- Prefer small validated patches over broad speculative rewrites.
- Preserve independence early; converge deliberately later.
- Use one implementer plus reviewers when edit collisions would be likely.
- Use worktrees only when competing implementations need real isolation.
- Keep persistent learning compressed and optional.
- Move deterministic mechanics into scripts.
- Keep the skill entrypoint short enough to be loaded often.

## First Usable Form

The first usable form is the `convergent-arbiter/` skill package:

- `SKILL.md` defines the operating loop.
- `references/` holds strategies, worker contracts, evidence rules, runner adapters, and artifact formats.
- `scripts/` provides lightweight mechanics for strategy suggestion, run setup, checkpointing, and lessons.

This is intentionally not a full launcher yet. It is the smallest structure that makes the idea operational while leaving room for richer runner adapters.
