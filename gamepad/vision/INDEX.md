# Vision — concept index

The full design doc is `2026-04-29-gamepad-mapper-conversion-lab-design.md`. It was authored during a Kiro plan/task experiment that's no longer in use, but it remains the most comprehensive snapshot of the long-term direction.

This index surfaces load-bearing concepts with line anchors so future plans can cite specific sections without re-reading 492 lines.

## Thesis (lines 3–9)

Build an agent-first lab that compares **real Steam Input** against **real JSM** behaviorally — same input trace, different mappers, observable event-stream delta. **Real-runtime comparison is authoritative; headless tests are acceleration only.** Steam Input → JSM is the first direction; JSM → Steam Input is preserved as a later path.

## Core architecture (lines 29–49)

Two mapper lanes — **reference lane** runs the source mapper, **candidate lane** runs the generated target. Components: trace runner, Steam Input lane, JSM lane, output observer, event normalizer, comparator, converter, knowledge base.

## Agent roles (lines 51–60)

| Role | Owns |
|------|------|
| Converter | Steam-to-JSM / JSM-to-Steam conversion rules; emits candidate configs |
| Validator | Runs configured trace suites; writes delta / loss / cycle artifacts |
| Adversarial trace generator | Required component (not commentary). Writes versioned trace files + suite manifests |
| Knowledge curator | Promotes evidence-backed observations into canonical references |

## Implementation readiness rules (lines 62–85)

Phase labels are not work orders. Every isolated agent assignment must include: **owner role, input files, output files, exact commands when known, host/hardware assumptions, acceptance criteria, stop/escalation criteria, run artifact location.** If a task can't be reduced to bounded inputs/outputs/checks, the agent writes a smaller task brief first.

## Result classifications (lines 151–162)

Each converted behavior is classified independently:

- `exact` — matches within exact-match rules
- `bounded_approximation` — measurable difference within useful tolerance
- `degraded_approximation` — intent preserved but precision/timing/interaction model meaningfully worse
- `unsupported_omitted` — no meaningful target equivalent
- `requires_user_choice` — multiple plausible translations, no safe default

Approximation quality is judged by **trace evidence, not agent confidence**.

## Cycle metrics (lines 164–191)

Every comparable behavior carries: `feature_id`, `trace_id`, `metric`, `current_error`, `previous_error`, `best_error`, `trend` (one of `new` / `improved` / `regressed` / `unchanged` / `incomparable`), `classification`, `confidence`, `stop_reason`. Stop reasons are a fixed enum (exact, under tolerance, plateaued, oscillating, unsupported, max cycles, blocked by mapper capability, blocked by regression risk).

## Validation policy (lines 193–208)

- Real Steam Input vs real JSM is authoritative
- Easy features do not compensate for broken hard features
- **No central scoreboard.** Adversarial search useful; score-chasing is not part of the acceptance path
- Every accepted change names exact traces, platforms, mapper versions, and feature IDs it covers
- Justified regressions must name affected feature, user-visible loss, reason it's unavoidable, and follow-up task that owns it

## Adversarial trace generation (lines 210–235)

Trace types: baseline, feature-directed, boundary, composition, mutation, regression, holdout. Suites are versioned and immutable once accepted. Every suite includes `trace-suite.manifest.json`, targeted feature IDs, access level (`tuning` / `regression` / `holdout`), parent suite or mutation source, and an intent field. **Holdout trace contents are withheld from converter task briefs** — validators may report holdout failures and aggregate deltas without giving the converter a path to tune to hidden traces.

## Controller profile strategy (lines 237–258)

Target mapper-neutral semantic controls, not a single physical controller. Canonical v1 profile is an extended gyro gamepad inspired by 8BitDo Ultimate 2 Wireless. Excluded from v1: touchpad finger position, touchpad as a special surface, adaptive trigger force feedback, microphone-button-specific behavior. **Before analog/trigger/gyro/accelerometer behavior is accepted, the canonical profile must declare axis names, neutral values, ranges, units, coordinate frame, sample cadence, and timestamp source.**

## Platform strategy (lines 260–269)

Linux is attractive for automation but must prove its results transfer to Windows. Windows validation happens early. Platform differences are recorded as **platform deltas, not hidden as converter failures**. JSM Linux changes allowed only for build / platform glue / test instrumentation / output recording — **never mapping semantics**.

## Non-semantic change boundary (lines 271–289)

**Allowed JSM changes:** build files, dependency detection, platform glue, test-only headless entry points behind explicit flags, input/output recording, trace emission, synthetic input providers feeding existing runtime, dependency/compiler compatibility fixes that don't alter mapper behavior.

