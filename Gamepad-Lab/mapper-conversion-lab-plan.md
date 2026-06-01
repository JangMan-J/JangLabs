# Mapper Conversion Lab — Working Plan

**Status:** Active working plan. This is the owned reformulation of the preserved design in
[`vision/`](./vision/INDEX.md). It supersedes the vision doc *for execution*; the vision remains the
preserved snapshot and is not mutated. Where this plan diverges, the diff is in §4.

**Date:** 2026-05-31 · build state in §11 verified on this box (CachyOS / Wayland / NVIDIA) this date.

**2026-06-01 update — Phase 0 complete (runtime-verified).** **0a (JSM lane): PASS** — real pad →
`SPACE`/`LMOUSE` observed at **evdev**, ~1–3 ms. **0b (Steam Input, R1): observable but NOT at evdev** —
on this Steam **Beta + experimental SteamRT3** (pressure-vessel-contained client) + Wayland/KWin, Steam
Input's kbd/mouse output is observable via **XI2** (`xinput test-xi2`, on the `xwayland-keyboard` seat),
**never on `/dev/input/event*`** (no uinput node, no `KEY_F9` at evdev). R1 is therefore **resolved as a
per-lane observation-plane fork** (§6), not a collapse. The research's evdev/XTEST/extest path was wrong
about the **plane** (output is at XI2, not evdev); the **injector** (X11 XTEST vs libei) is
**undetermined** — on this EIS-Xwayland even `xdotool`'s pure XTEST routes to the seat, so device-id
can't separate them — and extest's relevance is an untested follow-up. Durable detail:
`findings/steam_input_linux.md` + `findings/jsm_linux_port.md`; runs `20260601T065426Z-phase0-runtime-smoke/`
and `20260601T070951Z-phase0b-steam-input/`.

