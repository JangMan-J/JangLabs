# VDF Clean Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `tools/vdf_clean.py` to emit two output files per run — a conservative `clean.vdf` (no-op transforms only) and an aggressive `dedup.vdf` (group dedup, shell removal, metadata strip).

**Architecture:** Six new mutating passes added as module-level functions in `tools/vdf_clean.py`. Each pass accepts the parsed tree (a `Pairs` list) and returns a counts dict. A new `run_passes(root, aggressive)` orchestrator applies the right set of passes to an in-place deepcopy. `main()` calls it once per output path. Tests live in `tools/test_vdf_clean.py` using stdlib `unittest`, driving synthetic VDF strings through `tokenize` + `parse`.

**Tech Stack:** Python 3 (stdlib only: `re`, `argparse`, `pathlib`, `hashlib`, `copy`, `unittest`).

**Spec:** `docs/superpowers/specs/2026-04-22-vdf-clean-improvements-design.md`

---

## File Structure

- Modify: `tools/vdf_clean.py` — add 6 new pass functions + `run_passes()` orchestrator + CLI flag `--out-aggressive`. Existing functions (`tokenize`, `parse`, `Pairs`, `load_vdf`, `dump_vdf`, `analyze`, `build_layer_id_map`, `rewrite_bindings`, `deep_clean_cosmetic`, `strip_orphans`) are left intact.
- Create: `tools/test_vdf_clean.py` — unittest module with one `TestCase` per new pass plus one integration test against the Jangman fixture.

---

## Task 1: Test harness + `strip_empty_inputs`

**Files:**
- Create: `tools/test_vdf_clean.py`
- Modify: `tools/vdf_clean.py` — add `strip_empty_inputs()` after `deep_clean_cosmetic()` (around line 366)

- [ ] **Step 1: Write the failing test**

Create `tools/test_vdf_clean.py`:

```python
"""Unit tests for vdf_clean.py passes."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vdf_clean import (
    tokenize, parse, Pairs,
    strip_empty_inputs,
)


def parse_vdf(text):
    """Parse a VDF string into a Pairs tree (top-level)."""
    toks = tokenize(text)
    tree, _ = parse(toks)
    return tree


def keys_of(node):
    return [k for k, _ in node]


class TestStripEmptyInputs(unittest.TestCase):
    def test_removes_empty_inputs_block_in_group(self):
        tree = parse_vdf('''
            "controller_mappings"
            {
                "group"
                {
                    "id" "1"
                    "inputs" {}
                }
            }
        ''')
        counts = strip_empty_inputs(tree)
        group = tree.get_first("controller_mappings").get_first("group")
        self.assertNotIn("inputs", keys_of(group))
        self.assertEqual(counts["empty_inputs"], 1)

    def test_keeps_non_empty_inputs_block(self):
        tree = parse_vdf('''
            "controller_mappings"
            {
                "group"
                {
                    "id" "1"
                    "inputs" { "button_A" { "activators" {} } }
                }
            }
        ''')
        counts = strip_empty_inputs(tree)
        group = tree.get_first("controller_mappings").get_first("group")
        self.assertIn("inputs", keys_of(group))
        self.assertEqual(counts["empty_inputs"], 0)

    def test_recurses_into_nested_blocks(self):
        tree = parse_vdf('''
            "controller_mappings"
            {
                "preset"
                {
                    "nested"
                    {
                        "inputs" {}
                    }
                }
            }
        ''')
        counts = strip_empty_inputs(tree)
        self.assertEqual(counts["empty_inputs"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tools/test_vdf_clean.py -v`
Expected: `ImportError: cannot import name 'strip_empty_inputs'`

- [ ] **Step 3: Add `strip_empty_inputs` to `tools/vdf_clean.py`**

