"""
Steam Input VDF cleaner.

Parses a Steam Input layout VDF, computes which 'group' blocks are actually
reachable from live presets (action sets + action layers), and reports orphans.
Optionally writes a cleaned copy with:
  - orphan groups removed
  - unused preset group_source_bindings entries removed
  - layer-target IDs (add_layer/remove_layer/hold_layer) renumbered to match
    their preset ids (fixes the 'remove_layer 5' vs preset id=4 drift)

Usage:
  python vdf_clean.py <input.vdf>                     # dry-run analysis
  python vdf_clean.py <input.vdf> -o <output.vdf>     # write cleaned copy
"""

from __future__ import annotations
import sys
import re
import argparse
from pathlib import Path


# --------- VDF parser (preserves duplicate keys, uses list-of-pairs) ---------

TOKEN_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|(\{)|(\})', re.S)


def tokenize(text: str):
    # Strip // line comments (Steam VDFs don't use them but be safe)
    out = []
    for m in TOKEN_RE.finditer(text):
        s, o, c = m.group(1), m.group(2), m.group(3)
        if s is not None:
            out.append(("STR", s))
        elif o:
            out.append(("OBJ_OPEN", None))
        elif c:
            out.append(("OBJ_CLOSE", None))
    return out


class Pairs(list):
    """list of (key, value) where value is str or Pairs."""

    def get_all(self, key):
        return [v for k, v in self if k == key]

    def get_first(self, key, default=None):
        for k, v in self:
            if k == key:
                return v
        return default


def parse(tokens, i=0, top=True):
    pairs = Pairs()
    while i < len(tokens):
        tt, tv = tokens[i]
        if tt == "OBJ_CLOSE":
            return pairs, i + 1
        if tt != "STR":
            raise ValueError(f"expected key string at token {i}, got {tt}")
        key = tv
        i += 1
        if i >= len(tokens):
            raise ValueError("unexpected EOF after key")
        nt, nv = tokens[i]
        if nt == "STR":
            pairs.append((key, nv))
            i += 1
        elif nt == "OBJ_OPEN":
            sub, i = parse(tokens, i + 1, top=False)
            pairs.append((key, sub))
        else:
            raise ValueError(f"unexpected token {nt} after key {key!r}")
    if not top:
        raise ValueError("unclosed object")
    return pairs, i


def load_vdf(path):
    text = Path(path).read_text(encoding="utf-8")
    toks = tokenize(text)
    tree, _ = parse(toks)
    return tree


def dump_vdf(pairs, indent=0):
    out = []
    pad = "\t" * indent
    for k, v in pairs:
        if isinstance(v, list):
            out.append(f'{pad}"{k}"')
            out.append(f"{pad}{{")
            out.append(dump_vdf(v, indent + 1))
            out.append(f"{pad}}}")
        else:
            # mimic Steam spacing: "key"<tab><tab>"value"
            out.append(f'{pad}"{k}"\t\t"{v}"')
    return "\n".join(out)


# --------- Reachability analysis ---------

def walk_strings(node):
    """Yield every leaf string value in the tree."""
    if isinstance(node, list):
        for _, v in node:
            yield from walk_strings(v)
    else:
        yield node


def walk_bindings(node):
    """Yield every value of a key named 'binding'."""
    if isinstance(node, list):
        for k, v in node:
            if k == "binding" and isinstance(v, str):
                yield v
            else:
                yield from walk_bindings(v)


LAYER_OP_RE = re.compile(
    r'^\s*controller_action\s+(add_layer|remove_layer|hold_layer)\s+(\d+)'
)
MODE_SHIFT_RE = re.compile(r'^\s*mode_shift\s+\S+\s+(\d+)')
EMPTY_BINDING_RE = re.compile(r'^\s*(?:controller_action\s+)?empty_binding\b')


