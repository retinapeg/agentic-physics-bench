"""V3 tasks, plans and the shortcut simulation on the frozen generator."""
import random
import statistics
import unittest
from fractions import Fraction

import fixtures_v3 as F
import pendulum_v3
import shortcuts_v3
import tasks
import tasks_v2
import tasks_v3

# 4,000 draws per stratum, seed 7, tolerance +/-0.002: the table recorded in PROTOCOL.md section 6.
SHORTCUT_TABLE = {
    "S1": {"endpoint": 1.6, "split_halves": 2.5, "subsample_10": 100.0, "equal_spacing": 100.0, "nominal_grid": 100.0,
           "exact_2dp": 39.9, "exact_3dp": 100.0},
    "S2": {"endpoint": 3.5, "split_halves": 26.8, "subsample_10": 3.9, "equal_spacing": 8.8, "nominal_grid": 4.3,
           "exact_2dp": 40.3, "exact_3dp": 100.0},
}


def exact_slope(t_strings, v_strings):
    t, v = [Fraction(x) for x in t_strings], [Fraction(x) for x in v_strings]
    tb, vb = sum(t) / len(t), sum(v) / len(v)
    return sum((a - tb) * (b - vb) for a, b in zip(t, v)) / sum((a - tb) ** 2 for a in t)


class TaskTests(unittest.TestCase):
    def test_counts_schema_signs_and_strata(self):
        for split, per in (("dev", 2), ("heldout", 6)):
            cases, keys = tasks_v3.make_tasks(split)
            self.assertEqual(len(cases), 2 * per)
            for case, key in zip(cases, keys):
                self.assertEqual(set(case), {"id", "t_s", "v_m_per_s"})          # V1's schema: fit_line works unchanged
                p = tasks_v3.STRATA[key["stratum"]]
                self.assertEqual((len(case["t_s"]), len(case["v_m_per_s"]), key["n_points"]), (p["n"], p["n"], p["n"]))
                self.assertEqual(tasks_v3.stratum_of(case["id"]), key["stratum"])
                self.assertTrue(case["id"].startswith(tasks_v3.ID_PREFIX[split]))
                for s in case["v_m_per_s"]:
                    self.assertRegex(s, r"^-?\d+\.\d{2}$")
                for s in case["t_s"]:
                    self.assertRegex(s, r"^\d+\.\d{%d}$" % p["t_dp"])
            for stratum in tasks_v3.STRATUM_ORDER:
                signs = [1 if k["a_true"] > 0 else -1 for k in keys if k["stratum"] == stratum]
                self.assertEqual(signs, [-1, 1] * (per // 2))

    def test_s2_gaps_and_strictly_increasing_times(self):
        for split in ("dev", "heldout"):
            for case, key in zip(*tasks_v3.make_tasks(split)):
                t = [float(x) for x in case["t_s"]]
                self.assertEqual(t[0], 0.0)
                self.assertTrue(all(b > a for a, b in zip(t, t[1:])))
                if key["stratum"] == "S2":
                    gaps = [b - a for a, b in zip(t, t[1:])]
                    self.assertGreaterEqual(min(gaps), 0.1 - 0.011)              # U(0.1, 0.9) before 2-dp rounding
                    self.assertLessEqual(max(gaps), 0.9 + 0.011)
                    self.assertGreater(statistics.pstdev(gaps), 0.15)            # a genuinely irregular grid

    def test_reference_matches_independent_calculations(self):
        for split in ("dev", "heldout"):
            for case, key in zip(*tasks_v3.make_tasks(split)):
                t, v = [float(x) for x in case["t_s"]], [float(x) for x in case["v_m_per_s"]]
                self.assertAlmostEqual(key["a_ref"], statistics.linear_regression(t, v).slope, places=10)
                self.assertAlmostEqual(key["a_ref"], float(exact_slope(case["t_s"], case["v_m_per_s"])), places=10)

    def test_regeneration_is_byte_identical_and_splits_are_disjoint(self):
        for split in ("dev", "heldout"):
            for name, text in tasks_v3.files(split).items():
                self.assertEqual((F.C.DATA / name).read_text(), text, name)
        for name, text in pendulum_v3.files().items():
            self.assertEqual((F.C.DATA / name).read_text(), text, name)
        shown = lambda cs: {tuple(c["v_m_per_s"]) for c in cs}
        dev, held = tasks_v3.make_tasks("dev")[0], tasks_v3.make_tasks("heldout")[0]
        v2 = tasks_v2.make_tasks("scored")[0] + tasks_v2.make_tasks("dev")[0]
        v1 = tasks.make_scored_cases()[0] + tasks.make_dev_cases()[0]
        self.assertFalse(shown(dev) & shown(held))
        self.assertFalse((shown(dev) | shown(held)) & (shown(v2) | shown(v1)))   # new tasks, not V1's or V2's
        seeds = [s for split in tasks_v3.SEEDS.values() for s in split.values()]
        self.assertEqual(len(seeds), len(set(seeds)))

    def test_s1_is_v1s_procedure(self):
        rng = random.Random(tasks_v3.SEEDS["heldout"]["S1"])
        expected = [tasks.make_case(rng, f"h1-{i:02d}", -1 if i % 2 else 1, 0.5)[0] for i in range(1, 7)]
        self.assertEqual([c for c in tasks_v3.make_tasks("heldout")[0] if c["id"].startswith("h1")], expected)

    def test_plans(self):
        held = tasks_v3.make_plan("heldout")
        ids = [c["id"] for c in tasks_v3.make_tasks("heldout")[0]]
        self.assertEqual(len(held), 12 * 5 * 3)
        self.assertEqual({(p["task_id"], p["cell"], p["rep"]) for p in held},
                         {(t, c, r) for t in ids for c in tasks_v3.CELLS for r in (1, 2, 3)})
        self.assertEqual([p["rep"] for p in held], sorted(p["rep"] for p in held))          # repetition blocks in order
        for i in range(0, len(held), 5):                                                    # cells back to back per task
            self.assertEqual(len({p["task_id"] for p in held[i:i + 5]}), 1)
            self.assertEqual({p["cell"] for p in held[i:i + 5]}, set(tasks_v3.CELLS))
        self.assertGreater(len({tuple(p["cell"] for p in held[i:i + 5]) for i in range(0, len(held), 5)}), 5)
        pilot = tasks_v3.make_plan("dev")
        self.assertEqual(len(pilot), 15)
        self.assertEqual({p["task_id"] for p in pilot}, set(tasks_v3.PILOT_TASKS))
        self.assertTrue(all(p["task_id"].startswith("e") for p in pilot))                   # the pilot never touches held-out IDs
        b = pendulum_v3.load("heldout")[2]
        self.assertEqual(len(b), 60)
        self.assertEqual(len({(p["item_id"], p["frame"], p["rep"]) for p in b}), 60)
        self.assertEqual(len(pendulum_v3.load("dev")[2]), 6)

    def test_shortcut_simulation_reproduces_the_frozen_table(self):
        for stratum, expected in SHORTCUT_TABLE.items():
            self.assertEqual(shortcuts_v3.pass_rates(stratum), expected, stratum)
        hard = SHORTCUT_TABLE["S2"]
        for name in ("endpoint", "subsample_10", "equal_spacing", "nominal_grid"):
            self.assertLess(hard[name], 25.0)                   # the stricter proxy; split-halves is at 26.8 (declared)
        self.assertLess(hard["split_halves"], 50.0)             # V2's standard


if __name__ == "__main__":
    unittest.main()