Insert this function immediately after `deep_clean_cosmetic` (i.e., after the `walk(root); return counts` block, line 365):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tools/test_vdf_clean.py -v`
Expected: 3 passing tests (all `TestStripEmptyInputs` methods).

- [ ] **Step 5: Commit**

```bash
git add tools/test_vdf_clean.py tools/vdf_clean.py
git commit -m "vdf_clean: add strip_empty_inputs pass + test harness"
```

---

## Task 2: `drop_dead_layer_refs`

**Files:**
- Modify: `tools/vdf_clean.py` — add after `strip_empty_inputs`
- Modify: `tools/test_vdf_clean.py` — append `TestDropDeadLayerRefs`

- [ ] **Step 1: Write the failing tests**

Append to `tools/test_vdf_clean.py` (add `drop_dead_layer_refs` to the imports at the top too):

```python
class TestDropDeadLayerRefs(unittest.TestCase):
    def test_drops_binding_with_dead_add_layer_target(self):
        tree = parse_vdf('''
            "controller_mappings"
            {
                "group"
                {
                    "inputs"
                    {
                        "button_A"
                        {
                            "activators"
                            {
                                "Full_Press"
                                {
                                    "bindings"
                                    {
                                        "binding" "controller_action add_layer 99 1 0"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        ''')
        live_layer_ids = {2, 3}
        counts = drop_dead_layer_refs(tree, live_layer_ids)
        self.assertEqual(counts["dead_layer_refs"], 1)
        # The binding pair should be gone
        def find_bindings(n, acc=None):
            if acc is None: acc = []
            if isinstance(n, list):
                for k, v in n:
                    if k == "binding": acc.append(v)
                    else: find_bindings(v, acc)
            return acc
        self.assertEqual(find_bindings(tree), [])

    def test_keeps_live_layer_refs(self):
        tree = parse_vdf('''
            "root"
            {
                "x"
                {
                    "binding" "controller_action add_layer 2 1 0"
                    "binding" "controller_action remove_layer 3 1 0"
                    "binding" "controller_action hold_layer 2 1 0"
                }
            }
        ''')
        counts = drop_dead_layer_refs(tree, {2, 3})
        self.assertEqual(counts["dead_layer_refs"], 0)

    def test_drops_remove_and_hold_variants(self):
        tree = parse_vdf('''
            "root"
            {
                "x"
                {
                    "binding" "controller_action remove_layer 99 1 0"
                    "binding" "controller_action hold_layer 99 1 0"
                }
            }
        ''')
        counts = drop_dead_layer_refs(tree, {2})
        self.assertEqual(counts["dead_layer_refs"], 2)

    def test_ignores_non_layer_bindings(self):
        tree = parse_vdf('''
            "root"
            {
                "x"
                {
                    "binding" "key_press SPACE"
                    "binding" "mouse_button LEFT"
                }
            }
        ''')
        counts = drop_dead_layer_refs(tree, set())
        self.assertEqual(counts["dead_layer_refs"], 0)
```

Update the imports at the top of `tools/test_vdf_clean.py`:

```python
from vdf_clean import (
    tokenize, parse, Pairs,
    strip_empty_inputs,
    drop_dead_layer_refs,
)
```

- [ ] **Step 2: Run to verify failure**

Run: `python tools/test_vdf_clean.py -v`
Expected: `ImportError: cannot import name 'drop_dead_layer_refs'`

- [ ] **Step 3: Add `drop_dead_layer_refs` to `tools/vdf_clean.py`**

Insert after `strip_empty_inputs`:

```python
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
```

Note: `LAYER_OP_RE` is already defined at the top of the file.

- [ ] **Step 4: Run tests**

Run: `python tools/test_vdf_clean.py -v`
Expected: all `TestStripEmptyInputs` + `TestDropDeadLayerRefs` pass (7 tests total).

- [ ] **Step 5: Commit**

```bash
git add tools/vdf_clean.py tools/test_vdf_clean.py
git commit -m "vdf_clean: add drop_dead_layer_refs pass"
```

---

## Task 3: `strip_empty_bindings`

**Files:**
- Modify: `tools/vdf_clean.py` — add after `drop_dead_layer_refs`
- Modify: `tools/test_vdf_clean.py` — append `TestStripEmptyBindings`

- [ ] **Step 1: Write the failing tests**

Append to `tools/test_vdf_clean.py`:

```python
class TestStripEmptyBindings(unittest.TestCase):
    def test_removes_empty_binding_pair(self):
        tree = parse_vdf('''
            "root"
            {
                "x"
                {
                    "binding" "empty_binding, , "
                    "binding" "key_press SPACE"
                }
            }
        ''')
        counts = strip_empty_bindings(tree)
        # Only the real binding should remain
        x = tree.get_first("root").get_first("x")
        remaining = [v for k, v in x if k == "binding"]
        self.assertEqual(len(remaining), 1)
        self.assertTrue(remaining[0].startswith("key_press"))
        self.assertEqual(counts["empty_bindings"], 1)

    def test_no_empty_bindings(self):
        tree = parse_vdf('''
            "root"
            {
                "x" { "binding" "key_press A" }
            }
        ''')
        counts = strip_empty_bindings(tree)
        self.assertEqual(counts["empty_bindings"], 0)