def analyze(root):
    top = root.get_first("controller_mappings")
    if top is None:
        raise ValueError("no controller_mappings root")

    # Collect all groups by id
    groups_by_id = {}
    for k, v in top:
        if k == "group" and isinstance(v, list):
            gid = v.get_first("id")
            if gid is not None:
                groups_by_id[int(gid)] = v

    # Collect all presets
    presets = []
    for k, v in top:
        if k == "preset" and isinstance(v, list):
            presets.append(v)

    # Action sets (names in 'actions' block)
    actions = top.get_first("actions") or Pairs()
    action_set_names = {k for k, _ in actions}

    # Action layers (names in 'action_layers' block)
    action_layers_block = top.get_first("action_layers") or Pairs()
    action_layer_names = {k for k, _ in action_layers_block}

    preset_by_name = {}
    preset_by_id = {}
    for p in presets:
        name = p.get_first("name")
        pid = p.get_first("id")
        if name is not None:
            preset_by_name[name] = p
        if pid is not None:
            preset_by_id[int(pid)] = p

    # Reachable presets = all action sets + action layers that have presets
    live_preset_ids = set()
    for name in action_set_names | action_layer_names:
        p = preset_by_name.get(name)
        if p is not None:
            pid = p.get_first("id")
            if pid is not None:
                live_preset_ids.add(int(pid))

    # Also: follow add_layer/hold_layer/remove_layer to check what preset ids
    # are referenced by bindings (to detect drift)
    layer_refs_by_op = {"add_layer": set(), "remove_layer": set(), "hold_layer": set()}
    for g in groups_by_id.values():
        for b in walk_bindings(g):
            m = LAYER_OP_RE.match(b)
            if m:
                layer_refs_by_op[m.group(1)].add(int(m.group(2)))

    # Reachable group IDs
    live_group_ids = set()
    for pid in live_preset_ids:
        p = preset_by_id[pid]
        gsb = p.get_first("group_source_bindings") or Pairs()
        for k, _v in gsb:
            try:
                live_group_ids.add(int(k))
            except ValueError:
                pass

    # Transitive: follow mode_shift <src> <group_id> refs from reachable groups
    frontier = list(live_group_ids)
    while frontier:
        gid = frontier.pop()
        g = groups_by_id.get(gid)
        if g is None:
            continue
        for b in walk_bindings(g):
            m = MODE_SHIFT_RE.match(b)
            if m:
                tgt = int(m.group(1))
                if tgt not in live_group_ids:
                    live_group_ids.add(tgt)
                    frontier.append(tgt)

    # Orphans
    all_group_ids = set(groups_by_id.keys())
    orphan_group_ids = all_group_ids - live_group_ids

    # Preset orphans = declared presets not in any action set / action layer
    all_preset_ids = set(preset_by_id.keys())
    orphan_preset_ids = all_preset_ids - live_preset_ids

    return {
        "groups_by_id": groups_by_id,
        "preset_by_id": preset_by_id,
        "preset_by_name": preset_by_name,
        "action_set_names": action_set_names,
        "action_layer_names": action_layer_names,
        "live_preset_ids": live_preset_ids,
        "live_group_ids": live_group_ids,
        "orphan_group_ids": orphan_group_ids,
        "orphan_preset_ids": orphan_preset_ids,
        "layer_refs_by_op": layer_refs_by_op,
    }


# --------- Cleaning + renumber ---------