**Prohibited without a dedicated semantic-change proposal:** changing command parsing meaning, default settings, button/stick/trigger/gyro/chord/modeshift/tap/hold/double-press/timing behavior, `DigitalButton` / `JoyShock` / `Mapping` / `SettingsManager` / output semantics, or relabeling inputs/outputs to hide behavioral mismatch.

## Headless JSM scope (lines 291–338)

Headless JSM is a **test execution mode for JSM, not a reimplementation**. Loads normal configs through the real parser; replaces SDL/JSL device discovery with synthetic frames; replaces OS keyboard/mouse output with event recording; uses deterministic trace time. **It does not prove Steam Input behavior, OS-level routing, mouse/scancode quirks, SDL device discovery, real HID behavior, focus/tray/autoload behavior** — those still require real-runtime traces.

JSM seams already useful: `JslWrapper`, `joyShockPollCallback`, `JoyShock`, `DigitalButton`, `Gamepad`, `pressKey` / `moveMouse` / `setMouseNorm`, command/setting system. Missing: headless CLI, trace reader, synthetic `JslWrapper`, deterministic time injection, output recorders, JSONL emission.

## Knowledge base layout (lines 340–367)

Two layers:

- `kb/lab-notes/` — agent-written observations linked to evidence; mutable and noisy
- `kb/canonical/` — promoted semantics only; used by converters by default

Canonical files (per design): `control-catalog.json`, `mapper-functions.steam.json`, `mapper-functions.jsm.json`, `equivalence-rules.jsonl`, `capability-matrix.json`. Lab-notes file: `observations.jsonl`.

**Promotion rules:** anyone may append lab notes (with provenance); canonical entries require real-runtime evidence + schema validation + conflict checks + last-validated date; **headless-only evidence cannot promote a canonical mapper behavior**.

## Generated run artifacts (lines 134–149)

Each run produces: `run.manifest.json`, `reference.events.jsonl`, `candidate.events.jsonl`, `delta.json`, `loss.json`, `cycle-history.json`, `report.md`, `candidate.config`. The generated target config is **runnable output only** — explanations live in reports.

## Phase gate criteria (lines 369–380)

Each phase has a binary gate before downstream work depends on it:

| Phase | Gate |
|-------|------|
| 1 | Linux JSM build result + Linux smoke result + matching Windows smoke + `linux-lab-decision.md` (`linux-main` / `linux-build-only` / `linux-rejected`) |
| 2 | One controlled trace drives both real Steam Input and real JSM, both observed as typed events, delta written, Windows repeated or explicitly blocked |
| 3 | Trace, event, delta, loss, cycle-history, run-manifest, knowledge-base schemas have validating examples |
| 4 | One repeatable orchestration run produces all artifact types from the same trace |
| 5 | Each headless feature class matches real JSM within Phase 3 tolerances before that class is allowed for acceleration |
| 6 | Adversarial trace generator writes versioned suites + manifests the validator can consume; tuning/regression/holdout access rules documented |
| 7 | Canonical knowledge promotion requires evidence-backed entries + documented conflict handling |
| 8 | Converter cycles produce candidate config + loss report + cycle-history update + improvement-or-stop rationale per changed feature, no unaccepted regression |

## First executable task (lines 86–132)

Phase 1a/1b **JSM Linux feasibility spike**. Question: can JSM be built and minimally observed on Linux without changing mapping behavior? Target host: real Linux desktop or Linux VM (WSL is build-only unless explicitly allowed). Smoke config:

```text
RESET_MAPPINGS
S = SPACE
ZR = LMOUSE
```

Acceptance: completed configure/build, located JSM binary, attempted runtime smoke test, clear `result.md` (pass/fail/blocked). Artifacts under `runs/<UTC timestamp>-linux-jsm-feasibility/`: `environment.txt`, `configure.log`, `build.log`, `smoke.config`, `result.md`, `changes.patch` if needed.

## Open risks (lines 480–488)

- Steam Input layout generation/control may be more opaque than JSM config generation
- Virtual controller shape constrained by what Steam Input + JSM reliably recognize
- Linux automation may not transfer closely to Windows for some output channels
- Mouse delta, timing, gyro behavior need tolerance models
- Headless JSM may need careful refactoring to avoid accidentally changing runtime behavior
- KB promotion needs strict evidence rules to avoid turning speculation into converter logic

---

## How to use this index

When drafting a future plan: cite the relevant section by name + line range. Example: "Per *Validation Policy* (design doc lines 193–208), accepted changes name exact traces, platforms, mapper versions, and feature IDs."

If a future plan diverges from the vision, **annotate the divergence in the plan** rather than mutating the design doc. The doc is a snapshot; the plan can carry the diff.