```

Update imports:

```python
from vdf_clean import (
    tokenize, parse, Pairs,
    strip_empty_inputs,
    drop_dead_layer_refs,
    strip_empty_bindings,
)
```

- [ ] **Step 2: Run to verify failure**

Run: `python tools/test_vdf_clean.py -v`
Expected: `ImportError: cannot import name 'strip_empty_bindings'`

- [ ] **Step 3: Implement**

Insert after `drop_dead_layer_refs`:

```python
def strip_empty_bindings(root):
    """Remove 'binding' pairs whose value begins with 'empty_binding'.
    These are Steam's UI placeholder no-ops.
    """
    counts = {"empty_bindings": 0}

    def walk(node):
        if not isinstance(node, list):
            return
        i = 0
        while i < len(node):
            k, v = node[i]
            if k == "binding" and isinstance(v, str) and v.lstrip().startswith("empty_binding"):
                del node[i]
                counts["empty_bindings"] += 1
                continue
            if isinstance(v, list):
                walk(v)
            i += 1

    walk(root)
    return counts
```

- [ ] **Step 4: Run tests**

Run: `python tools/test_vdf_clean.py -v`
Expected: 9 passing tests.

- [ ] **Step 5: Commit**

```bash
git add tools/vdf_clean.py tools/test_vdf_clean.py
git commit -m "vdf_clean: add strip_empty_bindings pass"
```

---

## Task 4: `dedupe_groups`

**Files:**
- Modify: `tools/vdf_clean.py` — add `_canonical_group_sig`, `_remap_group_refs`, and `dedupe_groups` near the bottom (before the CLI section)
- Modify: `tools/test_vdf_clean.py` — append `TestDedupeGroups`

- [ ] **Step 1: Write the failing tests**

Append to `tools/test_vdf_clean.py`:

```python
class TestDedupeGroups(unittest.TestCase):
    def test_collapses_identical_groups_different_ids(self):
        tree = parse_vdf('''
            "controller_mappings"
            {
                "group"
                {
                    "id" "1"
                    "mode" "dpad"
                    "inputs" { "dpad_north" { "activators" {} } }
                }
                "group"
                {
                    "id" "2"
                    "mode" "dpad"
                    "inputs" { "dpad_north" { "activators" {} } }
                }
                "preset"
                {
                    "id" "0"
                    "name" "Default"
                    "group_source_bindings"
                    {
                        "1" "switch active"
                        "2" "switch active"
                    }
                }
            }
        ''')
        counts = dedupe_groups(tree)
        self.assertEqual(counts["groups_removed"], 1)
        top = tree.get_first("controller_mappings")
        group_ids = sorted(int(v.get_first("id")) for k, v in top if k == "group")
        self.assertEqual(group_ids, [1])  # lowest id is canonical
        preset = next(v for k, v in top if k == "preset")
        gsb_keys = [k for k, _ in preset.get_first("group_source_bindings")]
        self.assertEqual(gsb_keys, ["1"])  # collision collapsed to canonical

    def test_preserves_non_duplicate_groups(self):
        tree = parse_vdf('''
            "controller_mappings"
            {
                "group"
                {
                    "id" "1"
                    "mode" "dpad"
                }
                "group"
                {
                    "id" "2"
                    "mode" "four_buttons"
                }
            }
        ''')
        counts = dedupe_groups(tree)
        self.assertEqual(counts["groups_removed"], 0)

    def test_rewrites_mode_shift_refs(self):
        tree = parse_vdf('''
            "controller_mappings"
            {
                "group"
                {
                    "id" "1"
                    "mode" "dpad"
                }
                "group"
                {
                    "id" "2"
                    "mode" "dpad"
                }
                "group"
                {
                    "id" "3"
                    "mode" "four_buttons"
                    "inputs"
                    {
                        "button_A"
                        {
                            "activators"
                            {
                                "Full_Press"
                                {
                                    "bindings"
                                    {
                                        "binding" "mode_shift left_trackpad 2"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        ''')
        counts = dedupe_groups(tree)
        # Collect all binding values
        def all_bindings(n, acc=None):
            if acc is None: acc = []
            if isinstance(n, list):
                for k, v in n:
                    if k == "binding": acc.append(v)
                    else: all_bindings(v, acc)
            return acc
        bindings = all_bindings(tree)
        self.assertIn("mode_shift left_trackpad 1", bindings)
        self.assertEqual(counts["groups_removed"], 1)
        self.assertEqual(counts["refs_rewritten"], 1)

    def test_three_way_duplicate(self):
        tree = parse_vdf('''
            "controller_mappings"
            {
                "group" { "id" "5" "mode" "dpad" }
                "group" { "id" "3" "mode" "dpad" }
                "group" { "id" "7" "mode" "dpad" }
                "preset"
                {
                    "group_source_bindings"
                    {
                        "5" "a b"
                        "3" "a b"
                        "7" "a b"
                    }
                }
            }
        ''')
        counts = dedupe_groups(tree)
        self.assertEqual(counts["groups_removed"], 2)
        top = tree.get_first("controller_mappings")
        group_ids = sorted(int(v.get_first("id")) for k, v in top if k == "group")
        self.assertEqual(group_ids, [3])  # lowest