def build_layer_id_map(analysis):
    """
    Steam's layer-id counter drifts from preset ids when layers get deleted.
    We want a consistent mapping where add_layer/remove_layer/hold_layer targets
    equal the preset id.

    Strategy:
      - For each live action LAYER (not action set), its "canonical layer id"
        is its preset id.
      - Find every add_layer N in reachable bindings. Try to match N to a live
        preset. If N already equals a live preset id that's also an action
        layer, keep it. Otherwise, map it to the unique live action-layer id if
        there's exactly one candidate, else warn.
    """
    preset_by_id = analysis["preset_by_id"]
    action_layer_names = analysis["action_layer_names"]
    layer_preset_ids = set()
    for name in action_layer_names:
        p = analysis["preset_by_name"].get(name)
        if p is not None:
            pid = p.get_first("id")
            if pid is not None:
                layer_preset_ids.add(int(pid))

    # Collect all referenced layer targets across all three ops
    refs = (
        analysis["layer_refs_by_op"]["add_layer"]
        | analysis["layer_refs_by_op"]["remove_layer"]
        | analysis["layer_refs_by_op"]["hold_layer"]
    )

    id_map = {}
    warnings = []
    for r in refs:
        if r in layer_preset_ids:
            id_map[r] = r
        else:
            # drift: referenced layer id doesn't match any live action-layer preset
            if len(layer_preset_ids) == 1:
                target = next(iter(layer_preset_ids))
                id_map[r] = target
                warnings.append(f"layer ref {r} remapped to {target} (sole live layer)")
            else:
                # leave alone, flag it
                warnings.append(
                    f"layer ref {r} does not match any live layer preset "
                    f"({sorted(layer_preset_ids)}); manual review needed"
                )
    return id_map, warnings, layer_preset_ids


def rewrite_bindings(node, layer_id_map):
    """Mutates the tree: rewrite add_layer/remove_layer/hold_layer targets."""
    if not isinstance(node, list):
        return
    for i, (k, v) in enumerate(node):
        if k == "binding" and isinstance(v, str):
            m = LAYER_OP_RE.match(v)
            if m:
                op = m.group(1)
                old = int(m.group(2))
                if old in layer_id_map and layer_id_map[old] != old:
                    new = layer_id_map[old]
                    # Preserve the rest of the binding tail (e.g. " 1 1")
                    tail = v[m.end():]
                    node[i] = (k, f"controller_action {op} {new}{tail}")
        else:
            rewrite_bindings(v, layer_id_map)


def _is_empty_block(v):
    return isinstance(v, list) and len(v) == 0


def deep_clean_cosmetic(root, keep_localization_langs=("english",)):
    """
    Strip purely cosmetic junk in-place:
      - "name" "" and "description" "" pairs inside groups
      - empty "disabled_activators" {} blocks (anywhere)
      - non-kept localization language blocks
    Returns a dict with counts of what was removed.
    """
    counts = {
        "empty_name": 0,
        "empty_description": 0,
        "empty_disabled_activators": 0,
        "localization_langs_removed": 0,
    }

    def walk(node, ctx_is_group=False):
        if not isinstance(node, list):
            return
        i = 0
        while i < len(node):
            k, v = node[i]
            # Inside a group, remove empty name/description
            if ctx_is_group and k == "name" and v == "":
                del node[i]
                counts["empty_name"] += 1
                continue
            if ctx_is_group and k == "description" and v == "":
                del node[i]
                counts["empty_description"] += 1
                continue
            # Remove empty disabled_activators blocks
            if k == "disabled_activators" and _is_empty_block(v):
                del node[i]
                counts["empty_disabled_activators"] += 1
                continue
            # Recurse
            if isinstance(v, list):
                walk(v, ctx_is_group=(k == "group"))
            i += 1

    # Localization pass at top level
    top = root.get_first("controller_mappings")
    if top is not None:
        loc = top.get_first("localization")
        if isinstance(loc, list):
            kept = Pairs()
            for lk, lv in loc:
                if lk in keep_localization_langs:
                    kept.append((lk, lv))
                else:
                    counts["localization_langs_removed"] += 1
            loc.clear()
            loc.extend(kept)

    walk(root)
    return counts


def strip_empty_inputs(root):
    """Remove empty 'inputs' {} blocks anywhere in the tree.

    Returns counts dict.
    """
    counts = {"empty_inputs": 0}

    def walk(node):
        if not isinstance(node, list):
            return
        i = 0
        while i < len(node):
            k, v = node[i]
            if k == "inputs" and isinstance(v, list) and len(v) == 0:
                del node[i]
                counts["empty_inputs"] += 1
                continue
            if isinstance(v, list):
                walk(v)
            i += 1

    walk(root)
    return counts


