# JangLabs

Personal workspace for AI-assisted (Claude Code) experiments, investigations, and
tooling. It is a **monorepo of submodules**: a thin coordinator whose every top-level
directory is an independent project ("lab") living in its own git repository.

> **Workspace rule:** every top-level directory not beginning with `.` is a git
> submodule, and nothing else lives at the root. See [`CLAUDE.md`](./CLAUDE.md) and
> [`AGENTS.md`](./AGENTS.md) for the full policy and the conventions agents follow.

## Clone

```bash
git clone --recurse-submodules https://github.com/JangMan-J/JangLabs.git
# already cloned without submodules?
git submodule update --init --recursive
```

## Labs

Submodule paths are lowercase; their repos are that path PascalCased with a `JangLabs-`
prefix (`agent` → `JangLabs-Agent`).

| Lab | Repository | Focus |
|-----|------------|-------|
| [`agent/`](./agent) | [`JangLabs-Agent`](https://github.com/JangMan-J/JangLabs-Agent) | Multi-agent coordination skills (Convergent Arbiter; ACP / Agent-Teams arbiter prompts). |
| [`claude/`](./claude) | [`JangLabs-Claude`](https://github.com/JangMan-J/JangLabs-Claude) | The Claude Code harness — hooks, `CLAUDE.md` fragment, settings; installed globally via `agent-harness.py`. |
| [`jangsjedi/`](./jangsjedi) | [`JangLabs-JangsJedi`](https://github.com/JangMan-J/JangLabs-JangsJedi) | Visual orchestrator for multiple interactive Claude Code workers on a Pro/Max subscription (Rust workspace; supervisor + `agent-comms` spine, CXX-Qt UI spike). |
| [`jangsjyro/`](./jangsjyro) | [`JangLabs-JangsJyro`](https://github.com/JangMan-J/JangLabs-JangsJyro) | The JangsJyro JoyShockMapper fork (C++23; tracks `branch-a-port`). Hosts the `gamepad/` input-research lab (8BitDo / gyro / Steam-Input-vs-JSM) as a subdir. |
| [`proton/`](./proton) | [`JangLabs-Proton`](https://github.com/JangMan-J/JangLabs-Proton) | ProtonDB-driven Linux/Proton config inference (the `protondb-tuner` skill). |

## Working with this repo

Most work happens through Claude Code sessions, and almost always *inside one lab*. Each
lab is self-contained — its own README/`CLAUDE.md` is the authoritative entry point for
that lab's scope and conventions.

- **Edit a lab:** `cd <lab>/`, commit and push *inside* the lab (it's its own repo),
  then `git add <lab> && git commit` at the root to bump the pinned commit.
- **Update a lab to its latest:** `git submodule update --remote <lab>`, then bump.
- **Context re-scoping:** the `claude/` harness installs a `lab-scope` hook that
  announces which lab you're in (by working directory) and points at its entry doc.
  See *Lab scoping* in [`CLAUDE.md`](./CLAUDE.md).

## Layout conventions

Across the labs, recurring directory names mean the same thing:

- `tools/` — runnable scripts (mostly Python).
- `findings/` — durable knowledge surfaced across sessions (append-only).
- `reference/` — raw user-supplied artifacts (HID dumps, logs, screenshots).
- `runs/` — timestamped per-run evidence/diagnostics.
- `vision/` — preserved long-term direction docs (cite line anchors via the dir's `INDEX.md`).
- `handoffs/` / `HANDOFF.md` — resumable session entry points; don't edit casually.
