---
name: protondb-tuner
description: >-
  Infer a Linux/Proton configuration for a Steam game from ProtonDB's full
  report dataset. Produces a relevance-ranked catalog of every relevant launch
  parameter (each annotated with what it does or why it's needed) plus a
  system-tailored, risk-weighted suggested config (Foundation → Recommended →
  Optional). Use when the user asks how to run, configure, optimize, or fix a
  specific game on Linux / Proton / Steam Deck, wants launch options or a Proton
  version, or asks about a title's Linux playability / anti-cheat status.
argument-hint: "[game name or appid] [--priority parity|performance|fidelity|stability] [--compare \"<launch opts>\"]"
allowed-tools: Bash(python3 *)
---

# protondb-tuner

Turns ProtonDB's crowd-sourced reports into a per-game Linux configuration. Two outputs:

1. **Catalog (primary)** — every configuration parameter the data ties to the game, relevance-ranked (game-specificity × recency × runs-rate), each labelled *how* (what it improves) or *why* (the external constraint it satisfies — e.g. anti-cheat acceptance), with category, the axes it moves, a parity-risk read, staleness, and hardware applicability.
2. **Suggested config (secondary)** — assembled from the catalog for the user's hardware + chosen priority, in tiers: **Foundation** (maximize native parity), **Recommended** (low-risk fidelity/perf gains attested on their GPU), **Optional** (weigh the trade). It fuses three evidence layers: what's standard for the GPU vendor, what's specific to this game, and the semantic knowledge base.

Data: the official `bdefore/protondb-data` ODbL dump, pre-digested into `data/protondb.sqlite` (inferred per-game + per-vendor statistics) and `data/annotations.json` (the semantic layer). Per-report verdict is binary yes/no, so rankings are correlational, recency-windowed, and risk-aware — present them as "highest-likelihood starting point," never a guarantee.

## Inferred-DB status
!`python3 ${CLAUDE_SKILL_DIR}/scripts/recommend.py --db-status 2>/dev/null || echo "status check failed — see init below"`

## How to run

**Resolve the request, then run the recommender.** `$ARGUMENTS` holds the game (name or numeric appid) plus any flags.

- If `$ARGUMENTS` is empty: ask which game (name or Steam appid).
- If it begins with `init`: build the database (first-time setup or a full refresh) — see *Maintaining the database*.
- If it begins with `update`: refresh one game — see *Maintaining the database*.
- Otherwise treat it as a query:
  - numeric → `--appid`, else `--game "<name>"`.
  - Pass through `--priority` (default `parity`) and `--compare "<launch opts>"` / `--runtime "<proton>"` if the user gave a known config to validate.

```bash
# by name — --auto probes THIS host and shapes the output to it
python3 ${CLAUDE_SKILL_DIR}/scripts/recommend.py --auto --game "$ARGUMENTS"
# by appid, fidelity-leaning, validating an existing config
python3 ${CLAUDE_SKILL_DIR}/scripts/recommend.py --auto --appid 1808500 --priority fidelity \
  --compare "PROTON_ENABLE_NVAPI=1 mangohud %command%" --runtime proton-cachyos
```

The script prints a complete Markdown report. **Present it to the user**; you may tighten prose or lead with the Suggested-config block, but do not invent parameters that aren't in the output, and preserve the *why* lines and the anti-cheat warnings verbatim — they carry ban-risk and hardware-prerequisite caveats.

### Hardware profile — pass `--auto`
`--auto` runs `scripts/detect_system.py`, which probes the host for GPU vendor(s), display server, desktop, distro, kernel/ntsync, installed wrappers (gamemoderun/game-performance/mangohud/…), and installed Proton builds — then shapes the output to it. The GPU vendor is the big lever: on an AMD host it drops NVIDIA-only parameters (NVAPI/DLSS/…) outright and surfaces RADV/FSR ones; it also gates wrappers it can't find in PATH and names the actual Proton build to select. Run `python3 ${CLAUDE_SKILL_DIR}/scripts/detect_system.py --explain` to show the detected profile.

Explicit flags override detection: `--gpu {NVIDIA|AMD|INTEL}`, `--display {wayland|x11}`, `--distro <name>`, `--hybrid`/`--no-hybrid`. Use those (without `--auto`) when advising for a *different* machine than the one running Claude. Without `--auto` or flags, it falls back to a baked-in default profile.

### Priority presets
`parity` (default) anchors on native-parity then layers low-risk gains; `performance` and `fidelity` promote well-attested perf/visual knobs; `stability` keeps only the safest. The primary catalog is unaffected by priority — it only re-weights the suggested config.

## Maintaining the database

The shipped DB is a snapshot. The upstream dump refreshes monthly.

```bash
# Full rebuild — fetches the latest dump (~485 MB, cached outside the repo), ~minutes:
python3 ${CLAUDE_SKILL_DIR}/scripts/build_db.py
# Refresh a single game from the cached dump (fast); add --fetch to pull a newer dump first:
python3 ${CLAUDE_SKILL_DIR}/scripts/update_game.py --appid <appid>
```

Run a full rebuild if `--db-status` shows a stale dump or the user asks for current data. A per-game `update` is enough when only one title matters.

## Notes & limits
- Anti-cheat acceptance is publisher-gated and recency-sensitive; the report shows a recency-windowed playable/ban-risk flag, not a config you can force. Never recommend an anti-cheat bypass for an online title.
- Only ~14% of reports carry launch options and per-report quality is binary, so low-support params are flagged "thin evidence." Treat the output as a ranked starting point to try, not a proven optimum.
- Files: `scripts/recommend.py` (report), `scripts/detect_system.py` (host profiler, `--auto`), `scripts/build_db.py` / `scripts/update_game.py` (data), `scripts/common.py` (shared parsing), `data/protondb.sqlite`, `data/annotations.json`.