def drop_dead_layer_refs(root, live_layer_ids):
    """Remove 'binding' pairs whose add_layer/remove_layer/hold_layer target
    is not a live action-layer preset id.

    live_layer_ids: set of int preset ids that correspond to action layers.
    Returns counts dict.
    """
    counts = {"dead_layer_refs": 0}

    def walk(node):
        if not isinstance(node, list):
            return
        i = 0
        while i < len(node):
            k, v = node[i]
            if k == "binding" and isinstance(v, str):
                m = LAYER_OP_RE.match(v)
                if m and int(m.group(2)) not in live_layer_ids:
                    del node[i]
                    counts["dead_layer_refs"] += 1
                    continue
            if isinstance(v, list):
                walk(v)
            i += 1

    walk(root)
    return counts


def strip_empty_bindings(root):
    """Remove 'binding' pairs whose value is a Steam UI placeholder no-op.

    Matches both the bare form ('empty_binding, , ') and the
    controller_action wrapper ('controller_action empty_binding, , ').
    """
    counts = {"empty_bindings": 0}

    def walk(node):
        if not isinstance(node, list):
            return
        i = 0
        while i < len(node):
            k, v = node[i]
            if k == "binding" and isinstance(v, str) and EMPTY_BINDING_RE.match(v):
                del node[i]
                counts["empty_bindings"] += 1
                continue
            if isinstance(v, list):
                walk(v)
            i += 1

    walk(root)
    return counts


MODE_SHIFT_GROUP_RE = re.compile(r'^(\s*mode_shift\s+\S+\s+)(\d+)(.*)$')


def _canonical_group_sig(group):
    """Hash a group's content excluding its 'id' key (top-level only)."""
    import hashlib

    def serialize(node):
        if isinstance(node, list):
            return "[" + ",".join(f"{k}:{serialize(v)}" for k, v in node) + "]"
        return repr(node)

    filtered = [(k, v) for k, v in group if k != "id"]
    return hashlib.md5(serialize(filtered).encode("utf-8")).hexdigest()


def _rewrite_group_refs(root, remap):
    """Rewrite group_source_bindings keys and mode_shift binding targets
    using remap {old_id: new_id}. Returns number of rewrites performed.

    Duplicate GSB keys after rewrite are collapsed (canonical wins).
    """
    rewrites = 0
    top = root.get_first("controller_mappings")
    if top is None:
        return 0

    # group_source_bindings on each preset
    for k, v in top:
        if k != "preset" or not isinstance(v, list):
            continue
        gsb = v.get_first("group_source_bindings")
        if not isinstance(gsb, list):
            continue
        new_gsb = Pairs()
        seen_keys = set()
        for gk, gv in gsb:
            try:
                gid = int(gk)
            except ValueError:
                new_gsb.append((gk, gv))
                continue
            target = remap.get(gid, gid)
            target_key = str(target)
            if target != gid:
                rewrites += 1
            if target_key in seen_keys:
                continue  # collision with canonical already present
            seen_keys.add(target_key)
            new_gsb.append((target_key, gv))
        gsb.clear()
        gsb.extend(new_gsb)

    # mode_shift bindings anywhere in the tree
    def walk(node):
        nonlocal rewrites
        if not isinstance(node, list):
            return
        for i, (k, v) in enumerate(node):
            if k == "binding" and isinstance(v, str):
                m = MODE_SHIFT_GROUP_RE.match(v)
                if m:
                    old = int(m.group(2))
                    new = remap.get(old, old)
                    if new != old:
                        node[i] = (k, f"{m.group(1)}{new}{m.group(3)}")
                        rewrites += 1
            elif isinstance(v, list):
                walk(v)

    walk(root)
    return rewrites


