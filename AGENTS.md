# AGENTS.md — JangLabs

Cross-tool agent instructions for the JangLabs workspace. The canonical, fuller version
of everything here is [`CLAUDE.md`](./CLAUDE.md) — read it. This file is the short form
for agents that key on `AGENTS.md`.

## What this repo is

A **monorepo of submodules**. JangLabs is a thin coordinator; every top-level directory
is an independent project ("lab") that lives in its own git repository and is wired in
as a git submodule.

## The invariant — do not break it

**Every top-level directory not beginning with `.` is a git submodule, and nothing
else lives at the workspace root.** Only these may sit at the root:

1. Submodules (the labs). Submodule path is lowercase; its repo is that path PascalCased with a `JangLabs-` prefix (`agent` → `JangLabs-Agent`).
2. Dot-files / dot-dirs (`.git`, `.gitmodules`, `.gitignore`, `.devcontainer/`, `.claude-workspace`).
3. Root coordinator files (`CLAUDE.md`, `README.md`, `AGENTS.md`).

So: **never** create a plain directory or a stray file at the root.
New work becomes its own repo + submodule (`git submodule add`). Reference a sibling lab
by path/URL — never vendor or copy it in.

## Scope to the lab you're in

- Work happens *inside one lab*. The moment your working directory or edits enter
  `<lab>/`, **that lab's entry doc is the authority and overrides this root** (precedence
  `CLAUDE.md` → `AGENTS.md` → `README.md` → `HANDOFF.md`).
- Don't cross lab boundaries: a convention in one lab does not apply to another.
- The `synapse/` harness installs a `lab-scope` hook that auto-announces the active lab
  (by cwd) and its entry doc; it keys off the `.claude-workspace` marker at the root.

## Editing a lab (submodule workflow)

`cd <lab>/` → change → **commit & push inside the lab** (its history lives there) →
back at the root `git add <lab> && git commit` to bump the pinned SHA. Branch for PRs is
`main` (in JangLabs and each lab; `jangsjyro` tracks `branch-a-port`).

## Labs

`agent` · `synapse` · `gamepad` · `jangsjyro` · `proton` — see the table in
[`README.md`](./README.md) for repos and focus, and each lab's own `CLAUDE.md`.
