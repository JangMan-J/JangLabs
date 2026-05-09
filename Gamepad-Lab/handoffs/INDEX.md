# Handoffs — index

Resumable session seeds. Each file is meant to let a fresh session pick up cold by reading only that file.

**Sacred — additive only.** Don't mutate existing handoffs to reflect new state. If state has moved on, write a new handoff and mark the old one superseded here.

| Handoff | Topic | Current step | Status |
|---------|-------|--------------|--------|
| [`jsm_sdl3_viability.md`](./jsm_sdl3_viability.md) | Execute the JSM + SDL3 direct-DInput viability plan; decide whether to drop the ViGEm-DS4 bridge in favor of pad → SDL3 → JSM. | **Phase 2 Task 8** — clone SDL3 at pinned SHA `5848e58` and build `testcontroller.exe` for the isolation probe. | Active |
| [`jsm_branch_a_port_state.md`](./jsm_branch_a_port_state.md) | Port 8BitDo Ultimate 2 extended-button support into JSM via cherry-picks; live-verified 21/21 inputs (17 standard + 4 paddles) on 2026-04-22. | **Step 8** (upstream PR prep) — paused per user request. Step 7 workspace-artifact landing complete; Step 6 (timer QoL) done 2026-04-23. | Paused |
| [`arc_raiders_inventory_drag.md`](./arc_raiders_inventory_drag.md) | Diagnose gyro-freeze race during Arc Raiders inventory click-drag. Layer-override and the 50 ms-delayed remove cycle are the mechanism under test. | Hardware/binding setup documented through §3 in the file; test execution + analysis (§6/§7) are the next blocks to fill in. | Active |

## Plan-of-record links

- `jsm_sdl3_viability` ↔ `docs/superpowers/plans/2026-04-20-jsm-sdl3-viability.md`
- `jsm_branch_a_port_state` ↔ user plan at `%USERPROFILE%\.claude\plans\alright-claude-i-want-buzzing-mccarthy.md` (outside this repo)
- `arc_raiders_inventory_drag` ↔ no formal plan; investigation lives in this handoff plus the Arc Raiders findings.

## Conventions

- TL;DR at the top, current-status table next, then enough environmental context that a cold session can act.
- When promoting verified observations out of a handoff, write them to `findings/` and link from there back to the handoff.