def dedupe_groups(root):
    """Fold groups with identical content (ignoring id). The lowest id in
    each bucket becomes canonical; other ids are remapped and their group
    blocks removed.

    Returns counts dict with groups_removed, buckets_merged, refs_rewritten.
    """
    counts = {"groups_removed": 0, "buckets_merged": 0, "refs_rewritten": 0}
    top = root.get_first("controller_mappings")
    if top is None:
        return counts

    buckets = {}
    for k, v in top:
        if k != "group" or not isinstance(v, list):
            continue
        gid_str = v.get_first("id")
        if gid_str is None:
            continue
        try:
            gid = int(gid_str)
        except ValueError:
            continue
        sig = _canonical_group_sig(v)
        buckets.setdefault(sig, []).append(gid)

    remap = {}
    for sig, ids in buckets.items():
        if len(ids) < 2:
            continue
        counts["buckets_merged"] += 1
        canonical = min(ids)
        for gid in ids:
            if gid != canonical:
                remap[gid] = canonical

    if not remap:
        return counts

    counts["refs_rewritten"] = _rewrite_group_refs(root, remap)

    # Remove non-canonical groups
    doomed = set(remap.keys())
    new_top = Pairs()
    for k, v in top:
        if k == "group" and isinstance(v, list):
            gid_str = v.get_first("id")
            try:
                if gid_str is not None and int(gid_str) in doomed:
                    counts["groups_removed"] += 1
                    continue
            except ValueError:
                pass
        new_top.append((k, v))
    top.clear()
    top.extend(new_top)

    return counts


def _group_real_binding_count(group):
    """Count 'binding' pair values that are non-empty and not empty_binding."""
    count = 0
    def walk(node):
        nonlocal count
        if not isinstance(node, list):
            return
        for k, v in node:
            if k == "binding" and isinstance(v, str):
                s = v.strip()
                if s and not EMPTY_BINDING_RE.match(s):
                    count += 1
            elif isinstance(v, list):
                walk(v)
    walk(group)
    return count


def _group_settings_is_empty(group):
    """True iff group has no 'settings' block, or the settings block is empty."""
    settings = group.get_first("settings")
    if settings is None:
        return True
    if isinstance(settings, list) and len(settings) == 0:
        return True
    return False


def strip_shell_groups(root):
    """Remove groups that have zero real bindings AND no non-empty settings.

    Also drops group_source_bindings entries and mode_shift bindings that
    reference removed shell ids.

    Returns counts dict.
    """
    counts = {"shell_groups_removed": 0, "shell_ids": []}
    top = root.get_first("controller_mappings")
    if top is None:
        return counts

    shell_ids = set()
    for k, v in top:
        if k != "group" or not isinstance(v, list):
            continue
        gid_str = v.get_first("id")
        if gid_str is None:
            continue
        try:
            gid = int(gid_str)
        except ValueError:
            continue
        if _group_real_binding_count(v) == 0 and _group_settings_is_empty(v):
            shell_ids.add(gid)

    if not shell_ids:
        return counts

    counts["shell_ids"] = sorted(shell_ids)

    # Remove shell groups from top level
    new_top = Pairs()
    for k, v in top:
        if k == "group" and isinstance(v, list):
            gid_str = v.get_first("id")
            try:
                if gid_str is not None and int(gid_str) in shell_ids:
                    counts["shell_groups_removed"] += 1
                    continue
            except ValueError:
                pass
        new_top.append((k, v))
    top.clear()
    top.extend(new_top)

    # Drop GSB entries referencing shell ids
    for k, v in top:
        if k == "preset" and isinstance(v, list):
            gsb = v.get_first("group_source_bindings")
            if isinstance(gsb, list):
                kept = Pairs()
                for gk, gv in gsb:
                    try:
                        if int(gk) in shell_ids:
                            continue
                    except ValueError:
                        pass
                    kept.append((gk, gv))
                gsb.clear()
                gsb.extend(kept)

    # Drop mode_shift bindings targeting shell ids
    def walk(node):
        if not isinstance(node, list):
            return
        i = 0
        while i < len(node):
            k, v = node[i]
            if k == "binding" and isinstance(v, str):
                m = MODE_SHIFT_GROUP_RE.match(v)
                if m and int(m.group(2)) in shell_ids:
                    del node[i]
                    continue
            if isinstance(v, list):
                walk(v)
            i += 1

    walk(root)
    return counts


