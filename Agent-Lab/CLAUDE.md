# Agent-Lab — agent conventions

## What lives here

A single skill prompt: `acp_arbiter.md`. It coordinates ACP-compatible coding agents on a software task. See `README.md` for purpose and runtime expectations.

## Working in this lab

- **`acp_arbiter.md` is a prompt, not code.** Don't try to run it. Edits should preserve its skill-prompt contract: top-level `# Skill: ...` heading, `## Role`, `## Purpose`, `## User Inputs` JSON shape, and the strategy/execution sections that follow.
- **Inventory file lives outside the repo.** The arbiter reads/writes `~/.local/state/agent-inventory.json` (or the path documented in the skill). Do not check this file into the repo and do not invent a stub for it inside this directory.
- **Run artifacts are ephemeral.** The arbiter writes `runs/<run-id>/` per invocation. If artifacts ever land here, they are throwaway diagnostics — do not promote them to durable knowledge without a deliberate finding doc.
- **No subdirectories yet.** The repo-root README claims `tools/`, `findings/`, `handoffs/`, `reference/` as a recurring layout. Agent-Lab does not currently use any of them; only add a subdirectory if you have content that genuinely fits one of those buckets.

## What changes go where

| Change | Where |
|--------|-------|
| New skill prompt | New `<name>.md` at this lab's root |
| Worked example invocations | New `examples/` subdir (does not exist yet) |
| Runtime/integration notes | Append to this `CLAUDE.md` |
| Conceptual writeups | New `findings/<topic>.md` (create dir if first) |
