# inventory_input_test.py — reference guide

Single-file pygame tool for probing mouse-input behavior. Originally built
to investigate click/drag accuracy when gyro-driven cursors were involved;
expected to be repurposed across investigations. This doc is the map so a
fresh Claude session can modify the tool without re-reading the whole file.

## Run
```
python tools/inventory_input_test.py
```
Requires `pygame`. No CLI args. Optionally ESC to quit, R to reset, S to
save log, ↑/↓ to scroll the event log.

## Window layout
All dimensions derive from constants at the top of the file
(`CELL, COLS, ROWS, PAD, LOG_W, STATUS_H, LOG_TOP_H`). Edit those to
reshape; everything else follows.

```
┌──────────────────────────┬──────────────┐
│                          │  EVENT LOG   │  LOG_TOP_H tall
│      INVENTORY GRID      │  (draw_log)  │
│      (INV_W × INV_H)     ├──────────────┤
│    (draw_inventory)      │CLICK SUMMARY │  SUMMARY_H tall
│                          │(draw_summary)│
├──────────────────────────┴──────────────┤
│       STATUS BAR  (draw_status)         │  STATUS_H tall
└─────────────────────────────────────────┘
```

## Core data structures
| Dataclass        | Feeds panel        | Life cycle |
|------------------|--------------------|------------|
| `Item`           | INVENTORY GRID     | Built once at startup; mutated by drags |
| `LogEntry`       | INPUT EVENT LOG    | Appended on LMB_DOWN / LMB_UP / POST_CLICK |
| `SummaryEntry`   | CLICK SUMMARY      | Stashed as `_pending` on LMB_DOWN; finalized + appended on LMB_UP |
| `ClickMarker`    | Inventory overlay  | Appended on LMB_DOWN; fades after `MARKER_TTL` |
| `PostClickWatch` | (drift subsystem)  | Armed on LMB_DOWN; settled by `tick_post_click` |

## Event flow
```
MOUSEBUTTONDOWN → on_lmb_down
    → append LogEntry(LMB_DOWN)
    → append ClickMarker (skipped on DOUBLE_FIRE — flags existing marker instead)
    → stash self._pending = SummaryEntry(t, shift, prev_down_ms)
        (DOUBLE_FIRE: just sets _pending.double_fire = True; doesn't replace)
    → arm PostClickWatch

MOUSEMOTION → on_move
    → feed PostClickWatch (drift tracking)
    → push to trail

MOUSEBUTTONUP → on_lmb_up
    → append LogEntry(LMB_UP)
    → finalize self._pending:
        hold_ms    = up_t - pending.t   (full hold incl. any double-fire)
        prev_up_ms = up_t - prior up_t  (between this UP and previous UP)
        shift_held = pending.shift_held AND shift_at_up
      → append to self.summary, clear _pending
    → SPURIOUS_UP (no DOWN seen): _pending is None → no row added
    → complete any active drag

every frame → tick_post_click
    → once pw_ms elapsed, append LogEntry(POST_CLICK)
    → update last_marker.drift_px
```

## Panel → draw function map
| Panel             | Draw fn         | Data source |
|-------------------|-----------------|-------------|
| Inventory overlay | `draw_inventory`| `self.items, self.markers, self.trail, self.dragged` |
| INPUT EVENT LOG   | `draw_log`      | `self.log` |
| CLICK SUMMARY     | `draw_summary`  | `self.summary` |
| STATUS BAR        | `draw_status`   | live state (`lmb_held`, `last_move_t`, `pw_ms`, `dw_px`, etc.) |

## Palette (`C` dict at top of file)
Single source of truth for colors. Add a new field-specific color by adding a
key to `C` and referencing `C['your_key']` in the draw code. Do **not**
hardcode RGB tuples inside draw functions.

Current per-column colors in CLICK SUMMARY:
- `lmb_dn_iv` — Δdown interval (cyan)
- `lmb_up_iv` — Δup interval (violet)
- `hold`      — hold duration (gold)
- `item_hl`   — shift-held marker (yellow)
- `dim`       — timestamps, `—` placeholders, shift-not-held marker
- `warn`      — double-fire marker

