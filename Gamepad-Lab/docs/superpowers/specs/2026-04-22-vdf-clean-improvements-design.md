# VDF Clean — Improvements Design

**Date:** 2026-04-22
**Target tool:** `tools/vdf_clean.py`
**Test input:** `reference/vdf/jangman's jyro_v13.vdf` (5031 lines, 148 groups)

## Problem

The existing tool finds orphan groups/presets, renumbers drifted layer-id
references, and strips a small set of cosmetic junk behind `--deep`. A survey
of its output on the Jangman file found significant additional cruft it does
not remove:

- 99 empty `inputs {}` blocks
- ~30 binding-driven groups with zero real bindings ("shell groups")
- 52 duplicate groups (byte-identical ignoring `id`)
- 2 literal `empty_binding` no-op bindings
- `add_layer 4` / `remove_layer 4` bindings targeting a non-existent preset
  (tool warns but leaves them)
- `Timestamp "0"`, `major_revision "0"`, `minor_revision "0"`, `progenitor ""`
  metadata noise

## Goals

Extend the tool to emit two output files from a single invocation:

1. **`-o clean.vdf`** — conservative pass. All changes are semantic no-ops:
   the output runs identically in Steam.
2. **`--out-aggressive dedup.vdf`** — adds structural transforms (dedup, shell
   removal, metadata strip). Expected safe but not verified; user will
   round-trip through Steam to confirm.

## Non-goals

- Auditing `settings` blocks for default values (needs a defaults catalog —
  out of scope).
- New input formats, new parsers, or rewriting the VDF grammar.
- Changing the behavior of existing flags (`--deep`, `--no-renumber`, `--map`).

## CLI

```
python tools/vdf_clean.py INPUT.vdf \
    [-o clean.vdf] \
    [--out-aggressive dedup.vdf] \
    [--deep] [--no-renumber] [--map OLD=NEW]
```

Either output flag can be used alone. When `--out-aggressive` is specified,
`--deep` behaviour is implied for that file regardless of the `--deep` flag.
The conservative output still requires `--deep` to apply the existing
cosmetic pass; this preserves current behavior for the conservative path.

Dry-run (no output flag): unchanged — prints the existing report only.

## Pipeline

Shared to both outputs (applied in order):

1. `analyze()` — existing orphan/layer-ref analysis.
2. `strip_orphans()` — existing.
3. `rewrite_bindings()` — existing layer-id renumber (unless `--no-renumber`).
4. `deep_clean_cosmetic()` — existing (only if `--deep` for conservative; always
   for aggressive).
5. **NEW** `strip_empty_inputs()` — remove empty `inputs {}` blocks.
6. **NEW** `drop_dead_layer_refs()` — remove `binding` entries whose
   `add_layer|remove_layer|hold_layer` target is not a live action-layer
   preset id (after renumber).
7. **NEW** `strip_empty_bindings()` — remove `binding` entries whose value
   begins with `empty_binding`.

Aggressive-only additions (applied after the shared pipeline):

8. **NEW** `dedupe_groups()` — fold identical groups, rewrite references.
9. **NEW** `strip_shell_groups()` — remove groups that have no effective
   content under a mode-aware test.
10. **NEW** `strip_meta_noise()` — remove zero/empty top-level metadata keys.

To produce both outputs in one run, the tool parses the input once, then
does the shared pipeline on a deep copy per output (the pipeline mutates
in place). This avoids re-parsing and keeps the passes independent between
the two output streams.

## Algorithm details

### `strip_empty_inputs()` (shared)

Recursively walk the tree. For every pair `(k, v)` where `k == "inputs"` and
`v` is a `Pairs` list of length 0, delete the pair.

### `drop_dead_layer_refs()` (shared)

Compute `live_layer_ids = { preset.id for preset in presets if preset.name in action_layer_names }`.
After `rewrite_bindings()` completes, walk every `binding` and delete the
pair iff its value matches
`^controller_action (add_layer|remove_layer|hold_layer) (\d+)` and the
captured id is not in `live_layer_ids`.

Emit a counter in the report for how many bindings were dropped.

### `strip_empty_bindings()` (shared)

Walk every `binding` pair. Delete iff the value, stripped, starts with
`empty_binding`.

### `dedupe_groups()` (aggressive)

1. **Canonical hash.** For each group under `controller_mappings`, serialize
   the group's content recursively, omitting any pair with key `"id"` at the
   group's top level. Use `hashlib.md5(serialized).hexdigest()` as the hash
   key.
2. **Canonical selection.** Bucket groups by hash. For buckets with >1
   member, pick the member with the **lowest numeric id** as canonical.
3. **Remap build.** `remap = {dup_id: canonical_id for each non-canonical
   dup}`.
