# Arc Raiders — Steam Input Layout Context Seed

> **Purpose:** Context-efficient session starter. Paste this at the top of a new session to restore
> full technical context without re-deriving basics. Update §6 with test results and §7 after analysis.

---

## §1 — Hardware

- **Controller:** 8BitDo Ultimate 2 Wireless, 2.4GHz dongle, DInput mode (B+Home at startup)
- **VID/PID:** 0x2DC8 / 0x6012 (controller), 0x6013 (dongle alone)
- **HID polling:** 1006 Hz measured average, 0.10ms jitter stdev — definitively not a source of input issues
- **Calibration state:** Auto-calibration toggle is broken (fires regardless of toggle state). Working state:
  zero both noise tolerances in `[Steam]/config/[serial]_gyro.vdf` after calibration, don't reopen the
  calibration page this session or it will reset them. See `STEAM_INPUT_GYRO_REFERENCE.md` for VDF example.
- **Gyro mode:** "Gyro to Mouse" (newer beta mode, not legacy "As Mouse")
- **Gyro axis:** Yaw-only (Player Space mode dropped — roll noise caused directionless wriggle at low speeds)

---

## §2 — Layout Goals

Full gyro + full kb/m input replacement for Arc Raiders. **No mixed input** (no stick aiming alongside
gyro). The layout is being created from scratch using a generic gamepad template base.

**The specific mechanic under investigation:** inventory click-and-drag. Arc Raiders inventory uses
click-and-drag to move items. Gyro controls the cursor. The problem: if the cursor is still moving
when LMB_DOWN fires (gyro wasn't frozen yet), the drag either misses the item or starts from a drifted
position.

---

## §3 — Binding Architecture Under Test

**Trigger:** RT configured as a **digital trigger** (no analog threshold — soft-pull and full-pull fire
in the same Steam Input processing tick with no temporal separation).

**Base layer bindings:**
- RT soft-pull (SP) → `Add Action Layer: "Click"`  ← gyro freeze mechanism
- RT full-pull (FP) → LMB_DOWN

**"Click" action layer bindings:**
- Gyro: **DISABLED** (layer completely overrides base gyro config — this IS the freeze)
- RT FP → `Remove Action Layer: "Click"` + 50ms delay
- RT SP → `Clear Parent Action` (suppresses AddLayer re-trigger from the base layer bleeding through)

**Release:** after 50ms, RemLayer fires → base layer resumes → gyro re-enables.

**Why this architecture:** Layer override behavior in Steam Input is all-or-nothing on gyro — if the
layer touches gyro at all, it replaces the base layer's gyro config entirely. The Click layer exists
solely to freeze gyro for the duration of the click. The 50ms delay on RemLayer keeps gyro frozen
through the click and brief post-click window before cursor control returns.

---

## §4 — The Race Condition

Digital RT fires SP and FP simultaneously in the same Steam Input processing tick. This creates a race:

- **AddLayer path:** RT SP → `Add "Click" layer` → gyro disabled → cursor frozen → LMB_DOWN fires clean
- **LMB-first path:** RT FP → LMB_DOWN fires while gyro still active → cursor drifting at click time → drag fails

**The question:** is this race deterministic (AddLayer always wins, or always loses), probabilistic
(win rate varies by frame timing), or conditionally deterministic (predictable under some conditions)?

**Why the Ouija Effect matters here:** Steam's gyro filter state (1€ filter or similar) does NOT flush
on gyro toggle/layer change. Even if AddLayer wins and gyro is nominally disabled, filter decay means
brief residual mouse output may still arrive for a few ms after the layer activates. This could produce
DRIFT results even when the layer architecture is functionally correct. The distinction matters for
diagnosis: race-condition DRIFT and Ouija-bleed DRIFT look identical in raw pixel terms but have
different first_move_ms signatures (immediate vs. 5-15ms delay).

---

## §5 — Test Tool

**File:** `%USERPROFILE%\Claude\inventory_input_test.py`  
**Runtime:** Python 3.14 + `pygame-ce` (not `pygame` — no cp314 wheel; pygame-ce 2.5.7 has native cp314)

**What it measures:**
- `first_move_ms` — time in ms from LMB_DOWN to first MOUSEMOTION event in the post-click window
  - Near-zero (1–5ms): gyro was active at click time → LMB won the race
  - 10–30ms: possible Ouija bleed after a correct freeze → filter decay, not a race loss
  - No movement detected in window: cursor was frozen at click time → AddLayer won

**Summary log result codes:**
- `CLEAN` — click landed with no post-click drift exceeding threshold within window
- `DRIFT` — post-click movement exceeded DRIFT_WARN threshold (px)
- `…` — window hasn't closed yet (in-progress)
- `×2 DFIRE` — LMB_DOWN received while LMB already held (double-fire, binding issue)
- `MISS` — click landed outside any inventory cell

**Runtime-adjustable thresholds (UI buttons in status bar):**
- `POST_CLICK_WINDOW` — observation window after LMB_DOWN (default 50ms, range 10–500ms, step 5ms)
- `DRIFT_WARN` — pixel displacement threshold for DRIFT flag (default 2px, range 1–50px, step 1px)

**How to use:**
1. Launch the script — pygame window opens as a desktop window (not in terminal)
2. Have Steam running with the layout active, gyro enabled, game not required
3. Click inventory cells using RT (not mouse LMB) — the tool captures what Steam sends
4. Collect 20–50 samples across multiple sessions; note any pattern in CLEAN/DRIFT distribution
5. Key data to report: CLEAN%, DRIFT%, ×2 DFIRE count, typical first_move_ms range for DRIFT events

---

## §6 — Test Results

*[PLACEHOLDER — populate after test sessions]*

**Session date:**  
**Sample count:**  
**CLEAN:**  
**DRIFT:**  
**×2 DFIRE:**  
**MISS:**  
**first_move_ms range (DRIFT events):**  
**first_move_ms range (CLEAN events):**  
**Notes / observations:**

---

## §7 — Analysis and Next Steps

*[PLACEHOLDER — populate after §6 is filled]*

**Race condition characterization:**  
**Likely cause (race loss vs. Ouija bleed vs. binding error):**  
**Recommended architecture change (if any):**  
**Open questions:**

---

## §8 — Full Reference

Full gyro investigation findings (calibration, filter state, roll noise, Ouija Effect, layer override
behavior, Dots Per 360 anchoring): `%USERPROFILE%\Claude\STEAM_INPUT_GYRO_REFERENCE.md`