## Runtime threshold controls
Buttons in the status bar drive two instance attributes:
- `self.pw_ms`  — `POST-CLICK WINDOW`, bound to `btn_pw_minus/plus`
- `self.dw_px`  — `DRIFT WARN`,        bound to `btn_dw_minus/plus`

Adding a new threshold button: declare a `self.btn_xyz_±` rect pair in
`__init__`, lay them out in `draw_status` row 3, handle clicks in the
`MOUSEBUTTONDOWN` branch of `run()` **before** the fallback `on_lmb_down`.

## Gotchas
- `self.lmb_down_t` is set on the **first** DOWN of a cycle and not re-written
  on a subsequent DOUBLE_FIRE — so `hold_ms = up_t - lmb_down_t` reflects the
  full hold duration, and the live status-bar hold display does too. Capture
  the prior `lmb_down_t` / `lmb_up_t` before overwriting if you need deltas.
- `POST_CLICK_WINDOW` and `DRIFT_PIXEL_WARN` are *defaults*; runtime values
  live in `self.pw_ms` / `self.dw_px`. Always read the instance attributes in
  handlers, not the module constants.
- `last_summary` is `None` until the first click cycle **completes** (UP, not
  DOWN) — always null-check.
- `SPURIOUS_UP` (LMB_UP with no prior DOWN) produces a `LogEntry` but **no**
  `SummaryEntry` — `self._pending` is `None` so the finalize block is skipped.
- Rows in `self.summary` only ever appear after a complete DOWN→UP cycle.
  While a click is being held, the in-flight cycle lives in `self._pending`
  and is **not** rendered in the CLICK SUMMARY panel. Live hold-time feedback
  comes from the status bar (`draw_status` row 2), not the summary.
- DOUBLE_FIRE flags `self._pending.double_fire = True` but does not start a
  new cycle — the same pending entry is finalized when UP eventually arrives.
- The drift subsystem (`PostClickWatch` / `tick_post_click`) still exists and
  feeds `ClickMarker.drift_px` + POST_CLICK log entries, but it no longer
  touches `SummaryEntry` (decoupled on 2026-04-21). If you re-wire drift into
  the summary, mirror the `on_lmb_up → _pending` finalize pattern.

## Recipes

### Change CLICK SUMMARY columns
1. Edit fields on `SummaryEntry` (remove obsolete, add `Optional[float] = None`).
2. Populate them in `on_lmb_down` (at-press data) and `on_lmb_up` (at-release data).
3. Rewrite the row-render loop in `draw_summary`; each field gets its own
   `font_sm.render(..., C['color'])` blit at a fixed `col_x` offset.
4. Update the column-header string to match.

### Add a new tracked event type
1. Add a new `kind` string value to `LogEntry`.
2. Add a branch in `draw_log` for the color + prefix.
3. Record from wherever the event is observed (keydown handler, new watcher, etc.).

### Add a new panel
1. Reserve vertical space by reducing `LOG_TOP_H` or `SUMMARY_H`, or widen the window.
2. Add a `draw_newpanel` method following `draw_summary`'s structure.
3. Call it from `run()` between the existing draw calls.
4. If the panel needs state, add a `deque`/list to `App.__init__` and clear it in `_reset`.

### Adjust font sizes
- `font_sm` — 11pt, log/summary rows
- `font_md` — 13pt, column + section headers
- `font_lg` — 14pt bold, status bar values

All set once in `__init__`.

## Invariants
- `self.summary` and `self.log` are chronological oldest → newest. Both draw
  functions iterate `reversed(...)` so newest appears at the **bottom** of
  its panel.
- `self.hold_durations` and `self.lmb_event_times` are rolling windows used
  only by the status bar's rolling averages.
- `_reset()` must clear every `deque` / list / timestamp; extend it whenever
  you add new state.
