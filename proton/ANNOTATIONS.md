# `data/annotations.json` — schema & authoring guide

This file is the **semantic layer** of `protondb-tuner`. The statistical engine decides *which*
launchOptions parameters are empirically associated with a game (frequency among `verdict=yes`
reports, recency, GPU-vendor bucketing). This knowledge base supplies the part that can't be
derived from the data dump: **what each parameter means, why it's there, and how risky it is.**

The recommender joins the two: engine says "DXVK_ASYNC shows up a lot for game X" → this KB says
"that advice is superseded by GPL since DXVK 2.0, downrank it." Without the semantic layer the
recommender would happily parrot stale or dangerous strings.

> Author note: every record is written from primary docs (Proton/DXVK/VKD3D-Proton READMEs, Mesa
> docs, Arch Wiki, NVIDIA driver READMEs, upstream issues) — see each record's `doc_sources`.
> Records were **not** inferred from a single ProtonDB report.

---

## Top-level shape

```jsonc
{
  "schema_version": "1.0",
  "generated": "YYYY-MM-DD",
  "title": "...",
  "purpose": "...",                 // prose: what this file is for
  "consumption_notes": [ ... ],     // how a recommender should read it
  "user_environment": { ... },      // the box this KB is tuned for (see below)
  "enums": { ... },                 // closed value sets — the source of truth for validation
  "field_glossary": { ... },        // one-line definition of every parameter field
  "parameters": [ { ...record... }, ... ]
}
```

A consumer should:

1. Load `parameters` as a flat list.
2. For each engine-normalized key, test it against each record's `match.regex` (case-insensitive,
   Python `re`), falling back to `match.canonical_key` / `match.aliases` for an exact-token match.
3. Validate every enum-typed field against the top-level `enums` block; anything outside those sets
   is a data error (the repo ships a check — see "Validation" below).
4. Use `obsolescence.status ∈ {superseded, obsolete, default-now}` and low `confidence` as
   **downrank** signals; use `parity_risk` and `intent_type` to drive the explanation and warnings.

---

## Engine integration (`engine_integration` block)

`scripts/common.py` emits param IDs shaped `namespace|key|value`. The top-level `engine_integration`
block in the JSON is the **join contract**; apply each record's `match.regex` to the engine's `key`
(and, for the `proton`/`shellhack` namespaces, the `value`). Summary of the mapping:

| engine namespace | engine `key` example | this KB `kind` | notes |
|---|---|---|---|
| `env` | `DXVK_ASYNC`, `PROTON_USE_WINED3D` | `env` | match on key; values are normalized (`<custom>` for BUCKET_VARS, `<num>` for NUM_VARS, comma-sets sorted) |
| `wrapper` | `gamemoderun`, `prime-run`, `obs-vkcapture` | `wrapper` | `game-performance` has its **own** record (CachyOS wrapper, NOT gamemoderun); `mangoapp`→mangohud, `primusrun`/`optirun`→prime-run/offload; `umu-run`/`steam-run`/`pressure-vessel-wrap` = sniper/RT3 container entry (benign) |
| `arg` | `-dx11`, `-useallavailablecores`, `-nobattleye` | `game-arg` | lowercased; regexes anchor on leading dash/slash |
| `shellhack` | classification token (eval/sed/exec/…) | `launch-pattern` | → `launch_pattern_exe_swap` |
| `proton` | `variant:experimental`, `custom`, `notes_version` | `proton-runtime` | regexes match both these tokens and human spellings |

**Precedence:** a numbered version token (e.g. `Proton-7.0`) can match both `proton_variant_pinned_older`
and `proton_variant_official_stable`. Resolve by major version: `<=8` → pinned_older, `>=9` →
official_stable. GE/CachyOS build names resolve to their dedicated records despite embedding digits.

**Anti-cheat asymmetry (`anti_cheat_guidance` block):** the JSON carries a top-level
`anti_cheat_guidance` block the recommender must honor. Gate on online-vs-offline first. Where a
title's anti-cheat is developer-enabled and accepted on Linux (e.g. ARC Raiders — EAC, Steam Deck
Verified, works online on Proton 10), it runs out of the box: **do not** synthesize an EAC/BattlEye
flag (its absence is expected) and **never** recommend a bypass (`-eac-nop`, `-noBE`, exe-swap) for
online play — that risks an account ban and gains nothing. Bypass tokens are acceptable only for
offline/singleplayer of titles whose anti-cheat is not Linux-accepted.

> Implementation note: build names are normalized glued (`GE-Proton10-25`), so regexes that target
> them must **not** require a trailing `\b` after `proton` (there is no word boundary between
> `Proton` and `10`). The shipped GE regex was written accordingly.