```

Update imports:

```python
from vdf_clean import (
    tokenize, parse, Pairs,
    strip_empty_inputs,
    drop_dead_layer_refs,
    strip_empty_bindings,
    dedupe_groups,
)
```

- [ ] **Step 2: Run to verify failure**

Run: `python tools/test_vdf_clean.py -v`
Expected: `ImportError: cannot import name 'dedupe_groups'`

- [ ] **Step 3: Implement**

Insert this block in `tools/vdf_clean.py` after `strip_empty_bindings` and before the `# --------- CLI ---------` section header:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `python tools/test_vdf_clean.py -v`
Expected: 13 passing tests (3 empty_inputs + 4 layer refs + 2 empty_bindings + 4 dedupe).

- [ ] **Step 5: Commit**

```bash
git add tools/vdf_clean.py tools/test_vdf_clean.py
git commit -m "vdf_clean: add dedupe_groups pass with ref rewriting"
```

---

## Task 5: `strip_shell_groups`

**Files:**
- Modify: `tools/vdf_clean.py` — add after `dedupe_groups`
- Modify: `tools/test_vdf_clean.py` — append `TestStripShellGroups`

- [ ] **Step 1: Write the failing tests**

Append to `tools/test_vdf_clean.py`:

```python
class TestStripShellGroups(unittest.TestCase):
    def test_removes_binding_driven_shell(self):
        tree = parse_vdf('''
            "controller_mappings"
            {
                "group"
                {
                    "id" "10"
                    "mode" "dpad"
                    "inputs"
                    {
                        "dpad_north"
                        {
                            "activators"
                            {
                                "Full_Press"
                                {
                                    "bindings" {}
                                }
                            }
                        }
                    }
                }
                "preset"
                {
                    "group_source_bindings"
                    {
                        "10" "switch active"
                    }
                }
            }
        ''')
        counts = strip_shell_groups(tree)
        self.assertEqual(counts["shell_groups_removed"], 1)
        top = tree.get_first("controller_mappings")
        self.assertEqual([k for k, _ in top if k == "group"], [])
        preset = next(v for k, v in top if k == "preset")
        self.assertEqual(len(preset.get_first("group_source_bindings")), 0)

    def test_keeps_settings_driven_empty_inputs(self):
        # gyro_to_mouse with populated settings and no inputs must be kept
        tree = parse_vdf('''
            "controller_mappings"
            {
                "group"
                {
                    "id" "10"
                    "mode" "gyro_to_mouse"
                    "settings" { "gyro_enable_button" "1" }
                }
            }
        ''')
        counts = strip_shell_groups(tree)
        self.assertEqual(counts["shell_groups_removed"], 0)

    def test_keeps_group_with_real_binding(self):
        tree = parse_vdf('''
            "controller_mappings"
            {
                "group"
                {
                    "id" "10"
                    "mode" "dpad"
                    "inputs"
                    {
                        "dpad_north"
                        {
                            "activators"
                            {
                                "Full_Press"
                                {
                                    "bindings"
                                    {
                                        "binding" "key_press W"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        ''')
        counts = strip_shell_groups(tree)
        self.assertEqual(counts["shell_groups_removed"], 0)

    def test_drops_mode_shift_refs_to_shell(self):
        tree = parse_vdf('''
            "controller_mappings"
            {
                "group"
                {
                    "id" "10"
                    "mode" "dpad"
                }
                "group"
                {
                    "id" "11"
                    "mode" "four_buttons"
                    "inputs"
                    {
                        "button_A"
                        {
                            "activators"
                            {
                                "Full_Press"
                                {
                                    "bindings"
                                    {
                                        "binding" "mode_shift left_trackpad 10"
                                        "binding" "key_press A"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        ''')
        counts = strip_shell_groups(tree)
        self.assertEqual(counts["shell_groups_removed"], 1)
        def all_bindings(n, acc=None):
            if acc is None: acc = []
            if isinstance(n, list):
                for k, v in n:
                    if k == "binding": acc.append(v)
                    else: all_bindings(v, acc)
            return acc
        bindings = all_bindings(tree)
        self.assertEqual(bindings, ["key_press A"])
```

