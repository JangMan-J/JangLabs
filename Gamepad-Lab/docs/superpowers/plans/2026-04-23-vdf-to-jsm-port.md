# Cross-workspace plan: port Arc Raiders layout from Steam Input (VDF) to JSM fork

## Context

A personal Steam Input layout for Arc Raiders (8BitDo Ultimate 2 Wireless,
DInput) exists as a VDF at
`C:\Users\Entro\Claude\JangsJyro\reference\vdf\jangman's jyro_v13.vdf`, with
verified Steam Input tuning documented at
`C:\Users\Entro\Claude\JangsJyro\findings\steam_input.md`. The goal is a
functionally-similar layout that runs on the JSM fork (`branch-a-port`,
SDL3 backend, reaches the 8BitDo directly over DInput at the SDL3 layer).

Steam Input and JSM overlap substantially (gyro routing, flick stick,
tap / hold / release event modifiers, double-press, chords, modeshift) but
diverge on a few mechanics — most notably Steam's timed action-layer
`add_layer` / `remove_layer` cycle (the 50 ms-delayed remove that powers
the inventory click-and-drag gyro freeze). Translation is therefore part
mechanical and part judgment; automating the mechanical part and
surfacing the judgment calls is the whole point of this plan.

The plan produces three artifacts, strictly sequentially:

1. A translation audit (research artifact, durable knowledge).
2. Two tiered JSM configs for live testing (`safe` + `experimental`).
3. A `vdf_to_jsm.py` tool that encodes the validated mapping table with a
   structured ledger of non-translations.

## Dependency chain

**Step 1 → Step 2 → Step 3.** Strictly sequential.
Step 2 consumes Step 1's audit. Step 3 uses Step 2's hand-authored
`ArcRaiders.safe.txt` as ground truth for its regression test and cannot
start before Step 2 produces a working safe config.

## Step 1 — VDF-to-JSM translation audit

Purpose: enumerate every mechanic in the user's Arc Raiders VDF and grade
each for how confidently it can be expressed in JSM. Audit only — no JSM
config authoring in this step.

### 1a. Inventory

Parse `JangsJyro/reference/vdf/jangman's jyro_v13.vdf` using the parser in
`JangsJyro/tools/vdf_clean.py` (conservative pipeline). Emit a flat list
of every `group` / `input` / `activator` / `settings` node actually
present, with its VDF value and a `path:line` reference.

Reuse the existing parser; do not reimplement.

### 1b. Per-item translation audit

For each inventoried item, fill these columns:

| Column | Content |
|---|---|
| VDF concept + value | e.g. `group[14].mode = gyro_to_mouse`, `gyro_natural_sensitivity = 150` |
| JSM equivalent | command name + syntax, or `—` if none |
| Parameter conversion | formula (e.g. DP360 + `gyro_natural_sensitivity` → `REAL_WORLD_CALIBRATION` + `IN_GAME_SENS`) |
| Technical translatability | `Yes` / `Approx` / `No` |
| Semantic fidelity | `High` / `Medium` / `Low` + one-line *why* when below `High` |
| Claude's guess at player-importance | `High` / `Med` / `Low` — **explicitly labeled** "guess, please correct" |

Two-axis grading (technical × fidelity) is deliberate: collapsing them
into one scalar would hide exactly the compromise that matters.
Player-importance is a separate fourth column, explicitly flagged as
guess-quality, so Claude isn't silently demoting high-impact items.

### 1c. Ranking

Sort by `(technical × fidelity)` descending. Top = cleanest translations
(feed straight into `safe.txt`). Bottom = biggest compromises or hard
blockers (candidates for `experimental.txt` or the ledger).

### Step 1 artifact

`JangsJyro/findings/arc_raiders_vdf_to_jsm_audit.md` — Markdown table,
durable research-workspace finding per project convention.

### Step 1 critical reference files (read, not modify)

- `JangsJyro/reference/vdf/jangman's jyro_v13.vdf` — source VDF
- `JangsJyro/findings/steam_input.md` — Steam Input semantics + verified
  Arc Raiders tuning (§"User's verified Arc Raiders tuning")
- `JangsJyro/handoffs/arc_raiders_inventory_drag.md` — click-and-drag
  layer architecture (for the crown-jewel mechanic)
- `JangsJyro/tools/vdf_clean.py` — reuse the `parse_vdf` entry point
- `JangsJyro-JSM/JoyShockMapper/include/JoyShockMapper.h` — JSM button /
  stick / trigger / gyro enums
- `JangsJyro-JSM/JoyShockMapper/src/main.cpp` — JSM command registry
- `JangsJyro-JSM/JoyShockMapper/src/Mapping.cpp` — binding parse regex +
  event-modifier semantics

## Step 2 — Two tiered JSM configs (safe + experimental)

