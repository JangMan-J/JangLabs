# Gamepad Mapper Conversion Lab Design

## Purpose

Build an agent-first lab for converting gamepad mapper configurations between Steam Input and JoyShockMapper (JSM), starting with Steam Input to JSM and preserving a path for JSM to Steam Input later.

The lab exists to measure behavior, not just syntax. Given the same controller input trace, the system compares what real Steam Input emits with what real JSM emits from a candidate converted config. The final product is useful only if generated JSM configs behave closely enough in real JSM, especially on Windows.

## Design Goals

- Convert Steam Input layouts to clean JSM configs, with no explanatory comments in the generated config.
- Preserve bidirectional architecture so JSM to Steam Input can be added later.
- Use real Steam Input and real JSM as the authoritative behavioral oracle.
- Let agents iterate independently through structured artifacts rather than human inspection.
- Track exact, bounded approximation, degraded approximation, unsupported, and requires-user-choice results per feature.
- Record current, previous, and best-known error for each behavior across cycles.
- Support adversarial trace generation to expose failures and improve coverage.
- Persist learned mapper and controller behavior in reference files with evidence links.
- Validate Linux lab results against Windows early, before serious converter work.

## Non-Goals

- Do not rewrite JSM mapping semantics to make tests pass.
- Do not treat headless JSM as the source of truth.
- Do not rely on a single global score to accept conversion changes.
- Do not require touchpad or adaptive trigger support for the first canonical profile.
- Do not make generated JSM configs carry explanation or diagnostics.

## Core Architecture

The lab has two mapper lanes:

- Reference lane: runs the source mapper config.
- Candidate lane: runs the generated target mapper config.

For Steam Input to JSM, Steam Input is the reference and JSM is the candidate. For JSM to Steam Input, the roles are reversed.

Main components:

- Trace runner: emits deterministic virtual controller input.
- Steam Input lane: runs real Steam Input against the trace.
- JSM lane: runs real JSM against the trace.
- Output observer: captures keyboard, mouse, virtual gamepad, motion output, and later haptics/control signals when observable.
- Event normalizer: converts mapper-specific output into canonical typed events.
- Comparator: computes behavior deltas between reference and candidate event streams.
- Converter: generates candidate configs and structured loss reports.
- Knowledge base: stores observed and promoted mapper semantics for future agent work.

Real Steam Input versus real JSM comparison remains authoritative. Headless JSM can accelerate iteration only after parity with real JSM is proven for a feature class.

## Agent Roles

The lab is designed for isolated agents that receive small assignments with limited context. These are implementation roles, not fixed processes:

- Converter agent: changes Steam-to-JSM or JSM-to-Steam conversion rules and emits candidate configs.
- Validator agent: runs configured trace suites, compares reference and candidate event streams, and writes delta/loss/cycle artifacts.
- Adversarial trace generator agent: creates trace files intended to expose behavioral differences between Steam Input and JSM. It reads config features, previous deltas, knowledge-base notes, and trace schemas, then writes versioned trace files and trace-suite manifests.
- Knowledge curator agent: reviews lab notes and promotes evidence-backed behavior notes into canonical references.

The adversarial trace generator is a required system component. It must produce concrete trace artifacts that the converter and validator use; it is not just a review persona or commentary style.

## Implementation Readiness Rules

The phase plan is not itself an executable work order. Before an isolated agent starts any phase item, the assignment must include a task brief with:

- Owner role.
- Input files and prior artifacts the agent may read.
- Output files the agent must write.
- Exact commands when known.
- Required host environment and hardware assumptions.
- Acceptance criteria.
- Stop and escalation criteria.
- Run artifact location.

Agents must not turn broad phase labels such as "generalize lane" or "add comparator" into open-ended implementation work. If a task cannot be reduced to bounded inputs, outputs, and acceptance checks, the agent should write a smaller task brief first.

Default phase ownership:

