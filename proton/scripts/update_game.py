#!/usr/bin/env python3
"""
update_game.py — refresh ONE game's rows in data/protondb.sqlite without a full rebuild.

It re-reads the cached dump, filters to a single appid, recomputes that game's
summary / param / hardware-bucket rows, and replaces them in place. The GLOBAL
background table is reused as-is (it is the cross-game reference; a single game is
negligible against the ~52k-report launchOptions corpus). Re-run build_db.py to
refresh the background and pick up a newer monthly dump.

Usage:
  python3 scripts/update_game.py --appid 1808500
  python3 scripts/update_game.py --appid 1808500 --fetch    # pull latest dump first
  python3 scripts/update_game.py --appid 1808500 --dump PATH --db PATH
"""
import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import build_db as B  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(ROOT, "data", "protondb.sqlite")
CACHE_JSON = os.path.expanduser("~/.cache/protondb-tuner/reports_piiremoved.json")


def load_background(cur):
    bg_support = {}
    for pid, sup in cur.execute("SELECT param_id, support FROM background"):
        bg_support[pid] = sup
    bg_denom = dict(cur.execute("SELECT basis, denom FROM background_denom").fetchall())
    return bg_support, bg_denom


def update(appid, dump_path, db_path):
    if not os.path.exists(db_path):
        sys.exit(f"{db_path} missing -- run build_db.py first to create the background.")
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    bg_support, bg_denom = load_background(cur)
    if not bg_denom:
        sys.exit("background table empty -- run build_db.py first.")

    now_ts = int(dict(cur.execute("SELECT key,value FROM meta").fetchall()).get("dump_now_ts", "0"))

    with open(dump_path) as f:
        data = json.load(f)
    rs = [r for r in data if str(r.get("app", {}).get("steam", {}).get("appId")) == appid]
    if not rs:
        sys.exit(f"appid {appid} has no reports in {dump_path}")
    # keep now_ts consistent with current dump if it advanced
    now_ts = max(now_ts, max((r.get("timestamp", 0) or 0) for r in data))

    # ---- single-game accumulation (mirror of build_db pass 1, scoped to one appid) ----
    g_param = defaultdict(lambda: [0, 0, 0.0, 0] + [0] * 8)
    g_param_meta = {}
    basis_denom = defaultdict(int); basis_yes = defaultdict(int)
    basis_rw = defaultdict(float); basis_recent = defaultdict(int)
    basis_fault = defaultdict(lambda: defaultdict(int))
    s = {"title": "", "total": 0, "lo": 0, "yes_all": 0, "no_all": 0, "lo_yes": 0,
         "recent": 0, "recent_yes": 0, "ts_min": 1 << 62, "ts_max": 0,
         "ac_known": 0, "ac_impacted": 0, "mp_known": 0, "mp_important": 0,
         "online_attempt": 0, "online_played": 0, "eac_lo": 0,
         "var_recent_pos": defaultdict(int), "cust_recent_pos": defaultdict(int),
         "gpu": defaultdict(int)}

    gb_param = defaultdict(lambda: [0, 0])
    gb_denom = defaultdict(lambda: [0, 0])
    BTYPES = ("gpu_vendor", "display_server", "steamdeck")

    for r in rs:
        resp = r.get("responses", {}) or {}
        si = r.get("systemInfo", {}) or {}
        ts = r.get("timestamp", 0) or 0
        verdict = resp.get("verdict")
        yes = 1 if verdict == "yes" else 0
        lo = resp.get("launchOptions") or ""
        variant = resp.get("variant")
        custom = C.normalize_custom_proton(resp.get("customProtonVersion"))
        ntext = C.notes_text(resp.get("notes"))
        w = C.recency_weight(ts, now_ts)
        recent = C.months_ago(ts, now_ts) <= C.RECENT_WINDOW_MONTHS
        faults = {k: (1 if resp.get(k) == "yes" else 0) for k in C.FAULT_KEYS}

        s["title"] = r.get("app", {}).get("title") or s["title"]
        s["total"] += 1; s["yes_all"] += yes
        s["no_all"] += 1 if verdict == "no" else 0
        s["ts_min"] = min(s["ts_min"], ts); s["ts_max"] = max(s["ts_max"], ts)
        s["gpu"][C.gpu_vendor(si)] += 1
        ac = resp.get("isImpactedByAntiCheat")
        if ac in ("yes", "no"):
            s["ac_known"] += 1; s["ac_impacted"] += 1 if ac == "yes" else 0
        mp = resp.get("isMultiplayerImportant")
        if mp in ("yes", "no"):
            s["mp_known"] += 1; s["mp_important"] += 1 if mp == "yes" else 0
        if resp.get("onlineMultiplayerAttempted") == "yes":
            s["online_attempt"] += 1
        if resp.get("onlineMultiplayerPlayed") == "yes":
            s["online_played"] += 1

        params = []
        if lo:
            for ns, key, val in C.parse_launch_options(lo):
                params.append((C.param_id(ns, key, val), ns, key, val, C.BASIS_LAUNCHOPTS))
        if variant:
            params.append((C.param_id("proton", f"variant:{variant}", ""), "proton", f"variant:{variant}", "", C.BASIS_VARIANT))
        if custom:
            params.append((C.param_id("proton", "custom", custom), "proton", "custom", custom, C.BASIS_CUSTOMPROTON))
        for ver in C.mine_notes_versions(ntext):
            params.append((C.param_id("proton", "notes_version", ver), "proton", "notes_version", ver, C.BASIS_NOTES))

        bases_here = set()
        if lo:
            bases_here.add(C.BASIS_LAUNCHOPTS); s["lo"] += 1; s["lo_yes"] += yes
            if B.EAC_RUNTIME_RE.search(lo) or any(p[1] == "shellhack" for p in params):
                s["eac_lo"] += 1
        if variant:
            bases_here.add(C.BASIS_VARIANT)
        if custom:
            bases_here.add(C.BASIS_CUSTOMPROTON)
        if ntext:
            bases_here.add(C.BASIS_NOTES)
        for basis in bases_here:
            basis_denom[basis] += 1; basis_yes[basis] += yes; basis_rw[basis] += w
            if recent:
                basis_recent[basis] += 1
            for k, fv in faults.items():
                basis_fault[basis][k] += fv

        if recent:
            s["recent"] += 1; s["recent_yes"] += yes
            if yes:
                if variant:
                    s["var_recent_pos"][variant] += 1
                if custom:
                    s["cust_recent_pos"][custom] += 1

        for pid, ns, key, val, basis in params:
            g_param_meta.setdefault(pid, (ns, key, val, basis))
            cell = g_param[pid]
            cell[0] += 1; cell[1] += yes; cell[2] += w
            if recent:
                cell[3] += 1
            for i, k in enumerate(C.FAULT_KEYS):
                cell[4 + i] += faults[k]

        # buckets
        buckets = {"gpu_vendor": C.gpu_vendor(si),
                   "display_server": C.display_server(si, lo),
                   "steamdeck": "yes" if C.is_steam_deck(si, lo) else "no"}
        kept_pids = [p[0] for p in params]  # filter to support>=2 after the loop
        for bt in BTYPES:
            bv = buckets[bt]
            gb_denom[(bt, bv)][0] += 1; gb_denom[(bt, bv)][1] += yes
            for pid in set(kept_pids):
                gb_param[(pid, bt, bv)][0] += 1; gb_param[(pid, bt, bv)][1] += yes

    # ---- recompute rows using shared math (wrap accumulators in build_db's structures) ----
    g_param_w = {appid: g_param}
    g_basis_denom = {appid: basis_denom}; g_basis_yes = {appid: basis_yes}
    g_basis_rw = {appid: basis_rw}; g_basis_recent = {appid: basis_recent}
    g_basis_fault = {appid: basis_fault}
    param_rows = B.compute_game_param_rows(appid, g_param_w, g_param_meta, bg_support, bg_denom,
                                           g_basis_denom, g_basis_yes, g_basis_rw,
                                           g_basis_recent, g_basis_fault)

    # ---- summary row ----
    total, lo, yes_all = s["total"], s["lo"], s["yes_all"]
    baseline_yes = yes_all / total if total else 0.0
    baseline_yes_lo = s["lo_yes"] / lo if lo else None
    recent_yes_rate = s["recent_yes"] / s["recent"] if s["recent"] else None
    ac_share = s["ac_impacted"] / s["ac_known"] if s["ac_known"] else None
    mp_share = s["mp_important"] / s["mp_known"] if s["mp_known"] else None
    eac_share = s["eac_lo"] / lo if lo else 0.0
    online_played_share = s["online_played"] / total if total else 0.0
    dom_var = max(s["var_recent_pos"].items(), key=lambda x: x[1]) if s["var_recent_pos"] else (None, 0)
    dom_cust = max(s["cust_recent_pos"].items(), key=lambda x: x[1]) if s["cust_recent_pos"] else (None, 0)
    if s["ac_known"] >= 5 and ac_share is not None and ac_share >= 0.3:
        regime = "anticheat-mp"
    elif eac_share >= 0.10 or online_played_share >= 0.4 or \
            (s["mp_known"] >= 5 and mp_share is not None and mp_share >= 0.5):
        regime = "anticheat-mp"
    else:
        regime = "config-tunable"
    summ_row = (
        appid, s["title"], total, lo, yes_all, s["no_all"], round(baseline_yes, 4),
        s["lo_yes"], (round(baseline_yes_lo, 4) if baseline_yes_lo is not None else None),
        s["recent"], s["recent_yes"], (round(recent_yes_rate, 4) if recent_yes_rate is not None else None),
        (None if s["ts_min"] == 1 << 62 else s["ts_min"]), s["ts_max"],
        s["ac_known"], s["ac_impacted"], (round(ac_share, 4) if ac_share is not None else None),
        s["mp_known"], s["mp_important"], (round(mp_share, 4) if mp_share is not None else None),
        s["online_attempt"], s["online_played"], round(eac_share, 4),
        dom_var[0], dom_var[1], dom_cust[0], dom_cust[1],
        s["gpu"].get("NVIDIA", 0), s["gpu"].get("AMD", 0), s["gpu"].get("INTEL", 0),
        s["gpu"].get("UNKNOWN", 0), regime)

    # ---- replace rows for this appid ----
    cur.execute("DELETE FROM game_summary WHERE appid=?", (appid,))
    cur.execute("DELETE FROM game_param WHERE appid=?", (appid,))
    cur.execute("DELETE FROM game_param_bucket WHERE appid=?", (appid,))
    cur.execute("DELETE FROM game_bucket_denom WHERE appid=?", (appid,))

    cur.execute("INSERT INTO game_summary VALUES (%s)" % ",".join("?" * 32), summ_row)

    cols = ["appid", "param_id", "namespace", "key", "value", "display", "basis",
            "support", "denom", "prevalence", "base_rate", "lift", "smoothed_lift",
            "log_lift", "rweight_support", "rweight_denom", "recency_weighted_prevalence",
            "recent_support", "recent_denom", "recent_prevalence", "with_yes",
            "yes_rate_with_param", "verdict_delta", "perf_fault_delta",
            "graphical_fault_delta", "fault_assoc_json", "catalog_relevance"]
    cur.executemany("INSERT INTO game_param VALUES (%s)" % ",".join("?" * len(cols)),
                    [tuple(row[c] for c in cols) for row in param_rows])

    kept = {row["param_id"] for row in param_rows}
    bd_rows = [(appid, bt, bv, d[0], d[1]) for (bt, bv), d in gb_denom.items()]
    cur.executemany("INSERT INTO game_bucket_denom VALUES (?,?,?,?,?)", bd_rows)
    bp_rows = []
    for (pid, bt, bv), cell in gb_param.items():
        if cell[0] < 2 or pid not in kept:
            continue
        d = gb_denom.get((bt, bv), [0, 0])
        prev = cell[0] / d[0] if d[0] else 0.0
        yr = cell[1] / cell[0] if cell[0] else 0.0
        bp_rows.append((appid, pid, bt, bv, cell[0], d[0], round(prev, 5), cell[1], round(yr, 4)))
    cur.executemany("INSERT INTO game_param_bucket VALUES (?,?,?,?,?,?,?,?,?)", bp_rows)

    con.commit()
    con.close()
    print(f"[update] {appid} ({s['title']}): {total} reports, {lo} w/ launchOptions, "
          f"regime={regime}; wrote {len(param_rows)} params, {len(bp_rows)} bucket rows.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--appid", required=True)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--dump", default=None)
    ap.add_argument("--fetch", action="store_true", help="download the latest monthly dump first")
    args = ap.parse_args()
    if args.dump:
        dump_path = args.dump
    elif args.fetch:
        res = B.ensure_dump(fetch=True)
        dump_path = res[0] if isinstance(res, tuple) else res
    else:
        dump_path = CACHE_JSON
        if not os.path.exists(dump_path):
            sys.exit("No cached dump. Pass --fetch or --dump PATH.")
    update(args.appid, dump_path, args.db)


if __name__ == "__main__":
    main()
