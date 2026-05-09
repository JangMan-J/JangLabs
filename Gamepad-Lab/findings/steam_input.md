# Steam Input — non-obvious findings

Facts learned across sessions that a fresh Claude wouldn't know from
training or public documentation. Additions welcome — keep each section
brief and focused on one claim.

---

## "Smooth Fine Movements" is a 1€ filter

The binary toggle labelled "Smooth Fine Movements" in the post-2023 UI
and "1€ Filter" in the Oct 2023 gyro-overhaul release notes are the
same feature: an implementation of the 1€ filter (Casiez, Roussel,
Vogel — CHI 2012). Exposed as on/off only — Valve picked internal
`f_cmin` and `β` parameters; no knobs are user-tunable.

Reference: https://steamdeckhq.com/news/steam-deck-client-10-25-23-gyro-overhaul/

Implication for diagnosis: pure 1€ decays cleanly at rest by design.
If you see "wiggle-on-stop" with SFM on, the ringing is almost
certainly from the 1€ output feeding into `movement_threshold`'s
quantizer downstream, not from the filter itself.

## Gyro → mouse bypasses the OS pointer pipeline

Steam Input's gyro-to-mouse output does NOT go through Windows'
standard mouse processing. EPP ("Enhance Pointer Precision") and the
system-wide mouse-speed slider have no effect on gyro cursor motion.

Back-calculating pixel motion from Steam's `DP360 × sens` settings
yields literal ground-truth cursor output (1 count = 1 pixel for gyro
deltas), not an approximation.

## End-to-end rate bottleneck stack

"1000 Hz gyro" marketing refers to IMU chip internals. The actual
sample rate reaching the game is capped by the smallest link:

```
IMU chip (1000 Hz spec, typically 125–250 Hz actual in firmware)
  → HID report rate (1 kHz wired, 125–250 Hz on 2.4 GHz / BT)
  → SDL sensor dispatch (driver-specific; Switch driver ≈ 100 Hz clustered)
  → Steam Input internal processing (~250–500 Hz fixed)
  → Steam Input virtual mouse output (~500 Hz cap)
  → Windows mouse coalescing (~500 Hz effective)
  → Game input sampling (frame-rate bound, 60–240 Hz)
```

Most "high-spec" gyro advertising numbers are upstream of at least
three of these bottlenecks.

## Filter state persists across gyro toggles

Toggling gyro off and back on within a session does NOT reset Steam's
smoothing / 1€ / running-average state. Residual filter tails
accumulate over session time. No confirmed in-session flush mechanism.

Candidates worth testing: switching action sets and back, toggling a
gyro setting and reverting, controller disconnect/reconnect.

This is the root of the "Ouija Effect": cursor continues briefly along
its last trajectory after physical motion stops. Persists even with
clean calibration, yaw-only mode, and auto-calibration disabled.
Definitively a Steam software pipeline artifact — not hardware or bus
timing.

## Auto-calibration is broken

The UI toggle "Auto-Calibrate Gyro Drift when Stationary" does NOT
actually disable auto-calibration. Verified via Steam debug console
(`steam://open/console`, CVar `gyro_drift_calibration_debug 1`): auto-
cal fires regardless of toggle state once the calibration page has
been opened this session, and continues running after the calibration
window is closed.

### VDF workaround

After running calibration, fully exit Steam, then edit the per-serial
gyro VDF:

```
[Steam install]\config\[serial]_gyro.vdf
```

Zero the two tolerance fields; leave drift-per-sample untouched:

```
"gyro_data"
{
    "gyro_drift_per_sample_x"                    "..."
    "gyro_drift_per_sample_y"                    "..."
    "gyro_drift_per_sample_z"                    "..."
    "gyro_stationary_noise_tolerance"            "0"
    "accelerometer_stationary_noise_tolerance"   "0"
}
```

Relaunch Steam. Do NOT open the calibration page in-session — it
overwrites the zeroed tolerances and re-enables auto-cal.

## Action Layers override gyro all-or-nothing

Action Layers override ENTIRE input configurations, not individual
properties. If a layer touches gyro at all — even to change trigger
dampening (which counts as a gyro setting) — it REPLACES the base
layer's gyro config entirely, including 3DOF-to-2D mode and
gyro_enable mode-shifts.

Implications:
- A layer that wants to modify one gyro property must re-specify every
  other gyro property you want retained.
- "Disable gyro in this layer" is the typical freeze/unfreeze
  mechanism — add a layer with gyro bindings inactive, remove it to
  restore.

## Roll-axis noise at low speeds

With 3DOF-to-2D in Player Space (dynamic yaw/roll blend), low-speed
cursor motion is dominated by whichever axis is momentarily noisier.
Roll on commodity IMUs has different noise characteristics than yaw,
so micro pitch changes shift the blend ratio and produce directionless
wriggle.

Switching to **Yaw-only** 3DOF mode substantially reduces this.

## VDF file behavior

### Layer id drift

Binding references (`add_layer N`, `remove_layer N`, `hold_layer N`)
do NOT stay synchronized with preset `id` fields when layers are
added or deleted in the configurator. After UI edits, stale refs
point at wrong or nonexistent layers. Must be renumbered before or
during any programmatic cleanup.

### In-memory state overrides the file

Steam regenerates layer ids and scaffolding groups from in-memory
state whenever the configurator opens. External file edits only
"stick" under this sequence:

1. Fully exit Steam (the entire client, not just the configurator).
2. Swap the edited file in.
3. Relaunch Steam.
4. Do NOT open the configurator for the edited controller this
   session.

If the configurator is opened after the swap, Steam re-serializes
from memory and overwrites the clean file.

### Cleanup rules

- Orphan groups: groups not reachable from any live preset's
  `group_source_bindings` are safe to strip.