- Feasibility and runtime harness tasks: Validator agent.
- Artifact schema tasks: Validator agent.
- Headless JSM acceleration tasks: Validator agent, with JSM source changes isolated behind test modes.
- Trace-suite tasks: Adversarial trace generator agent.
- Knowledge-base tasks: Knowledge curator agent.
- Converter parser, emitter, and repair-loop tasks: Converter agent.

## First Executable Task Contract

The first executable assignment is the Phase 1a/1b JSM Linux feasibility spike. It exists to answer whether JSM can be built and minimally observed on Linux without changing mapping behavior.

Target host:

- Prefer a real Linux desktop or Linux VM with real input/output device access.
- WSL may be used only for build-only discovery unless a task brief explicitly accepts its runtime limitations.
- Report distro, kernel, compiler, CMake version, generator, installed dependency state, `/dev/uinput` access, `/dev/input` access, desktop/session type if runtime is tested, and whether the agent installed any dependencies.

Baseline build commands:

```sh
cmake -B build-linux -S . -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++
cmake --build build-linux
```

Expected binary:

- `build-linux/JoyShockMapper/JoyShockMapper`
- If the binary path differs, record the actual path and the CMake target that produced it.

Minimal smoke config:

```text
RESET_MAPPINGS
S = SPACE
ZR = LMOUSE
```

Minimal smoke behavior:

- Press and release `S`; observe one `SPACE` down/up pair.
- Press and release `ZR`; observe one left mouse down/up pair.
- For this first smoke test, event count and event order are exact checks. Timing is recorded but not used as a pass/fail tolerance unless the observation method itself depends on a timeout.

Required run artifacts:

- Store all artifacts under `docs/superpowers/runs/<UTC timestamp>-linux-jsm-feasibility/`.
- Write `environment.txt`.
- Write `configure.log`.
- Write `build.log`.
- Write `smoke.config`.
- Write `result.md`.
- If code changes were needed, write `changes.patch` or link the exact commit.

Success requires a completed configure/build, a located JSM binary, an attempted runtime smoke test, and a clear `result.md` stating pass, fail, or blocked. Stop and escalate if semantic mapping changes appear necessary, if the host cannot support runtime observation, or if dependency installation/hardware access is outside the task brief.

## Generated Artifacts

Each run should produce structured artifacts that agents can consume without prose interpretation:

- `run.manifest.json`: environment, OS, mapper versions, controller profile, trace suite, source and candidate hashes.
- `reference.events.jsonl`: normalized event stream from the reference mapper.
- `candidate.events.jsonl`: normalized event stream from the candidate mapper.
- `delta.json`: exact/tolerant comparison results and behavior errors.
- `loss.json`: conversion classification and explanation by feature.
- `cycle-history.json`: previous/current/best metrics and stop reasons.
- `report.md`: human summary derived from structured artifacts.
- `candidate.config`: clean generated target config.

The generated target config is runnable output only. Explanations live in reports.

Before Phase 3 defines stable schemas, Phase 1 and Phase 2 may write provisional text or JSON artifacts in the run directory. Provisional artifacts must be clearly labeled and later normalized or replaced by schema-backed artifacts. Prose notes are evidence, not machine-readable truth.

## Result Classifications

Each converted behavior is classified independently:

- `exact`: same behavior within exact-match rules.
- `bounded_approximation`: measurable difference, within useful tolerance.
- `degraded_approximation`: intent preserved but precision, timing, or interaction model is meaningfully worse.
- `unsupported_omitted`: no meaningful target equivalent.
- `requires_user_choice`: multiple plausible translations and no safe default.

Approximations are allowed when they are likely useful to a user and when the system can describe the loss. Approximation quality is judged by trace evidence, not agent confidence.

## Cycle Metrics

Every comparable behavior needs a stable identity and cycle history:

- `feature_id`
- `trace_id`
- `metric`
- `current_error`
- `previous_error`
- `best_error`
- `trend`
- `classification`
- `confidence`
- `stop_reason`