Purpose: deliver a playable safe base and a second tier that adds the
medium / low-confidence mechanics, so live testing can bisect failures.

### 2a. Verify `INCLUDE` semantics

Before authoring the tiers, confirm by reading
`JoyShockMapper/src/main.cpp` (and, if needed, loading a minimal test
config at the running JSM console) that:
- `INCLUDE "file.txt"` cascades settings as expected, and
- later files can override earlier settings where needed.

If semantics differ from assumption, fall back to duplication instead of
composition. Decision recorded in the handoff note (2d).

### 2b. Author `ArcRaiders.safe.txt`

Contents: every audit row with **technical = Yes AND fidelity = High**,
plus best-effort bindings for any game-critical input whose only viable
translation is lower-confidence. Best-effort stubs carry an inline
comment: `# approx — superseded in experimental`.

Rule: the safe base must be *playable* (every required input has a
binding), not merely *provably correct*. A config in which the character
can't reload is untestable.

Seed from the existing scaffold at
`JangsJyro/tools/jsm_sdl3_config.txt` — already wired with verified
gyro settings:
- `GYRO_SENS = 2`
- `GYRO_CUTOFF_RECOVERY = 0`
- `GYRO_SMOOTH_THRESHOLD = 0`
- `HOME = ^GYRO_OFF`
- `MOUSE_X_FROM_GYRO_AXIS = Y` (yaw → mouse X)
- `MOUSE_Y_FROM_GYRO_AXIS = X` (pitch → mouse Y)

Header comment lists the three required fields:
- What it covers
- What it deliberately omits (and why)
- What to test live

### 2c. Author `ArcRaiders.experimental.txt`

First line: `INCLUDE "ArcRaiders.safe.txt"`.

Then: the medium- and low-confidence items from the audit. Specifically:
- `Long_Press` activators → JSM event modifier `'` (tap) / `_` (hold), with
  a note about the global `HOLD_PRESS_TIME` vs Steam's per-binding
  `long_press_time`.
- `Double_Press` → JSM `BTN,BTN` syntax.
- Superseded best-effort stubs from the safe base (re-bind with the
  better, riskier approximation).
- Inventory click-and-drag gyro freeze (the crown-jewel mechanic):
  chord-style modeshift approximation. Proposed shape — holding ZR at
  soft-pull modeshifts to a "ZR held" profile with gyro suppressed, then
  full-pull fires LMB. Document the known timing gap vs Steam's
  50 ms-delayed `remove_layer` in the header comment.

Same three-field header comment as `safe.txt`.

### 2d. In-flight handoff note

`JangsJyro-JSM/handoffs/arc_raiders_config_port.md`:
- Brief context (2-3 sentences).
- Pointer to the Step 1 audit.
- `INCLUDE` semantics decision from 2a.
- Test-results log — filled in during live testing.

### Step 2 artifacts (locations)

Both config files live in the JSM fork workspace, excluded from git via
`.git/info/exclude` (personal configs, not upstream material):
- `JangsJyro-JSM/configs/ArcRaiders.safe.txt`
- `JangsJyro-JSM/configs/ArcRaiders.experimental.txt`

Handoff note is also workspace-local (already excluded by the existing
`handoffs/` rule):
- `JangsJyro-JSM/handoffs/arc_raiders_config_port.md`

### Step 2 critical reference files

- `JangsJyro-JSM/JoyShockMapper/README.md` — config syntax reference
- `JangsJyro/tools/jsm_sdl3_config.txt` — scaffold to extend
- `JangsJyro/findings/arc_raiders_vdf_to_jsm_audit.md` — Step 1 output

## Step 3 — `vdf_to_jsm.py` translator tool

Purpose: encode the mappings validated in Step 2 into an automated tool,
plus a structured ledger of mechanics that require user judgment. New
tool — not an extension of `vdf_clean.py` — because the purposes differ
(clean for Steam round-trip vs. translate to JSM) and a single tool
serving both would muddy the concerns.

### 3a. Extract validated mappings into a registry

Convert Step 2's hand-authored rules into a structured registry (Python
dict at module top, or a sibling YAML). Each entry shape:

```python
{
  "vdf_pattern": {...},      # selector matching VDF nodes
  "jsm_template": "...",     # with {placeholder} interpolation
  "param_conversion": fn,    # callable: vdf_value -> jsm_value
}
```

The registry is the tool's knowledge base and the one thing that
actually encodes Step 2's lessons.

### 3b. Tool scaffolding

Create `JangsJyro/tools/vdf_to_jsm.py`. Import the VDF parser from
`vdf_clean.py` — do not duplicate it, do not extend `vdf_clean.py`
itself. Walk the parsed VDF, match each node against the registry, emit
JSM lines for matches.

