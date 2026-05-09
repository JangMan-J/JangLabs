# Findings — index

Append-only durable knowledge. Edit only to mark superseded with a forward link or to fix factual errors. Prefer adding a new file over rewriting an old one.

## Steam Input behavior

| File | Gist |
|------|------|
| [`steam_input.md`](./steam_input.md) | Behavioral observations: gyro modes, layer-override semantics, trigger thresholds, timing quirks. The substrate finding for any Steam-Input-side claim. |
| [`arc_raiders_vdf_inventory.md`](./arc_raiders_vdf_inventory.md) | Inventory of VDF sections, groups, and bindings in the tuned Arc Raiders profile (v13). |

## VDF → JSM translation

| File | Gist |
|------|------|
| [`arc_raiders_vdf_to_jsm_audit.md`](./arc_raiders_vdf_to_jsm_audit.md) | Translation audit: mapping Steam Input concepts (layers, activators, chords) to JSM equivalents. Documents gaps — layer override is all-or-nothing, no analog-trigger conditional, no gyro-freeze delay. |

## JSM + SDL3 substrate

| File | Gist | Status |
|------|------|--------|
| [`jsm_sdl3_verified.md`](./jsm_sdl3_verified.md) | Promotion summary — JSM SDL3 integration + 8BitDo branch-a-port adopted as the baseline. | Active |
| [`jsm_sdl3_source_verification.md`](./jsm_sdl3_source_verification.md) | Phase 1 static source audit; pinned SHAs (JSM `bb69784`, SDL3 `release-3.4.4` / `5848e58`); 8BitDo HIDAPI driver presence verified. Verdict YELLOW with 3 watch items. | Active |
| [`jsm_sdl3_live_verification.md`](./jsm_sdl3_live_verification.md) | Live button-firing on 8BitDo Ultimate 2 post-branch-a-port; 21/21 verified, references `reference/JSM_JangManJ/run2.txt`. | Active |
| [`jsm_wrapper_substrate.md`](./jsm_wrapper_substrate.md) | Earlier recommendation on substrate choice (build JSM master, don't wrap). | **Superseded 2026-04-20** by `jsm_sdl3_verified.md` |

## Hardware / HID

| File | Gist |
|------|------|
| [`gyro_hid.md`](./gyro_hid.md) | Raw HID frame structure for the 8BitDo Ultimate 2 gyro: byte indices, coordinate frame, sample rates across DInput / NS / raw HID. v1.03+ firmware required for the 34-byte sensor-bearing report. |

## Cross-reference

- Live-verification artifacts: `../reference/JSM_JangManJ/`
- Pinned-SHA notes echo back to handoffs: `../handoffs/jsm_sdl3_viability.md` and `../handoffs/jsm_branch_a_port_state.md`.
