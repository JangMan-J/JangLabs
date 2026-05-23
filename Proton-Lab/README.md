# protondb-tuner

A Claude Code **skill** that infers a Linux/Proton configuration for a Steam game from ProtonDB's full crowd-sourced report dataset.

For a given title it produces:

- **A relevance-ranked catalog** of every configuration parameter the data ties to the game — each annotated with what it does (*how*) or why it's present when that isn't obvious (*why*, e.g. anti-cheat acceptance), plus category, the axes it moves (native-parity / visual-fidelity / performance), a parity-risk read, staleness, and hardware applicability.
- **A system-tailored, risk-weighted suggested config** in tiers — **Foundation** (maximize native parity) → **Recommended** (low-risk gains attested on the user's GPU) → **Optional** (weigh the trade) — assembled by fusing three evidence layers: GPU-vendor baseline, game-specific enrichment, and a curated semantic knowledge base.

## Data

- Source: the official [`bdefore/protondb-data`](https://github.com/bdefore/protondb-data) ODbL dump (~360k reports). The raw dump is cached outside the repo; only derived data ships here.
- `data/protondb.sqlite` — inferred per-game + per-GPU-vendor statistics (frequency, recency-weighted prevalence, enrichment lift, runs-rate / fault associations, hardware buckets).
- `data/annotations.json` — the semantic layer: per-parameter meaning, *how*/*why* intent, effect axes, parity-risk prior, obsolescence, hardware scope.

Per-report verdict is **binary** (did it run), not a graded tier — so all rankings are correlational, recency-windowed, and risk-aware. Output is a *highest-likelihood starting point*, never a guarantee.

## Layout

```
SKILL.md                 # skill entrypoint (modes: query / init / update)
scripts/
  common.py              # launchOptions tokenizer/normalizer, hardware bucketing, scoring math
  detect_system.py       # host profiler (--auto): GPU vendor(s), display, distro, kernel/ntsync, tools, Proton builds
  build_db.py            # fetch latest dump → build inferred DB
  update_game.py         # refresh one game in place
  recommend.py           # fuse DB + annotations + host profile → catalog + tiered config
  export_demo.py         # per-game JSON export
data/
  protondb.sqlite        # inferred database
  annotations.json       # semantic knowledge base
  ANNOTATIONS.md         # KB schema + caveats
docs/
  example-arc-raiders.md # worked example output
```

## Use

Lives at `~/Projects/Jangs-Lab/Proton-Lab/` (the skill itself is named `protondb-tuner`) and is installed as a personal skill at `~/.claude/skills/protondb-tuner` (symlink → this directory). In Claude Code:

```
/protondb-tuner arc raiders
/protondb-tuner 1808500 --priority fidelity
/protondb-tuner cyberpunk 2077 --compare "gamemoderun mangohud %command%"
```

Or directly:

```bash
python3 scripts/recommend.py --game "arc raiders"            # report
python3 scripts/recommend.py --db-status                     # DB freshness
python3 scripts/build_db.py                                  # full rebuild (fetches latest dump)
python3 scripts/update_game.py --appid 1808500               # refresh one game
```

Hardware profile defaults to this machine (`--gpu NVIDIA --display wayland --distro cachyos --hybrid`); override with `--gpu/--display/--distro/--hybrid` for other systems (the GPU vendor materially changes the recommendation).
