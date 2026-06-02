# agent — conventions

> **Lab scope — `agent/`** · nested repo [`JangLabs-agent`](https://github.com/JangMan-J/JangLabs-agent). This file is the authority for work *inside this lab* and **overrides** the workspace root [`../CLAUDE.md`](../CLAUDE.md). Stay in this lab — don't reach into or edit sibling labs from here.

## What lives here

Multi-agent and multi-worker coordination experiments. `convergent-arbiter/` is the current usable skill package. `acp_arbiter.md` coordinates ACP-compatible coding agents, while `agent_team_arbiter.md` adapts the same arbitration objective to Claude Code Agent Teams. See `README.md` for purpose and runtime expectations.

## Working in this lab

- **Skill prompt Markdown is prompt text, not code.** Don't try to run standalone prompt drafts. Edits should preserve the skill-prompt contract: top-level `# Skill: ...` heading, role/purpose/input shape, and strategy/execution sections. For packaged skills, preserve valid `SKILL.md` frontmatter and progressive-disclosure references.
- **Inventory files live outside the repo.** The ACP arbiter reads/writes `~/.local/state/agent-inventory.json` (or the path documented in the skill). The Agent Teams arbiter treats persistent lessons as optional and stores them only at the documented external path. Do not check these files into the repo and do not invent stubs for them inside this directory.
- **Run artifacts are ephemeral.** The arbiters may write `runs/<run-id>/` per invocation. If artifacts ever land here, they are throwaway diagnostics; do not promote them to durable knowledge without a deliberate finding doc.
- **Subdirectories are now intentional.** `convergent-arbiter/` contains the active skill package; `findings/` contains conceptual project notes. Add more directories only when they support a concrete artifact or finding.

## What changes go where

| Change | Where |
|--------|-------|
| New skill prompt draft | New `<name>.md` at this lab's root |
| New usable skill package | New `<skill-name>/SKILL.md` with references/scripts as needed |
| Worked example invocations | New `examples/` subdir (does not exist yet) |
| Runtime/integration notes | Append to this `CLAUDE.md` |
| Conceptual writeups | New `findings/<topic>.md` (create dir if first) |