Update imports:

```python
from vdf_clean import (
    tokenize, parse, Pairs,
    strip_empty_inputs,
    drop_dead_layer_refs,
    strip_empty_bindings,
    dedupe_groups,
    strip_shell_groups,
)
```

- [ ] **Step 2: Run to verify failure**

Run: `python tools/test_vdf_clean.py -v`
Expected: `ImportError: cannot import name 'strip_shell_groups'`

- [ ] **Step 3: Implement**

Insert after `dedupe_groups`:

```python
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
                if s and not s.startswith("empty_binding"):
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
```

- [ ] **Step 4: Run tests**

Run: `python tools/test_vdf_clean.py -v`
Expected: 17 passing tests.

- [ ] **Step 5: Commit**

```bash
git add tools/vdf_clean.py tools/test_vdf_clean.py
git commit -m "vdf_clean: add strip_shell_groups pass"
```

---

## Task 6: `strip_meta_noise`

**Files:**
- Modify: `tools/vdf_clean.py` — add after `strip_shell_groups`
- Modify: `tools/test_vdf_clean.py` — append `TestStripMetaNoise`

- [ ] **Step 1: Write the failing tests**

Append to `tools/test_vdf_clean.py`:

```python
class TestStripMetaNoise(unittest.TestCase):
    def test_removes_zero_timestamp_and_revisions(self):
        tree = parse_vdf('''
            "controller_mappings"
            {
                "version" "3"
                "Timestamp" "0"
                "major_revision" "0"
                "minor_revision" "0"
                "progenitor" ""
            }
        ''')
        counts = strip_meta_noise(tree)
        top = tree.get_first("controller_mappings")
        keys = [k for k, _ in top]
        self.assertEqual(keys, ["version"])
        self.assertEqual(counts["meta_removed"], 4)

    def test_keeps_non_zero_meta(self):
        tree = parse_vdf('''
            "controller_mappings"
            {
                "Timestamp" "1700000000"
                "major_revision" "2"
                "progenitor" "template://foo.vdf"
            }
        ''')
        counts = strip_meta_noise(tree)
        top = tree.get_first("controller_mappings")
        self.assertEqual(len(top), 3)
        self.assertEqual(counts["meta_removed"], 0)

    def test_does_not_recurse(self):
        # A group containing a 'Timestamp' "0" pair should NOT be touched
        tree = parse_vdf('''
            "controller_mappings"
            {
                "group"
                {
                    "Timestamp" "0"
                }
            }
        ''')
        counts = strip_meta_noise(tree)
        group = tree.get_first("controller_mappings").get_first("group")
        self.assertEqual([k for k, _ in group], ["Timestamp"])
        self.assertEqual(counts["meta_removed"], 0)
```