**JSM source (directed):** the user's fork **`JangsJyro-JSM`** —
`https://github.com/JangMan-J/JangsJyro-JSM.git`, branch **`branch-a-port`**, local working copy
`~/Projects/JangsJyro-JSM`. This is *the* JSM source for the lab (not an upstream clone). Referenced by
URL + SHA per `Jangs-Lab/CLAUDE.md` (no cross-repo symlink; don't copy the tree into Gamepad-Lab).

**Citations:** references to the preserved design read `design §<lines>`, into
`vision/2026-04-29-gamepad-mapper-conversion-lab-design.md` (anchors mirror `vision/INDEX.md`).

**Execution discipline:** every code-producing task runs under `/tdd` (`mattpocock/skills@tdd`) —
red → green → refactor, vertical tracer-bullet slices, behavior-through-public-interface. See §2 for the
one place that discipline is *adapted* to a fixed, immutable oracle.

---

## 1. Objective & definition of done

**Inherited objective (fixed, fully owned):** an agent-first lab that converts gamepad mapper configs
between **Steam Input** and **JoyShockMapper (JSM)** — Steam Input → JSM first, JSM → Steam Input
preserved as a later path — proving each conversion **behaviorally**, with *real* Steam Input vs *real*
JSM as the authoritative oracle (`design §3–9`).

**Definition of done (mine):** *you hand me a Steam Input layout, I emit a clean JSM config, and I can
show — feature by feature, on real Windows JSM, against holdout traces the converter never saw —
whether each behavior is `exact`, `bounded`, `degraded`, `unsupported`, or `requires_user_choice`, with
the loss named.*

Scope, non-goals, and the bidirectional architecture are inherited unchanged (`design §9–27`).

---

## 2. The spine (non-negotiable operating principles)

1. **Real-runtime oracle is authoritative** (`design §193–208`; `Gamepad-Lab/CLAUDE.md` "real-runtime
   evidence beats source review"). A source read or a doc claim is a *hypothesis* until it fires on a
   real runtime and is captured as an event.

2. **Anti-Goodhart armor is the point.** A converter optimizing against a mutable oracle will cheat it.
   Three inherited defenses, elevated to first-class: **no central scoreboard** (`design §206`); the
   **non-semantic-change boundary on JSM** — build glue, test harnessing, I/O recording only, *never*
   mapping semantics (`design §271–289`); **holdout traces** withheld from converter briefs
   (`design §210–235`).

3. **TDD discipline — adapted for an immutable oracle.** The `/tdd` loop maps onto the lab: an
   adversarial **trace is the failing test (red)**; the converter emits a matching config (green); the
   non-semantic boundary is the **refactor constraint**. **But green has only two legal forms**, because
   JSM/Steam are immutable third-party oracles:
   - **(a)** the converter emits a config that closes the delta, or
   - **(b)** an **honest classification** that the gap is irreducible (`degraded` / `unsupported` /
     `requires_user_choice`).

   A red trace does not always become green by writing code — sometimes by truthfully labeling the loss.
   "Patch JSM so the trace matches" is the Goodhart failure this plan is armored against. The `/tdd`
   rule *"verify through the public interface, not internals"* == "observe emitted events, never peek at
   JSM `DigitalButton`/Steam internal state."

4. **Observe at the kernel input plane — but per-lane (corrected 2026-06-01).** Inject via
   `uinput`/`uhid`; capture emitted keyboard/mouse output. **This is plane-dependent and NOT uniform
   across lanes** — the original "everything is evdev-observable, so Wayland is an asset" claim held only
   for emitters that write `uinput`:
   - **JSM lane → evdev.** JSM writes real `uinput` devices (`JoyShockMapper_KEYBOARD/_MOUSE`), so its
     output *is* at `/dev/input/event*`, compositor-agnostic (verified Phase 0a).
   - **Steam Input lane → XI2 / Wayland seat (NOT evdev).** On this Wayland + SteamRT3 stack Steam Input
     output is observable via **XI2** (`xinput test-xi2`) on the Xwayland seat, **never at evdev**
     (verified Phase 0b); the injector (XTEST vs libei) is undetermined. The lab needs a **second
     observer** for this lane (§5, §6-R1).
   Exceptions still apply: gyro *input* (R2) and JSM's Linux *virtual-gamepad output* stub (§5).

5. **Evidence over confidence; expose gaps.** Approximation quality is judged by trace evidence, not
   agent confidence (`design §161`). Reports never hide gaps; justified regressions name the feature,
   the loss, the reason, and the follow-up task that owns it.

---

## 3. What I inherit already built (the lab is well past greenfield)

The biggest correction to the abstract vision: **the JSM source, a reproducible Linux build, the gyro
profile, and a real Steam⇄JSM config pair already exist.** The plan folds them in (per `vdf/README.md`:
when reapplying, **fork or copy out** — do not expand `vdf/` in place; and per `Jangs-Lab/CLAUDE.md`:
reference the JSM repo by URL, don't symlink/copy wholesale).

| Asset | What it gives the lab | Status |
|---|---|---|
| **`JangsJyro-JSM` fork** (`branch-a-port`) | The JSM source. Lineage: **Electronicks/JoyShockMapper `next`** base (→ `bb69784`) **+ ceski (@ceski-1) downstream controller-support backport** **+ JangMan integration**. SDL3 wired via CPM, **pinned `release-3.4.8`** (latest stable; gyro verified at 3.4.4 — re-confirm at 3.4.8 in Phase 6), `SDL_HIDAPI ON`; SDL is the Linux default. | **Source of record** |
| └ ceski backport (`b368fa5` 8BitDo, `6b7f923` Flydigi, `afbea5f` Switch 2 Pro, `437476f`/`c501407` 64-bit buttons, `44091ec` `JS_TYPE_UNKNOWN`, `2c07c5e` bus defs, `439dc1e` extra buttons, +timer/priority) | **The Ultimate 2 is now first-class:** `JS_TYPE_8BITDO_ULTIMATE2_WIRELESS`, `JS_VENDOR_8BITDO 0x2dc8`, `JS_PRODUCT…_ULTIMATE2_WIRELESS 0x6012`, mapped at `SDLWrapper.cpp:108`. **Supersedes the build-handoff's `JS_TYPE_UNKNOWN` caveat.** | De-risks gyro |
| └ JangMan integration (`4d8927e` merge-artifact fix, `3979fed` `_guid` restore, `09b84db` SDL3-3.4.4 pin + touchpad guard) | Makes the backport compile; pins the SDL3 whose `SDL_hidapi_8bitdo` driver surfaces this pad's gyro. | Build-enabling |
| `~/Projects/JangsJyro-JSM/docs/superpowers/` | `2026-05-03-linux-build-reproduction-handoff.md` (the build recipe), `linux-environment-setup-ubuntu.md` (deps — **Ubuntu/apt; translate to pacman**), `plans/…-jsm-linux-feasibility.md`, `specs/…-lab-design.md` (vision origin). | Reuse |
| `~/Projects/JangsJyro-JSM/configs/ArcRaiders.{safe,experimental}.txt` | **Hand-authored JSM translation of `jyro_v13.vdf`**, same feature-ID taxonomy as the VDF audit; `OMITS` block enumerates the four gotchas. This is the **JSM (candidate) half of the A-B pair.** | Real candidate |
| `vdf/vdf_clean.py` (+28 tests) | Working Steam-Input VDF parser/cleaner — the converter's **Steam-side parser front-end**. | Reuse (fork out) |
| `vdf/translation_audit.md` + `vdf/reference/jangman's jyro_v13.vdf` | The converter's **initial rule set (hypotheses)** + the **Steam (reference) half of the A-B pair** and end-to-end target. | Reuse / target |
| `findings/gyro_hid.md` | Canonical gyro facts (±2000 dps, ~125 Hz actual, int16 axis map, 34-byte HID report, SDL3 driver behavior). | Canonical input |
| Physical 8BitDo Ultimate 2 Wireless | Ground-truth device for real-runtime gyro + validating synthetic injection. | On hand |
| `tools/gyro_*.py` | Windows-era raw-HID probes — HID-layout **reference only** (assume `hidapi.dll`). | Reference |

**Crucial relationship:** `vdf/translation_audit.md` and the `ArcRaiders.*.txt` configs were produced by
*static review* — what the vision says is **not authoritative**. Their grades are **predictions**; the
lab's job is to confirm/refute them with real-runtime traces. The audit's seven "quick wins" become the
first tracer bullets; its four "load-bearing gotchas" become the first adversarial traces.

---

## 4. Divergences from the preserved vision (the diff)

Per `Gamepad-Lab/CLAUDE.md`: the plan carries the diff; the design doc is not mutated.

| # | Vision (preserved) | This plan (owned) | Why |
|---|---|---|---|
| D1 | Phase 1 = JSM build; Steam observability deferred to Phase 2. | **Phase 0 front-loads Steam observability** alongside the build. | Steam Input is the irreducible black box; the build is now near-solved (D4), so the crux *is* observability. |
| D2 | A-B proof is one of Phase 2's five items. | **A-B proof (one button, both runtimes, one delta) is the headline milestone (Phase 1)**; all horizontal infra is subordinate. | Vertical tracer-bullet first (`/tdd`); bulk infra before one delta tests imagined behavior. |
| D3 | Schemas (Phase 3) precede a working harness. | **Schemas formalized after the loop runs** (Phases 1–2 use labeled provisional artifacts). | Don't fix contracts before the loop teaches what they must carry. |
| D4 | Converter + build implied greenfield; "clone JSM". | **Use the `JangsJyro-JSM` fork**: source exists, builds on Linux (recipe known), the Ultimate 2 classifies, SDL3+HIDAPI is wired, and a real Steam⇄JSM **A-B config pair already exists.** | §3. The vision predates this built state. |
| D5 | Gyro folded into general phases. | **Gyro is its own risked lane (Phase 6)** behind an injection spike — but now de-risked: spoof the **native 8BitDo IDs** (device classifies; SDL3 driver surfaces gyro). | `uinput` can't surface SDL gyro; needs a driver-matched HID device (R2). |
| D6 | Adversarial generator is Phase 6. | **First adversarial set (the four `vdf` gotchas) pulled to Phase 4**, right after the quick wins. | I hold the hypotheses + the `OMITS` config; highest-value behavioral questions; where "green = classify" is proven. |
| D7 | Run artifacts under `docs/superpowers/runs/…`. | **`runs/` and `kb/` at the Gamepad-Lab root.** | `docs/superpowers/` is the fork's retired Kiro experiment (confirmed — vision was authored there). |
| D8 | Single 5-way classification enum. | **5-way enum *plus* the `vdf` two-axis grade (technical × fidelity), kept distinct.** | The audit warns: don't flatten two axes to one score — itself anti-Goodhart. See §7. |
| — | TDD unspecified. | **`/tdd` overlay on every code task, with the immutable-oracle adaptation (§2.3).** | Execution discipline the vision left open. |

Everything not listed is inherited unchanged: the phase skeleton, roles, result classes, cycle metrics,
validation policy, non-semantic boundary, headless scope, KB promotion rules, phase-gate idea.

---

## 5. Architecture

Two lanes (`design §29–49`): **reference** (Steam Input) and **candidate** (JSM). Pipeline:
**trace runner → {Steam lane | JSM lane} → output observer → event normalizer → comparator →
{converter | curator}**, looping; holdout traces gate acceptance.

**Observation plane (this box):**
- **Input:** `uinput` for digital buttons + standard analog axes; **`uhid` for gyro** — present the
  native 8BitDo VID `0x2dc8` / PID `0x6012` with the documented 34-byte report (`findings/gyro_hid.md`)
  so SDL3's `SDL_hidapi_8bitdo` surfaces deterministic synthetic `SDL_SENSOR_GYRO` *and* JSM classifies
  it as `JS_TYPE_8BITDO_ULTIMATE2_WIRELESS`.
- **Output (per-lane — corrected 2026-06-01):**
  - **JSM lane:** read `/dev/input/event*` (evdev) — keyboard, mouse (incl. relative-motion = the
    observable form of gyro→mouse). `tools/evdev_capture.py`. Compositor-independent (uinput). ✓ Phase 0a.
  - **Steam Input lane:** read the **XI2 / Wayland seat** plane — `tools/xi2_capture.py` (parses
    `xinput test-xi2 --root`). The XI2 **device id** identifies the *plane* (`xwayland-keyboard:N` = the
    Xwayland seat — where XTEST, libei, *and* physical all surface on EIS-Xwayland; `Virtual core XTEST
    keyboard` = legacy XTEST device, often unused under EIS), **not** the injector. Steam Input output is
    **not** on evdev here (Phase 0b; `findings/steam_input_linux.md`).
  - The comparator/normalizer therefore ingests **two capture sources** and normalizes both to the same
    key/mouse event vocabulary.
- **Linux output constraint (from the build handoff):** JSM's Linux **virtual-gamepad output is a stub**
  (`src/linux/Gamepad.cpp`; `Gamepad::getNew` → `nullptr`). **Keyboard/mouse output via uinput works.**
  ⇒ Phases 1–2 target keyboard/mouse-output mappings (e.g. `S=SPACE`, `ZR=LMOUSE`); any mapping whose
  JSM output is a *virtual-controller* event is **Windows-only** until the Linux `Gamepad` is
  implemented (allowed as non-semantic platform glue — log it as a `platform-delta`, not a failure).
- **Device-claim gotcha:** Steam Input hides controllers from SDL while running and re-exposes via its
  shim; the 8BitDo tray app claims HID exclusively. Lanes therefore run in **separate processes/runs**
  against the same trace, never contending for one device.

**Roles (agent-first, `design §51–60`):** Converter, Validator, Adversarial trace generator (a required
component), Knowledge curator — each an isolated agent with a bounded brief (`design §62–85`). The
`convergent-arbiter` skill coordinates when a phase needs independent attempts reconciled; the `Agent`
tool covers single assignments.

---

## 6. Crux risks, ranked (resolve top-down)

- **R1 — Steam Input observability (project-defining, RESOLVED 2026-06-01 — plane-fork, not collapse).**
  Steam Input *can* be driven and its kbd/mouse output observed with exact fidelity — but **at the XI2 /
  Wayland-seat plane, not evdev** (Phase 0b; real button press → 11× F9 KeyPress on XI2
  `xwayland-keyboard`, 1:1, zero at evdev). The "real vs real" oracle stands; the cost is that **the two
  lanes are observed on different planes** (JSM=evdev, Steam=XI2/seat) and the lab needs an XI2 observer
  (§5). Caveats: result is for **Steam Beta + experimental SteamRT3 on Wayland/KWin** — an X11 session
  or stable Steam may differ (R1-followup, secondary); the injection mechanism (XTEST vs libei) is
  **undetermined** and extest's relevance is an open follow-up. See `findings/steam_input_linux.md`.
- **R2 — Gyro input injection (de-risked, not done).** SDL gyro needs a driver-matched device; `uinput`
  won't surface it. **Primary path: `uhid` spoof of the native 8BitDo IDs + 34-byte report** (device
  classifies; SDL3 driver surfaces sensors). Fallbacks: headless JSM synthetic `JslWrapper`; real-pad
  replay for ground truth. **Phase 6.**
- **R3 — Linux→Windows transfer.** Linux automates; Windows certifies. Each gate repeats on Windows or
  is explicitly blocked (`design §260–269`). The fork already fixes the Windows SDL-target compile.
- **R4 — Tolerance models** (mouse delta, timing, gyro) — defined per feature class as first traced.
- **R5 — CMake 4.3.3 on this box (minor, new).** CMake 4.x drops compatibility with very old
  `cmake_minimum_required`; watch CPM sub-deps at configure. Not expected to block (SDL3 3.4.8 and the
  small header-only deps are modern).
- **Classification (RESOLVED):** the Ultimate 2 now classifies as a dedicated JSM type — no longer a
  risk.

---

## 7. Classification system (reconciled — D8)

Two complementary axes, never collapsed to a scalar:
- **Empirical result (per trace, the verdict)** — 5-way enum (`design §151–162`): `exact` ·
  `bounded_approximation` · `degraded_approximation` · `unsupported_omitted` · `requires_user_choice`.
- **Static grade (per mechanic, the hypothesis)** — from `vdf/translation_audit.md`: technical
  translatability (Yes/Approx/No) × semantic fidelity (High/Med/Low).

Divergence between predicted grade and traced result is itself a finding (corrects the audit, feeds the
KB). Each behavior carries the full cycle-metric record (`design §164–191`).

---

## 8. Canonical controller profile v1 (grounded in real hardware + the fork)

Declarations the vision requires before analog/gyro acceptance (`design §237–258`), now real:
- **Device:** 8BitDo Ultimate 2 Wireless, VID `0x2DC8` / PID `0x6012`, DInput (Home+B). Classifies in
  the fork as `JS_TYPE_8BITDO_ULTIMATE2_WIRELESS`.
- **Digital:** face buttons, d-pad, shoulders, stick clicks, start/back/home/capture, 4 rear/aux.
- **Analog:** sticks + triggers (standard Generic-Desktop axes).
- **Gyro:** °/s; ±2000 dps (`GYRO_SCALE = 2000/32767`); frame `pitch=-sGyroY, yaw=+sGyroZ,
  roll=-sGyroX`; **~125 Hz actual delivery** (not the 1000 Hz spec — synthetic frames emit at a declared
  deterministic rate; tolerance vs real captures assumes ~125 Hz); timestamp = trace-deterministic.
- **Accelerometer:** g (`ACCEL_SCALE = 1/4096`), same axis convention.
- **Excluded from v1:** touchpad, adaptive-trigger force feedback, mic-button behavior.

---

## 9. Knowledge base layout (`design §340–367`)

Repo-root `kb/`: `kb/lab-notes/observations.jsonl` (provenance-tagged, mutable, append-by-anyone) and
`kb/canonical/` (`control-catalog.json`, `mapper-functions.steam.json`, `mapper-functions.jsm.json`,
`equivalence-rules.jsonl`, `capability-matrix.json`). **Canonical promotion requires real-runtime
evidence + schema + conflict check + last-validated date; headless-only evidence cannot promote.** Seed
`equivalence-rules.jsonl` from `vdf/translation_audit.md` rows **only after each is trace-verified** (the
audit enters as lab-notes hypotheses).

---

## 10. Phased plan with gates (`design §369–380`)

Each phase item becomes a bounded task brief before an agent starts (`design §62–85`); the plan is a
map, not a work order.

| Phase | Goal | Gate (binary) |
|---|---|---|
| **0 — Crux de-risk** ✅ **DONE 2026-06-01** | **(0a)** ✅ JSM builds + runs on this box; real pad → `S=SPACE`/`ZR=LMOUSE` observed at **evdev** (~1–3 ms). **(0b)** ✅ Steam Input driven by the real pad; F9 binding observed at **XI2/Wayland seat** (not evdev). | **MET (with fork):** real JSM emits at evdev **and** real Steam Input emits an observable event — but on **different planes**. R1 forked the observation plane per lane (§6) rather than failing. |
| **1 — Tracer bullet** | One `uinput` trace → both lanes → **one delta** on `S=SPACE`, classify `exact`. | One cross-runtime delta from one trace; Windows repeated or blocked. |
| **2 — Walk the quick wins** | `/tdd` vertical slices over the seven `vdf` quick wins (keyboard/mouse-output ones first per §5); build comparator/normalizer only as far as each slice needs. The `ArcRaiders.safe.txt` ⇄ `jyro_v13.vdf` pair supplies ready mappings. | Quick wins trace-classified; comparator/normalizer handle digital + analog + basic timing. |
| **3 — Artifact contracts** | Lock schemas (trace, event, delta, loss, cycle-history, run-manifest, KB note); retrofit Phases 1–2 artifacts. | Each schema has a validating example; prior artifacts migrated. |
| **4 — Adversarial set #1** | The four `vdf` gotchas as adversarial traces (timed `remove_layer` "Click layer", global `HOLD_PRESS_TIME`, Local-Space yaw-roll blend, two-action-set swap). Exercise "green = honest classification." | Each gotcha trace-classified; every divergence from the audit's static grade documented. |
| **5 — Harden harness** | Generalize both lanes; repeatable run orchestration emitting the full artifact set from one trace. | One orchestration run emits all artifact types. |
| **6 — Gyro lane** | **(6a)** injection spike (R2: native-8BitDo `uhid` spoof; fallback headless `JslWrapper`); **(6b)** declare canonical gyro profile (§8); **(6c)** trace `gyro_to_mouse` + Local-Space gotcha → mouse-delta at evdev; gyro tolerance model. | Gyro observed end-to-end through real runtimes with a tolerance model; gyro classifications trace-backed. |
| **7 — Headless acceleration** | Synthetic `JslWrapper`, output recorders, deterministic time (`design §291–338`). May be the primary input path for some gyro cases — but cannot **promote** canonical behavior; real runtime certifies. | Each headless feature class matches real JSM within Phase-3 tolerances before acceleration use. |
| **8 — Knowledge base** | Lab-notes from runs; promote trace-verified JSM + Steam behavior + equivalence rules; capability matrix. | Promotion requires evidence-backed entries + documented conflict handling. |
| **9 — Converter (close the loop)** | Fork `vdf_clean.py` + audit out of `vdf/`; JSM emitter → loss classifier (trace-verified rules) → repair loop (`/tdd`: red trace → converter green **or** classify) → Windows regression → holdout suite. Run all of `jyro_v13.vdf`; classify every mechanic **by trace**, and compare against `ArcRaiders.*.txt` as the human-authored baseline. Later: JSM→Steam. | Converter cycles produce candidate config + loss + cycle-history + improvement-or-classify rationale per feature; no unaccepted regression; holdout failures reported. |

---

## 11. First executable task (Phase 0 — full brief)

To the readiness contract (`design §62–85`).

- **Owner role:** Validator agent.
- **Inputs:** this plan; `~/Projects/JangsJyro-JSM` @ `branch-a-port`; that fork's
  `docs/superpowers/2026-05-03-linux-build-reproduction-handoff.md` and `linux-environment-setup-ubuntu.md`;
  `findings/gyro_hid.md`; the per-turn system fingerprint.
- **Outputs (provisional, labeled):** under `runs/<UTC-timestamp>-phase0-oracle-feasibility/`:
  `environment.txt`, `configure.log`, `build.log`, `smoke.config`, `steam-probe.md`, `result.md`, and a
  patch file for the four deltas if they get committed to the fork.

**Build state verified on this box (2026-05-31):**
- Toolchain: **gcc 16.1.1**, **clang 22.1.6**, **CMake 4.3.3**. gcc is *newer* than the 15.2.0 that hit
  the gcc-16 + SDL3-on-Wayland internal-compiler error → **clang-for-C is mandatory here** (R5: watch CMake 4).
- SDL3 deps present **except `hidapi`** (install it). `xscrnsaver` (the handoff's first failure point)
  is already satisfied.
- **The four handoff patches are NOT in the tree** — all must be (re)applied: `#include <chrono>` in
  `JoyShockMapper/include/Gamepad.h`; `#include <algorithm>` in
  `JoyShockMapper/src/TriggerEffectGenerator.cpp`; `return false;` in the empty `isInitialized` stub of
  `src/linux/Gamepad.cpp` and the four empty stubs of `src/linux/Whitelister.cpp`. (Real, safe,
  non-semantic; commit them to the fork.)

- **Commands** (verify before running; login shell is **fish** so interactive `set -x VAR val`, not
  `export`; committed scripts use `#!/usr/bin/env bash`; install verb is `pacman -S`, AUR via `paru`):
  ```bash
  # deps (translate the fork's Ubuntu/apt notes → Arch; hidapi is the known gap)
  sudo pacman -S --needed hidapi   # plus: verify gtkmm3, libayatana-appindicator, libevdev, libusb, sdl deps
  # build the fork — clang for BOTH C and C++ (avoids the gcc-16 + SDL3 Wayland ICE); clean tree
  JSM=~/Projects/JangsJyro-JSM
  cmake -S "$JSM" -B "$JSM/build-linux" -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
  cmake --build "$JSM/build-linux" -j
  # expected binary: $JSM/build-linux/JoyShockMapper/JoyShockMapper
  # fallback if Wayland C source still ICEs: add -DSDL_WAYLAND=OFF (JSM uses SDL for input, not its UI)
  ```
  ```text
  # smoke.config (keyboard/mouse output only — Linux virtual-gamepad output is stubbed, §5)
  RESET_MAPPINGS
  S = SPACE
  ZR = LMOUSE
  ```
  - **0a observe:** synthetic `S`/`ZR` press-release via `uinput`; capture at evdev one `SPACE` and one
    left-mouse down/up pair (count + order exact; timing recorded, not gated).
  - **0b observe:** bind the equivalent Steam Input action for the same synthetic controller; confirm an
    evdev-observable emission; record the device-claim interaction.
- **Host assumptions:** this box; `uinput` module loaded + `/dev/uinput` accessible; user in the input
  group (re-login if newly added); udev rule for JSM virtual devices; Steam installed.
- **Acceptance:** completed configure/build; located binary; attempted runtime smoke on **both** lanes;
  `result.md` states pass/fail/blocked per lane.
- **Stop & escalate if:** a *semantic* JSM change seems required (→ semantic-change proposal, do not
  proceed); Steam Input can't be observed at evdev with usable fidelity (→ R1 fork); device access /
  dependency install falls outside this brief.

---

## 12. Risk register

- **R1 Steam observability** — ✅ **RESOLVED (Phase 0b, 2026-06-01):** observable at **XI2/Wayland seat**,
  not evdev → per-lane plane-fork, oracle intact. Followup (secondary): X11-session / stable-Steam retest.
- **R2 gyro injection** — Phase 6; de-risked via native-8BitDo `uhid` spoof.
- **R3 Linux→Windows transfer** — repeat each gate on Windows or block.
- **R4 tolerance models** — per feature class.
- **R5 CMake 4.3.3 compat** — watch CPM sub-deps at configure.
- **Linux virtual-gamepad output is stubbed** — virtual-controller-output mappings are Windows-only
  until the Linux `Gamepad` is implemented (non-semantic platform glue).
- **KB promotion** — real-runtime-evidence-only; the `vdf` audit + `ArcRaiders.*.txt` enter as
  hypotheses, never canonical.
- **RESOLVED:** JSM Linux build (recipe known); Ultimate 2 classification (first-class type);
  SDL3+HIDAPI gyro plumbing (in place); Windows SDL-target compile (fixed in the fork).

---

## 13. Repo layout & where things go

New top-level dirs this plan introduces: `runs/` (per-run artifacts), `kb/` (`canonical/` + `lab-notes/`).
JSM is **not** vendored here — it lives in the sibling repo `~/Projects/JangsJyro-JSM` and is referenced
by URL + SHA (`Jangs-Lab/CLAUDE.md`: no cross-repo symlinks). Existing routing (`Gamepad-Lab/CLAUDE.md`)
unchanged: durable facts → `findings/`; raw artifacts → `reference/<topic>/`; diagnostic scripts →
`tools/` + a line in `tools/README.md`. **`vdf/` is forked *out of*, never expanded in place.**
**`vision/` is never mutated.**

---

## 14. Cross-references

- JSM source: `https://github.com/JangMan-J/JangsJyro-JSM.git` @ `branch-a-port` (local
  `~/Projects/JangsJyro-JSM`). Lineage: Electronicks/JoyShockMapper + ceski (@ceski-1) + JangMan.
- Build recipe + runtime notes: that fork's `docs/superpowers/2026-05-03-linux-build-reproduction-handoff.md`,
  `linux-environment-setup-ubuntu.md`, `plans/2026-04-29-jsm-linux-feasibility.md`.
- A-B pair: `vdf/reference/jangman's jyro_v13.vdf` (Steam) ⇄ fork `configs/ArcRaiders.{safe,experimental}.txt` (JSM).
- Converter front-end + playbook: `vdf/README.md`, `vdf/translation_audit.md`, `vdf/vdf_clean.py`.
- Canonical hardware facts: `findings/gyro_hid.md`.
- Preserved design: `vision/INDEX.md` + `vision/2026-04-29-gamepad-mapper-conversion-lab-design.md`.
- Execution discipline: `~/.claude/skills/tdd/SKILL.md` (`/tdd`).