Stop reasons include:

- exact
- under tolerance
- plateaued
- oscillating
- unsupported
- max cycles
- blocked by mapper capability
- blocked by regression risk

This lets agents know whether a degraded behavior is improving, regressing, or pragmatically stuck.

Until Phase 3 defines formal schemas, every metric must state its unit, comparison rule, and legal direction of improvement. `trend` values are limited to `new`, `improved`, `regressed`, `unchanged`, and `incomparable`. New `stop_reason` values require an artifact-contract update.

## Validation Policy

Acceptance is conservative and per-feature:

- Real Steam Input vs real JSM is authoritative.
- Headless tests are acceleration only.
- Easy features do not compensate for broken hard features.
- Regressions block acceptance unless explicitly justified.
- Trace suites are versioned.
- Tuning traces and holdout traces are separated.
- Unsupported and degraded behavior must be exposed directly.
- Reports must not hide coverage gaps.

No central scoreboard should determine success. Adversarial search is useful, but score-chasing is not part of the acceptance path.

Every accepted change must include a validation statement naming the exact traces, platforms, mapper versions, and feature IDs it covers. Regressions are not accepted because another feature improved. A justified regression must name the affected feature, the user-visible loss, the reason it is unavoidable, and the follow-up task that owns it.

## Adversarial Trace Generation

Adversarial agents generate traces that expose behavioral differences. They do not define success by themselves.

Trace types:

- Baseline traces for ordinary input.
- Feature-directed traces for activators, layers, chords, gyro, sticks, and triggers.
- Boundary traces around timing windows, deadzones, thresholds, and release order.
- Composition traces combining mode shifts, chords, gyro enable states, and analog movement.
- Mutation traces with small perturbations of timing and axis values.
- Regression traces for previously discovered deltas.
- Holdout traces withheld from converter tuning.

Accepted traces are immutable within a versioned suite. New adversarial traces can reveal failures, but cannot rewrite prior results.

Each trace suite must include:

- `trace-suite.manifest.json`
- Versioned trace files.
- Targeted feature IDs.
- Access level: `tuning`, `regression`, or `holdout`.
- Parent suite or mutation source when applicable.
- A short intent field explaining what behavioral difference the trace is meant to expose.

Converter agents may receive tuning and regression traces. Holdout trace contents are withheld from converter task briefs; validators may report holdout failures and aggregate deltas without giving the converter a path to tune directly to the hidden trace.

## Controller Profile Strategy

The converter should target mapper-neutral semantic controls, not a single physical controller. The first validation profile should still be concrete and repeatable.

Canonical v1 profile:

- Extended gyro gamepad inspired by 8BitDo Ultimate 2 Wireless.
- Standard face buttons, d-pad, shoulders, stick clicks, start/back/home/capture.
- Analog sticks and triggers.
- Gyro and accelerometer.
- Four extra rear/aux buttons.

Excluded from v1:

- Touchpad finger position.
- Touchpad as a special surface.
- Adaptive trigger force feedback.
- Microphone-button-specific behavior.

Later profiles should check that the converter is not accidentally tied to one device normalization path.

Before analog, trigger, gyro, or accelerometer behavior can be accepted, the canonical profile must declare axis names, neutral values, ranges, units, coordinate frame, sample cadence, and timestamp source. Digital button tests may proceed earlier because their state model is only pressed/released.

## Platform Strategy

Linux is attractive for automation, but it must prove that its results transfer to Windows. Windows validation happens early.

Rules:

- Linux may become the main automation lab only after early parity gates.
- Windows must certify release confidence for generated JSM configs.
- Platform differences are recorded as platform deltas, not hidden as converter failures.
- JSM Linux changes are allowed only for build, platform glue, test instrumentation, and output/input recording, not mapping semantics.

## Non-Semantic Change Boundary

Allowed JSM changes for the lab:

