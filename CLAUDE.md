# Project: Jangs-Lab

This repo is a multi-lab workspace for AI-assisted experimentation. Each top-level `*-Lab/` directory is an independent project with its own scope, conventions, and (usually) its own per-lab `CLAUDE.md` or `README.md`.

## When working in this repo

1. **Start at the lab boundary, not the repo root.** A task is almost always inside one lab. Read that lab's README/CLAUDE.md before editing anything inside it.
2. **Don't cross-contaminate labs.** Conventions in `Gamepad-Lab/` (Python tooling, raw HID references) do not apply to `Agent-Lab/` (skill prompts), and vice versa.
3. **Resumable handoffs are sacred.** Where a lab has a `handoffs/` directory, each file is meant to let a fresh session pick up cold. Do not edit them casually.
4. **Findings are append-only knowledge.** `findings/*.md` records non-obvious facts learned across sessions. Update or add files there when discoveries would otherwise be lost.

## Repo-level conventions

- Branch for PRs: `main`.
- No build system at the repo root; each lab manages its own dependencies (often just ad-hoc Python).
- Avoid absolute-path symlinks — they break on clone. If you need to reference work in another local repo, copy the file or link by URL.
- Large binary artifacts (screenshots, HID dumps) live under each lab's `reference/`. Don't sprinkle them elsewhere.

## Labs

- `Agent-Lab/` — multi-agent coordination skills (e.g. ACP arbiter).
- `ArchLinux-Lab/` — Arch Linux install notes and rendered guides.
- `Gamepad-Lab/` — Steam Input / gyro / controller-mapping investigations and tooling.
