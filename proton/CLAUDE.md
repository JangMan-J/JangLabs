# proton — agent conventions

> **Lab scope — `proton/`** · nested repo [`JangLabs-proton`](https://github.com/JangMan-J/JangLabs-proton). This file is the authority for work *inside this lab* and **overrides** the workspace root [`../CLAUDE.md`](../CLAUDE.md). Stay in this lab — don't reach into or edit sibling labs from here.

## Read first

1. [`SKILL.md`](./SKILL.md) — the skill entrypoint and invocation contract (`protondb-tuner`; modes `query` / `init` / `update`). This governs how Claude Code runs the skill.
2. [`README.md`](./README.md) — quick-start, data sources, and the file layout.
3. [`data/ANNOTATIONS.md`](./data/ANNOTATIONS.md) — the semantic knowledge-base schema. Read before touching `data/annotations.json`.

## What lives here

A Claude Code **skill** (`protondb-tuner`) that turns ProtonDB's crowd-sourced report dump into a per-game Linux/Proton configuration: a relevance-ranked **catalog** of every parameter the data ties to a title, plus a host-tailored, risk-weighted **suggested config** (Foundation → Recommended → Optional). All runtime logic is pure-stdlib Python 3 under `scripts/`; the data and curated semantic layer are under `data/`.

The skill is installed personally as `~/.claude/skills/protondb-tuner` (a symlink → this directory), so edits here are live.

## Where things go

| Change | Where |
|--------|-------|
| Skill behavior / invocation contract | `SKILL.md` (front-matter `name`/`description`/`argument-hint`/`allowed-tools`, then the run instructions) |
| Runtime logic (scoring, parsing, host probe, DB build) | `scripts/*.py` — stdlib only, no external deps; keep `common.py` the shared core |
| A parameter's meaning / intent / risk / hardware scope | `data/annotations.json`, following the schema in `data/ANNOTATIONS.md` (closed enum sets, strict validation) |
| New worked-example output | `docs/example-<game>.md` |
| Quick-start / layout / usage prose | `README.md` |

## Conventions

- **Binary verdicts, correlational output.** Per-report data is yes/no "did it run," so every ranking is correlational, recency-windowed (6-month half-life), and risk-aware. Present results as a "highest-likelihood starting point," never a guarantee.
- **Intent `how` vs `why` is load-bearing.** `how` = the benefit is self-evident from the name; `why` = it satisfies an external constraint (anti-cheat, DRM, a workaround). Preserve `why` lines and anti-cheat warnings verbatim when presenting — they carry ban-risk and hardware-prerequisite caveats.
- **Never recommend an anti-cheat bypass for online play.** Developer-enabled, Linux-accepted titles run out of the box; bypass tokens are acceptable only for offline/singleplayer.
- **The inferred DB is a build artifact.** `data/protondb.sqlite` (~58 MB) is regenerable via `scripts/build_db.py` and is git-ignored; `data/annotations.json` is the curated source-of-record and ships in-repo.
- **Enum values are closed sets.** `intent_type`, `category`, `parity_risk`, `hardware_scope`, `obsolescence_status`, `confidence`, `kind` are all defined in the top-level `enums` block of `annotations.json`; validation is strict.
- **`--auto` shapes output to the host.** GPU vendor is the big lever (drops NVIDIA-only params on AMD, etc.). Pass explicit `--gpu/--display/--distro/--hybrid` only when advising for a *different* machine than the one running Claude.

## Re-scoping entry point

A session whose cwd enters `proton/` should load `SKILL.md` first (responsibilities + invocation), then `README.md` (data layout). `data/ANNOTATIONS.md` is the deep reference for the knowledge layer. The skill runs via `python3 scripts/recommend.py …`.
