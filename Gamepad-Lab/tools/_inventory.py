"""
One-shot inventory extractor for Step 1a of the VDF-to-JSM translation plan.

Reuses vdf_clean.py's parser + analyzer to produce a flat Markdown dump of
every reachable group / input / activator / setting in a Steam Input VDF,
suitable as the raw material for the Step 1b per-item audit.

Usage:
    python _inventory.py <input.vdf>
"""

from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8")

from vdf_clean import Pairs, analyze, load_vdf


def fmt_value(v) -> str:
    if isinstance(v, list):
        return f"<{len(v)} child pairs>"
    return f"`{v}`"


def main(path: str) -> None:
    root = load_vdf(path)
    a = analyze(root)
    top = root.get_first("controller_mappings")

    print(f"# VDF inventory — `{Path(path).name}`")
    print()
    print(f"**Source:** `{path}`")
    print()

    # Metadata
    print("## Top-level metadata")
    for k in (
        "title", "description", "creator", "controller_type",
        "major_revision", "minor_revision", "Timestamp", "progenitor",
    ):
        v = top.get_first(k)
        if v is not None and not isinstance(v, list):
            print(f"- `{k}` = `{v}`")
    print()

    # Action sets
    print("## Action sets")
    actions_block = top.get_first("actions") or Pairs()
    for name, body in actions_block:
        if not isinstance(body, list):
            continue
        title = body.get_first("title") or ""
        p = a["preset_by_name"].get(name)
        pid = p.get_first("id") if p is not None else "?"
        print(f"- `{name}` → preset id `{pid}`, title `{title}`")
    print()

    # Action layers
    print("## Action layers")
    layers_block = top.get_first("action_layers") or Pairs()
    for name, body in layers_block:
        if not isinstance(body, list):
            continue
        title = body.get_first("title") or ""
        parent = body.get_first("parent_set_name") or "?"
        p = a["preset_by_name"].get(name)
        pid = p.get_first("id") if p is not None else "?"
        print(f"- `{name}` → preset id `{pid}`, parent `{parent}`, title `{title}`")
    print()

    # Preset → group mappings
    print("## Per-preset group references (live only)")
    for pid in sorted(a["live_preset_ids"]):
        p = a["preset_by_id"][pid]
        name = p.get_first("name") or "?"
        print()
        print(f"### Preset {pid} — `{name}`")
        gsb = p.get_first("group_source_bindings") or Pairs()
        if not gsb:
            print("- _(no group_source_bindings)_")
            continue
        for k, v in gsb:
            print(f"- group `{k}` → `{v}`")
    print()

    # Per-group detail
    print("## Per-group detail (reachable only)")
    for gid in sorted(a["live_group_ids"]):
        g = a["groups_by_id"].get(gid)
        if g is None:
            continue
        mode = g.get_first("mode") or "?"
        print()
        print(f"### Group {gid} — mode `{mode}`")

        settings = g.get_first("settings")
        if isinstance(settings, list) and settings:
            print()
            print("**Settings:**")
            for k, v in settings:
                if isinstance(v, str):
                    print(f"- `{k}` = `{v}`")

        inputs = g.get_first("inputs")
        if isinstance(inputs, list) and inputs:
            print()
            print("**Inputs:**")
            for in_name, in_body in inputs:
                if not isinstance(in_body, list):
                    continue
                print(f"- `{in_name}`")
                activators = in_body.get_first("activators")
                if not isinstance(activators, list):
                    continue
                for act_type, act_body in activators:
                    if not isinstance(act_body, list):
                        continue
                    bindings_block = act_body.get_first("bindings")
                    if isinstance(bindings_block, list):
                        for bk, bv in bindings_block:
                            if isinstance(bv, str):
                                print(f"    - `{act_type}` / `{bk}` = `{bv}`")
                    asettings = act_body.get_first("settings")
                    if isinstance(asettings, list):
                        for sk, sv in asettings:
                            if isinstance(sv, str):
                                print(f"    - `{act_type}` / setting `{sk}` = `{sv}`")
    print()

    # Orphan groups (informational — likely cruft from Steam's UI)
    orphans = sorted(a["orphan_group_ids"])
    if orphans:
        print(f"## Orphan groups (not reachable; {len(orphans)} total)")
        print(f"- IDs: {', '.join(str(i) for i in orphans)}")
        print()

    # Layer ops referenced by bindings (for crosscheck)
    refs = a["layer_refs_by_op"]
    if any(refs.values()):
        print("## Layer-op references found in bindings")
        for op, ids in refs.items():
            if ids:
                print(f"- `{op}` → preset ids: {', '.join(str(i) for i in sorted(ids))}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python _inventory.py <input.vdf>", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1])