4. **Rewrite references.**
   - For each preset's `group_source_bindings`, rewrite every entry's key via
     `remap`. If the remapped key collides with an existing key in the same
     `group_source_bindings` block, drop the duplicate (the canonical entry
     wins).
   - Walk every `binding` value. For patterns
     `^mode_shift (\S+) (\d+)`, rewrite the group id via `remap` if matched.
5. **Delete duplicates.** Remove the non-canonical groups from
   `controller_mappings`.
6. Report: bucket count, total groups removed, total references rewritten.

### `strip_shell_groups()` (aggressive)

A group is classified **shell** iff **both**:

- Its `inputs` block has zero `binding` descendants where the binding value
  is non-empty and does not start with `empty_binding`, AND
- Its `settings` block is absent, or is a `Pairs` of length 0.

Rationale: binding-driven modes (`dpad`, `four_buttons`, `trigger`,
`switches`, `scrollwheel`) need populated `inputs`; setting-driven modes
(`gyro_to_*`, `joystick_*`, `mouse_region`, `flickstick`) have empty inputs
by design but have populated `settings`. The dual-condition test eliminates
dead shells without false-positiving on setting-driven configured modes.

Once shell ids are identified:

- Remove them from `controller_mappings`.
- Drop any `group_source_bindings` entries referencing them on any preset.
- Walk every `binding`; if it matches `^mode_shift \S+ (\d+)` and the id
  is a shell, delete the binding pair.

Report shell count and ids.

This pass runs after `dedupe_groups()`, so only canonical groups are
considered.

### `strip_meta_noise()` (aggressive)

On the `controller_mappings` top-level pair list only:

- Remove `(k, v)` where `k == "Timestamp"` and `v == "0"`.
- Remove `(k, v)` where `k == "major_revision"` and `v == "0"`.
- Remove `(k, v)` where `k == "minor_revision"` and `v == "0"`.
- Remove `(k, v)` where `k == "progenitor"` and `v == ""`.

Non-zero/non-empty values preserved. No recursion.

## Edge cases

- **Preset group_source_bindings collisions on dedup.** When remapping a
  preset's GSB, if `remap[32] = 28` and the preset already has `"28"` as a
  GSB key with a different value string, we keep the existing canonical
  entry and drop the remapped duplicate. The canonical group's own bindings
  are what run; per-preset modifier strings on the duplicate entry are
  discarded. Document this as a known behavioural delta if the aggressive
  output is loaded in Steam.
- **Dedup before shell strip.** Running dedup first simplifies shell
  detection: we only examine canonical groups.
- **Order of passes vs. counter reporting.** Each new pass returns a dict
  of counts; the aggressive report aggregates them into a new "Aggressive
  pass" section in `format_report`.
- **Both outputs requested with identical flags.** The aggressive pass
  operates on a separate deep copy; the conservative output is never
  mutated by aggressive passes. Confirmed by running the pipeline on
  independent `copy.deepcopy(root)` instances.

## Verification

- **Unit-level:** Add a small `tests/vdf_clean_test.py` using synthetic
  VDF strings that exercise each new pass in isolation (empty inputs,
  dead layer ref, empty_binding, duplicate groups, shell groups, meta
  keys). Assert pass counters and output tree shape.
- **Integration:** Run on `reference/vdf/jangman's jyro_v13.vdf`. Expect:
  - Conservative output parses successfully via `load_vdf()`.
  - Aggressive output parses successfully via `load_vdf()`.
  - Aggressive output line count < conservative output line count < input.
  - Re-running `analyze()` on the aggressive output reports 0 orphans,
    0 dead layer refs, 0 empty_binding, 0 empty inputs, 0 duplicate
    groups.
- **Steam round-trip (out of spec scope, user-driven):** User loads the
  aggressive output in Steam, inspects the layout, saves, confirms no
  regressions vs. the conservative output. Flagged as a post-ship
  validation step.

## Deferred / out of scope

- **#7 Settings default-value pruning.** Requires a per-mode defaults
  catalog extracted from Steam Input defaults. Not attempted here.
- **Other empty block types** (`disabled_buttons`, `disabled_chords`,
  etc.) — survey found zero instances in the Jangman file. Revisit if
  other VDFs show them.
- **Localization filter expansion** (`--deep` currently keeps only
  `english` — configurable). Unchanged.

## Expected line-count impact (Jangman)

| Output           | Lines | % of input |
|------------------|-------|------------|
| Input            | 5031  | 100%       |
| Current `--deep` | 4386  | 87%        |
| New `clean.vdf`  | ~4000 | ~80% (est) |
| `dedup.vdf`      | ~2500 | ~50% (est) |

The dedup estimate assumes ~50 duplicate groups at ~20 lines each
collapsing, plus ~30 shell groups at ~10 lines each. Actual numbers
reported on implementation.
