# Jangs-Lab

Personal workspace for AI-assisted (Claude Code) experiments, investigations, and tooling. Each subdirectory is an independent "lab" with its own focus.

## Labs

| Lab | Focus |
|-----|-------|
| [`Agent-Lab/`](./Agent-Lab) | Multi-agent coordination skills and ACP arbiter prompts. |
| [`ArchLinux-Lab/`](./ArchLinux-Lab) | Personal Arch Linux install guide (rendered HTML). |
| [`Gamepad-Lab/`](./Gamepad-Lab) | 8BitDo Ultimate 2 Wireless. Currently: Linux-side input-latency / gyro troubleshooting on the Arch install above. Preserved long-term direction in `vision/`: a Steam-Input-vs-JSM behavioral comparison lab. |

## Working with this repo

This is an agent-coding workspace — most work happens through Claude Code sessions. See [`CLAUDE.md`](./CLAUDE.md) for project-level conventions agents should follow.

Each lab is self-contained; tooling, references, and findings live alongside the work they describe. Per-lab READMEs (where present) are the authoritative entry point for that lab.

## Layout conventions

Across the labs, recurring directory names mean the same thing:

- `tools/` — runnable scripts (mostly Python).
- `findings/` — durable knowledge surfaced across sessions.
- `reference/` — raw user-supplied artifacts (HID dumps, logs, screenshots).
- `vision/` — preserved long-term direction docs that aren't actively executed but inform future plans (cite line anchors via the dir's `INDEX.md`).