def strip_meta_noise(root):
    """Remove zero/empty top-level metadata keys from controller_mappings.

    Affected keys (removed iff value matches):
      Timestamp       "0"
      major_revision  "0"
      minor_revision  "0"
      progenitor      ""
    """
    counts = {"meta_removed": 0}
    top = root.get_first("controller_mappings")
    if top is None:
        return counts

    REMOVE = {
        "Timestamp": "0",
        "major_revision": "0",
        "minor_revision": "0",
        "progenitor": "",
    }

    new_top = Pairs()
    for k, v in top:
        if k in REMOVE and isinstance(v, str) and v == REMOVE[k]:
            counts["meta_removed"] += 1
            continue
        new_top.append((k, v))
    top.clear()
    top.extend(new_top)
    return counts


def strip_orphans(root, analysis):
    """Remove orphan groups from top level and drop orphan groups from preset
    group_source_bindings. Also remove orphan presets."""
    top = root.get_first("controller_mappings")
    orphan_group_ids = analysis["orphan_group_ids"]
    orphan_preset_ids = analysis["orphan_preset_ids"]

    # Filter top children
    new_children = Pairs()
    for k, v in top:
        if k == "group" and isinstance(v, list):
            gid = v.get_first("id")
            if gid is not None and int(gid) in orphan_group_ids:
                continue
        if k == "preset" and isinstance(v, list):
            pid = v.get_first("id")
            if pid is not None and int(pid) in orphan_preset_ids:
                continue
        new_children.append((k, v))
    # replace in-place
    top.clear()
    top.extend(new_children)

    # Strip orphan group refs from surviving presets' group_source_bindings
    for k, v in top:
        if k == "preset" and isinstance(v, list):
            gsb = v.get_first("group_source_bindings")
            if isinstance(gsb, list):
                kept = Pairs()
                for gk, gv in gsb:
                    try:
                        if int(gk) in orphan_group_ids:
                            continue
                    except ValueError:
                        pass
                    kept.append((gk, gv))
                gsb.clear()
                gsb.extend(kept)


# --------- CLI ---------

def format_report(analysis, layer_id_map, warnings, layer_preset_ids):
    lines = []
    lines.append("=== Presets ===")
    for pid in sorted(analysis["preset_by_id"].keys()):
        p = analysis["preset_by_id"][pid]
        name = p.get_first("name")
        live = "live" if pid in analysis["live_preset_ids"] else "ORPHAN"
        role = ""
        if name in analysis["action_set_names"]:
            role = "action set"
        elif name in analysis["action_layer_names"]:
            role = "action layer"
        lines.append(f"  id={pid:<3} name={name:<20} [{live}] {role}")

    lines.append("")
    lines.append(f"=== Groups: {len(analysis['groups_by_id'])} total, "
                 f"{len(analysis['live_group_ids'])} live, "
                 f"{len(analysis['orphan_group_ids'])} orphan ===")
    if analysis["orphan_group_ids"]:
        lines.append(f"  orphan ids: {sorted(analysis['orphan_group_ids'])}")

    lines.append("")
    lines.append("=== Layer-id references (add_layer / remove_layer / hold_layer) ===")
    for op, ids in analysis["layer_refs_by_op"].items():
        lines.append(f"  {op}: {sorted(ids)}")
    lines.append(f"  live action-layer preset ids: {sorted(layer_preset_ids)}")

    if any(layer_id_map.get(k, k) != k for k in layer_id_map):
        lines.append("")
        lines.append("=== Proposed layer-id renumbering ===")
        for old, new in sorted(layer_id_map.items()):
            if old != new:
                lines.append(f"  {old} -> {new}")

    if warnings:
        lines.append("")
        lines.append("=== Warnings ===")
        for w in warnings:
            lines.append(f"  {w}")

    return "\n".join(lines)



