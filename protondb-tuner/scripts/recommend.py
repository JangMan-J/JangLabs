#!/usr/bin/env python3
"""
protondb-tuner — recommender / report generator.

Consumes the inferred database (data/protondb.sqlite, built by build_db.py) and
the semantic knowledge base (data/annotations.json), and for one game emits:

  PRIMARY  — a relevance-ranked CATALOG of every configuration parameter the
             data shows is relevant to the game. Each entry is annotated with
             what it does (a "how" line) or why it is present when that is not
             self-evident (a "why" line, e.g. anti-cheat acceptance), plus its
             category, the axes it moves, a parity-risk read, staleness, the
             hardware it applies to, and the underlying evidence.

  SECONDARY — a system-tailored configuration assembled FROM that catalog, in
             risk-weighted tiers (Foundation -> Recommended -> Optional), filtered
             to a hardware profile and an optimization priority, and rendered as a
             concrete runtime choice + launch-options string.

Optionally validates a known-good launch string with --compare / --runtime.

The objective the SECONDARY output optimizes (the project's stated model):
  1. native parity is the anchor — first maximize the chance the title runs and
     behaves as it does on its native (Windows) platform;
  2. then layer visual-fidelity and performance gains, each DISCOUNTED by the
     parity risk it introduces (low-risk gains strongly preferred);
  3. fidelity-vs-performance is an explicit, weighed trade, never applied blindly.

Pure stdlib. Reads the DB read-only; writes nothing.
"""
import argparse
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # parse_launch_options, param_id, normalize_custom_proton, etc.
import detect_system  # host profiler (GPU vendor, display, distro, tools, proton builds)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_DB = os.path.join(ROOT, "data", "protondb.sqlite")
DEFAULT_KB = os.path.join(ROOT, "data", "annotations.json")

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
RISK_NAME = {0: "low", 1: "medium", 2: "high"}

# Params whose benefit depends on external hardware the data can't confirm (e.g. an
# HDR display). Never auto-promote to Recommended / the assembled string — keep in
# Optional with the prerequisite spelled out.
CONDITIONAL_IDS = {"proton_enable_hdr"}

# Hardware scopes that DO NOT apply to a given GPU vendor -> suppressed in the
# secondary recommendation (still listed in the catalog, tagged N/A).
SCOPE_APPLIES = {
    # scope            : predicate(profile) -> bool
    "universal":        lambda p: True,
    "amd-and-nvidia":   lambda p: p["gpu"] in ("NVIDIA", "AMD"),
    "nvidia-only":      lambda p: p["gpu"] == "NVIDIA",
    "amd-only":         lambda p: p["gpu"] == "AMD",
    "mesa-only":        lambda p: p["gpu"] in ("AMD", "INTEL"),
    "intel-only":       lambda p: p["gpu"] == "INTEL",
    "hybrid-laptop":    lambda p: p.get("hybrid", False),
    "steam-deck":       lambda p: p.get("deck", False),
}

# This machine, as reported by the harness fingerprint + annotations user_environment.
DEFAULT_PROFILE = {
    "gpu": "NVIDIA", "hybrid": True, "display": "wayland",
    "distro": "cachyos", "deck": False,
}

PRIORITIES = ("parity", "performance", "fidelity", "stability")


# ---------------------------------------------------------------------------
# KB loading + matching (implements annotations.json engine_integration contract)
# ---------------------------------------------------------------------------
class KB:
    def __init__(self, path):
        with open(path) as fh:
            self.doc = json.load(fh)
        self.records = self.doc["parameters"]
        self.by_id = {r["id"]: r for r in self.records}
        for r in self.records:
            r["_re"] = re.compile(r["match"]["regex"]) if r.get("match", {}).get("regex") else None
        self.ac_guidance = self.doc.get("anti_cheat_guidance", {})
        self.user_env = self.doc.get("user_environment", {})

    def _first_regex_match(self, text, allowed_ids=None):
        for r in self.records:
            if allowed_ids is not None and r["id"] not in allowed_ids:
                continue
            rx = r["_re"]
            if rx and rx.search(text):
                return r
        return None

    def match(self, namespace, key, value):
        """Map an engine param (namespace|key|value) to a KB record, or None."""
        if namespace == "shellhack":
            return self.by_id.get("launch_pattern_exe_swap")
        if namespace == "proton":
            return self._match_proton(key, value)
        if namespace == "env":
            return self._first_regex_match(key)
        if namespace == "arg":
            return self._first_regex_match(key)
        if namespace == "wrapper":
            r = self._first_regex_match(key)
            if r:
                return r
            # alias fallbacks documented in engine_integration.namespace_map
            alias = {"mangoapp": "mangohud", "primusrun": "prime_run",
                     "optirun": "prime_run"}.get(key)
            return self.by_id.get(alias) if alias else None
        return None

    def _match_proton(self, key, value):
        # GE / CachyOS custom build names resolve to dedicated records first.
        token = value or key
        if re.search(r"cachyos", token, re.I):
            return self.by_id.get("proton_variant_cachyos")
        if re.search(r"GE[- ]?Proton", token, re.I):
            return self.by_id.get("proton_variant_ge")
        if key.startswith("variant:"):
            return self._first_regex_match(key)
        # notes_version / numbered tokens: precedence by major version.
        m = re.search(r"(\d+)\.(\d+)", token)
        if m:
            major = int(m.group(1))
            return self.by_id.get(
                "proton_variant_pinned_older" if major <= 8 else "proton_variant_official_stable")
        if re.search(r"experimental|hotfix|next", token, re.I):
            return self.by_id.get("proton_variant_experimental")
        return self._first_regex_match(token)


