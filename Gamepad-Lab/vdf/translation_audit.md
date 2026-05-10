# Arc Raiders VDF → JSM translation audit

**Source VDF:** `./reference/jangman's jyro_v13.vdf` (the v13 tuned profile this audit is grounded in)
**Inventory:** auto-generated section/group/binding dump that lived alongside this audit; not preserved here (regenerable from the source VDF via `vdf_clean.py`'s `analyze` pass).
**JSM scaffold:** historical `jsm_sdl3_config.txt` from the prior workspace; not preserved. Reapplying the work means re-authoring the JSM config from this audit row-by-row.
**Plan-of-record:** the Kiro-shaped `vdf-to-jsm-port` plan was discarded with the rest of the Kiro workflow; the rows below are the durable artifact.

## Ground rules

- **VDF is authoritative.** Where prior behavioral notes disagreed with the VDF (e.g. yaw-only vs Local Space), the VDF's value wins — the v13 file is what the user ultimately settled on.
- **Two-axis grading.** *Technical translatability* (Yes / Approx / No) and *semantic fidelity* (High / Medium / Low + brief reason when below High) are kept separate so a technically-possible translation with high-loss behavior doesn't get hidden behind one averaged number.
- **Player importance.** Stated directly as High / Med / Low with a one-line reason; this is the author's read, not a user-declared rank — correct freely.
- **Row granularity.** One row per mechanic whose translation risk is distinct. Settings on the same Steam "page" that translate uniformly are merged; settings with divergent risk are split out.
- **Row IDs.** `G.` gyro, `S.` sticks, `T.` triggers, `B.` face/D-pad/bumper/system buttons, `L.` layers & architecture, `X.` cross-cutting. Ranked summary at the bottom.

---

## L — Layers & architecture

| ID | VDF concept | JSM equivalent | Conversion | Technical | Fidelity | Importance |
|---|---|---|---|---|---|---|
| L.1 | Two action sets: `Default` (Game, preset 0) and `Preset_1000006` (Menu, preset 1). Controller-wide context swap, driven by game focus. | JSM runs one config at a time. The closest analogs are (a) separate `AutoLoad/<game>.txt` files keyed by foreground window, (b) in-console `READ` to swap, or (c) a "Menu modeshift" held behind a dedicated button. None preserve Steam's automatic game-vs-Steam-overlay detection. | Author Game as the main config; approximate Menu as a held-modeshift on a dedicated input (e.g. hold Select) OR produce a second `.txt` file and switch manually. | Approx | Low — runtime context-swap doesn't exist; approximation forces a manual or button-held mode. | Med — Menu preset is a usability nicety; game-critical actions all live in Default. |
| L.2 | `Aim` action layer (preset 2, parent `Default`) — overlays on Default, replaces gyro with `mode = disabled` (group 288) and alters LS/RS edge bindings. | `NO_GYRO_BUTTON` + a held-button modeshift that rebinds LS/RS. JSM has no "layer" object; every layered state must be reproduced per-button with modeshift chords. | Decompose: on layer-active button held → `GYRO_OFF = NONE`; LS/RS assignments change in the held-mode. | Approx | Medium — the conceptual layer is reproducible input-by-input, but the activation trigger (see below) does not currently appear as an `add_layer` binding in the inventory — flag for Step 2 inspection. | Med — Aim layer tightens gyro off for scope-like aiming; quality-of-life, not blocking. |
| L.3 | `Click` action layer (preset 3, parent `Preset_1000006` / Menu) — the **crown-jewel mechanic**. Activated by 6+ inputs via a choreographed `controller_action add_layer 4` (t=0ms) → click (LMB/RMB/SHIFT, t=50ms) → `controller_action remove_layer 4` (t=150ms) sequence. Purpose: freeze gyro motion around a click so cursor doesn't slide during click-and-drag. | JSM has no `add_layer` with delayed `remove_layer`. Closest approximation: chord-modeshift that fires `GYRO_OFF` on soft-press and LMB on full-press of the same input (relies on analog trigger soft/full split — works for RT, fails for face buttons & R3 which are digital). A second approach is `^GYRO_OFF` toggle + rapid re-toggle, but timing fidelity is lost. | Per-invoker strategy: **RT** → modeshift on `ZR` soft + `ZRF` firing LMB (analog split works); **face buttons X/Y** → modeshift chord `ZR,X` / `ZR,Y` forcing user to hold RT while pressing (input semantics diverge from VDF); **R3 click, LS edge, Menu dpad edge** → no clean JSM translation, must either drop the freeze or accept gyro drift during their clicks. | Approx | **Low** — JSM cannot express the timed 50 ms delayed `remove_layer`; it must either freeze gyro for as long as the button is held (over-long freeze) or release immediately (under-frozen). Every invocation of this pattern degrades. | **High** — this is the signature mechanic the user engineered specifically for inventory click-and-drag; losing it would visibly change inventory play. |
| L.4 | `mode_shift <input> <group_id>` bindings — non-destructive, scoped group swap within a preset (e.g. L3 in Game → `mode_shift gyro 272` swaps gyro to a precision config). | Held-button modeshift: `L3,GYRO_SENS` or similar chord syntax where the new values apply only while L3 is held. | Direct — both concepts are "held-modifier swap." | Yes | High — nearly exact; JSM's chord-modeshift is the same idea. | Med — used for precision-gyro toggle; useful but not essential. |
| L.5 | `controller_action` layer ops invoked from multiple inputs, all bound via `Long_Press` activator with `delay_start` / `delay_end` values (e.g. 0 / 50 / 150 ms for Click layer). | JSM's closest analog is the tap/hold event modifier on the *containing* binding, not the layer op. The timed choreography (several actions fired on the same button at different offsets) has no JSM equivalent. | Collapse the choreography to a single JSM event on each invoker — typically, fire the primary action (the click) and accept the loss of the `add_layer`/`remove_layer` surrounding frames. | Approx | Low — the timed sequence is lost; only the outcome action remains. | High (for Click layer invokers) / Low (elsewhere). |

## G — Gyro

| ID | VDF concept | JSM equivalent | Conversion | Technical | Fidelity | Importance |
|---|---|---|---|---|---|---|
| G.1 | `group[14].mode = gyro_to_mouse` (Game preset primary gyro). | `GYRO_SENS = N`, `MOUSE_X_FROM_GYRO_AXIS = Y`, `MOUSE_Y_FROM_GYRO_AXIS = X` (default axis routing), no stick mode for gyro. | Direct — JSM's default gyro path *is* gyro-to-mouse. | Yes | High | High — foundational. |
| G.2 | `gyro_to_2d_conversion_style = 3` (Steam Local Space — yaw + tilt-modulated roll blend). | `GYRO_SPACE = LOCAL` + yaw axis routed to mouse X. JSM's `LOCAL` reads raw controller axes and does not do Steam's dynamic yaw-roll blend. | Enum map: `3 → GYRO_SPACE = LOCAL`. `gyro_roll_scale` (2500) and `gyro_mouse_sample_angle_offset` (10) — the tuning for Steam's blend — have no JSM counterpart and are dropped. | Approx | Medium — flat-held controller matches Steam exactly; tilted/vertical grip diverges because roll no longer contributes to horizontal output. | High — felt continuously during aiming; primary gyro identity. |
| G.3 | `gyro_natural_sensitivity = 150` + `flickstick_rotation_sensitivity = 6680` (the DP360 of the layout; pixels per 360°). | `REAL_WORLD_CALIBRATION = (6680 / 360)` ≈ `18.56` (pixels per degree baseline), combined with `IN_GAME_SENS = 1.0` and `GYRO_SENS = f(150)` to reproduce the same pixel-per-degree feel. | Two-part: (a) RWC maps the 6680 DP360, (b) `GYRO_SENS` is calibrated to match `gyro_natural_sensitivity = 150` — expect iterative tuning in Step 2 against the existing scaffold value `GYRO_SENS = 2`. | Yes | Medium — concepts map; numeric match is subject to in-game sensitivity pipeline and requires live-hardware calibration. | High — sensitivity mismatch is immediately felt. |
| G.4 | `gyro_precision_speed = 1500` (Steam's high-end of the slow-to-fast sensitivity curve). | `MIN_GYRO_SENS` / `MAX_GYRO_SENS` + `MIN_GYRO_THRESHOLD` / `MAX_GYRO_THRESHOLD` — JSM's linear sens ramp on angular velocity. | Approximate by picking a MIN/MAX sens pair that produces the same slow-end scaling; exact match requires empirical tuning. | Approx | Medium — JSM's sens-ramp and Steam's precision-speed tuning use different math; the *shape* of the curve isn't guaranteed to match. | Med — affects fine-aim feel; matters at low-speed micro-adjusts. |
| G.5 | `gyro_speed_deadzone = 98` (deg/s under which gyro input is suppressed). | `GYRO_CUTOFF_SPEED = 98` (same unit, same semantic). | Identity. | Yes | High | Med. |
| G.6 | `mouse_move_threshold = 2` (below-this-deg/s tighten). | `GYRO_CUTOFF_RECOVERY` (similar aim-tightening semantic). | Approximate unit transfer (Steam threshold ≈ JSM recovery band). | Approx | Medium — similar intent, not guaranteed identical behavior. | Med. |
| G.7 | `gyro_ratchet_button_mask = 33554434` (Game) — bit mask naming L1 / LB as ratchet-hold to temporarily disable gyro. | `GYRO_OFF = L` (or whichever button the mask decodes to). | Decode the mask to the specific button (bit 1 = ZR, bit 25 = L1, bit 26 = Select on Steam Controller mapping — verify during Step 2), bind `GYRO_OFF` to that input. | Yes | High — JSM's `GYRO_OFF = button` is semantically identical. | Med — common ergonomic feature. |
| G.8 | `mouse_dampening_trigger = 4` + `mouse_trigger_clamp_amount = 75` — when the named trigger (LT soft-pull) is engaged, gyro sensitivity is damped by 75%. | Held-modeshift: when the trigger is active, apply reduced `GYRO_SENS`. Requires analog-trigger soft-press detection (JSM `ZL_MODE` non-digital). | `ZL,GYRO_SENS = <0.25 × base>` as a chord-modeshift while ZL is held past soft threshold. | Approx | Medium — the dampening *triggers* on soft-press, but JSM applies the reduced sens immediately on the first soft event; ramp-in dynamics differ. | Med — affects ADS feel. |
| G.9 | `group[247]` — Menu preset gyro: `gyro_natural_sensitivity = 350`, ratchet on Start button, different clamping. | Either omit Menu gyro entirely (accept gyro-off during menus) or produce a second config. | Drop for v1 safe tier; cover in experimental via a Menu modeshift if the Menu preset is retained at all (see L.1). | Approx | Low — likely dropped; JSM cannot easily reproduce two active gyro profiles at once. | Low — menu gyro is cosmetic; game-critical gyro is Default. |
| G.10 | `group[272]` — precision-gyro variant invoked by L3 mode_shift in Game: lower sens (125), tighter deadzone (48), threshold 1. | Held-modeshift under L3: `L3,GYRO_SENS = <lower>`, `L3,GYRO_CUTOFF_SPEED = 48`. | Direct modeshift chord. | Yes | High — JSM's held-modeshift is the same idea. | Med — tactical-level gyro toggle. |
| G.11 | `group[288].mode = disabled` (Aim layer — gyro off entirely). | `GYRO_OFF = NONE` plus the layer's activation trigger (see L.2). | While Aim layer is active, force gyro off. | Yes | High | Med. |
| G.12 | `group[211]` (Click-layer gyro): still `gyro_to_mouse` but with `gyro_ratchet_button_mask = 0` (no ratchet) + `mouse_dampening_trigger = 6`. | In JSM, the Click-layer approximation already disables gyro during the click (L.3); the nuanced mid-click gyro config is effectively replaced by "off." | Omit; the approximation in L.3 subsumes it. | Approx | Low — the mid-sequence gyro config is lost entirely. | Low — inside a 100ms window, nobody will notice mid-sequence gyro nuance. |

## S — Sticks

| ID | VDF concept | JSM equivalent | Conversion | Technical | Fidelity | Importance |
|---|---|---|---|---|---|---|
| S.1 | Game LS: `group[129].mode = dpad`, layout 3 (radial edge binding), cardinal outputs W / S / A / D. Stick treated as 4-way digital dpad, not analog joystick. | `LEFT_STICK_MODE = NO_MOUSE`, then bind `LUP = W`, `LDOWN = S`, `LLEFT = A`, `LRIGHT = D`. Ring-mode `OUTER` if needed to match layout-3 edge-binding. | Direct four-way key map. | Yes | High — WASD output is exactly what JSM's stick-to-keys does. | High — movement. |
| S.2 | Game LS click (`joystick_click`) = `RIGHT_SHIFT` + `Long_Press LEFT_SHIFT` (200ms). | `L3 = RSHIFT 'LSHIFT_` (tap-press RSHIFT, hold-press LSHIFT). | Event-modifier syntax: `'` for tap, `_` for hold. | Yes | High — JSM's tap/hold modifiers match Steam's Full_Press vs Long_Press. | Med — sprint/walk toggle. |
| S.3 | Game LS edge (layout 3 radial edge): `V` on outer ring. | `LRING = V` with `LEFT_RING_MODE = OUTER`. | Direct. | Yes | High. | Low — situational. |
| S.4 | Game RS: `group[221].mode = joystick_move`, output to right analog stick (output_joystick 2), curve exponent 5, `custom = 125`, asymmetric horiz/vert sensitivity 35%/35%, haptic_intensity 2. | `RIGHT_STICK_MODE = RIGHT_STICK`. *But:* JSM emits the right stick as a virtual gamepad stick (requires ViGEm on Windows); the curve_exponent / custom values are Steam-specific and have only approximate JSM analogs (`RIGHT_STICK_AXIS_X` / `_Y`, `RIGHT_STICK_UNPOWER`, `RIGHT_STICK_UNDEADZONE`). | Set mode + approximate curve via JSM's power-curve settings; drop haptic intensity (no JSM equivalent). | Approx | Medium — stick-as-gamepad output works; curve shape is an approximation. | Med — RS is a secondary control; Arc Raiders is gyro-primary. |
| S.5 | Game RS click = `C` + `Long_Press LEFT_CONTROL` (200ms). | `R3 = C 'LCONTROL_`. | Direct. | Yes | High | Med. |
| S.6 | Menu LS: `group[275].mode = dpad` with `mouse_delta` output (225 px steps in cardinal directions) — LS moves mouse cursor in discrete steps for menu navigation. | `LEFT_STICK_MODE = MOUSE_AREA` (position-based) or individual LUP/LDOWN/LLEFT/LRIGHT bindings producing mouse movement. JSM lacks the "225 px discrete step" concept. | Bind the four LS directions to mouse movement in JSM, accept continuous rather than stepped output. | Approx | Medium — continuous vs stepped feels different but serves the same purpose. | Low — only affects Menu preset, which is deprioritized (see L.1). |
| S.7 | Menu LS edge: `controller_action add_layer 4` on edge (Click layer invoker). | Inherits L.3's limitations. | Drop for safe tier; experimental tier attempts per L.3. | Approx | Low | Low (only in Menu). |
| S.8 | Aim-layer RS/LS: `group[307]` dpad with inverted edge_binding, edge triggers choreographed `Long_Press LEFT_SHIFT + LEFT_CLICK + remove_layer 4 @+125ms`. | Inherits the Aim-layer and Click-layer approximation issues. | Drop the layer-op portion; keep the SHIFT+LMB combo on edge. | Approx | Low | Low. |

## T — Triggers

| ID | VDF concept | JSM equivalent | Conversion | Technical | Fidelity | Importance |
|---|---|---|---|---|---|---|
| T.1 | Game LT (`group[4]`): trigger mode, `Full_Press` = `mouse_button RIGHT`, haptic 2. Threshold semantics: triggers on full pull past `deadzone_outer_radius = 27500`. | `ZL = RMOUSE`, `ZL_MODE = NO_FULL` (treat as single button on full pull) or analog threshold via `TRIGGER_THRESHOLD`. | Direct; haptic drops silently. | Yes | High — RMB on LT is exactly what JSM does. | High — ADS. |
| T.2 | Game RT (`group[5]`): `Full_Press` = `mouse_button LEFT`, haptic 2. | `ZR = LMOUSE` with appropriate `ZR_MODE`. | Direct. | Yes | High | High — fire. |
| T.3 | Menu RT (`group[246]`): choreographed `Long_Press` sequence fires `add_layer 4` @+0ms → `mouse_button LEFT` @+50ms → `remove_layer 4` @+150ms. *The Click-layer invoker.* | Per L.3: approximate via soft/full split — soft pull disables gyro (modeshift), full pull fires LMB. Timing fidelity lost. | Soft-pull threshold modeshift: `ZR,GYRO_OFF = NONE` on soft, `ZRF = LMOUSE` on full. | Approx | Low — the 50 ms click timing and gyro-off window are not reproducible; we get either over- or under-frozen. | High — this is the crown-jewel in a trigger. |
| T.4 | Aim-layer triggers (`group[300]`, `group[301]`): trigger mode, no bindings (inherits or nops). | `ZL = NONE` / `ZR = NONE` within the Aim-modeshift state. | Direct. | Yes | High | Low. |

## B — Buttons (face, D-pad, bumpers, system)

| ID | VDF concept | JSM equivalent | Conversion | Technical | Fidelity | Importance |
|---|---|---|---|---|---|---|
| B.1 | Game A (`button_a`) = `SPACE` (Full_Press). | `S = SPACE` (JSM uses compass names: S = South / A / Cross). | Direct. | Yes | High | High (jump). |
| B.2 | Game B (`button_b`) = `LEFT_ALT` (Full_Press). | `E = LALT` (E = East / B / Circle). | Direct. | Yes | High | High (lean/crouch). |
| B.3 | Game X (`button_x`) = `E` (Full_Press) + `R` (Long_Press, 175 ms). | `W = E 'R_` — JSM's `'` fires on tap release, `_` fires on hold. `HOLD_PRESS_TIME` governs the threshold globally (default 150 ms, close to 175). | Direct if 150 ms global is acceptable; exact 175 ms requires `HOLD_PRESS_TIME = 175`. | Yes | High — near-exact with threshold tuning. | High (use / reload). |
| B.4 | Game Y (`button_y`) = `F` (Full_Press) + `X` (Long_Press, 175 ms). | `N = F 'X_`. | Direct. | Yes | High | High (pick up / alt). |
| B.5 | Game LB (`left_bumper`) = `Q` (Full_Press) + `mode_shift` (dpad 111, RT variants 216/217) + `Chord` with key `3` (LB+key3 → 3). Also L1 acts as gyro-ratchet per G.7. | `L = Q`. The mode_shift becomes a held-modeshift on `L`. The `Chord` activator (LB+key3=3) needs `L,DOWN = 3` or similar simultaneous-press syntax. | Three bindings on one button: `L = Q` (primary), `L,<chord-target> = 3` (chord), and `GYRO_OFF = L` (ratchet — already in G.7). | Approx | Medium — all three effects can be bound, but interaction between them (e.g. ratchet + chord + primary) may have precedence differences from Steam. | High (weapon slot). |
| B.6 | Game RB (`right_bumper`) = `SCROLL_UP` / `SCROLL_DOWN` (cycled Full_Press, 10 Hz repeat) + `H` (Long_Press, 175 ms). | `R = SCROLLUP+ 'H_` — JSM's `+` turbo modifier fires repeatedly while held; tap separator `'` and hold `_` for the double-action. *The cycled scroll-up-then-scroll-down isn't a JSM concept.* | Pick one (scroll-up) for the simple case; the cycled behavior is Steam-specific. | Approx | Medium — cycling alternates on each press in Steam; JSM would fire the same scroll direction each time. | Med — weapon wheel cycling. |
| B.7 | Game D-pad (`group[114]`): N=G, S=B, E=MIDDLE_CLICK, W=Z (all Full_Press). | `UP = G`, `DOWN = B`, `RIGHT = MMOUSE`, `LEFT = Z`. (JSM D-pad uses `UP/DOWN/LEFT/RIGHT`.) | Direct. | Yes | High | Med (gadgets). |
| B.8 | Menu D-pad (`group[286]`): N=SCROLL_UP (10 Hz), S=SCROLL_DOWN (10 Hz), E=TAB, W=ESCAPE. | Per-preset direction rebinds, or modeshift to Menu state. | Within Menu-modeshift: `<menu>,UP = SCROLLUP+`, `<menu>,DOWN = SCROLLDOWN+`, etc. | Yes | High — simple rebinds. | Low (Menu only). |
| B.9 | Game Select (`button_escape`) = `ESCAPE`. | `MINUS = ESC` (Minus = Select on Switch-mapping / View on Xbox / Share on PS). | Direct. | Yes | High | Med. |
| B.10 | Game Menu (`button_menu`) = `TAB` (Full_Press) + `M` (Long_Press, 175 ms). | `PLUS = TAB 'M_`. | Direct. | Yes | High | Med. |
| B.11 | Menu Select = `E`, Menu Menu = `Q`. | Within Menu-modeshift: `<menu>,MINUS = E`, `<menu>,PLUS = Q`. | Direct. | Yes | High | Low. |
| B.12 | Face-button A/B in Menu preset: A = `MIDDLE_CLICK` / Long_Press `LEFT_CONTROL` (200 ms); B = `ESCAPE` / Long_Press `LEFT_ALT` (200 ms). | Within Menu-modeshift: `<menu>,S = MMOUSE 'LCONTROL_`, `<menu>,E = ESC 'LALT_`. | Direct, but `HOLD_PRESS_TIME` is global — 200ms in Menu vs 175ms in Game creates a conflict. | Approx | Medium — single global hold threshold means one will be slightly off. | Low (Menu). |
| B.13 | Face-button X/Y in Menu: each fires the Click-layer choreography (add_layer 4 / click / remove_layer 4). | Per L.3 approximations — each face button needs a modeshift on RT held. | Within Menu-modeshift: bind X/Y to fire LMB with gyro suppressed for the duration of the press — but without RT held these are digital-only, so the approximation is a compromise. | Approx | Low — digital button can't trigger a timed freeze via analog threshold tricks; gyro stays hot during the click. | Med — menu interaction UX. |
| B.14 | Game LB chord (LB + key `3` → `3`): `Chord` activator. | `L+<something> = 3` (simultaneous press) or chord-modifier — JSM supports `+` for simultaneous. | Direct chord. | Yes | High | Low. |

## X — Cross-cutting

| ID | VDF concept | JSM equivalent | Conversion | Technical | Fidelity | Importance |
|---|---|---|---|---|---|---|
| X.1 | Haptic rumble on trigger/stick-click events (`haptic_intensity` 1-2 values throughout). | JSM has rumble-out via `LMOUSE = R8000` etc. but no "haptic intensity on trigger click" concept for input devices. | Dropped entirely. | No | N/A — not translated. | Low — feel nicety, no gameplay impact. |
| X.2 | `Long_Press` timing values (175 / 200 / 250 ms across bindings). | JSM `HOLD_PRESS_TIME` is a single global setting. | Pick the most common value (175 ms) globally; accept drift for 200 / 250 ms bindings. | Approx | Medium — one global threshold cannot match multiple per-binding values. | Med — affects tap/hold precision. |
| X.3 | Repeat rates on scroll / D-pad menu bindings (`repeat_rate = 10`, 10 Hz). | JSM `+` turbo modifier with `TURBO_PERIOD` global. | Direct — set `TURBO_PERIOD = 100` (ms) to match 10 Hz, then suffix the output with `+`. | Yes | High | Low. |
| X.4 | Trigger `deadzone_outer_radius = 27500`, `edge_binding_radius = 15000`, `adaptive_threshold = 0`. | `TRIGGER_THRESHOLD = <normalized>` + `ZL_MODE` / `ZR_MODE` selection. | 15000/32768 ≈ 0.46 threshold for edge-bind; adjust per mode. | Approx | Medium — trigger curve in JSM is simpler; exact threshold landing may feel different. | Med (feel of LT/RT pull). |
| X.5 | RS `curve_exponent = 5`, `custom = 125`, asymmetric `horizontal_scale 35% / vertical_scale 35%`. | `RIGHT_STICK_UNPOWER`, `RIGHT_STICK_UNDEADZONE`, separate X/Y sensitivity. | Approximate via JSM's power-curve settings; accept shape mismatch. | Approx | Medium — gross shape matches, fine shape diverges. | Low (RS is secondary). |
| X.6 | `Start_Press` activator (fires on initial frame of press, before Long_Press timing kicks in). | JSM `\` start-press (which is the default). | Direct — the default binding behavior in JSM. | Yes | High | Low. |
| X.7 | Stick deadzones: `deadzone_inner_radius`, `deadzone_outer_radius` (variable across groups). | `LEFT_STICK_DEADZONE_INNER` / `_OUTER`, `RIGHT_STICK_DEADZONE_INNER` / `_OUTER`. | Normalize Steam values (0–32767) to JSM 0–1 floats. | Yes | High | Med. |
| X.8 | Top-level controller metadata (`title`, `creator`, `controller_type`). | JSM uses file-level comments (`#`). | Transplant into header comment of the config file. | Yes | High | Low. |

---

## Ranked summary (cleanest first, biggest compromises last)

Ordered by `(technical × fidelity)` descending. Ties broken by Importance (higher matters more).

| Rank | ID | One-line |
|---:|---|---|
| 1 | G.1 | Primary gyro mode → JSM default gyro-to-mouse path. |
| 2 | G.5 | `gyro_speed_deadzone` → `GYRO_CUTOFF_SPEED`. |
| 3 | G.7 | Ratchet-mask → `GYRO_OFF = L`. |
| 4 | G.10, L.4 | `mode_shift` / precision-gyro toggle → JSM held-modeshift. |
| 5 | G.11 | Aim-layer `gyro disabled` → `GYRO_OFF = NONE`. |
| 6 | S.1, S.2, S.3, S.5 | LS/RS WASD + clicks + ring-edge → direct JSM stick-to-keys. |
| 7 | T.1, T.2 | LT/RT fire + ADS → direct `ZL = RMOUSE`, `ZR = LMOUSE`. |
| 8 | T.4 | Aim-layer trigger no-ops → `ZL/ZR = NONE` in modeshift. |
| 9 | B.1–B.4 | Face buttons A/B/X/Y with Full_Press + Long_Press → JSM tap/hold. |
| 10 | B.7, B.8 | D-pad rebinds (Game + Menu) → direct JSM UP/DOWN/LEFT/RIGHT. |
| 11 | B.9, B.10, B.11 | System buttons in Game + Menu → direct JSM MINUS/PLUS. |
| 12 | B.14 | LB+key chord → JSM `+` simultaneous-press. |
| 13 | X.3 | Repeat_rate → `TURBO_PERIOD` + `+` suffix. |
| 14 | X.6 | Start_Press → JSM default `\` start-press. |
| 15 | X.7 | Stick deadzones → direct with unit normalization. |
| 16 | X.8 | Controller metadata → header comment. |
| 17 | G.2 | Conversion style 3 (Local Space) → `GYRO_SPACE = LOCAL`. **Loses tilt-angle roll blend.** |
| 18 | G.3 | Natural sens + DP360 → `REAL_WORLD_CALIBRATION` + `GYRO_SENS`. Empirical calibration needed. |
| 19 | G.4 | Precision_speed → `MIN/MAX_GYRO_SENS` ramp. Curve shape approximate. |
| 20 | G.6 | Move_threshold → `GYRO_CUTOFF_RECOVERY` (approximate unit). |
| 21 | G.8 | Trigger-dampening → held-modeshift `GYRO_SENS` reduction. |
| 22 | S.4 | RS joystick_move → `RIGHT_STICK_MODE = RIGHT_STICK` with curve approximation (requires ViGEm). |
| 23 | S.6 | Menu LS stepped mouse → continuous mouse. |
| 24 | B.5 | Game LB (primary + mode_shift + chord + ratchet) — three effects on one input. |
| 25 | B.6 | Game RB scroll-cycle → single-direction scroll (loses alternation). |
| 26 | B.12 | Menu face-button A/B (200 ms holds) — global `HOLD_PRESS_TIME` conflict with Game (175 ms). |
| 27 | X.2 | `Long_Press` global threshold mismatch (175 / 200 / 250 ms → one global). |
| 28 | X.4 | Trigger thresholds (edge_binding_radius, adaptive_threshold) — JSM has simpler trigger curve. |
| 29 | X.5 | RS curve exponent + asymmetric scaling — shape approximation only. |
| 30 | L.1 | Two-action-set runtime swap → manual `READ` or Menu-modeshift. |
| 31 | L.2 | Aim layer → decomposed via held-button modeshift. Activation trigger needs Step 2 re-inspection. |
| 32 | G.9 | Menu gyro — likely dropped for safe tier. |
| 33 | S.7, S.8 | Menu LS edge / Aim-layer RS/LS layer-op edge triggers → drop layer-op portions. |
| 34 | T.3 | **Menu RT Click-invoker choreography** — soft/full-pull approximation; timing fidelity low. |
| 35 | B.13 | Menu face-button X/Y Click-invokers — digital inputs can't trigger timed freeze. |
| 36 | G.12 | Click-layer gyro config — subsumed by L.3 approximation. |
| 37 | L.3 | **Crown-jewel click-layer choreography** — JSM cannot express timed `remove_layer`; every invoker degrades. |
| 38 | L.5 | `controller_action` timed sequence — lost; only the outcome action remains. |
| 39 | X.1 | Haptic rumble — no JSM input-side equivalent, dropped. |

## Flags & open questions for Step 2

1. **Aim-layer activation (L.2):** no `add_layer 2` binding appears in the inventory. Activation mechanism needs re-inspection of the raw VDF before Step 2 can approximate it. Suspected: either held-button attached to the preset via Steam UI metadata (not in parsed nodes), or an input that the inventory walker missed.
2. **Ratchet button mask decoding (G.7):** `33554434` decimal → need bit-pattern → physical button. Steam Controller button bit layout: bit 1 (2) = ZR, bit 25 (33554432) = L1, bit 26 (67108864) = Select. `33554434 = 33554432 + 2 = L1 + ZR`. So ratchet fires when **L1 OR ZR** is held. Confirm during Step 2.
3. **Bumper RB scroll-cycle (B.6):** the cycled SCROLL_UP-then-SCROLL_DOWN behavior is probably a Steam-internal implementation of a weapon wheel. Pick one direction as the "canonical" scroll during Step 2.
4. **HOLD_PRESS_TIME (X.2):** set to 175 ms globally; accept the Menu-preset 200 ms / 250 ms holds as slightly-shorter-than-Steam.
5. **Mode_shift group `272` (G.10) vs L3 click (S.2):** L3 fires both the precision-gyro mode_shift (via `switches` group 7) *and* `RIGHT_SHIFT` / Long_Press `LEFT_SHIFT` (via `joystick_clicks`). These are two separate VDF bindings to the same physical button — JSM must combine them under a single `L3 = ...` statement (chord-modeshift with embedded output).