---

## `user_environment`

Records carry a `hardware_scope`; this block says what the target box actually is so the recommender
can suppress irrelevant advice. Current target:

| field | value |
|---|---|
| `gpu` | NVIDIA GeForce RTX 4090 (Ada, laptop) |
| `nvidia_kernel_module` | open kernel module (`nvidia-open`), 595.71.05 |
| `topology` | Intel iGPU + NVIDIA dGPU **hybrid laptop** (Optimus / muxless; PRIME render offload) |
| `display_server` | Wayland |
| `desktop` | KDE Plasma |
| `distro` | CachyOS (Arch-based) |

Implications baked into `scope_implications`: `amd-only`/`mesa-only` RADV/ACO records are **not**
applicable (no AMD dGPU); `nvidia-only`, `frame-generation`, `upscaling` (DLSS), `gpu-offload-hybrid`,
and `display-wayland` records are highly relevant.

---

## Per-parameter record

```jsonc
{
  "id": "dxvk_async",                       // stable snake_case PRIMARY KEY (never reused)
  "match": {
    "canonical_key": "DXVK_ASYNC",          // the exact var/flag/wrapper token
    "aliases": ["dxvk.enableAsync", ...],   // other spellings seen in launchOptions
    "regex": "(?i)\\bDXVK_ASYNC\\b|..."     // Python regex to map the engine's normalized key
  },
  "kind": "env",                            // structural type (see enum)
  "value_type": "boolean",                  // shape of the value (see enum)
  "values": ["0","1"],                      // OPTIONAL: documented accepted values
  "description": "plain-language what-it-does, self-authored",
  "intent_type": "how",                     // how | why | both  (see below — the core distinction)
  "intent_note": "...",                     // REQUIRED for why/both: names the external mechanism
  "category": "shader-cache-stutter",       // coarse group (see enum)
  "effect_axes": [                          // which axes it moves + direction
    { "axis": "performance", "direction": "improves" },
    { "axis": "visual-fidelity", "direction": "degrades" }
  ],
  "parity_risk": "low",                     // low | medium | high
  "parity_risk_rationale": "one-line why",
  "obsolescence": {
    "status": "superseded",                 // current | partial | superseded | obsolete | default-now
    "since": "DXVK 2.0",
    "note": "..."
  },
  "hardware_scope": "universal",            // see enum
  "confidence": "high",                     // documentation strength for THIS annotation
  "doc_sources": ["https://..."]
}
```

### Field reference

| field | meaning |
|---|---|
| `id` | Stable `snake_case` primary key. Safe to hardcode in the recommender; never reused. |
| `match.canonical_key` | The exact token as written in a launch string / env. |
| `match.aliases` | Alternate spellings, related companion vars, or compat-config equivalents. |
| `match.regex` | Case-insensitive Python regex; the intended way to map a normalized key to this record. |
| `kind` | Structural type of the token. |
| `value_type` | Shape of the carried value. |
| `values` | Documented accepted values when the set is finite (omit for free-form). |
| `description` | Self-authored plain language. Deliberately avoids leaning on fixed jargon. |
| `intent_type` | **The central classification.** See next section. |
| `intent_note` | Required when `intent_type` is `why` or `both`: spells out the external mechanism so the recommender can explain it to the user. |
| `category` | Coarse grouping for filtering/sorting/UI. |
| `effect_axes` | List of `{axis, direction}` — which of the three axes the parameter moves. |
| `parity_risk` + `…_rationale` | Likelihood it **degrades** native parity / adds instability, plus a one-line reason. |
| `obsolescence` | `{status, since, note}` — whether the advice is still live. |
| `hardware_scope` | Which hardware the parameter is meaningful on. |
| `confidence` | How strong the documentation is **for this annotation** (not how common the param is). |
| `doc_sources` | Primary URLs consulted. |

---

## The `intent_type` distinction (the heart of this KB)

- **`how`** — the benefit is **self-evident once named**: the parameter improves the visual result
  or runtime smoothness. *Example:* `mesa_glthread` (offloads GL calls to another thread → more FPS),
  `-USEALLAVAILABLECORES` (use all cores → less CPU bottleneck). The recommender can present these as
  straightforward optimizations.

- **`why`** — the parameter exists to **satisfy an external constraint** the user wouldn't otherwise
  infer: anti-cheat acceptance, a DRM/launcher quirk, or a known crash/regression workaround. For
  these, `intent_note` **must explain the external mechanism**, not a performance story. *Example:*
  `PROTON_EAC_RUNTIME` — "the title uses Easy Anti-Cheat; this loads Proton's EAC runtime so the
  anti-cheat module initializes and the session isn't rejected" (NOT "improves performance").

