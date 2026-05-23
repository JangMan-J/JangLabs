#!/usr/bin/env python3
"""
export_demo.py — export a single game's inferred view to JSON for the skill demo.

Pulls all stats from data/protondb.sqlite (no recompute) and, if the raw dump is
available, attaches a few real launchOptions extraction examples (clean + messy).

Usage:
  python3 scripts/export_demo.py --appid 1808500 --out data/arc_raiders_demo.json
  python3 scripts/export_demo.py --appid 1808500            # prints to stdout
"""
import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(ROOT, "data", "protondb.sqlite")
CACHE_JSON = os.path.expanduser("~/.cache/protondb-tuner/reports_piiremoved.json")

BUCKET_FOCUS = {
    "gpu_vendor": ["NVIDIA", "AMD", "INTEL"],
    "display_server": ["wayland", "x11"],
    "steamdeck": ["yes"],
}


def dict_rows(cur, q, args=()):
    cur.execute(q, args)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def classify_lo(s):
    nc = s.count("%command%")
    parsed = C.parse_launch_options(s)
    has_shellhack = any(ns == "shellhack" for ns, _, _ in parsed)
    reasons = []
    if nc == 0:
        reasons.append("no %command% token")
    if nc > 1:
        reasons.append("duplicate %command%")
    if has_shellhack:
        reasons.append("shell-hack present")
    if ";" in s.split("%command%")[0]:
        reasons.append("semicolon-separated env")
    return ("clean" if not reasons else "messy"), reasons, parsed


def extraction_examples(appid, n_clean=3, n_messy=3):
    if not os.path.exists(CACHE_JSON):
        return []
    data = json.load(open(CACHE_JSON))
    los = [r["responses"]["launchOptions"]
           for r in data
           if str(r.get("app", {}).get("steam", {}).get("appId")) == appid
           and r["responses"].get("launchOptions")]
    clean, messy = [], []
    seen = set()
    for s in los:
        if s in seen:
            continue
        seen.add(s)
        cls, reasons, parsed = classify_lo(s)
        rec = {"raw": s, "classification": cls,
               "messy_reasons": reasons,
               "parsed": [{"namespace": ns, "param": C.param_display(ns, k, v)} for ns, k, v in parsed]}
        if cls == "clean" and len(clean) < n_clean:
            clean.append(rec)
        elif cls == "messy" and len(messy) < n_messy:
            messy.append(rec)
        if len(clean) >= n_clean and len(messy) >= n_messy:
            break
    return clean + messy


def build_param_buckets(cur, appid, param_id):
    out = {}
    rows = dict_rows(cur, """SELECT bucket_type,bucket_value,support,denom,prevalence,yes_rate_with_param
                             FROM game_param_bucket WHERE appid=? AND param_id=?""", (appid, param_id))
    for r in rows:
        bt, bv = r["bucket_type"], r["bucket_value"]
        if bv not in BUCKET_FOCUS.get(bt, []):
            continue
        out.setdefault(bt, {})[bv] = {
            "support": r["support"], "denom": r["denom"],
            "prevalence": r["prevalence"], "yes_rate_with_param": r["yes_rate_with_param"],
        }
    return out


def gpu_vendor_baseline(cur, appid, vendors=("NVIDIA", "AMD"), top=15):
    """
    Global per-GPU-vendor baseline knobs (from background_bucket): params that are
    standard for a vendor ACROSS ALL games, with this game's own vendor-bucket
    prevalence + enrichment alongside. Lets the recommender separate a 'GPU-vendor
    baseline layer' (e.g. PROTON_ENABLE_NVAPI on NVIDIA) from game-specific knobs.
    """
    out = {}
    for v in vendors:
        rows = dict_rows(cur, """SELECT bk.param_id, bg.display, bk.support, bk.denom, bk.base_rate
            FROM background_bucket bk JOIN background bg ON bg.param_id=bk.param_id
            WHERE bk.bucket_type='gpu_vendor' AND bk.bucket_value=? AND bk.basis='launchopts'
            ORDER BY bk.base_rate DESC LIMIT ?""", (v, top))
        items = []
        for r in rows:
            g = cur.execute("""SELECT prevalence FROM game_param_bucket WHERE appid=? AND param_id=?
                               AND bucket_type='gpu_vendor' AND bucket_value=?""",
                            (appid, r["param_id"], v)).fetchone()
            game_prev = g[0] if g else None
            enrich = round(game_prev / r["base_rate"], 2) if (game_prev and r["base_rate"]) else None
            items.append({"param": r["display"],
                          "global_vendor_baseline": round(r["base_rate"], 4),
                          "global_support": r["support"], "global_denom": r["denom"],
                          "this_game_vendor_prevalence": game_prev,
                          "vendor_enrichment_vs_baseline": enrich})
        out[v] = items
    return out


