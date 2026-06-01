# agent

Multi-agent and multi-worker coordination experiments.

## Contents

| File | Type | What it is |
|------|------|------------|
| `convergent-arbiter/` | Skill package | A usable Convergent Arbiter skill: compact runtime instructions, progressive-disclosure references, and small scripts for strategy suggestion, run setup, checkpoints, and lessons. |
| `acp_arbiter.md` | Skill prompt | An arbiter that coordinates multiple ACP-compatible coding agents on one objective: discovers agents, runs them in isolated worktrees, compares results with evidence, resyncs when one path becomes stronger, and synthesizes a final patch. |
| `agent_team_arbiter.md` | Skill-ready prompt | An adaptation of the arbiter idea for Claude Code Agent Teams: one lead session creates role-specific teammates, uses the shared task list and direct messages for coordination, preserves independent diagnosis, enforces file/workstream ownership, and synthesizes the final result by evidence. |
| `findings/convergent-arbiter-intent.md` | Project note | Describes the intent, design bias, non-goals, and first usable shape for Convergent Arbiter. |
| `findings/convergent-arbiter-roadmap.md` | Project note | Describes planned milestones from the usable skill package toward runner-neutral core, local runner, Agent Teams adapter, ACP adapter, and evaluation harness. |

## What Convergent Arbiter is

Convergent Arbiter is an evidence-based coordination pattern for software work. Given one objective, it preserves independent diagnoses or solution attempts long enough to produce useful evidence, then deliberately converges through comparison, validation, resynchronization, and final synthesis.

The skill package in `convergent-arbiter/` is the current primary artifact. The older prompt drafts remain as source material and framework-specific variants.

## What ACP is

[ACP](https://agentclientprotocol.com/llms.txt) — Agent Client Protocol — is a control plane for launching, coordinating, and supervising coding agents. The arbiter relies on an ACP runtime to enumerate available agents/models and dispatch work.

## What Claude Agent Teams are

Claude Code Agent Teams coordinate multiple Claude Code sessions under a lead session. Teammates have separate context windows, communicate through direct messages/mailbox, and share a task list. Unlike the ACP arbiter, Agent Teams do not provide cross-provider agent discovery and do not automatically isolate teammate edits in worktrees, so the Agent Teams prompt emphasizes explicit teammate roles and file/workstream ownership.

## Runtime expectations (per `acp_arbiter.md`)

- **Inventory file:** `~/.local/state/acp-arbiter/agent-inventory.json` (Linux). Persistent learning lives here.
- **Run artifacts:** `runs/<run-id>/` directories created per invocation.
- **Input shape:** `{ "objective": "...", "arbitrationStrategy": "auto", "autonomyLevel": "standard", "budget": "normal" }`.

## Runtime expectations (per `agent_team_arbiter.md`)

- **Claude Code:** v2.1.32 or later.
- **Feature flag:** `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.
- **Coordination model:** lead session + teammates + shared task list + direct messages.
- **Isolation model:** explicit file ownership by default; manual worktrees only when independent implementation competition needs real isolation.
- **Input shape:** `{ "objective": "...", "arbitrationStrategy": "auto", "autonomyLevel": "standard", "budget": "normal" }`.

## Runtime expectations (per `convergent-arbiter/`)

- **Skill entrypoint:** `convergent-arbiter/SKILL.md`.
- **References:** `convergent-arbiter/references/`.
- **Scripts:** `convergent-arbiter/scripts/`.
- **Input shape:** `{ "objective": "...", "strategy": "auto", "autonomy": "standard", "budget": "normal" }`.
- **Default stance:** runner-agnostic. Use Agent Teams, ACP, subagents, manual sessions, or single-session fallback according to the task and environment.

## How to use it

The Markdown prompt files are **skill prompts**, not runnable code. The `convergent-arbiter/` directory is a skill package. Its scripts are runnable helpers; its Markdown files are instructions and references.

## Status

`convergent-arbiter/` is the active usable form. The prompt files remain useful source drafts. There are no worked example runs in-tree yet.