- Deep-clean targets: empty `name ""` / `description ""` inside
  groups, empty `disabled_activators {}` blocks, non-English
  localization strings.
- Deep-clean preserves: all live groups, preset structure, every
  functional binding.

## Sensitivity / Dots Per 360 semantics

- Higher DP360 = MORE counts per 360° = MORE sensitive. Counter-
  intuitive if you think of it as analogous to mouse DPI; intuitive
  if you read it as "counts per revolution." Doubling DP360 doubles
  effective sensitivity at the same sens multiplier.
- DP360 and 3DOF mode must stay consistent across action sets and
  layers in a layout — they define the physical-to-virtual base
  mapping. Only the sens MULTIPLIER should vary between layers.
- MEMS gyros deliver continuous angular velocity at ~0.06 °/s per
  LSB. That is far finer than any DP360 setting interacts with.
  There is no chip-side "resolution" to match.
- Anchor DP360 to `screen_width × desired_wrist_range`. Example:
  1920 px, 180° wrist rotation to cross → 3840 DP360.
- `precision_speed` slider value is literal °/s (not a percentage or
  divisor). Max 15 °/s. On a clean pipeline, setting it to max and
  disabling the other three smoothing / deadzone / threshold options
  often yields the cleanest menu cursor (verified at 6680 DP360 × 2.5×
  sens on an 8BitDo Ultimate 2 Wireless).

## Setting semantics (VDF-level)

- `repeat_rate` is a no-op unless `hold_repeats = 1` is also set.
- `edge_binding_radius` + `edge_binding_invert = 1` fires when stick
  deflection is BELOW the radius (inner ring), not above. Useful for
  "hold while near-centered" patterns.
- `always_on_action` inside a group's switches block = persistent
  held action while that layer/group is active (fires on activate,
  releases on deactivate).

### Activator delay model (verified 2026-04-21 via `tools/inventory_input_test.py`)

For Regular Press (and Start Press) activators, the synthesized
output edges are:

```
DOWN fires at  press_time   + delay_start
UP   fires at  max(release_time + delay_end,  DOWN_time + ~1 tick)
```

- Both delays are independent edge-shifters from the corresponding
  physical edge. Neither is "duration-based"; both are "schedule a
  future event from the matching physical event."
- Synthesized hold width = `max(physical_hold + delay_end − delay_start, ~1 tick)`.
  When the math goes negative (`delay_start > physical_hold + delay_end`),
  Steam Input clamps so UP fires at least one tick after DOWN — a
  minimum-width pulse always emits, never a dropped click.
- **`delay_start` is pure latency, NOT a tap filter.** A 50 ms tap
  through a 750 ms `delay_start` still fires a click 750 ms later.
  Anyone wanting "ignore short taps" must use Long Press's
  `long_press_time` instead — that's the only knob that gates
  engagement on continued holding.
- Useful patterns from this model:
  - latency-with-preserved-tap-width: `delay_start = delay_end = N`
  - minimum-width press regardless of tap: `delay_start = 0`,
    `delay_end = N` → synthesized width is always ≥ N (good for
    games that drop sub-frame presses)

### Activator state across layer re-evaluation (verified 2026-04-21)

When the layer stack changes while a binding is held, Steam Input
re-evaluates activators on held inputs. Behavior splits by activator
type:

- **Regular Press** and **Start Press**: re-fire on re-evaluation.
  Each layer add/remove issues a fresh engagement edge → fresh DOWN
  scheduled, plus an UP for the previously-engaged firing.
- **Long Press** (including `long_press_time = 0`): does NOT re-fire.
  The `ENGAGED` state survives re-evaluation; only physical release
  ends it. Long Press behaves more like an input *latch* than an
  edge-driven activator.

**Consequence — the self-toggling-binding trap.** Any binding whose
activator set both adds/removes a layer AND has another action
intended to stay held (LMB, etc.) will enter a self-perpetuating cycle
on every layer toggle. The cycle is invisible while the held action
has zero `delay_start` (the UP and DOWN coalesce on one tick into a
continuous hold). Adding any `delay_start` to the held action exposes
the cycle as visible turbo at period = `remove_layer.delay_start`,
gap = `held_action.delay_start`.

**Rule of thumb:** for any binding that participates in layer
transitions, default ALL its activators to Long Press 0 ms. This is
not a workaround; it is the only activator type that doesn't
participate in the re-evaluation feedback loop.

## Layout patterns worth knowing

### Grab action layer (rapid menu loot)

- Base LS has an inverted outer-ring edge: `edge_binding_radius = 32000`,
  `edge_binding_invert = 1`. Fires on outer-ring deflection →
  `hold_layer <Grab>`.
- Grab layer has an outer-ring edge on LS: LMB turbo via
  `delay_start = 125`, `hold_repeats = 1`, `repeat_rate = 250`.
- Grab layer has `always_on_action` → LEFT_SHIFT (bulk grab modifier
  in most games).

Effect: deflecting the stick into its outer ring engages a grab mode
that fires LMB repeatedly while LEFT_SHIFT is held — sweep-loot
pattern without needing button combos.

## User's verified Arc Raiders tuning

- Controller: 8BitDo Ultimate 2 Wireless, 2.4 GHz dongle, DInput mode
- Screen: 3840 × 2160
- DP360: 6680, sens: 2.5×
- 3DOF mode: yaw-only (Player Space dropped due to roll noise)
- Gyro mode: "Gyro to Mouse" (newer beta; legacy "As Mouse" is gone)
- `precision_speed`: 15 °/s (max)
- `smooth_fine_movements` / 1€ filter: OFF
- `movement_threshold`: OFF
- `gyro_speed_deadzone`: OFF
