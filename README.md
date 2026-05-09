# Jangs-Lab

Personal workspace for AI-assisted (Claude Code) experiments, investigations, and tooling. Each subdirectory is an independent "lab" with its own focus.

## Labs

| Lab | Focus |
|-----|-------|
| [`Agent-Lab/`](./Agent-Lab) | Multi-agent coordination skills and ACP arbiter prompts. |
| [`ArchLinux-Lab/`](./ArchLinux-Lab) | Arch Linux installation notes and rendered guides. |
| [`Gamepad-Lab/`](./Gamepad-Lab) | Steam Input / gyro investigations, controller-mapping tools, and pipeline diagnostics for the 8BitDo Ultimate 2 Wireless. |

## Working with this repo

This is an agent-coding workspace — most work happens through Claude Code sessions. See [`CLAUDE.md`](./CLAUDE.md) for project-level conventions agents should follow.

Each lab is self-contained; tooling, references, and findings live alongside the work they describe. Per-lab READMEs (where present) are the authoritative entry point for that lab.

## Layout conventions

Across the labs, recurring directory names mean the same thing:

- `tools/` — runnable scripts (mostly Python).
- `findings/` — durable knowledge surfaced across sessions.
- `handoffs/` — self-contained context seeds so a fresh agent session can resume a paused investigation cold.
- `reference/` — raw user-supplied artifacts (HID dumps, VDFs, screenshots).
- `docs/` — narrative documentation.