- **`both`** — has a clear `how` benefit *and* a `why` reason; `intent_type` holds the **primary**
  and `intent_note` captures the secondary. *Example:* `game_arg_force_dx11` — how: steadier frames;
  why: the game's DX12 path is broken under Proton so DX11/DXVK is the working route.

This split is what lets the recommender produce honest copy. A `why` parameter described as a
performance tweak would be actively misleading (the canonical failure mode the task warns about).

---

## Enums (closed value sets)

All defined in the top-level `enums` block — that block is the source of truth; this table is a
human mirror.

| enum | values |
|---|---|
| `kind` | `env`, `wrapper`, `game-arg`, `proton-runtime`, `compat-config`, `launch-pattern` |
| `value_type` | `boolean`, `enum`, `integer`, `string`, `path`, `list`, `flag`, `selection` |
| `intent_type` | `how`, `why`, `both` |
| `category` | `proton-runtime-selection`, `anti-cheat-or-drm`, `dxvk-rendering`, `vkd3d-d3d12`, `nvidia-feature`, `amd-mesa`, `gpu-offload-hybrid`, `shader-cache-stutter`, `frame-generation`, `upscaling`, `wine-dll-modding`, `launcher-or-ux`, `cpu-scheduling`, `display-wayland`, `monitoring-overlay`, `wine-sync`, `wine-compat-workaround` |
| `effect_axis` | `native-parity`, `visual-fidelity`, `performance` |
| `direction` | `improves`, `degrades`, `mixed`, `neutral`, `enables` |
| `parity_risk` | `low`, `medium`, `high` |
| `obsolescence_status` | `current`, `partial`, `superseded`, `obsolete`, `default-now` |
| `hardware_scope` | `universal`, `nvidia-only`, `amd-only`, `intel-only`, `hybrid-laptop`, `mesa-only`, `steam-deck`, `amd-and-nvidia` |
| `confidence` | `high`, `medium`, `low` |

**`direction` semantics on the `native-parity` axis:** `improves` = moves the Linux experience
toward what the game does on native Windows; `enables` = the title (or a mode of it) **does not
function at all** without the parameter (anti-cheat runtimes, launcher skips, hybrid-GPU offload);
`degrades` = introduces a regression vs native; `mixed`/`neutral` as usual.

**`obsolescence.status`:** `current` (live advice) · `partial` (situational/legacy but can still
matter) · `superseded` (a newer mechanism replaced it; usually a no-op now) · `obsolete` (dead) ·
`default-now` (the behavior is on by default, so explicitly setting it is redundant). The last three
are downrank signals.

---

## Coverage summary (v1.0 — 70 parameters)

By category:

| n | category |
|---|---|
| 6 | upscaling |
| 6 | vkd3d-d3d12 |
| 6 | nvidia-feature |
| 6 | amd-mesa |
| 5 | proton-runtime-selection |
| 5 | monitoring-overlay |
| 5 | display-wayland |
| 5 | anti-cheat-or-drm |
| 4 | cpu-scheduling |
| 4 | gpu-offload-hybrid |
| 4 | dxvk-rendering |
| 3 | shader-cache-stutter |
| 3 | wine-compat-workaround |
| 3 | wine-sync |
| 3 | launcher-or-ux |
| 1 | frame-generation |
| 1 | wine-dll-modding |

By intent: **24 how · 11 both · 35 why** (the heavy `why` skew is expected — most non-obvious
launchOptions are constraint/workaround tokens, which is exactly the knowledge the data dump lacks).

By hardware scope: 46 universal · 11 nvidia-only · 6 amd-only · 4 hybrid-laptop · 3 mesa-only.

The four upscalers now form a complete set — DLSS (`proton_dlss_upgrade`, NVIDIA), XeSS
(`proton_xess_upgrade`, Intel/cross-vendor), FSR4 (`proton_fsr4_upgrade` + `proton_fsr4_rdna3_upgrade`,
AMD), and Proton's vendor-agnostic FSR1 FShack (`wine_fullscreen_fsr`) — plus gamescope FSR.

> **Sync primitives (`wine-sync`):** the KB distinguishes the three Wine sync paths — esync
> (`proton_no_esync`), fsync (`proton_no_fsync`), and **ntsync (`proton_use_ntsync`)**. NTSYNC is the
> in-kernel NT-sync driver (kernel 6.14+, `/dev/ntsync`); it is the most accurate/lowest-overhead
> path and the empirically strongest signal for sync-sensitive titles (e.g. it is the top yes-rate
> parameter for ARC Raiders). Enabled by default in the newest GE/CachyOS builds when the kernel
> supports it, so an explicit `PROTON_USE_NTSYNC=1` may be redundant there — see the record's
> `obsolescence.note`.

