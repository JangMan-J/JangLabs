#!/usr/bin/env python3
"""
build_db.py — full (re)build of the protondb-tuner inference database.

Pipeline:
  1. ensure the latest bdefore/protondb-data dump is downloaded + extracted to the cache
  2. pass 1: accumulate GLOBAL background base rates, per-game summaries, and
     per-game per-parameter stats (support / verdict / fault / recency)
  3. pass 2: for the kept (game, param) pairs, accumulate per-hardware-bucket stats
  4. compute lift / smoothed-lift / catalog-relevance and write SQLite

Usage:
  python3 scripts/build_db.py                 # fetch latest if needed, full rebuild
  python3 scripts/build_db.py --no-fetch      # use already-cached dump
  python3 scripts/build_db.py --dump PATH --db PATH

The raw dump is cached under ~/.cache/protondb-tuner and is NEVER committed.
"""
import argparse
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

CACHE_DIR = os.path.expanduser("~/.cache/protondb-tuner")
DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "protondb.sqlite")
GH_API = "https://api.github.com/repos/bdefore/protondb-data/contents/reports"
RAW_BASE = "https://raw.githubusercontent.com/bdefore/protondb-data/master/reports/"

_MON = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

EAC_RUNTIME_RE = re.compile(r"PROTON_(EAC_RUNTIME|USE_EAC_LINUX)|PROTON_(BATTLEYE_RUNTIME|USE_BATTLEYE)", re.I)


# --------------------------------------------------------------------------
# dump acquisition
# --------------------------------------------------------------------------
def latest_dump_name():
    out = subprocess.check_output(["curl", "-sL", GH_API], text=True)
    entries = [d["name"] for d in json.loads(out) if d.get("name", "").startswith("reports_")]

    def key(n):
        m = re.match(r"reports_([a-z]+)(\d+)_(\d+)\.tar\.gz", n)
        return (int(m.group(3)), _MON.get(m.group(1), 0), int(m.group(2))) if m else (0, 0, 0)

    entries.sort(key=key)
    return entries[-1]


