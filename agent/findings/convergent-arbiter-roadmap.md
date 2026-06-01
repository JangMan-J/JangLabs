# Convergent Arbiter Roadmap

## Current Milestone: Usable Skill Package

Status: complete as the first usable form.

Deliverables:

- compact `SKILL.md`
- progressive-disclosure references
- scripts for strategy suggestion, run initialization, checkpoint append, and lessons update
- lab README/CLAUDE updates
- intent and roadmap documents

Completion standard:

- a user or agent can load the skill and run a non-trivial coding task with explicit strategy, worker roles, checkpoints, validation, and final synthesis
- scripts run locally without external dependencies
- docs explain the purpose and next implementation steps

Verification performed:

- `SKILL.md` validates with the skill-creator quick validator
- helper scripts compile
- strategy suggestion, run initialization, checkpoint append, and lessons append were smoke-tested under `/tmp`

## Next Milestone: Runner-Neutral Core

Goal: make the arbiter concepts concrete enough to test independently from any agent framework.

Planned pieces:

- JSON schema or typed definitions for objective, worker, task packet, checkpoint, evidence, candidate, decision, validation result, and lesson
- strategy phase definitions in machine-readable YAML or JSON
- deterministic report generator from checkpoints and validation records
- small verifier that checks run artifacts for missing required fields

Why this matters:

The project should be testable without launching live agents. If the artifact model is good, runners can be swapped without rewriting the arbitration logic.

## Next Milestone: Local Runner

Goal: support a single-session or manual-session runner that exercises the full loop without depending on Agent Teams or ACP.

Planned pieces:

- create run directory
- create task packets from selected strategy
- let the current agent execute staged roles
- capture checkpoints
- run validation command
- assemble final report

Why this matters:

This gives the project a reliable baseline and a way to dogfood the workflow immediately.

## Next Milestone: Claude Agent Teams Adapter

Goal: use Claude Code Agent Teams as an ergonomic coordination surface.

Planned pieces:

- team design templates
- teammate task packet templates
- shared-task-list conventions
- direct-message resync templates
- file ownership guidance
- optional worktree setup for competing implementations

Why this matters:

Agent Teams map well to the lead/teammate mental model and are the fastest route to real multi-worker use.

## Next Milestone: ACP Adapter

Goal: support provider/model diversity and deterministic agent session control.

Planned pieces:

- ACP discovery script
- capability probing
- model/config tuple probing
- worktree allocation
- session dispatch
- checkpoint ingestion
- inventory update

Why this matters:

ACP is the better long-term control plane for heterogeneous agents and repeatable experiments.

## Next Milestone: Evaluation Harness

Goal: determine whether arbitration improves outcomes.

Planned pieces:

- sample tasks with known acceptance criteria
- compare single-pass baseline against convergent runs
- measure validation success, patch size, regression rate, and time/token cost
- record strategy fit by task class

Why this matters:

Without evaluation, the arbiter can become elaborate ceremony. The project should prove when coordination pays for itself.

## Open Design Questions

- How much autonomy should the arbiter have before asking the user?
- What evidence format is strict enough to be useful but light enough to fill during real work?
- Should synthesis be done by the lead only, or can a dedicated synthesis worker produce the final patch?
- When should persistent lessons be trusted for strategy/model selection?
- How should conflicting valid candidates be represented when no single patch clearly dominates?
- What is the minimum viable ACP runner that proves provider diversity without overbuilding?

## Near-Term Implementation Order

1. Validate the current scripts and docs.
2. Add a verifier for run artifacts.
3. Add a worked example under `examples/`.
4. Convert strategy definitions to machine-readable files.
5. Build a local runner that executes the loop in staged passes.
6. Add Agent Teams adapter guidance or commands.
7. Build ACP discovery/probe scripts only after the core artifact model stabilizes.