def _compute_live_layer_ids(analysis):
    """Derive the set of preset ids that are action layers."""
    live = set()
    for name in analysis["action_layer_names"]:
        p = analysis["preset_by_name"].get(name)
        if p is not None:
            pid = p.get_first("id")
            if pid is not None:
                try:
                    live.add(int(pid))
                except ValueError:
                    pass
    return live


def run_passes(root, analysis, layer_id_map, aggressive, apply_deep):
    """Mutate root in place, applying the shared pipeline plus optional
    aggressive passes. Returns an aggregated counts dict.
    """
    import copy as _copy  # imported locally to keep module top lean

    combined = {}

    # Layer-id renumber (existing)
    rewrite_bindings(root, layer_id_map)

    # Orphan strip (existing)
    strip_orphans(root, analysis)

    # Deep cosmetic (existing) — always for aggressive, conditional for conservative
    if apply_deep or aggressive:
        combined.update(deep_clean_cosmetic(root))

    # New shared passes
    combined.update(strip_empty_inputs(root))
    combined.update(drop_dead_layer_refs(root, _compute_live_layer_ids(analysis)))
    combined.update(strip_empty_bindings(root))

    if aggressive:
        combined.update(dedupe_groups(root))
        combined.update(strip_shell_groups(root))
        combined.update(strip_meta_noise(root))

    return combined


def main():
    import copy

    ap = argparse.ArgumentParser(
        epilog=(
            "Two-output model: -o/--output writes a conservative clean VDF "
            "(safe transforms only). --out-aggressive adds dedup, shell removal, "
            "and metadata stripping. Both may be specified in one run. The aggressive "
            "output always applies --deep cosmetic cleanup regardless of the flag."
        ),
    )
    ap.add_argument("input")
    ap.add_argument("-o", "--output", help="write conservative cleaned VDF here")
    ap.add_argument("--out-aggressive",
                    help="write aggressively-cleaned VDF here "
                         "(adds dedup, shell removal, meta strip)")
    ap.add_argument("--no-renumber", action="store_true",
                    help="don't rewrite layer-id refs (incompatible with --map)")
    ap.add_argument("--map", action="append", default=[],
                    metavar="OLD=NEW",
                    help="explicit layer-ref remap (can be repeated)")
    ap.add_argument("--deep", action="store_true",
                    help="also strip cosmetic junk in the conservative output "
                         "(empty name/description on groups, empty "
                         "disabled_activators blocks, non-english localization "
                         "entries). Always applied to --out-aggressive.")
    args = ap.parse_args()

    if args.no_renumber and args.map:
        ap.error("--no-renumber cannot be combined with --map; choose one")
    if not args.output and not args.out_aggressive:
        ap.error("specify -o/--output and/or --out-aggressive (at least one is required)")

    root = load_vdf(args.input)
    analysis = analyze(root)
    layer_id_map, warnings, layer_preset_ids = build_layer_id_map(analysis)

    for m in args.map:
        old_s, new_s = m.split("=", 1)
        layer_id_map[int(old_s)] = int(new_s)

    if args.no_renumber:
        layer_id_map = {}

    print(format_report(analysis, layer_id_map, warnings, layer_preset_ids))

    def _write_output(path, aggressive):
        tree = copy.deepcopy(root)
        counts = run_passes(tree, analysis, layer_id_map,
                            aggressive=aggressive, apply_deep=args.deep)
        out = dump_vdf(tree)
        Path(path).write_text(out + "\n", encoding="utf-8")
        label = "aggressive" if aggressive else "conservative"
        print(f"\n=== {label} pass counts ===")
        for k, v in counts.items():
            print(f"  {k}: {v}")
        print(f"Wrote {path}")

    if args.output:
        _write_output(args.output, aggressive=False)
    if args.out_aggressive:
        _write_output(args.out_aggressive, aggressive=True)


if __name__ == "__main__":
    main()