def ensure_dump(fetch=True):
    os.makedirs(CACHE_DIR, exist_ok=True)
    json_path = os.path.join(CACHE_DIR, "reports_piiremoved.json")
    if not fetch:
        if not os.path.exists(json_path):
            sys.exit("No cached dump and --no-fetch given. Run without --no-fetch first.")
        return json_path
    name = latest_dump_name()
    tgz = os.path.join(CACHE_DIR, name)
    if not os.path.exists(tgz):
        print(f"[fetch] downloading {name} ...")
        subprocess.check_call(["curl", "-sL", "-o", tgz, RAW_BASE + name])
    # extract (always overwrite json so it matches the chosen tarball)
    print(f"[fetch] extracting {name} ...")
    subprocess.check_call(["tar", "xzf", tgz, "-C", CACHE_DIR])
    return json_path, name


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
def build(dump_path, db_path, dump_name="(local)"):
    t0 = time.time()
    with open(dump_path) as f:
        data = json.load(f)
    N = len(data)
    now_ts = max((r.get("timestamp", 0) or 0) for r in data)
    print(f"[build] {N} reports loaded in {time.time()-t0:.1f}s; now_ts={now_ts}")

    # ---- global background ----
    bg_support = defaultdict(int)                 # param_id -> count (all games)
    bg_meta = {}                                  # param_id -> (ns,key,val,basis)
    bg_denom = defaultdict(int)                   # basis -> count
    # vendor-split global background: lets a consumer separate "GPU-vendor BASELINE"
    # knobs (common-on-NVIDIA but not game-specific, e.g. PROTON_ENABLE_NVAPI) from
    # game-specific ones. keyed (param_id, gpu_vendor) and (basis, gpu_vendor).
    bg_vend_support = defaultdict(int)
    bg_vend_denom = defaultdict(int)

    # ---- per game ----
    g_basis_denom = defaultdict(lambda: defaultdict(int))     # appid -> basis -> n
    g_basis_yes = defaultdict(lambda: defaultdict(int))       # appid -> basis -> yes
    g_basis_rw = defaultdict(lambda: defaultdict(float))      # appid -> basis -> sum weight
    g_basis_recent = defaultdict(lambda: defaultdict(int))    # appid -> basis -> n (last window)
    g_basis_fault = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # appid->basis->faultkey->true

    # appid -> param_id -> [support, with_yes, rw_support, recent_support, f0..f7]
    g_param = defaultdict(lambda: defaultdict(lambda: [0, 0, 0.0, 0] + [0] * 8))
    g_param_meta = {}                             # param_id -> (ns,key,val,basis)

    g_sum = defaultdict(lambda: {
        "title": "", "total": 0, "lo": 0, "yes_all": 0, "no_all": 0, "lo_yes": 0,
        "recent": 0, "recent_yes": 0, "ts_min": 1 << 62, "ts_max": 0,
        "ac_known": 0, "ac_impacted": 0, "mp_known": 0, "mp_important": 0,
        "online_attempt": 0, "online_played": 0, "eac_lo": 0,
        "var_recent_pos": defaultdict(int), "cust_recent_pos": defaultdict(int),
        "gpu": defaultdict(int),
    })

    def emit(param_id, ns, key, val, basis):
        bg_meta.setdefault(param_id, (ns, key, val, basis))
        g_param_meta.setdefault(param_id, (ns, key, val, basis))

    for r in data:
        appid = str(r.get("app", {}).get("steam", {}).get("appId"))
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
        # NOTE: fault flags and the AC/MP fields are STRING "yes"/"no" (not JSON bool).
        faults = {k: (1 if resp.get(k) == "yes" else 0) for k in C.FAULT_KEYS}

        s = g_sum[appid]
        s["title"] = r.get("app", {}).get("title") or s["title"]
        s["total"] += 1
        s["yes_all"] += yes
        s["no_all"] += 1 if verdict == "no" else 0
        s["ts_min"] = min(s["ts_min"], ts)
        s["ts_max"] = max(s["ts_max"], ts)
        vendor = C.gpu_vendor(si)
        s["gpu"][vendor] += 1
        ac = resp.get("isImpactedByAntiCheat")
        if ac in ("yes", "no"):
            s["ac_known"] += 1
            if ac == "yes":
                s["ac_impacted"] += 1
        mp = resp.get("isMultiplayerImportant")
        if mp in ("yes", "no"):
            s["mp_known"] += 1
            if mp == "yes":
                s["mp_important"] += 1
        if resp.get("onlineMultiplayerAttempted") == "yes":
            s["online_attempt"] += 1
        if resp.get("onlineMultiplayerPlayed") == "yes":
            s["online_played"] += 1

        # collect the report's parameters across namespaces, tagged with denom basis
        params = []   # (param_id, ns, key, val, basis)
        if lo:
            for ns, key, val in C.parse_launch_options(lo):
                pid = C.param_id(ns, key, val)
                params.append((pid, ns, key, val, C.BASIS_LAUNCHOPTS))
        if variant:
            pid = C.param_id("proton", f"variant:{variant}", "")
            params.append((pid, "proton", f"variant:{variant}", "", C.BASIS_VARIANT))
        if custom:
            pid = C.param_id("proton", "custom", custom)
            params.append((pid, "proton", "custom", custom, C.BASIS_CUSTOMPROTON))
        for ver in C.mine_notes_versions(ntext):
            pid = C.param_id("proton", "notes_version", ver)
            params.append((pid, "proton", "notes_version", ver, C.BASIS_NOTES))

        # basis-level denominators / yes / faults / recency for this report
        bases_here = set()
        if lo:
            bases_here.add(C.BASIS_LAUNCHOPTS)
            s["lo"] += 1
            s["lo_yes"] += yes
            if EAC_RUNTIME_RE.search(lo) or any(p[1] == "shellhack" for p in params):
                s["eac_lo"] += 1
        if variant:
            bases_here.add(C.BASIS_VARIANT)
        if custom:
            bases_here.add(C.BASIS_CUSTOMPROTON)
        if ntext:
            bases_here.add(C.BASIS_NOTES)
        for basis in bases_here:
            bg_denom[basis] += 1
            bg_vend_denom[(basis, vendor)] += 1
            g_basis_denom[appid][basis] += 1
            g_basis_yes[appid][basis] += yes
            g_basis_rw[appid][basis] += w
            if recent:
                g_basis_recent[appid][basis] += 1
            for k, fv in faults.items():
                g_basis_fault[appid][basis][k] += fv

        if recent:
            s["recent"] += 1
            s["recent_yes"] += yes
            if yes:
                if variant:
                    s["var_recent_pos"][variant] += 1
                if custom:
                    s["cust_recent_pos"][custom] += 1

        # per-param accumulation
        for pid, ns, key, val, basis in params:
            emit(pid, ns, key, val, basis)
            bg_support[pid] += 1
            bg_vend_support[(pid, vendor)] += 1
            cell = g_param[appid][pid]
            cell[0] += 1
            cell[1] += yes
            cell[2] += w
            if recent:
                cell[3] += 1
            for i, k in enumerate(C.FAULT_KEYS):
                cell[4 + i] += faults[k]

    print(f"[build] pass 1 done in {time.time()-t0:.1f}s")

    # ---- decide keep-set: per-game params with support>=MIN_SUPPORT_STORE ----
    keep = defaultdict(set)   # appid -> set(param_id)
    for appid, pmap in g_param.items():
        for pid, cell in pmap.items():
            if cell[0] >= C.MIN_SUPPORT_STORE:
                keep[appid].add(pid)

    # ---- pass 2: hardware buckets for kept (game, param) pairs ----
    # bucket key: (appid, param_id, btype, bval) -> [support, with_yes]
    gb_param = defaultdict(lambda: [0, 0])
    # (appid, btype, bval) -> [denom, yes]  (per basis-agnostic report population that HAS the param's basis)
    gb_denom = defaultdict(lambda: [0, 0])
    BTYPES = ("gpu_vendor", "display_server", "steamdeck")

    for r in data:
        appid = str(r.get("app", {}).get("steam", {}).get("appId"))
        if appid not in keep:
            continue
        resp = r.get("responses", {}) or {}
        si = r.get("systemInfo", {}) or {}
        lo = resp.get("launchOptions") or ""
        yes = 1 if resp.get("verdict") == "yes" else 0
        variant = resp.get("variant")
        custom = C.normalize_custom_proton(resp.get("customProtonVersion"))
        ntext = C.notes_text(resp.get("notes"))

        buckets = {
            "gpu_vendor": C.gpu_vendor(si),
            "display_server": C.display_server(si, lo),
            "steamdeck": "yes" if C.is_steam_deck(si, lo) else "no",
        }

        # which params does this report carry, among the kept set
        pids = []
        if lo:
            for ns, key, val in C.parse_launch_options(lo):
                pids.append(C.param_id(ns, key, val))
        if variant:
            pids.append(C.param_id("proton", f"variant:{variant}", ""))
        if custom:
            pids.append(C.param_id("proton", "custom", custom))
        for ver in C.mine_notes_versions(ntext):
            pids.append(C.param_id("proton", "notes_version", ver))
        kept_pids = [p for p in set(pids) if p in keep[appid]]
        if not kept_pids:
            # still count denom for buckets so coverage is known? only if report carries some basis
            pass

        for btype in BTYPES:
            bval = buckets[btype]
            gb_denom[(appid, btype, bval)][0] += 1
            gb_denom[(appid, btype, bval)][1] += yes
            for pid in kept_pids:
                cell = gb_param[(appid, pid, btype, bval)]
                cell[0] += 1
                cell[1] += yes

    print(f"[build] pass 2 (buckets) done in {time.time()-t0:.1f}s")

    write_db(db_path, dump_name, now_ts, N, bg_support, bg_meta, bg_denom,
             g_sum, g_param, g_param_meta, g_basis_denom, g_basis_yes, g_basis_rw,
             g_basis_recent, g_basis_fault, keep, gb_param, gb_denom,
             bg_vend_support, bg_vend_denom)
    print(f"[build] wrote {db_path} in {time.time()-t0:.1f}s total")


