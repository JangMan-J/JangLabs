# vdf — Steam Input VDF tooling and translation knowledge

Preserved-and-active material for converting Steam Input layouts (VDF format) into JoyShockMapper (JSM) configs. The work here was done against the user's tuned Arc Raiders v13 profile but the **translation principles and tooling are reusable** for any Steam-Input-to-JSM port. This directory exists because the user intends to retrace and reapply this work in a future project — it is not historical.

## Contents

```
vdf/
├── README.md              (this file)
├── vdf_clean.py           (Steam Input VDF parser + cleaner)
├── test_vdf_clean.py      (unittest harness — 28 tests, stdlib only)
├── translation_audit.md   (the load-bearing reference: row-by-row VDF→JSM mapping with technical/fidelity grades)
└── reference/
    ├── jangman's jyro_v13.vdf    (source-of-truth tuned profile — the audit is grounded in this file)
    └── controller_8bitdo.vdf     (controller config layer)
```

## `vdf_clean.py`

Parses a Steam Input layout VDF, computes which `group` blocks are reachable from live presets (action sets + action layers), and emits two cleaned outputs:

- **Conservative `clean.vdf`** — no-op transforms only: orphan group removal, unused `group_source_bindings` entries removed, layer-target ID renumbering (fixes the `remove_layer 5` vs preset `id=4` drift).
- **Aggressive `dedup.vdf`** — adds: `strip_empty_inputs`, `drop_dead_layer_refs`, `strip_empty_bindings`, `dedupe_groups`, `strip_shell_groups`, `strip_meta_noise`.

Stdlib only (`re`, `argparse`, `pathlib`, `hashlib`, `copy`, `unittest`). VDF parser preserves duplicate keys via a `Pairs` (list-of-tuples) representation — Steam VDFs are not strict JSON-equivalent and the duplicate-key cases matter.

```sh
python vdf_clean.py <input.vdf>                                  # dry-run analysis
python vdf_clean.py <input.vdf> -o <output.vdf>                  # conservative output
python vdf_clean.py <input.vdf> -o clean.vdf --out-aggressive dedup.vdf
```

## `test_vdf_clean.py`

28 tests in stdlib `unittest`. Three classes:

- Per-pass tests against synthetic VDF strings (`TestStripEmptyInputs`, `TestStripEmptyBindings`, `TestStripShellGroups`, `TestStripMetaNoise`, `TestDropDeadLayerRefs`, `TestDedupeGroups`).
- `TestRunPassesSynthetic` — end-to-end against synthetic VDF, no fixture dependency.
- `TestJangmanIntegration` — end-to-end against `reference/jangman's jyro_v13.vdf`. Skips if the fixture is missing.

```sh
cd vdf/ && python -m unittest test_vdf_clean -v
```

## `translation_audit.md`

The single freshest reference for the VDF→JSM translation. Row-by-row breakdown of each mechanic in the v13 profile with **two-axis grading**: technical translatability (Yes / Approx / No) and semantic fidelity (High / Medium / Low). One row per mechanic whose translation risk is distinct.

The audit is grounded in the Arc Raiders v13 profile but the **translation principles** generalize. When retracing this work, treat the audit as the conversion playbook.

### Load-bearing gotchas (read these before starting any conversion)

These are the four places where Steam Input and JSM diverge in ways that require deliberate workarounds:

1. **The 50 ms `add_layer` / `remove_layer` choreography (the "Click layer" pattern).** Steam Input's signature trick: at `t=0` add a layer that disables gyro, at `t=50ms` fire the click, at `t=150ms` remove the layer. Used to freeze the cursor during click-and-drag. **JSM has no equivalent** — there's no timed `remove_layer`. The closest approximation is a soft/full analog-trigger split: soft pull does `GYRO_OFF`, full pull fires the click. This works for `RT` but **fails for digital inputs** (face buttons, R3, stick edges). Every digital invocation of this pattern degrades — accept it or drop the freeze. See audit row L.3.
2. **Global `HOLD_PRESS_TIME`.** Steam allows per-binding `Long_Press` timing values (175 / 200 / 250 ms across the v13 profile). JSM has a **single global `HOLD_PRESS_TIME`** — pick the most common value, accept drift on the rest. See X.2.
3. **Steam Local Space yaw-roll blend.** `gyro_to_2d_conversion_style = 3` does a dynamic yaw + tilt-modulated roll blend. JSM's `GYRO_SPACE = LOCAL` reads raw axes and does **not** reproduce the blend. `gyro_roll_scale` and `gyro_mouse_sample_angle_offset` are silently dropped. Flat-held controller matches; tilted/vertical grip diverges. See G.2.
4. **Two-action-set context swap (Game vs Menu).** Steam runs both presets in one config and swaps based on game focus. JSM runs **one config at a time**; the closest analogs are separate `AutoLoad/<game>.txt` files, in-console `READ` swaps, or a held-button "Menu modeshift". None preserves Steam's automatic Steam-overlay detection. See L.1.

### Quick wins (translate cleanly)

These translate near-exactly with no fidelity loss — start with these to build confidence:

- Primary gyro mode (`gyro_to_mouse` → JSM default path)
- `gyro_speed_deadzone` → `GYRO_CUTOFF_SPEED` (identity)
- Ratchet button mask → `GYRO_OFF = <button>`
- `mode_shift` → JSM held-modeshift chord (`L3,GYRO_SENS = N` syntax)
- Sticks-to-WASD via `LEFT_STICK_MODE = NO_MOUSE` + `LUP/LDOWN/LLEFT/LRIGHT = key`
- Trigger fire/ADS (LT/RT → `ZL/ZR = mouse-button`)
- Face buttons with `Full_Press` + `Long_Press` → JSM tap (`'`) + hold (`_`) modifiers

See the ranked summary at the bottom of `translation_audit.md` for the full clean-to-compromise ordering.

## Reference VDFs

- **`jangman's jyro_v13.vdf`** — the user's tuned Arc Raiders Steam Input layout. The v13 here matters: it's the version the user "ultimately settled on" and where the audit's authoritative readings come from.
- **`controller_8bitdo.vdf`** — a controller-level config layer. Less important for translation work; included for completeness.

## When reapplying this work

1. Run the cleaner on the source VDF first to drop orphans and rename drifted layer refs — work from the cleaned tree, not the raw export.
2. Use `translation_audit.md` row-by-row as the conversion playbook. Author one mechanic at a time.
3. Treat the four load-bearing gotchas above as predictable losses — design around them, don't try to invent JSM equivalents that don't exist.
4. The audit's two-axis grading (technical × fidelity) is the right framing: a "technically possible" translation can still be high-loss; don't flatten the two axes into a single score.
