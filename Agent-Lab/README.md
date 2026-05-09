# Agent-Lab

Multi-agent coordination skills. The lab is currently a single skill prompt.

## Contents

| File | Type | What it is |
|------|------|------------|
| `acp_arbiter.md` | Skill prompt | An arbiter that coordinates multiple ACP-compatible coding agents on one objective: discovers agents, runs them in isolated worktrees, compares results with evidence, resyncs when one path becomes stronger, and synthesizes a final patch. |

## What ACP is

[ACP](https://agentclientprotocol.com/llms.txt) — Agent Client Protocol — is a control plane for launching, coordinating, and supervising coding agents. The arbiter relies on an ACP runtime to enumerate available agents/models and dispatch work.

## Runtime expectations (per `acp_arbiter.md`)

- **Inventory file:** `~/.local/state/acp-arbiter/agent-inventory.json` (Linux). Persistent learning lives here.
- **Run artifacts:** `runs/<run-id>/` directories created per invocation.
- **Input shape:** `{ "objective": "...", "arbitrationStrategy": "auto", "autonomyLevel": "standard", "budget": "normal" }`.

## How to use it

`acp_arbiter.md` is a **skill prompt**, not runnable code. It's meant to be loaded as a Claude Code skill (or equivalent harness) and invoked with the input shape above. Don't try to execute the markdown directly.

## Status

No README/CLAUDE.md before today; the skill prompt itself is the spec. There are no examples or worked outputs in-tree yet.