def base_rate_for(bg_support, bg_denom, pid, basis):
    d = bg_denom.get(basis, 0)
    return (bg_support.get(pid, 0) / d) if d else 0.0


def compute_game_param_rows(appid, g_param, g_param_meta, bg_support, bg_denom,
                            g_basis_denom, g_basis_yes, g_basis_rw, g_basis_recent,
                            g_basis_fault):
    rows = []
    for pid, cell in g_param[appid].items():
        support, with_yes, rw_support, recent_support = cell[0], cell[1], cell[2], cell[3]
        if support < C.MIN_SUPPORT_STORE:
            continue
        ns, key, val, basis = g_param_meta[pid]
        denom = g_basis_denom[appid].get(basis, 0)
        if denom == 0:
            continue
        prevalence = support / denom
        base_rate = base_rate_for(bg_support, bg_denom, pid, basis)
        # raw lift uses the smoothed base_rate floor to avoid div0; smoothed_lift is the primary
        raw_lift = (prevalence / base_rate) if base_rate > 0 else float("inf")
        slift = C.smoothed_lift(support, denom, base_rate)
        log_lift = math.log(slift) if slift > 0 else 0.0

        rw_denom = g_basis_rw[appid].get(basis, 0.0)
        rwp = (rw_support / rw_denom) if rw_denom > 0 else 0.0
        rec_denom = g_basis_recent[appid].get(basis, 0)
        rec_prev = (recent_support / rec_denom) if rec_denom > 0 else 0.0

        baseline_yes = (g_basis_yes[appid].get(basis, 0) / denom) if denom else 0.0
        yes_rate_param = with_yes / support
        verdict_delta = yes_rate_param - baseline_yes

        fault_deltas = {}
        for i, k in enumerate(C.FAULT_KEYS):
            f_param = cell[4 + i] / support
            f_base = (g_basis_fault[appid][basis].get(k, 0) / denom) if denom else 0.0
            fault_deltas[k] = round(f_param - f_base, 4)

        specificity = max(0.0, log_lift)
        catalog_relevance = specificity * rwp

        rows.append({
            "appid": appid, "param_id": pid, "namespace": ns, "key": key, "value": val,
            "display": C.param_display(ns, key, val), "basis": basis,
            "support": support, "denom": denom, "prevalence": round(prevalence, 5),
            "base_rate": round(base_rate, 6), "lift": (None if raw_lift == float("inf") else round(raw_lift, 4)),
            "smoothed_lift": round(slift, 4), "log_lift": round(log_lift, 4),
            "rweight_support": round(rw_support, 3), "rweight_denom": round(rw_denom, 3),
            "recency_weighted_prevalence": round(rwp, 5),
            "recent_support": recent_support, "recent_denom": rec_denom,
            "recent_prevalence": round(rec_prev, 5),
            "with_yes": with_yes, "yes_rate_with_param": round(yes_rate_param, 4),
            "verdict_delta": round(verdict_delta, 4),
            "perf_fault_delta": fault_deltas["performanceFaults"],
            "graphical_fault_delta": fault_deltas["graphicalFaults"],
            "fault_assoc_json": json.dumps(fault_deltas),
            "catalog_relevance": round(catalog_relevance, 5),
        })
    rows.sort(key=lambda x: x["catalog_relevance"], reverse=True)
    return rows