# ---------------------------------------------------------------------------
# DB access
# ---------------------------------------------------------------------------
def open_db(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def resolve_game(con, appid, game):
    if appid:
        row = con.execute("select * from game_summary where appid=?", (str(appid),)).fetchone()
        if row:
            return row
    if game:
        rows = con.execute(
            "select * from game_summary where lower(title) like ? order by total_reports desc",
            ("%" + game.lower() + "%",)).fetchall()
        if rows:
            return rows[0]
    return None


def load_params(con, appid, profile):
    """Load all game_param rows + attach the matching hardware-bucket stats."""
    params = [dict(r) for r in con.execute(
        "select * from game_param where appid=? order by catalog_relevance desc", (appid,)).fetchall()]
    # bucket stats for this profile's GPU vendor and display server
    buckets = {}
    for r in con.execute(
            "select * from game_param_bucket where appid=? and "
            "((bucket_type='gpu_vendor' and bucket_value=?) or (bucket_type='display_server' and bucket_value=?))",
            (appid, profile["gpu"], profile["display"])):
        buckets.setdefault(r["param_id"], {})[r["bucket_type"]] = dict(r)
    for p in params:
        p["bucket"] = buckets.get(p["param_id"], {})
    return params


def collapse_proton_customs(params):
    """
    Per-point-release GE-Proton custom builds (GE-Proton10-25, 10-26, ...) are one
    knob — "use a recent GE-class build". Merge them into a single catalog row so
    the catalog isn't flooded with near-identical version rows. proton-cachyos
    builds collapse the same way.
    """
    def merge(group, value, display):
        if len(group) <= 1:
            return None
        sup = sum(p["support"] or 0 for p in group)
        rec_sup = sum(p["recent_support"] or 0 for p in group)
        yes = sum(p["with_yes"] or 0 for p in group)
        m = dict(group[0])
        m.update({
            "param_id": f"proton|custom|{value}", "key": "custom", "value": value,
            "display": display, "support": sup, "recent_support": rec_sup,
            "with_yes": yes, "yes_rate_with_param": (yes / sup if sup else None),
            "smoothed_lift": max((p["smoothed_lift"] or 0) for p in group),
            "recent_prevalence": max((p["recent_prevalence"] or 0) for p in group),
            "catalog_relevance": max((p["catalog_relevance"] or 0) for p in group),
            "verdict_delta": max((p["verdict_delta"] or 0) for p in group),
            "perf_fault_delta": 0.0, "bucket": {},
        })
        return m

    groups = {
        "GE-Proton (recent builds)": (re.compile(r"GE[- ]?Proton", re.I), "Proton build = GE-Proton (recent builds)"),
        "proton-cachyos": (re.compile(r"cachyos", re.I), "Proton build = proton-cachyos"),
    }
    out, consumed = [], set()
    for value, (pat, display) in groups.items():
        grp = [p for p in params if p["namespace"] == "proton" and p["key"] == "custom"
               and pat.search(p["value"] or "")]
        if len(grp) > 1:
            for p in grp:
                consumed.add(id(p))
            m = merge(grp, value, display)
            if m:
                out.append(m)
    keep = [p for p in params if id(p) not in consumed] + out
    keep.sort(key=lambda p: p["catalog_relevance"] or 0, reverse=True)
    return keep


# ---------------------------------------------------------------------------
# Vendor-baseline layer (what's standard for a GPU vendor across ALL games)
# ---------------------------------------------------------------------------
# Members of the "gamemode wrapper" equivalence class (one knob, distro-specific name).
GAMEMODE_MEMBERS = ("wrapper|gamemoderun|", "wrapper|game-performance|")
BASELINE_THRESHOLD = 0.08  # min global vendor prevalence to count as "standard hygiene"


def load_vendor_baseline(con, gpu):
    """param_id -> global prevalence among that GPU vendor's reports (all games)."""
    out = {}
    for r in con.execute(
            "select param_id, base_rate from background_bucket "
            "where bucket_type='gpu_vendor' and bucket_value=?", (gpu,)):
        out[r["param_id"]] = r["base_rate"]
    return out


def param_layer(p):
    """Which evidence layer explains this param: game-specific vs vendor-standard."""
    lift = p.get("smoothed_lift") or 0
    rs = p.get("recent_support") or 0
    vb = p.get("vendor_baseline") or 0
    if lift >= 2.0 and rs >= 2:
        return "game-specific"
    if vb >= 0.05:
        return "vendor-standard"
    return "general"


def inject_baseline(con, kb, profile, vendor_baseline, items_by_id, summary):
    """
    Add 'standard for your GPU' hygiene params that this game's own data is too
    thin to surface — the layer that keeps recommendations useful on the ~37k
    sparsely-reported games. Conservative: KB-annotated, low-risk, beneficial,
    hardware-applicable, current, and above the vendor-baseline threshold.
    """
    gpu = profile["gpu"]
    have_gamemode = any(m in items_by_id and items_by_id[m]["rec"]["tier"] in ("recommended", "optional")
                        for m in GAMEMODE_MEMBERS)
    injected = []
    for pid, base in sorted(vendor_baseline.items(), key=lambda kv: -kv[1]):
        if base < BASELINE_THRESHOLD:
            break
        ns, key, val = (pid.split("|", 2) + ["", ""])[:3]
        # Runtime selection is handled in Foundation, not as launch-option hygiene.
        if ns not in ("env", "wrapper", "arg"):
            continue
        # gamemode equivalence: one class, distro-preferred name
        if pid in GAMEMODE_MEMBERS:
            if have_gamemode:
                continue
            key = "game-performance" if profile["distro"] == "cachyos" else "gamemoderun"
            ns, val, pid = "wrapper", "", f"wrapper|{key}|"
        if pid in items_by_id and items_by_id[pid]["rec"]["tier"] == "recommended":
            continue
        kb_rec = kb.match(ns, key, val)
        if not kb_rec or RISK_ORDER.get(kb_rec["parity_risk"], 1) != 0:
            continue
        if not applies(kb_rec["hardware_scope"], profile) or not is_beneficial(benefit_axes(kb_rec)):
            continue
        if (kb_rec.get("obsolescence", {}) or {}).get("status", "current") in ("superseded", "obsolete", "default-now"):
            continue
        p = {"param_id": pid, "namespace": ns, "key": key, "value": val,
             "display": common.param_display(ns, key, val), "support": 0, "recent_support": 0,
             "recent_prevalence": None, "smoothed_lift": None, "yes_rate_with_param": None,
             "verdict_delta": 0, "perf_fault_delta": 0, "bucket": {}, "vendor_baseline": base,
             "_injected": True}
        rec = {"tier": "recommended", "risk": "low", "risk_notes": [], "axes": benefit_axes(kb_rec),
               "obsolescence": "current", "applicable": True, "layer": "vendor-standard",
               "caveats": [f"standard on {gpu} across games ({pct(base)} of {gpu} reports) — "
                           f"not specific to {summary['title']}, but a safe general default."]}
        it = {"p": p, "kb": kb_rec, "rec": rec}
        injected.append(it)
        items_by_id[pid] = it
        if ns == "wrapper" and key in ("gamemoderun", "game-performance"):
            have_gamemode = True
    return injected


# ---------------------------------------------------------------------------
# Scoring / tiering
# ---------------------------------------------------------------------------
def applies(scope, profile):
    return SCOPE_APPLIES.get(scope, lambda p: True)(profile)


def effective_risk(p, kb_rec):
    """KB parity_risk prior, adjusted by this game's evidence."""
    base = RISK_ORDER.get(kb_rec["parity_risk"], 1) if kb_rec else 1  # unknown -> medium
    risk = base
    notes = []
    gb = p["bucket"].get("gpu_vendor")
    # Strong matching-hardware evidence relaxes a cautious prior by one notch.
    if gb and gb["support"] >= 10 and gb["yes_rate_with_param"] is not None \
            and gb["yes_rate_with_param"] >= 0.93 and (p["recent_prevalence"] or 0) > 0:
        if risk > 0:
            risk -= 1
            notes.append(f"risk relaxed: {gb['support']} {p_gpu(p)} reports at "
                         f"{pct(gb['yes_rate_with_param'])} runs-rate")
    # Association with FAILURE raises risk.
    if (p["verdict_delta"] or 0) <= -0.10:
        risk = min(2, risk + 1)
        notes.append(f"associated with WORSE outcomes (verdict Δ {p['verdict_delta']:+.2f}) — "
                     "often a troubleshooting attempt, not a fix")
    # Performance-fault association is a caveat (does not by itself raise risk).
    if (p["perf_fault_delta"] or 0) >= 0.15:
        notes.append(f"reports using it log more performance faults (Δ {p['perf_fault_delta']:+.2f})")
    return risk, notes


def p_gpu(p):
    gb = p["bucket"].get("gpu_vendor")
    return gb["bucket_value"] if gb else "GPU"


def benefit_axes(kb_rec):
    """Return dict axis->direction from the KB, or {} if unannotated."""
    out = {}
    if kb_rec:
        for ea in kb_rec.get("effect_axes", []):
            out[ea["axis"]] = ea["direction"]
    return out


def is_beneficial(axes):
    return any(d in ("improves", "enables") for d in axes.values())


def classify(p, kb_rec, profile, priority, summary):
    """
    Assign a param to a tier and build its rationale.
    Tiers: foundation | recommended | optional | warned | suppressed | catalog-only
    (proton-runtime rows are handled separately and tagged 'runtime').
    """
    ns = p["namespace"]
    cat = kb_rec["category"] if kb_rec else None
    axes = benefit_axes(kb_rec)
    risk, risk_notes = effective_risk(p, kb_rec)
    obso = (kb_rec.get("obsolescence", {}) or {}).get("status", "current") if kb_rec else "unknown"
    applicable = applies(kb_rec["hardware_scope"], profile) if kb_rec else True
    online = (summary["regime_hint"] or "").startswith("anticheat") or \
        (summary["online_played"] or 0) > 0.3 * max(1, summary["total_reports"])

    rec = {
        "tier": None, "risk": RISK_NAME[risk], "risk_notes": risk_notes,
        "axes": axes, "obsolescence": obso, "applicable": applicable, "caveats": [],
        "layer": param_layer(p),
    }

    if ns == "proton":
        rec["tier"] = "runtime"
        return rec

    # --- anti-cheat / DRM gating (the asymmetric rule) ---
    if cat == "anti-cheat-or-drm":
        bypass = kb_rec["id"] in ("game_arg_eac_nop", "game_arg_no_battleye", "launch_pattern_exe_swap")
        if bypass:
            if online:
                rec["tier"] = "warned"
                rec["caveats"].append(
                    "BYPASS on an online title: risks an ACCOUNT BAN and enables nothing — "
                    "this game's anti-cheat is accepted on Linux, so never bypass it.")
            else:
                rec["tier"] = "optional"
                rec["caveats"].append(
                    "Offline/singleplayer only — lets the game launch where its anti-cheat "
                    "is not Linux-accepted; does NOT enable online play.")
            return rec
        # An AC *runtime* flag (PROTON_EAC_RUNTIME etc.). If AC is accepted OOB, it is informational.
        rec["tier"] = "foundation-note"
        rec["caveats"].append(
            "Usually unnecessary: the anti-cheat runtime is provided automatically by modern "
            "Proton for this title (most working reports set no anti-cheat flag).")
        return rec

    if not applicable:
        rec["tier"] = "suppressed"
        rec["caveats"].append(f"not applicable to your hardware ({kb_rec['hardware_scope']}).")
        return rec

    if obso in ("superseded", "obsolete"):
        rec["tier"] = "suppressed"
        rec["caveats"].append("stale: superseded/obsolete — modern Proton/DXVK handle this; setting it is a no-op or counterproductive.")
        return rec
    if obso == "default-now":
        rec["tier"] = "suppressed"
        rec["caveats"].append("already the default in current Proton — no need to set it explicitly.")
        return rec

    support = p["support"] or 0
    recent_support = p["recent_support"] or 0
    gb2 = p["bucket"].get("gpu_vendor")
    ev_support = max(support, (gb2["support"] if gb2 else 0))
    # A param only earns the Recommended tier if it is actually attested: enough
    # total reports AND some recent ones. Tiny-n params drop to Optional (flagged).
    well_attested = ev_support >= 5 and recent_support >= 2

    beneficial = is_beneficial(axes) or kb_rec is None
    neutral = bool(axes) and not beneficial

    if risk == 0 and beneficial and well_attested:
        tier = "recommended"
    else:
        tier = "optional"
        if risk >= 2:
            rec["caveats"].append("higher parity risk — apply only if you specifically need it.")
        if not well_attested:
            rec["caveats"].append(f"thin evidence (n={support}) — surfaced but not strongly attested.")
        if neutral:
            rec["caveats"].append("elective (no effect on how the game runs).")

    # CachyOS: prefer game-performance over Feral GameMode; never stack the two.
    if kb_rec and kb_rec["id"] == "gamemoderun" and profile["distro"] == "cachyos" and tier == "recommended":
        tier = "optional"
        rec["caveats"].append("alternative to game-performance — CachyOS recommends game-performance; don't stack them.")

    # priority adjustments (only promote well-attested items)
    if priority == "stability" and tier == "recommended" and "native-parity" not in axes:
        tier = "optional"
    if priority == "performance" and axes.get("performance") == "improves" \
            and tier == "optional" and risk <= 1 and well_attested:
        tier = "recommended"
    if priority == "fidelity" and axes.get("visual-fidelity") == "improves" \
            and tier == "optional" and risk <= 1 and well_attested:
        tier = "recommended"

    # Host-aware gating (only applied when --auto detected a host profile).
    tools = profile.get("tools")
    if tools is not None and ns == "wrapper" and not tools.get(p["key"], False) and tier == "recommended":
        tier = "optional"
        rec["caveats"].append(f"not installed on this host — `{p['key']}` not found in PATH.")
    if p["key"] == "PROTON_USE_NTSYNC" and profile.get("ntsync") is False and tier == "recommended":
        tier = "optional"
        rec["caveats"].append("this host has no /dev/ntsync (needs kernel ≥6.14) — no effect until then.")

    # Conditional features (HDR, …) never auto-apply — they need hardware we can't see.
    if kb_rec and kb_rec["id"] in CONDITIONAL_IDS and tier == "recommended":
        tier = "optional"
        rec["caveats"].append("conditional — only worthwhile with an HDR-capable display and HDR enabled "
                              "in your compositor (KDE Plasma 6 qualifies); not applied automatically.")

    if kb_rec is None:
        rec["caveats"].append("no semantic annotation yet — surfaced on data signal alone; meaning unverified.")
    rec["tier"] = tier
    return rec


# ---------------------------------------------------------------------------
# Runtime decision (Foundation anchor)
# ---------------------------------------------------------------------------
def choose_runtime(con, summary, profile):
    appid = summary["appid"]
    rows = con.execute(
        "select param_id,support,with_yes,yes_rate_with_param from game_param_bucket "
        "where appid=? and bucket_type='gpu_vendor' and bucket_value=? and param_id like 'proton|variant:%' "
        "order by support desc", (appid, profile["gpu"])).fetchall()
    variant_yes = {r["param_id"].split(":", 1)[1].rstrip("|"): dict(r) for r in rows}
    # CachyOS users: the local GE-class build is proton-cachyos.
    ge_label = "proton-cachyos (or GE-Proton, e.g. " + (summary["dominant_custom_recent"] or "GE-Proton latest") + ")" \
        if profile["distro"] == "cachyos" else (summary["dominant_custom_recent"] or "GE-Proton latest")
    lines = []
    best = None
    for v in ("ge", "official", "experimental"):
        d = variant_yes.get(v)
        if d and d["support"] >= 5:
            lines.append((v, d["support"], d["yes_rate_with_param"]))
    lines.sort(key=lambda t: (t[2] or 0), reverse=True)
    if lines:
        best = lines[0][0]
    return {"ge_label": ge_label, "ranked": lines, "best": best,
            "dominant_variant": summary["dominant_variant_recent"],
            "dominant_custom": summary["dominant_custom_recent"]}


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------
def pct(x):
    return "—" if x is None else f"{100 * x:.0f}%"


def annot_line(p, kb_rec, rec):
    """The 'how' or 'why' sentence for a parameter."""
    if kb_rec is None:
        return "(no annotation) " + p["display"]
    desc = kb_rec["description"].strip()
    if kb_rec["intent_type"] in ("why", "both") and kb_rec.get("intent_note"):
        return f"WHY: {desc} ({kb_rec['intent_note']})"
    return f"HOW: {desc}"


def evidence_str(p):
    bits = [f"{p['support']} reports", f"recent {pct(p['recent_prevalence'])} of tinkered configs",
            f"lift ×{p['smoothed_lift']:.1f}", f"runs-rate {pct(p['yes_rate_with_param'])}"]
    gb = p["bucket"].get("gpu_vendor")
    if gb and gb["support"]:
        bits.append(f"[{gb['bucket_value']}: {gb['support']} rpts, {pct(gb['yes_rate_with_param'])}]")
    return " · ".join(bits)


def _negated(p):
    """True if the token disables/negates its feature (so it must not merge with the positive form)."""
    val = (p.get("value") or "").lower()
    key = (p.get("key") or "")
    return (val in ("0", "off", "false", "disabled", "no")
            or key.startswith(("PROTON_NO_", "PROTON_DISABLE_")) or "DISABLE" in key.upper())


def group_same_record(items):
    """Collapse items that map to the same KB record in the same direction into one
    entry (e.g. the PROTON_ENABLE_HDR / ENABLE_HDR_WSI / DXVK_HDR trio). Negated
    forms (=0 / PROTON_NO_*) stay separate. Returns [(representative_item, [displays])]."""
    out, idx = [], {}
    for it in items:
        kbid = it["kb"]["id"] if it["kb"] else None
        if kbid and not _negated(it["p"]) and kbid in idx:
            out[idx[kbid]][1].append(it["p"]["display"])
            continue
        if kbid and not _negated(it["p"]):
            idx[kbid] = len(out)
        out.append((it, [it["p"]["display"]]))
    return out


def render_markdown(con, summary, items, runtime, profile, priority, compare=None):
    A = []
    title = summary["title"]
    A.append(f"# protondb-tuner — {title}  (appId {summary['appid']})")
    A.append("")
    # Playability flag — recency-windowed, shown for EVERY game (not only anti-cheat titles).
    regime = summary["regime_hint"]
    ry = summary["recent_yes_rate"]
    rn = summary["recent_reports"] or 0
    anti = bool(regime and regime.startswith("anticheat"))
    if rn >= 8 and ry is not None:
        rate, basis = ry, f"{pct(ry)} of the last {rn} reports run"
    elif summary["baseline_yes_rate"] is not None:
        rate, basis = (summary["baseline_yes_rate"],
                       f"{pct(summary['baseline_yes_rate'])} of {summary['total_reports']} all-time reports run (few recent)")
    else:
        rate, basis = None, None
    if rate is None:
        A.append("**Playability:** unknown — too few reports to judge.")
    elif rate >= 0.8:
        A.append(f"🟢 **Playable** — {basis}." + (" Anti-cheat is currently accepted on Linux." if anti else ""))
    elif rate >= 0.5:
        A.append(f"🟡 **Works with effort** — only {basis}; expect to tinker, and verify before relying on it.")
    elif anti:
        A.append(f"🔴 **Blocked / ban-risk** — only {basis}; treat as not Linux-supported (publisher anti-cheat).")
    else:
        A.append(f"🔴 **Likely broken on Linux** — only {basis}; the parameters below are long-shots, not a known fix.")
    if anti:
        A.append("")
        A.append("> Anti-cheat acceptance is publisher-set and can flip on a patch date — a *recency-windowed* read, "
                 "not a config you can force. (Status is inferred from online-play + EAC-runtime reports; the "
                 "structured anti-cheat field is often empty.)")
    A.append("")

    # ---- SECONDARY first as a quick-start, then the full catalog. ----
    A.append("## Suggested configuration for your system")
    A.append(f"_Profile: {profile['gpu']} · {profile['display']} · {profile['distro']}"
             f"{' · hybrid laptop' if profile.get('hybrid') else ''} · priority: **{priority}**_")
    d = profile.get("detected")
    if d:
        gpus = ", ".join(g["vendor"] for g in d.get("gpus", [])) or "?"
        nvk = (f" · open kmod {d['nvidia_driver']}"
               if d.get("nvidia_open_kmod") and d.get("nvidia_driver") else "")
        A.append("")
        A.append(f"_Auto-detected host: GPU {gpus} (primary {d['gpu']}"
                 f"{', hybrid' if d.get('hybrid') else ''}){nvk} · {d.get('display')}/{d.get('desktop')} · "
                 f"{d.get('distro_name') or d.get('distro')} · kernel {d.get('kernel')} · "
                 f"ntsync {'yes' if d.get('ntsync') else 'no'}._")
    A.append("")
    A.append("**Foundation — maximize native parity (do these first):**")
    A.append(f"- **Runtime:** {runtime['ge_label']} under Steam Linux Runtime 3 (\"sniper\").  "
             + (f"On your GPU, GE-class builds run best in the data ("
                + ", ".join(f"{v} {pct(y)}@{n}rpts" for v, n, y in runtime["ranked"]) + ")."
                if runtime["ranked"] else ""))
    _builds = profile.get("proton_builds") or []
    _installed = next((b["name"] for kind in ("cachyos", "ge", "experimental")
                       for b in _builds if b["kind"] == kind), None)
    if _installed:
        A.append(f"  - ✓ **Installed on this host:** `{_installed}` — select it in the game's "
                 "Properties → Compatibility dropdown.")
    elif profile.get("detected") is not None:
        A.append("  - No GE-class Proton found in your compatibilitytools.d — install proton-cachyos or "
                 "GE-Proton (e.g. via ProtonPlus / ProtonUp-Qt) to match the data's best runtime.")
    if regime and regime.startswith("anticheat"):
        A.append("- **Anti-cheat:** add no flag. This title's EAC is dev-enabled and loads automatically; "
                 "a bypass would risk a ban and gain nothing.")
    foundation_notes = [it for it in items if it["rec"]["tier"] == "foundation-note"]
    for rep, displays in group_same_record(foundation_notes):
        toks = " / ".join(f"_{x}_" for x in displays)
        A.append(f"- {toks} — {rep['rec']['caveats'][0]}")
    A.append("")

    def emit(tier, header, blurb):
        chosen = [it for it in items if it["rec"]["tier"] == tier]
        if not chosen:
            return
        A.append(f"**{header}**")
        if blurb:
            A.append(f"_{blurb}_")
        for rep, displays in group_same_record(chosen):
            p, kb_rec, rec = rep["p"], rep["kb"], rep["rec"]
            lab = {"game-specific": " ·_game-specific_",
                   "vendor-standard": f" ·_standard on {profile['gpu']}_"}.get(rec.get("layer"), "")
            tag = " / ".join(f"`{x}`" for x in displays) + lab
            extra = ""
            if rec["caveats"]:
                extra = "  — " + " ".join(rec["caveats"])
            risknote = f" _(risk: {rec['risk']}"
            if rec["risk_notes"]:
                risknote += "; " + "; ".join(rec["risk_notes"])
            risknote += ")_"
            A.append(f"- {tag} — {annot_line(p, kb_rec, rec)}{risknote}{extra}")
        A.append("")

    emit("recommended", "Recommended — low-risk fidelity / performance gains, attested on your hardware", "")

    # Optional: annotated items in full, then a capped digest of the unannotated long tail.
    opt = [it for it in items if it["rec"]["tier"] == "optional"]
    opt_annot = [it for it in opt if it["kb"]]
    opt_data = [it for it in opt if not it["kb"]]
    if opt_annot:
        A.append("**Optional / advanced — weigh the trade before adding**")
        for rep, displays in group_same_record(opt_annot):
            p, kb_rec, rec = rep["p"], rep["kb"], rep["rec"]
            tag = " / ".join(f"`{x}`" for x in displays)
            extra = ("  — " + " ".join(rec["caveats"])) if rec["caveats"] else ""
            rn = " _(risk: " + rec["risk"] + ("; " + "; ".join(rec["risk_notes"]) if rec["risk_notes"] else "") + ")_"
            A.append(f"- {tag} — {annot_line(p, kb_rec, rec)}{rn}{extra}")
        A.append("")
    if opt_data:
        shown = min(8, len(opt_data))
        A.append(f"**Data-only signals (no annotation yet; top {shown} of {len(opt_data)})**")
        A.append("_Parameters other players tie to this game that the knowledge base does not yet describe — "
                 "shown for completeness, meaning unverified, ranked by relevance._")
        for it in opt_data[:8]:
            p, rec = it["p"], it["rec"]
            A.append(f"- `{p['display']}` — {p['support']} reports, runs-rate {pct(p['yes_rate_with_param'])}, risk {rec['risk']}")
        if len(opt_data) > 8:
            A.append(f"- …and {len(opt_data) - 8} more (see the full catalog below).")
        A.append("")

    # assembled launch string
    chosen_env_wrap = [it for it in items if it["rec"]["tier"] in ("recommended",)
                       and it["p"]["namespace"] in ("env", "wrapper", "arg")]
    launch = assemble_launch(chosen_env_wrap, profile)
    A.append("**Assembled launch options (Recommended tier):**")
    A.append("```")
    A.append(launch)
    A.append("```")
    warned = [it for it in items if it["rec"]["tier"] == "warned"]
    if warned:
        A.append("")
        A.append("**⚠️ Do NOT use for this title:**")
        for it in warned:
            A.append(f"- `{it['p']['display']}` — {' '.join(it['rec']['caveats'])}")
    A.append("")

    # ---- compare / validation ----
    if compare is not None:
        A.append("## Validation against your known-good config")
        A.extend(render_compare(compare))
        A.append("")

    # ---- PRIMARY full catalog ----
    A.append("## Full parameter catalog (relevance-ranked)")
    A.append("_Every parameter the data ties to this game, most game-specific first. "
             "Hardware/stale tags show whether it applies to you._")
    A.append("")
    A.append("| # | Parameter | How/Why | Category | Axes | Risk | Applies | Evidence |")
    A.append("|--:|---|---|---|---|---|---|---|")
    for i, it in enumerate([x for x in items if not x["p"].get("_injected")], 1):
        p, kb_rec, rec = it["p"], it["kb"], it["rec"]
        how = "—"
        if kb_rec:
            how = ("WHY" if kb_rec["intent_type"] in ("why", "both") else "HOW")
        axes = ",".join(f"{a[:4]}{'+' if d in ('improves','enables') else '-' if d=='degrades' else '~'}"
                        for a, d in rec["axes"].items()) or "—"
        applies_tag = "✓" if rec["applicable"] else f"✗ {kb_rec['hardware_scope'] if kb_rec else ''}"
        if rec["obsolescence"] in ("superseded", "obsolete", "default-now"):
            applies_tag = "stale"
        cat = kb_rec["category"] if kb_rec else "unannotated"
        A.append(f"| {i} | `{p['display']}` | {how} | {cat} | {axes} | {rec['risk']} | {applies_tag} | "
                 f"{p['support']}r·rec{pct(p['recent_prevalence'])}·×{(p['smoothed_lift'] or 0):.1f}·{pct(p['yes_rate_with_param'])} |")
    A.append("")
    A.append("Legend: Axes = nati(ve-parity)/visu(al-fidelity)/perf, `+` improves/enables · `-` degrades · `~` mixed. "
             "Evidence = reports · recent prevalence among tinkered configs · enrichment lift · runs-rate.")
    return "\n".join(A)


def assemble_launch(items, profile):
    # wrappers (mutually-exclusive CPU schedulers handled), then envs, then %command%, then args
    envs, wraps, args = [], [], []
    have_scheduler = False
    # order wrappers: scheduler first, then mangohud-ish
    _tools = profile.get("tools") or {}
    if profile["distro"] == "cachyos" and _tools.get("game-performance", True):
        sched_pref = "game-performance"
    else:
        sched_pref = "gamemoderun"
    for it in items:
        p = it["p"]
        if p["namespace"] == "env":
            envs.append(p["display"])
        elif p["namespace"] == "wrapper":
            if p["key"] in ("gamemoderun", "game-performance"):
                if have_scheduler:
                    continue
                wraps.insert(0, sched_pref)
                have_scheduler = True
            else:
                wraps.append(p["key"])
        elif p["namespace"] == "arg":
            args.append(p["key"])
    parts = []
    if envs:
        parts.append(" ".join(sorted(envs)))
    if wraps:
        parts.append(" ".join(wraps))
    parts.append("%command%")
    if args:
        parts.append(" ".join(args))
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Compare (validation against a known launch string)
# ---------------------------------------------------------------------------
def build_compare(con, kb, summary, items_by_id, launch_str, runtime_str):
    appid = summary["appid"]
    parsed = common.parse_launch_options(launch_str) if launch_str else []
    rows = []
    seen = set()
    for ns, key, val in parsed:
        pid = common.param_id(ns, key, val)
        seen.add(pid)
        gp = con.execute("select * from game_param where appid=? and param_id=?", (appid, pid)).fetchone()
        kb_rec = kb.match(ns, key, val)
        in_catalog = items_by_id.get(pid)
        rows.append({
            "display": common.param_display(ns, key, val),
            "in_game_data": gp is not None,
            "yes_rate": (gp["yes_rate_with_param"] if gp else None),
            "support": (gp["support"] if gp else 0),
            "tier": (in_catalog["rec"]["tier"] if in_catalog else ("data-thin" if gp is None else "below-threshold")),
            "annot": (kb_rec["intent_type"] if kb_rec else None),
        })
    # runtime
    runtime_note = None
    if runtime_str:
        kb_rec = kb.match("proton", "custom", common.normalize_custom_proton(runtime_str) or runtime_str)
        runtime_note = (runtime_str, kb_rec["id"] if kb_rec else None)
    # additions we'd recommend that are NOT in the user's config
    additions = [it for it in items_by_id.values()
                 if it["rec"]["tier"] == "recommended" and it["p"]["param_id"] not in seen
                 and it["p"]["namespace"] in ("env", "wrapper", "arg")]
    return {"rows": rows, "runtime": runtime_note, "additions": additions}


def render_compare(c):
    out = []
    if c["runtime"]:
        rt, rid = c["runtime"]
        out.append(f"- **Runtime `{rt}`** → matched KB record `{rid}` (a GE-class build) — "
                   "consistent with the Foundation recommendation. ✓")
    out.append("")
    out.append("| Your parameter | In game data? | runs-rate | tier the skill assigns |")
    out.append("|---|---|---|---|")
    for r in c["rows"]:
        out.append(f"| `{r['display']}` | {'yes ('+str(r['support'])+'r)' if r['in_game_data'] else 'no'} "
                   f"| {pct(r['yes_rate'])} | {r['tier']} |")
    if c["additions"]:
        out.append("")
        out.append("**Evidence-backed additions your current config is missing:**")
        for it in c["additions"]:
            out.append(f"- `{it['p']['display']}` — runs-rate {pct(it['p']['yes_rate_with_param'])} "
                       f"({it['p']['support']} reports); {annot_line(it['p'], it['kb'], it['rec'])}")
    return out


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="protondb-tuner recommender")
    ap.add_argument("--appid")
    ap.add_argument("--game")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--annotations", default=DEFAULT_KB)
    ap.add_argument("--auto", action="store_true",
                    help="probe this host (detect_system.py) to build the profile; CLI flags below still override")
    ap.add_argument("--gpu", default=None, choices=["NVIDIA", "AMD", "INTEL"])
    ap.add_argument("--display", default=None, choices=["wayland", "x11"])
    ap.add_argument("--distro", default=None)
    ap.add_argument("--hybrid", action="store_true", default=None)
    ap.add_argument("--no-hybrid", dest="hybrid", action="store_false")
    ap.add_argument("--deck", action="store_true", default=None)
    ap.add_argument("--priority", default="parity", choices=PRIORITIES)
    ap.add_argument("--compare", help="a known-good launch-options string to validate against")
    ap.add_argument("--runtime", help="the Proton runtime used in --compare (e.g. proton-cachyos)")
    ap.add_argument("--format", default="md", choices=["md", "json"])
    ap.add_argument("--db-status", action="store_true", help="print inferred-DB freshness and exit")
    args = ap.parse_args()

    if args.db_status:
        if not os.path.exists(args.db):
            print("inferred DB not built — run the skill's init step (build_db.py)")
            return
        con = open_db(args.db)
        meta = {r["key"]: r["value"] for r in con.execute("select key,value from meta")}
        import datetime as _dt
        def _d(ts):
            return _dt.datetime.fromtimestamp(int(ts or 0), _dt.timezone.utc).strftime("%Y-%m-%d")
        dump, built = _d(meta.get("dump_now_ts")), _d(meta.get("built_at"))
        ngames = con.execute("select count(*) from game_summary").fetchone()[0]
        print(f"DB ready · {meta.get('total_reports','?')} reports across {ngames} games · "
              f"dump dated {dump} · built {built}")
        return

    detected = detect_system.detect() if args.auto else {}

    def _pick(cli, key, dflt):
        if cli is not None:
            return cli                       # explicit CLI flag wins
        if detected.get(key) is not None:
            return detected[key]             # then host detection
        return dflt                          # then the baked-in default

    profile = {
        "gpu": _pick(args.gpu, "gpu", DEFAULT_PROFILE["gpu"]),
        "display": _pick(args.display, "display", DEFAULT_PROFILE["display"]),
        "distro": _pick(args.distro, "distro", DEFAULT_PROFILE["distro"]),
        "hybrid": _pick(args.hybrid, "hybrid", DEFAULT_PROFILE["hybrid"]),
        "deck": _pick(args.deck, "deck", False),
        "tools": detected.get("tools"),
        "ntsync": detected.get("ntsync"),
        "proton_builds": detected.get("proton_builds", []),
        "detected": detected or None,
    }

    con = open_db(args.db)
    summary = resolve_game(con, args.appid, args.game)
    if not summary:
        print(f"Game not found (appid={args.appid!r} game={args.game!r}). "
              "Build the DB with scripts/build_db.py first.", file=sys.stderr)
        sys.exit(2)
    summary = dict(summary)
    appid = summary["appid"]

    kb = KB(args.annotations)
    params = collapse_proton_customs(load_params(con, appid, profile))
    vendor_baseline = load_vendor_baseline(con, profile["gpu"])
    for p in params:
        p["vendor_baseline"] = vendor_baseline.get(p["param_id"], 0.0)
    runtime = choose_runtime(con, summary, profile)

    items = []
    items_by_id = {}
    for p in params:
        kb_rec = kb.match(p["namespace"], p["key"], p["value"])
        rec = classify(p, kb_rec, profile, args.priority, summary)
        it = {"p": p, "kb": kb_rec, "rec": rec}
        items.append(it)
        items_by_id[p["param_id"]] = it
    # Layer (a): fold in vendor-standard hygiene the game's own data is too thin to show.
    items += inject_baseline(con, kb, profile, vendor_baseline, items_by_id, summary)

    compare = None
    if args.compare or args.runtime:
        compare = build_compare(con, kb, summary, items_by_id, args.compare, args.runtime)

    if args.format == "json":
        out = {
            "game": {k: summary[k] for k in ("appid", "title", "regime_hint", "recent_yes_rate", "recent_reports")},
            "runtime": runtime,
            "catalog": [{
                "param": it["p"]["display"], "namespace": it["p"]["namespace"],
                "tier": it["rec"]["tier"], "risk": it["rec"]["risk"],
                "intent": (it["kb"]["intent_type"] if it["kb"] else None),
                "category": (it["kb"]["category"] if it["kb"] else None),
                "applicable": it["rec"]["applicable"],
                "obsolescence": it["rec"]["obsolescence"],
                "support": it["p"]["support"], "recent_prevalence": it["p"]["recent_prevalence"],
                "smoothed_lift": it["p"]["smoothed_lift"], "yes_rate": it["p"]["yes_rate_with_param"],
                "description": (it["kb"]["description"] if it["kb"] else None),
                "caveats": it["rec"]["caveats"],
            } for it in items],
        }
        if compare:
            out["compare"] = {"rows": compare["rows"],
                              "additions": [it["p"]["display"] for it in compare["additions"]]}
        print(json.dumps(out, indent=2))
    else:
        print(render_markdown(con, summary, items, runtime, profile, args.priority, compare))


if __name__ == "__main__":
    main()
