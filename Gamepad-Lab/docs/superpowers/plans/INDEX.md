# Plans — index

Implementation plans for agentic execution. Each plan uses checkbox (`- [ ]`) syntax and is meant to be executed task-by-task by a sub-skill (e.g. `superpowers:subagent-driven-development` or `superpowers:executing-plans`).

| Plan | Goal | Spec | Status |
|------|------|------|--------|
| [`2026-04-20-jsm-sdl3-viability.md`](./2026-04-20-jsm-sdl3-viability.md) | Decide whether to adopt pad → SDL3 → JSM in place of the ViGEm-DS4 bridge, gated by a static source-verification phase. | `../specs/2026-04-20-jsm-sdl3-viability-design.md` | **Phase 1 done** (verdict YELLOW); Phase 2 in progress at **Task 8** (per `../../handoffs/jsm_sdl3_viability.md`). Supersedes `2026-04-19-jsm-master-sdl3-build.md` (no longer in-tree). |
| [`2026-04-22-vdf-clean-improvements.md`](./2026-04-22-vdf-clean-improvements.md) | Extend `tools/vdf_clean.py` to emit two output files per run — conservative `clean.vdf` + aggressive `dedup.vdf`. Six new mutating passes + unittest harness. | `../specs/2026-04-22-vdf-clean-improvements-design.md` | Active. Plan and tests structurally landed; check `tools/test_vdf_clean.py` for current pass coverage. |
| [`2026-04-23-vdf-to-jsm-port.md`](./2026-04-23-vdf-to-jsm-port.md) | Cross-workspace plan: port the Arc Raiders Steam Input layout (VDF) to the JSM `branch-a-port` fork. Three artifacts in sequence — translation audit, two tiered JSM configs, `vdf_to_jsm.py` tool. | None in this lab — references `../specs/` indirectly; cross-workspace context. | Active. Translation audit landed at `../../findings/arc_raiders_vdf_to_jsm_audit.md`. |

## Other specs (no matching plan in-tree)

- `../specs/2026-04-18-claude-workflow-reference-design.md` — workflow reference design predating these plans.

## Runs directory

The design doc references `docs/superpowers/runs/<run-id>/` as the destination for per-run trace artifacts. The directory will be created on first use.
