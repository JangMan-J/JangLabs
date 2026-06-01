# JangLabs

Personal workspace for AI-assisted (Claude Code) experiments, investigations, and tooling. Each subdirectory is an independent "lab" with its own focus.

## Labs

| Lab | Focus |
|-----|-------|
| [`agent/`](./agent) | Multi-agent coordination skills and ACP / Agent-Teams arbiter prompts. |
| [`claude/`](./claude) | Claude Code harness — hooks, CLAUDE.md fragment, settings; installed globally via `install.sh`. |
| [`gamepad/`](./gamepad) | 8BitDo Ultimate 2 Wireless. Linux-side input-latency / gyro troubleshooting. Preserved long-term direction in `vision/`: a Steam-Input-vs-JSM behavioral comparison lab. |
| [`jangsjyro/`](./jangsjyro) | **Git submodule** (independent repo + remote, [JangMan-J/jangsjyro](https://github.com/JangMan-J/jangsjyro)): the JangsJyro JoyShockMapper fork — JSM source for the `gamepad/` lab, pinned by commit SHA. |
| [`proton/`](./proton) | ProtonDB-driven Linux/Proton config inference (the `protondb-tuner` skill). |
| [`theme/`](./theme) | Data-first theme capture and semantic color-role mapping across KDE, Kvantum, Kitty, and Warp. |

## Working with this repo

This is an agent-coding workspace — most work happens through Claude Code sessions. See [`CLAUDE.md`](./CLAUDE.md) for project-level conventions agents should follow.

Each lab is self-contained; tooling, references, and findings live alongside the work they describe. Per-lab READMEs (where present) are the authoritative entry point for that lab.

## Layout conventions

Across the labs, recurring directory names mean the same thing:

- `tools/` — runnable scripts (mostly Python).
- `findings/` — durable knowledge surfaced across sessions.
- `reference/` — raw user-supplied artifacts (HID dumps, logs, screenshots).
- `vision/` — preserved long-term direction docs that aren't actively executed but inform future plans (cite line anchors via the dir's `INDEX.md`).