CLI shape (proposal):
```
python tools/vdf_to_jsm.py <input.vdf> \
    -o <out.safe.txt> \
    --ledger <out.ledger.md> \
    [--unresolved <out.unresolved.txt>]
```

### 3c. Ledger emission (two structured categories)

- **Hard blockers.** Steam feature with no JSM equivalent at any
  confidence (radial menus, per-binding haptics, multi-binding fallback
  chains). Tool logs `skipped` in `ArcRaiders.ledger.md` with VDF
  `path:line`. Nothing emitted in `.safe.txt`.
- **Soft gaps.** Steam feature has multiple possible JSM approximations;
  correct choice depends on user preference. Tool emits a commented
  placeholder `# NEEDS DECISION: <option A> / <option B>` in
  `ArcRaiders.unresolved.txt` and logs the gap in the ledger. User
  fills the file in and `INCLUDE`s it on top of `.safe.txt`.

### 3d. Regression test

Run the tool on `jangman's jyro_v13.vdf`. Diff the generated
`.safe.txt` against the hand-authored
`JangsJyro-JSM/configs/ArcRaiders.safe.txt`. Close every diff by either
fixing the tool or adding a ledger entry. Zero-diff is the pass bar.

This regression test exists for free because the ordering (audit →
hand-craft → tool) provides a human-verified ground truth before the
tool is built.

### 3e. Second-VDF smoke test

Run on `JangsJyro/reference/vdf/controller_8bitdo.vdf` (the Steam 8BitDo
template). Confirm:
- The tool does not crash.
- The ledger is non-empty and correctly classifies the template's
  unfamiliar mechanics as blockers or soft gaps.

This catches Arc-Raiders-specific assumptions that leaked into the
registry.

### Scope discipline

Registry seeded from *exactly* what Step 2 validated. Ledger seeded from
*exactly* what Step 2 revealed. Do not generalize for hypothetical
future VDFs in this step — tool grows naturally when real ones arrive.

### Step 3 artifacts

- `JangsJyro/tools/vdf_to_jsm.py`
- `JangsJyro/tools/test_vdf_to_jsm.py` (matching the style of the
  existing `test_vdf_clean.py`)
- Tool outputs land in a caller-specified directory; regression
  comparison uses the hand-authored safe base from Step 2.

### Step 3 critical reference files

- `JangsJyro/tools/vdf_clean.py` — parser to import (`parse_vdf`)
- `JangsJyro/tools/test_vdf_clean.py` — test style to mirror
- `JangsJyro-JSM/configs/ArcRaiders.safe.txt` — regression ground truth

## Verification plan (end-to-end)

**Step 1 — audit completeness**
- File exists at `JangsJyro/findings/arc_raiders_vdf_to_jsm_audit.md`.
- Row count matches the group count produced by running
  `vdf_clean.py` on `jyro_v13.vdf` in conservative mode (cross-check).
- Every row has all six columns populated; importance column explicitly
  marked as guess-quality.

**Step 2 — live-hardware config validation (8BitDo Ultimate 2 Wireless,
SDL3 backend)**
- With JSM running, `READ configs\ArcRaiders.safe.txt` at the JSM
  console parses with no error output.
- Launch Arc Raiders. Exercise: movement, aim (gyro response at expected
  sensitivity), shoot, reload, menu navigation, inventory click. All
  function, even if inventory click-and-drag is imperfect in the safe
  tier.
- Switch to `READ configs\ArcRaiders.experimental.txt`. Retest the same
  inputs, focusing on whether the chord-modeshift approximation of the
  click-layer freeze is acceptable (no drift during drag, no cursor
  jumps on release).

**Step 3 — tool behavior**
- Running
  `python tools/vdf_to_jsm.py "reference/vdf/jangman's jyro_v13.vdf" -o /tmp/arc_safe.txt --ledger /tmp/arc.ledger.md`
  produces output identical to
  `configs/ArcRaiders.safe.txt` (or every diff is explained by a
  ledger entry).
- `arc.ledger.md` is non-empty and classifies each entry as a hard
  blocker or soft gap with a VDF `path:line` reference.
- Running the tool on `controller_8bitdo.vdf` does not crash.

## Out of scope / explicit non-goals

- Upstreaming the configs to Electronicks/JoyShockMapper. These are
  personal and gitignored.
- Generalizing the translator beyond jyro_v13-flavoured Arc Raiders
  VDFs. Tool grows when fed real new inputs, not speculatively.
- Building a GUI for the translator.
- Replacing or deprecating `vdf_clean.py`; it remains the canonical
  Steam-round-trip tool, and only its parser is reused.
- Proposing JSM feature requests for Steam Input features with no JSM
  analog (radial menus, per-binding haptics, timed `remove_layer`).
  Those remain future work, logged in the ledger.
