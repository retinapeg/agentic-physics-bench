"""Checks for the development cases in src/tasks.py.

Run from the repo root: python3 -m unittest -v tests.test_tasks
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


def exact_slope(t_strings, v_strings):
    """Least-squares slope in exact rational arithmetic, straight from the strings."""
    t = [Fraction(x) for x in t_strings]
    v = [Fraction(x) for x in v_strings]
    t_bar, v_bar = sum(t) / len(t), sum(v) / len(v)
    return sum((a - t_bar) * (b - v_bar) for a, b in zip(t, v)) / sum((a - t_bar) ** 2 for a in t)


class DevCaseTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.keys = tasks.make_dev_cases()

    def test_reproducible(self):
        self.assertEqual((self.cases, self.keys), tasks.make_dev_cases())

    def test_case_shows_no_answer_fields(self):
        for case in self.cases:
            self.assertEqual(set(case), {"id", "t_s", "v_m_per_s"})

    def test_grid_precision_and_signs(self):
        grid = [f"{0.5 * i:.1f}" for i in range(10)]
        for case, key, sign in zip(self.cases, self.keys, tasks.DEV_SIGNS):
            self.assertEqual(case["t_s"], grid)
            for s in case["v_m_per_s"]:
                self.assertRegex(s, r"^-?\d+\.\d{2}$")
            self.assertEqual(sign * key["a_true"] > 0, True)
            self.assertLessEqual(abs(key["a_true"]), tasks.A_MAX)
            self.assertEqual(key["a_ref"] > 0, key["a_true"] > 0, f"{key['id']}: sign of a_ref differs from a_true")

    def test_reference_matches_independent_calculations(self):
        for case, key in zip(self.cases, self.keys):
            t = [float(x) for x in case["t_s"]]
            v = [float(x) for x in case["v_m_per_s"]]
            self.assertAlmostEqual(key["a_ref"], statistics.linear_regression(t, v).slope, places=12)
            self.assertAlmostEqual(key["a_ref"], float(exact_slope(case["t_s"], case["v_m_per_s"])), places=12)

    def test_saved_files_match_generator(self):
        for name, rows in (("dev_cases.jsonl", self.cases), ("dev_keys.jsonl", self.keys)):
            path = ROOT / "data" / name
            if not path.exists():
                self.skipTest(f"{path} not written yet; run python3 src/tasks.py")
            self.assertEqual(path.read_text(), tasks.to_jsonl(rows))
        # The key file agrees with a fit computed only from the case file.
        saved_cases = [json.loads(line) for line in (ROOT / "data" / "dev_cases.jsonl").read_text().splitlines()]
        saved_keys = [json.loads(line) for line in (ROOT / "data" / "dev_keys.jsonl").read_text().splitlines()]
        for case, key in zip(saved_cases, saved_keys):
            self.assertEqual(case["id"], key["id"])
            self.assertAlmostEqual(key["a_ref"], float(exact_slope(case["t_s"], case["v_m_per_s"])), places=12)


class ScoredCaseTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.keys = tasks.make_scored_cases()
        self.plan = tasks.run_plan([c["id"] for c in self.cases], tasks.SCORED_SIGNS)

    def test_reproducible_and_separate_from_dev(self):
        self.assertEqual((self.cases, self.keys), tasks.make_scored_cases())
        dev_cases, _ = tasks.make_dev_cases()
        self.assertFalse({tuple(c["v_m_per_s"]) for c in dev_cases} & {tuple(c["v_m_per_s"]) for c in self.cases})

    def test_twelve_cases_six_of_each_generating_sign(self):
        self.assertEqual([c["id"] for c in self.cases], [f"s-{i:02d}" for i in range(1, 13)])
        signs = [1 if k["a_true"] > 0 else -1 for k in self.keys]
        self.assertEqual(signs, list(tasks.SCORED_SIGNS))
        self.assertEqual((signs.count(-1), signs.count(1)), (6, 6))
        for case in self.cases:
            self.assertEqual(set(case), {"id", "t_s", "v_m_per_s"})

    def test_condition_order_three_each_within_each_sign_group(self):
        for sign in (-1, 1):
            firsts = [p["order"][0] for p in self.plan if p["generating_sign"] == sign]
            self.assertEqual(sorted(firsts), ["direct"] * 3 + ["workflow"] * 3)
        for p in self.plan:
            self.assertEqual(sorted(p["order"]), ["direct", "workflow"])

    def test_reference_matches_independent_calculations(self):
        for case, key in zip(self.cases, self.keys):
            t = [float(x) for x in case["t_s"]]
            v = [float(x) for x in case["v_m_per_s"]]
            self.assertAlmostEqual(key["a_ref"], statistics.linear_regression(t, v).slope, places=12)
            self.assertAlmostEqual(key["a_ref"], float(exact_slope(case["t_s"], case["v_m_per_s"])), places=12)

    def test_saved_scored_files_match_generator(self):
        files = {"scored_cases.jsonl": tasks.to_jsonl(self.cases), "scored_keys.jsonl": tasks.to_jsonl(self.keys),
                 "scored_plan.json": json.dumps(self.plan, indent=1) + "\n"}
        for name, text in files.items():
            path = ROOT / "data" / name
            if not path.exists():
                self.skipTest(f"{name} not written yet")
            self.assertEqual(path.read_text(), text)


if __name__ == "__main__":
    unittest.main()