def export(appid, db_path, top=40):
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    meta = dict(cur.execute("SELECT key,value FROM meta").fetchall())
    summ = dict_rows(cur, "SELECT * FROM game_summary WHERE appid=?", (appid,))
    if not summ:
        sys.exit(f"appid {appid} not found in {db_path}. Run build_db.py or update_game.py first.")
    summ = summ[0]

    bg_denom = dict(cur.execute("SELECT basis,denom FROM background_denom").fetchall())

    bucket_denoms = {}
    for r in dict_rows(cur, "SELECT bucket_type,bucket_value,denom,yes FROM game_bucket_denom WHERE appid=?", (appid,)):
        yr = r["yes"] / r["denom"] if r["denom"] else None
        bucket_denoms.setdefault(r["bucket_type"], {})[r["bucket_value"]] = {
            "denom": r["denom"], "yes": r["yes"], "yes_rate": round(yr, 4) if yr is not None else None}

    params = dict_rows(cur, """SELECT * FROM game_param WHERE appid=? AND support>=?
                               ORDER BY catalog_relevance DESC LIMIT ?""",
                       (appid, C.MIN_SUPPORT_CATALOG, top))
    catalog = []
    for i, p in enumerate(params, 1):
        catalog.append({
            "rank": i,
            "param": p["display"], "namespace": p["namespace"],
            "key": p["key"], "value": p["value"], "basis": p["basis"],
            "subscores": {
                "support": p["support"], "denom": p["denom"], "prevalence": p["prevalence"],
                "base_rate_global": p["base_rate"],
                "lift_raw": p["lift"], "smoothed_lift": p["smoothed_lift"], "log_lift": p["log_lift"],
                "recency_weighted_prevalence": p["recency_weighted_prevalence"],
                "recent_support": p["recent_support"], "recent_denom": p["recent_denom"],
                "recent_prevalence": p["recent_prevalence"],
                "yes_rate_with_param": p["yes_rate_with_param"],
                "verdict_delta_vs_baseline": p["verdict_delta"],
                "perf_fault_delta": p["perf_fault_delta"],
                "graphical_fault_delta": p["graphical_fault_delta"],
                "fault_assoc": json.loads(p["fault_assoc_json"]),
            },
            "catalog_relevance": p["catalog_relevance"],
            "hardware_buckets": build_param_buckets(cur, appid, p["param_id"]),
        })

    out = {
        "schema_version": 1,
        "generated_at": int(time.time()),
        "build_meta": meta,
        "appid": appid,
        "title": summ["title"],
        "summary": summ,
        "regime": {
            "hint": summ["regime_hint"],
            "signals": {
                "online_played": summ["online_played"], "online_attempted": summ["online_attempted"],
                "total_reports": summ["total_reports"],
                "eac_runtime_share_of_launchopts": summ["eac_runtime_share"],
                "ac_field_known": summ["ac_known"], "ac_impacted_share": summ["ac_impacted_share"],
                "mp_field_known": summ["mp_known"],
                "recent_yes_rate": summ["recent_yes_rate"],
            },
            "note": ("Anti-cheat/MP regime: config is NOT the decisive lever; success is gated by "
                     "whether the anti-cheat vendor enabled a Proton runtime (exogenous). High recent "
                     "yes-rate => the runtime IS currently accepted on Linux. Treat config params as "
                     "comfort/perf tweaks, and lean on the recency-windowed yes-rate as the go/no-go."),
        },
        "global_background_denominators": bg_denom,
        "hardware_bucket_denominators": bucket_denoms,
        "gpu_vendor_baseline": gpu_vendor_baseline(cur, appid),
        "catalog": catalog,
        "extraction_examples": extraction_examples(appid),
        "scoring_notes": {
            "catalog_relevance": "max(0, log(smoothed_lift)) * recency_weighted_prevalence  "
                                 "-- game-SPECIFICITY ordering only; NOT a benefit/risk score.",
            "smoothed_lift": "(support + k) / (denom*base_rate + k), k=%s  -- observed vs expected, "
                             "shrunk toward 1 at low support." % meta.get("smooth_k"),
            "selection_bias_warning": ("Users add launch options when STRUGGLING, so yes_rate_with_param "
                                       "and verdict_delta are weak/negatively-biased signals of efficacy "
                                       "(see -dx11). Lean on enrichment (lift) + recency for the catalog; "
                                       "defer benefit/risk to the annotation KB. All sub-scores are stored "
                                       "raw so a consumer can re-weight."),
            "basis": "launchopts params scored vs reports-with-launchOptions; proton variant/custom/notes "
                     "params scored vs their own present-population (see background_denominators).",
            "min_support_catalog": meta.get("min_support_catalog"),
        },
    }
    con.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--appid", required=True)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--out", default=None)
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args()
    data = export(args.appid, args.db, args.top)
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        print(f"wrote {args.out} ({len(data['catalog'])} catalog params)")
    else:
        print(text)


if __name__ == "__main__":
    main()
