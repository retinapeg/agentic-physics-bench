"""Checks for the V2 task groups (no model calls). Verification code written by Claude (2026-09-23).
Run from the repo root: python3 -m unittest -v tests.test_v2_tasks
"""
import json
import statistics
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import tasks  # noqa: E402
import tasks_v2  # noqa: E402


def exact_slope(t_strings, v_strings):
    t = [Fraction(x) for x in t_strings]
    v = [Fraction(x) for x in v_strings]
    t_bar, v_bar = sum(t) / len(t), sum(v) / len(v)
    return sum((a - t_bar) * (b - v_bar) for a, b in zip(t, v)) / sum((a - t_bar) ** 2 for a in t)


class TaskTests(unittest.TestCase):
    def test_reproducible_and_splits_disjoint(self):
        dev, scored = tasks_v2.make_tasks("dev"), tasks_v2.make_tasks("scored")
        self.assertEqual(dev, tasks_v2.make_tasks("dev"))
        self.assertEqual(scored, tasks_v2.make_tasks("scored"))
        v1_cases, _ = tasks.make_scored_cases()
        shown = lambda cs: {tuple(c["v_m_per_s"]) for c in cs}
        self.assertFalse(shown(dev[0]) & shown(scored[0]))
        self.assertFalse(shown(scored[0]) & shown(v1_cases))  # new held-out cases, not V1's

    def test_schema_counts_groups_and_signs(self):
        for split, per in (("dev", 2), ("scored", 6)):
            cases, keys = tasks_v2.make_tasks(split)
            self.assertEqual(len(cases), 3 * per)
            for case, key in zip(cases, keys):
                self.assertEqual(set(case), {"id", "t_s", "v_m_per_s"})  # V1's schema: fit_line works unchanged
                self.assertEqual(case["id"], key["id"])
                self.assertEqual(tasks_v2.group_of(case["id"]), key["group"])
                p = tasks_v2.GROUPS[key["group"]]
                self.assertEqual((len(case["t_s"]), len(case["v_m_per_s"]), key["n_points"]), (p["n"], p["n"], p["n"]))
                for s in case["v_m_per_s"]:
                    self.assertRegex(s, r"^-?\d+\.\d{2}$")
                for s in case["t_s"]:
                    self.assertRegex(s, r"^\d+\.\d{%d}$" % p["t_dp"])
                self.assertLessEqual(abs(key["a_true"]), tasks.A_MAX)
            for g in tasks_v2.GROUP_ORDER:
                signs = [1 if k["a_true"] > 0 else -1 for k in keys if k["group"] == g]
                self.assertEqual(signs, [-1, 1] * (per // 2))

    def test_times_strictly_increasing_and_jitter_bounded(self):
        for split in ("dev", "scored"):
            for case, key in zip(*tasks_v2.make_tasks(split)):
                t = [float(x) for x in case["t_s"]]
                self.assertTrue(all(b > a for a, b in zip(t, t[1:])), case["id"])
                p = tasks_v2.GROUPS[key["group"]]
                for i, ti in enumerate(t):
                    self.assertLessEqual(abs(ti - p["dt"] * i - p["jitter"]), p["jitter"] + 0.5 * 10 ** -p["t_dp"] + 1e-9)
                    self.assertGreaterEqual(ti, 0.0)

    def test_easy_group_is_v1s_procedure(self):
        # Same seed in, same case out: V1's make_case with sigma 0.5 on the V1 grid.
        import random
        rng = random.Random(tasks_v2.SEEDS["scored"]["easy"])
        expected = [tasks.make_case(rng, f"g1-{i:02d}", -1 if i % 2 else 1, 0.5)[0] for i in range(1, 7)]
        cases, _ = tasks_v2.make_tasks("scored")
        self.assertEqual([c for c in cases if c["id"].startswith("g1")], expected)

    def test_reference_matches_independent_calculations(self):
        for split in ("dev", "scored"):
            for case, key in zip(*tasks_v2.make_tasks(split)):
                t = [float(x) for x in case["t_s"]]
                v = [float(x) for x in case["v_m_per_s"]]
                self.assertAlmostEqual(key["a_ref"], statistics.linear_regression(t, v).slope, places=12)
                self.assertAlmostEqual(key["a_ref"], float(exact_slope(case["t_s"], case["v_m_per_s"])), places=12)

    def test_saved_files_match_generator(self):
        for split in ("dev", "scored"):
            for name, text in tasks_v2.files(split).items():
                path = tasks_v2.DATA_DIR / name
                if not path.exists():
                    self.skipTest(f"{name} not written yet; run python3 src/tasks_v2.py [scored]")
                self.assertEqual(path.read_text(), text, name)
        # The key file agrees with a fit computed only from the task file.
        for split in ("dev", "scored"):
            saved_cases = [json.loads(l) for l in (tasks_v2.DATA_DIR / f"{split}_tasks.jsonl").read_text().splitlines()]
            saved_keys = [json.loads(l) for l in (tasks_v2.DATA_DIR / f"{split}_keys.jsonl").read_text().splitlines()]
            for case, key in zip(saved_cases, saved_keys):
                self.assertEqual(case["id"], key["id"])
                self.assertAlmostEqual(key["a_ref"], float(exact_slope(case["t_s"], case["v_m_per_s"])), places=12)


class PlanTests(unittest.TestCase):
    def test_plan_is_balanced_seeded_and_block_ordered(self):
        for split, reps in (("dev", 1), ("scored", 3)):
            cases, _ = tasks_v2.make_tasks(split)
            ids = [c["id"] for c in cases]
            plan = tasks_v2.make_plan(split)
            self.assertEqual(plan, tasks_v2.make_plan(split))
            self.assertEqual(len(plan), len(ids) * 3 * reps)
            self.assertEqual([p["seq"] for p in plan], list(range(1, len(plan) + 1)))
            cells = {(p["task_id"], p["condition"], p["rep"]) for p in plan}
            self.assertEqual(cells, {(t, c, r) for t in ids for c in tasks_v2.CONDITIONS for r in range(1, reps + 1)})
            self.assertEqual([p["rep"] for p in plan], sorted(p["rep"] for p in plan))  # rep blocks in sequence
            for i in range(0, len(plan), 3):  # each task's three conditions run back to back
                self.assertEqual(len({p["task_id"] for p in plan[i:i + 3]}), 1)
                self.assertEqual({p["condition"] for p in plan[i:i + 3]}, set(tasks_v2.CONDITIONS))
        scored = tasks_v2.make_plan("scored")
        first_conditions = [p["condition"] for p in scored[::3]]
        self.assertGreater(len(set(first_conditions)), 1)  # the condition order really is shuffled
        self.assertNotEqual([p["task_id"] for p in scored[:54:3]], sorted(p["task_id"] for p in scored[:54:3]))


if __name__ == "__main__":
    unittest.main()