Update imports:

```python
from vdf_clean import (
    tokenize, parse, Pairs,
    strip_empty_inputs,
    drop_dead_layer_refs,
    strip_empty_bindings,
    dedupe_groups,
    strip_shell_groups,
    strip_meta_noise,
)
```

- [ ] **Step 2: Run to verify failure**

Run: `python tools/test_vdf_clean.py -v`
Expected: `ImportError: cannot import name 'strip_meta_noise'`

- [ ] **Step 3: Implement**

Insert after `strip_shell_groups`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `python tools/test_vdf_clean.py -v`
Expected: 20 passing tests.

- [ ] **Step 5: Commit**

```bash
git add tools/vdf_clean.py tools/test_vdf_clean.py
git commit -m "vdf_clean: add strip_meta_noise pass"
```

---

## Task 7: Pipeline orchestrator + `--out-aggressive` CLI flag

**Files:**
- Modify: `tools/vdf_clean.py` — replace `main()` at the bottom of the file

- [ ] **Step 1: Replace `main()`**

Replace the existing `main()` function (starting at `def main():`) with this version:

```python
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

    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", help="write conservative cleaned VDF here")
    ap.add_argument("--out-aggressive",
                    help="write aggressively-cleaned VDF here "
                         "(adds dedup, shell removal, meta strip)")
    ap.add_argument("--no-renumber", action="store_true",
                    help="don't rewrite layer-id refs")
    ap.add_argument("--map", action="append", default=[],
                    metavar="OLD=NEW",
                    help="explicit layer-ref remap (can be repeated)")
    ap.add_argument("--deep", action="store_true",
                    help="also strip cosmetic junk in the conservative output "
                         "(empty name/description on groups, empty "
                         "disabled_activators blocks, non-english localization "
                         "entries). Always applied to --out-aggressive.")
    args = ap.parse_args()

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
```

- [ ] **Step 2: Smoke test conservative output**

Run:
```bash
python tools/vdf_clean.py "reference/vdf/jangman's jyro_v13.vdf" -o /tmp/clean.vdf --deep
```

On Windows, substitute an accessible path (e.g. `%TEMP%/clean.vdf`).

Expected:
- Prints the existing analysis report.
- Prints a "conservative pass counts" section with `empty_inputs: 99`, `dead_layer_refs: 2` (roughly — one each for add_layer 4 / remove_layer 4), `empty_bindings: 2`.
- Writes the output file.

- [ ] **Step 3: Smoke test aggressive output**

Run:
```bash
python tools/vdf_clean.py "reference/vdf/jangman's jyro_v13.vdf" --out-aggressive %TEMP%/dedup.vdf
```

Expected:
- Prints "aggressive pass counts" including `groups_removed` (dedup), `shell_groups_removed`, `meta_removed`.
- Writes the aggressive output file, smaller than the conservative one.

- [ ] **Step 4: Smoke test both outputs in one invocation**

Run:
```bash
python tools/vdf_clean.py "reference/vdf/jangman's jyro_v13.vdf" \
    -o %TEMP%/clean.vdf --deep \
    --out-aggressive %TEMP%/dedup.vdf
```