def write_db(db_path, dump_name, now_ts, N, bg_support, bg_meta, bg_denom,
             g_sum, g_param, g_param_meta, g_basis_denom, g_basis_yes, g_basis_rw,
             g_basis_recent, g_basis_fault, keep, gb_param, gb_denom,
             bg_vend_support, bg_vend_denom):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(SCHEMA)

    cur.executemany("INSERT INTO meta VALUES (?,?)", [
        ("dump_file", dump_name), ("dump_now_ts", str(now_ts)),
        ("built_at", str(int(time.time()))), ("total_reports", str(N)),
        ("halflife_months", str(C.HALFLIFE_MONTHS)),
        ("recent_window_months", str(C.RECENT_WINDOW_MONTHS)),
        ("smooth_k", str(C.SMOOTH_K)), ("min_support_store", str(C.MIN_SUPPORT_STORE)),
        ("min_support_catalog", str(C.MIN_SUPPORT_CATALOG)),
    ])

    cur.executemany("INSERT INTO background_denom VALUES (?,?)", list(bg_denom.items()))
    bg_rows = []
    for pid, sup in bg_support.items():
        ns, key, val, basis = bg_meta[pid]
        bg_rows.append((pid, ns, key, val, C.param_display(ns, key, val), basis,
                        sup, bg_denom.get(basis, 0),
                        round(sup / bg_denom[basis], 6) if bg_denom.get(basis) else 0.0))
    cur.executemany("INSERT INTO background VALUES (?,?,?,?,?,?,?,?,?)", bg_rows)

    # vendor-split global background (gpu_vendor), support>=2 to suppress noise
    cur.executemany("INSERT INTO background_bucket_denom VALUES (?,?,?,?)",
                    [(basis, "gpu_vendor", vend, d) for (basis, vend), d in bg_vend_denom.items()])
    bgv_rows = []
    for (pid, vend), sup in bg_vend_support.items():
        if sup < 2 or pid not in bg_meta:
            continue
        basis = bg_meta[pid][3]
        d = bg_vend_denom.get((basis, vend), 0)
        bgv_rows.append((pid, "gpu_vendor", vend, basis, sup, d,
                         round(sup / d, 6) if d else 0.0))
    cur.executemany("INSERT INTO background_bucket VALUES (?,?,?,?,?,?,?)", bgv_rows)

    # game summaries (total>=3 to keep the table meaningful)
    sum_rows = []
    for appid, s in g_sum.items():
        if s["total"] < 3:
            continue
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
        # regime hint
        if s["ac_known"] >= 5 and ac_share is not None and ac_share >= 0.3:
            regime = "anticheat-mp"
        elif eac_share >= 0.10 or online_played_share >= 0.4 or \
                (s["mp_known"] >= 5 and mp_share is not None and mp_share >= 0.5):
            regime = "anticheat-mp"
        else:
            regime = "config-tunable"
        sum_rows.append((
            appid, s["title"], total, lo, yes_all, s["no_all"], round(baseline_yes, 4),
            s["lo_yes"], (round(baseline_yes_lo, 4) if baseline_yes_lo is not None else None),
            s["recent"], s["recent_yes"], (round(recent_yes_rate, 4) if recent_yes_rate is not None else None),
            (None if s["ts_min"] == 1 << 62 else s["ts_min"]), s["ts_max"],
            s["ac_known"], s["ac_impacted"], (round(ac_share, 4) if ac_share is not None else None),
            s["mp_known"], s["mp_important"], (round(mp_share, 4) if mp_share is not None else None),
            s["online_attempt"], s["online_played"], round(eac_share, 4),
            dom_var[0], dom_var[1], dom_cust[0], dom_cust[1],
            s["gpu"].get("NVIDIA", 0), s["gpu"].get("AMD", 0), s["gpu"].get("INTEL", 0),
            s["gpu"].get("UNKNOWN", 0), regime,
        ))
    cur.executemany("INSERT INTO game_summary VALUES (%s)" % ",".join("?" * 32), sum_rows)

    # per-game param rows
    param_rows = []
    cols = ["appid", "param_id", "namespace", "key", "value", "display", "basis",
            "support", "denom", "prevalence", "base_rate", "lift", "smoothed_lift",
            "log_lift", "rweight_support", "rweight_denom", "recency_weighted_prevalence",
            "recent_support", "recent_denom", "recent_prevalence", "with_yes",
            "yes_rate_with_param", "verdict_delta", "perf_fault_delta",
            "graphical_fault_delta", "fault_assoc_json", "catalog_relevance"]
    for appid in keep:
        for row in compute_game_param_rows(appid, g_param, g_param_meta, bg_support, bg_denom,
                                           g_basis_denom, g_basis_yes, g_basis_rw,
                                           g_basis_recent, g_basis_fault):
            param_rows.append(tuple(row[c] for c in cols))
    cur.executemany("INSERT INTO game_param VALUES (%s)" % ",".join("?" * len(cols)), param_rows)

    # bucket denom + bucket params (support>=2)
    bd_rows = [(a, bt, bv, d[0], d[1]) for (a, bt, bv), d in gb_denom.items()]
    cur.executemany("INSERT INTO game_bucket_denom VALUES (?,?,?,?,?)", bd_rows)

    bp_rows = []
    for (appid, pid, bt, bv), cell in gb_param.items():
        if cell[0] < 2:
            continue
        d = gb_denom.get((appid, bt, bv), [0, 0])
        prev = cell[0] / d[0] if d[0] else 0.0
        yr = cell[1] / cell[0] if cell[0] else 0.0
        bp_rows.append((appid, pid, bt, bv, cell[0], d[0], round(prev, 5), cell[1], round(yr, 4)))
    cur.executemany("INSERT INTO game_param_bucket VALUES (?,?,?,?,?,?,?,?,?)", bp_rows)

    con.commit()
    print(f"[db] background={len(bg_rows)} background_bucket={len(bgv_rows)} summaries={len(sum_rows)} "
          f"game_param={len(param_rows)} bucket_denom={len(bd_rows)} bucket_param={len(bp_rows)}")
    con.close()


SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE background_denom (basis TEXT PRIMARY KEY, denom INTEGER);
CREATE TABLE background (
  param_id TEXT PRIMARY KEY, namespace TEXT, key TEXT, value TEXT, display TEXT,
  basis TEXT, support INTEGER, denom INTEGER, base_rate REAL
);
CREATE TABLE background_bucket_denom (
  basis TEXT, bucket_type TEXT, bucket_value TEXT, denom INTEGER,
  PRIMARY KEY (basis, bucket_type, bucket_value)
);
CREATE TABLE background_bucket (
  param_id TEXT, bucket_type TEXT, bucket_value TEXT, basis TEXT,
  support INTEGER, denom INTEGER, base_rate REAL,
  PRIMARY KEY (param_id, bucket_type, bucket_value)
);
CREATE TABLE game_summary (
  appid TEXT PRIMARY KEY, title TEXT, total_reports INTEGER, lo_reports INTEGER,
  yes_all INTEGER, no_all INTEGER, baseline_yes_rate REAL,
  lo_yes INTEGER, baseline_yes_rate_lo REAL,
  recent_reports INTEGER, recent_yes INTEGER, recent_yes_rate REAL,
  ts_min INTEGER, ts_max INTEGER,
  ac_known INTEGER, ac_impacted INTEGER, ac_impacted_share REAL,
  mp_known INTEGER, mp_important INTEGER, mp_important_share REAL,
  online_attempted INTEGER, online_played INTEGER, eac_runtime_share REAL,
  dominant_variant_recent TEXT, dominant_variant_recent_n INTEGER,
  dominant_custom_recent TEXT, dominant_custom_recent_n INTEGER,
  gpu_nvidia INTEGER, gpu_amd INTEGER, gpu_intel INTEGER, gpu_unknown INTEGER,
  regime_hint TEXT
);
CREATE TABLE game_param (
  appid TEXT, param_id TEXT, namespace TEXT, key TEXT, value TEXT, display TEXT, basis TEXT,
  support INTEGER, denom INTEGER, prevalence REAL, base_rate REAL, lift REAL,
  smoothed_lift REAL, log_lift REAL, rweight_support REAL, rweight_denom REAL,
  recency_weighted_prevalence REAL, recent_support INTEGER, recent_denom INTEGER,
  recent_prevalence REAL, with_yes INTEGER, yes_rate_with_param REAL, verdict_delta REAL,
  perf_fault_delta REAL, graphical_fault_delta REAL, fault_assoc_json TEXT,
  catalog_relevance REAL,
  PRIMARY KEY (appid, param_id)
);
CREATE TABLE game_bucket_denom (
  appid TEXT, bucket_type TEXT, bucket_value TEXT, denom INTEGER, yes INTEGER,
  PRIMARY KEY (appid, bucket_type, bucket_value)
);
CREATE TABLE game_param_bucket (
  appid TEXT, param_id TEXT, bucket_type TEXT, bucket_value TEXT,
  support INTEGER, denom INTEGER, prevalence REAL, with_yes INTEGER, yes_rate_with_param REAL,
  PRIMARY KEY (appid, param_id, bucket_type, bucket_value)
);
CREATE INDEX idx_gp_appid ON game_param(appid);
CREATE INDEX idx_gp_relevance ON game_param(appid, catalog_relevance);
CREATE INDEX idx_gpb_appid ON game_param_bucket(appid);
CREATE INDEX idx_bg_basis ON background(basis);
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=None, help="path to reports_piiremoved.json (default: cache)")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--no-fetch", action="store_true", help="use cached dump, do not hit the network")
    args = ap.parse_args()

    if args.dump:
        dump_path, dump_name = args.dump, os.path.basename(args.dump)
    else:
        res = ensure_dump(fetch=not args.no_fetch)
        if isinstance(res, tuple):
            dump_path, dump_name = res
        else:
            dump_path, dump_name = res, "(cached)"
    build(dump_path, args.db, dump_name)


if __name__ == "__main__":
    main()