> **Validation-oracle params** (the user's known-good ARC Raiders config) are all present and each
> resolves to exactly one record: `PROTON_ENABLE_NVAPI` → `proton_enable_nvapi`; `PROTON_DLSS_UPGRADE`
> → `proton_dlss_upgrade`; `__GL_SHADER_DISK_CACHE_SKIP_CLEANUP` → `gl_shader_disk_cache`;
> `PROTON_NVIDIA_LIBS_NO_32BIT` → `proton_nvidia_libs_no_32bit`; `game-performance` →
> `game_performance` (distinct from `gamemoderun`); `mangohud` → `mangohud`.

Flagged **stale** (recommender should downrank): `DXVK_ASYNC` (superseded by GPL @ DXVK 2.0),
`DXVK_STATE_CACHE` (superseded by GPL), `RADV_PERFTEST=gpl` (default-now), `mesa_glthread`
(default-now per-app since Mesa 22.3), `PROTON_FORCE_LARGE_ADDRESS_AWARE` (default-now in Proton).

---

## Low-confidence / thin-evidence records (do not overstate)

These four are marked `confidence: low` because primary documentation was thin or the parameter
appears vestigial; the recommender should hedge or require an explicit report citing them:

| id / key | why uncertain |
|---|---|
| `vkd3d_feature_level` (`VKD3D_FEATURE_LEVEL`) | Not documented as a live env var in current vkd3d-proton (feature level auto-detected); the documented path is Proton's `vkd3dfl12` compat-config. Treated as legacy. |
| `vkd3d_shader_model` (`VKD3D_SHADER_MODEL`) | Not in the current vkd3d-proton README; SM 6.x is baseline so the override is largely vestigial. |
| `proton_enable_nvidia_reflex` (`PROTON_ENABLE_NVIDIA_REFLEX`) | No clearly-documented standalone variable of this exact name was found. Reflex is delivered via dxvk-nvapi + the `VK_NV_low_latency2` extension once NVAPI is on (VKD3D-Proton 2.12+). Map "Reflex" intent onto `proton_enable_nvapi`. |
| `aco_debug` (`ACO_DEBUG`) | A developer/diagnostic compiler switch, not a real performance lever; rarely belongs in a recommendation. |

Additional medium-confidence caveats worth surfacing rather than asserting:

- **`PROTON_DISABLE_NVAPI` vs `PROTON_NO_NVAPI`** — canonical spelling per the Proton README is
  `PROTON_DISABLE_NVAPI` (compat-config `disablenvapi`); `PROTON_NO_NVAPI` is recorded as an alias
  but its exact validity is unverified.
- **`VKD3D_CONFIG` token `dxr11`** — historical; current builds fold DXR 1.1 into the `dxr` token
  (docs show `dxr` and experimental `dxr12`). The KB lists `dxr`/`dxr12` and notes the `dxr11`
  mapping.
- **`DXVK_FRAME_RATE` / `DXVK_STATE_CACHE`** — these env vars weren't in the trimmed README excerpt
  retrieved; behavior is asserted from PCGamingWiki/DXVK history. `DXVK_STATE_CACHE` is additionally
  marked superseded.
- **`PROTON_DLSS_UPGRADE` / `PROTON_FSR4_UPGRADE` / `PROTON_DLSS_INDICATOR`** — documented for
  GE-Proton / proton-cachyos builds; may not exist in stock Valve Proton. Scoped accordingly.
- **`obs_gamecapture` / `strangle`** — common in the wild but lightly documented upstream; medium
  confidence on exact invocation.

---

## Validation

The repo can self-check the file against its own `enums` block:

```python
import json
d = json.load(open("data/annotations.json"))
e = d["enums"]
for p in d["parameters"]:
    assert p["intent_type"] in e["intent_type"], p["id"]
    assert p["category"] in e["category"], p["id"]
    assert p["parity_risk"] in e["parity_risk"], p["id"]
    assert p["hardware_scope"] in e["hardware_scope"], p["id"]
    assert p["confidence"] in e["confidence"], p["id"]
    assert p["kind"] in e["kind"], p["id"]
    assert p["obsolescence"]["status"] in e["obsolescence_status"], p["id"]
    for ax in p["effect_axes"]:
        assert ax["axis"] in e["effect_axis"] and ax["direction"] in e["direction"], p["id"]
    if p["intent_type"] in ("why", "both"):
        assert p.get("intent_note"), f"{p['id']} missing intent_note"
```

`id` values are unique and intended to be stable across schema versions; add new parameters with new
`id`s rather than renaming existing ones.