Expected: both files written. `wc -l` on them: aggressive < conservative < input.

- [ ] **Step 5: Run unit tests to confirm no regression**

Run: `python tools/test_vdf_clean.py -v`
Expected: 20 passing tests.

- [ ] **Step 6: Commit**

```bash
git add tools/vdf_clean.py
git commit -m "vdf_clean: wire new passes + --out-aggressive CLI flag"
```

---

## Task 8: Integration test against Jangman fixture

**Files:**
- Modify: `tools/test_vdf_clean.py` — append `TestJangmanIntegration`

- [ ] **Step 1: Write the integration test**

Append to `tools/test_vdf_clean.py`:

```python
import copy
from vdf_clean import load_vdf, analyze, build_layer_id_map, run_passes, dump_vdf


class TestJangmanIntegration(unittest.TestCase):
    FIXTURE = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "reference", "vdf", "jangman's jyro_v13.vdf",
    )

    def setUp(self):
        if not os.path.exists(self.FIXTURE):
            self.skipTest("Jangman fixture not present")
        self.root = load_vdf(self.FIXTURE)
        self.analysis = analyze(self.root)
        self.layer_id_map, _w, _l = build_layer_id_map(self.analysis)

    def _run(self, aggressive):
        tree = copy.deepcopy(self.root)
        counts = run_passes(
            tree, self.analysis, self.layer_id_map,
            aggressive=aggressive, apply_deep=True,
        )
        # Round-trip: dump + reparse must succeed without error
        text = dump_vdf(tree)
        from vdf_clean import tokenize, parse
        toks = tokenize(text)
        parse(toks)
        return tree, text, counts

    def test_conservative_output_parses_and_is_smaller(self):
        _tree, text, counts = self._run(aggressive=False)
        input_text = open(self.FIXTURE, encoding="utf-8").read()
        self.assertLess(len(text), len(input_text))
        self.assertGreater(counts["empty_inputs"], 0)
        self.assertGreater(counts["empty_bindings"], 0)
        self.assertGreater(counts["dead_layer_refs"], 0)

    def test_aggressive_output_is_smaller_than_conservative(self):
        _t1, cons_text, _ = self._run(aggressive=False)
        _t2, aggr_text, counts = self._run(aggressive=True)
        self.assertLess(len(aggr_text), len(cons_text))
        self.assertGreater(counts["groups_removed"], 0)
        self.assertGreater(counts["shell_groups_removed"], 0)
        self.assertGreater(counts["meta_removed"], 0)

    def test_aggressive_output_has_no_orphans_or_dupes(self):
        tree, _text, _counts = self._run(aggressive=True)
        # Re-analyze
        analysis2 = analyze(tree)
        self.assertEqual(len(analysis2["orphan_group_ids"]), 0)
        self.assertEqual(len(analysis2["orphan_preset_ids"]), 0)
        # Check no duplicate groups remain
        from vdf_clean import _canonical_group_sig
        top = tree.get_first("controller_mappings")
        sigs = []
        for k, v in top:
            if k == "group" and isinstance(v, list):
                sigs.append(_canonical_group_sig(v))
        self.assertEqual(len(sigs), len(set(sigs)))
```

- [ ] **Step 2: Run tests**

Run: `python tools/test_vdf_clean.py -v`
Expected: 23 passing tests (20 unit + 3 integration).

- [ ] **Step 3: Commit**

```bash
git add tools/test_vdf_clean.py
git commit -m "vdf_clean: add Jangman integration test"
```

---

## Final verification

- [ ] **Run full test suite:** `python tools/test_vdf_clean.py -v` — all 23 pass.
- [ ] **Sanity-diff the outputs:** open `clean.vdf` and `dedup.vdf` in an editor; spot-check that `group_source_bindings` keys still match surviving group ids in each file.
- [ ] **Steam round-trip (manual, user-driven, out of plan scope):** load `dedup.vdf` in Steam, verify layout behaves identically; this is the gate for the aggressive output.
