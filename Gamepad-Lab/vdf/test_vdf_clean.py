"""Unit tests for vdf_clean.py passes."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vdf_clean import (
    tokenize, parse, Pairs,
    strip_empty_inputs,
    drop_dead_layer_refs,
    strip_empty_bindings,
    dedupe_groups,
    strip_shell_groups,
    strip_meta_noise,
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
        nested = tree.get_first("controller_mappings").get_first("preset").get_first("nested")
        self.assertNotIn("inputs", keys_of(nested))
        self.assertEqual(counts["empty_inputs"], 1)


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

    def test_removes_controller_action_empty_binding(self):
        tree = parse_vdf('''
            "root"
            {
                "x"
                {
                    "binding" "controller_action empty_binding, , "
                    "binding" "key_press Q"
                }
            }
        ''')
        counts = strip_empty_bindings(tree)
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

    def test_treats_wrapped_empty_binding_as_shell_content(self):
        # _group_real_binding_count must recognize Steam's wrapped form
        # so a group whose only "real" binding is a wrapped empty_binding
        # is correctly classified as a shell.
        tree = parse_vdf('''
            "controller_mappings"
            {
                "group"
                {
                    "id" "10"
                    "mode" "dpad"
                    "inputs"
                    {
                        "click"
                        {
                            "activators"
                            {
                                "Full_Press"
                                {
                                    "bindings"
                                    {
                                        "binding" "controller_action empty_binding, , "
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


class TestRunPassesSynthetic(unittest.TestCase):
    """End-to-end tests for run_passes against a synthetic VDF string.

    Unlike TestJangmanIntegration, these do not depend on the
    reference/ fixture and therefore never skip on fresh clones.
    """

    SYNTHETIC = '''
        "controller_mappings"
        {
            "version" "3"
            "Timestamp" "0"
            "progenitor" ""
            "actions"
            {
                "Default" { "StickPadGyro" {} "AnalogTrigger" {} "Button" {} }
            }
            "preset"
            {
                "id" "0"
                "name" "Default"
                "group_source_bindings"
                {
                    "1" "switch active"
                    "2" "switch active"
                    "3" "switch active"
                    "4" "switch active"
                }
            }
            "group"
            {
                "id" "1"
                "mode" "dpad"
                "inputs" { "dpad_north" { "activators" { "Full_Press" { "bindings" { "binding" "key_press W" } } } } }
            }
            "group"
            {
                "id" "2"
                "mode" "dpad"
                "inputs" { "dpad_north" { "activators" { "Full_Press" { "bindings" { "binding" "key_press W" } } } } }
            }
            "group"
            {
                "id" "3"
                "mode" "trigger"
                "inputs"
                {
                    "click"
                    {
                        "activators"
                        {
                            "Full_Press"
                            {
                                "bindings" { "binding" "controller_action empty_binding, , " }
                            }
                        }
                    }
                }
            }
            "group"
            {
                "id" "4"
                "mode" "four_buttons"
                "inputs" { }
            }
        }
    '''

    def _build(self):
        # Import inside the method to mirror the other integration class's style
        from vdf_clean import (
            load_vdf, analyze, build_layer_id_map, run_passes,
            dump_vdf, tokenize, parse,
        )
        import copy
        import io

        # Parse the synthetic VDF into a tree via the existing parse pipeline
        toks = tokenize(self.SYNTHETIC)
        tree, _ = parse(toks)
        analysis = analyze(tree)
        layer_id_map, _w, _l = build_layer_id_map(analysis)
        return tree, analysis, layer_id_map

    def _run(self, aggressive):
        import copy
        from vdf_clean import run_passes, dump_vdf, tokenize, parse
        tree, analysis, layer_id_map = self._build()
        mutated = copy.deepcopy(tree)
        counts = run_passes(
            mutated, analysis, layer_id_map,
            aggressive=aggressive, apply_deep=True,
        )
        text = dump_vdf(mutated)
        # Round-trip must succeed
        parse(tokenize(text))
        return mutated, text, counts

    def test_conservative_pipeline_exercises_shared_passes(self):
        _tree, _text, counts = self._run(aggressive=False)
        self.assertGreater(counts["empty_inputs"], 0)
        self.assertGreater(counts["empty_bindings"], 0)

    def test_aggressive_pipeline_exercises_aggressive_passes(self):
        _tree, _text, counts = self._run(aggressive=True)
        # The two identical groups (ids 1, 2) should fold
        self.assertGreater(counts["groups_removed"], 0)
        # The Timestamp="0" and progenitor="" should be removed
        self.assertGreater(counts["meta_removed"], 0)

    def test_aggressive_output_strictly_smaller_than_conservative(self):
        _t1, cons_text, _ = self._run(aggressive=False)
        _t2, aggr_text, _ = self._run(aggressive=True)
        self.assertLess(len(aggr_text), len(cons_text))


import copy
from vdf_clean import load_vdf, analyze, build_layer_id_map, run_passes, dump_vdf


class TestJangmanIntegration(unittest.TestCase):
    FIXTURE = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "reference", "jangman's jyro_v13.vdf",
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


if __name__ == "__main__":
    unittest.main()