- Build files, dependency detection, and platform glue.
- Test-only headless entry points behind explicit flags or separate targets.
- Input recording, output recording, logging, and trace emission.
- Synthetic input providers that feed the existing runtime path.
- Dependency version and compiler compatibility fixes that do not alter mapper behavior.

Prohibited without a dedicated semantic-change proposal:

- Changing command parsing meaning.
- Changing default settings.
- Changing button, stick, trigger, gyro, chord, modeshift, tap, hold, double-press, or timing behavior.
- Changing `DigitalButton`, `JoyShock`, `Mapping`, `SettingsManager`, or output semantics to make lab tests pass.
- Relabeling inputs or outputs in a way that hides a behavioral mismatch.

Any task that touches shared mapping code must include a written note explaining why the change is non-semantic and which real-runtime parity check protects it.

## Headless JSM

Headless JSM is a test execution mode for JSM, not a reimplementation.

It should:

- Load normal JSM configs through the real parser.
- Replace SDL/JSL device discovery with synthetic controller frames.
- Feed frames into the existing JSM runtime path.
- Replace OS keyboard/mouse output with event recording.
- Replace virtual controller output with event recording.
- Use deterministic trace time where possible.
- Emit normalized JSONL events.

It should share:

- Config parsing.
- Command semantics.
- Button mapping logic.
- Tap, hold, double press, simultaneous press, diagonal press, chord, and modeshift behavior.
- Stick math.
- Gyro math.
- Trigger thresholds.
- Virtual controller mapping decisions.
- Defaults and settings behavior.

It does not prove:

- Steam Input behavior.
- OS-level routing.
- Windows/Linux mouse and scancode quirks.
- SDL device discovery.
- Real controller HID behavior.
- Focus, tray, autoload, and user-session behavior unless explicitly tested.

Existing JSM source already has useful seams:

- `JslWrapper` abstracts input.
- `joyShockPollCallback` is the main input-processing entry point.
- `JoyShock` owns controller processing.
- `DigitalButton` owns button state machines.
- `Gamepad` abstracts virtual controller output.
- `pressKey`, `moveMouse`, and `setMouseNorm` form the keyboard/mouse output boundary.
- The command/setting system already parses JSM config behavior.

Missing pieces include a headless CLI, trace reader, synthetic `JslWrapper`, deterministic time injection, output recorders, and JSONL emission.

The first headless slice is intentionally narrow: load a normal config, feed digital button down/up frames for `S = SPACE` and `ZR = LMOUSE`, and record the resulting keyboard/mouse events. Stick, gyro, trigger thresholds, timing windows, and virtual controller output remain disabled for acceleration until the first slice matches real JSM and each later feature class earns its own parity result.

## Reference Knowledge Base

The lab should persist learned behavior so agents can answer "what does this control or mapper function do?" without rediscovering it.

Use two knowledge layers:

- `kb/lab-notes/`: agent-written observations linked to evidence. Mutable and noisy.
- `kb/canonical/`: promoted semantics only. Used by converters by default.

Reference files:

- `kb/canonical/control-catalog.json`
- `kb/canonical/mapper-functions.steam.json`
- `kb/canonical/mapper-functions.jsm.json`
- `kb/canonical/equivalence-rules.jsonl`
- `kb/canonical/capability-matrix.json`
- `kb/lab-notes/observations.jsonl`

Each entry must include provenance: run IDs, trace IDs, mapper version, platform, device profile, confidence, and last validation date.

Lab notes may suggest hypotheses. Canonical files guide conversion decisions.

Promotion rules:

- Any agent may append lab notes if they include provenance.
- Canonical entries require real-runtime evidence, schema validation, conflict checks, and a last-validated date.
- Headless-only evidence may support a hypothesis but cannot promote a canonical mapper behavior.
- Conflicting observations remain in lab notes until a validator task resolves or scopes the conflict.

## Phase Gate Criteria

Each phase has a gate that must be satisfied before expensive downstream work depends on it:

- Phase 1 gate: Linux JSM build result, Linux smoke result or block reason, matching Windows smoke result, and `linux-lab-decision.md` choosing `linux-main`, `linux-build-only`, or `linux-rejected`.
- Phase 2 gate: one controlled trace drives real Steam Input and real JSM equivalent mappings, both outputs are observed as typed events, a delta is written, and Windows is repeated or explicitly blocked.
- Phase 3 gate: trace, event, delta, loss, cycle-history, run-manifest, and knowledge-base schemas have validating examples.
- Phase 4 gate: one repeatable orchestration run produces manifest, reference events, candidate events, delta, loss, and report artifacts from the same trace.
- Phase 5 gate: each headless feature class matches real JSM within Phase 3 tolerances before that class is allowed for acceleration.
- Phase 6 gate: the adversarial trace generator writes versioned suites and manifests that the validator can consume, with tuning/regression/holdout access rules documented.
- Phase 7 gate: canonical knowledge promotion requires evidence-backed entries and documented conflict handling.
- Phase 8 gate: converter cycles produce candidate config, loss report, cycle-history update, and an improvement or stop rationale per changed feature, with no unaccepted regression.

## Human-Readable Phase Plan

### 1. Feasibility Gates

1a. Build and run JSM on Linux with non-semantic changes only.

1b. Run minimal real JSM behavior test on Linux.

1c. Run matching minimal real JSM behavior test on Windows.

1d. Decide whether Linux can be the main automation lab.

### 2. Steam/JSM A-B Proof

2a. Prove Steam Input can be driven by controlled virtual input.

2b. Prove Steam Input output can be observed as typed events.

2c. Run one hand-authored equivalent Steam/JSM mapping.

2d. Compare outputs from both real runtimes.

2e. Repeat or certify the tiny A-B proof on Windows before building expensive general infrastructure.

### 3. Artifact Contracts

3a. Define trace format.

3b. Define normalized event format.

3c. Define delta, loss, and cycle-history formats.

3d. Define run manifest and environment capture.

3e. Define knowledge-base note and promotion formats.

### 4. Real Runtime Harness

4a. Generalize Steam lane.

4b. Generalize JSM lane.

4c. Add output observers.

4d. Add comparator.

4e. Add repeatable run orchestration.

### 5. Headless Acceleration

5a. Add synthetic `JslWrapper`.

5b. Add recording keyboard/mouse output.

5c. Add recording virtual gamepad output.

5d. Add deterministic trace-time control.

5e. Certify headless JSM against real JSM before use.

### 6. Trace Intelligence

6a. Add baseline traces.

6b. Implement the adversarial trace generator agent and have it write feature-directed trace files.

6c. Add boundary and mutation traces.

6d. Add regression traces.

6e. Add holdout traces.

### 7. Knowledge Base

7a. Record lab observations from runs.

7b. Promote verified JSM behavior notes.

7c. Promote verified Steam Input behavior notes.

7d. Promote equivalence rules with evidence.

7e. Maintain capability matrix.

### 8. Converter Work

8a. Steam layout parser.

8b. JSM config emitter.

8c. Loss classifier.

8d. Iterative repair loop.

8e. Windows regression suite.

8f. Later: JSM-to-Steam path.

## Open Risks

- Steam Input layout generation and runtime control may be more opaque than JSM config generation.
- Virtual controller shape may be constrained by what Steam Input and JSM reliably recognize.
- Linux automation may not transfer closely enough to Windows for some output channels.
- Mouse deltas, timing, and gyro behavior will need tolerance models.
- Headless JSM may require careful refactoring to avoid accidentally changing runtime behavior.
- Knowledge-base promotion needs strict evidence rules to avoid turning speculation into converter logic.

## Approval State

This design captures the agreed direction: a real-runtime Steam Input vs JSM behavioral lab, agent-first artifacts, early Windows parity gates, adversarial trace generation without score-chasing, a reference knowledge base, and many small isolated tasks grouped into readable phases.
