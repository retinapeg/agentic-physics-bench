"""Checks for the deterministic analysis (no model calls).

Run from the repo root: python3 -m unittest -v tests.test_analyze
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import analyze  # noqa: E402


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.keys, self.cases, self.episodes = analyze.load()

    def test_counts_match_a_direct_recount_of_the_raw_file(self):
        if not self.episodes:
            self.skipTest("no scored episodes yet")
        s = analyze.summarize(self.plan, self.keys, self.cases, self.episodes)
        for cond in analyze.CONDITIONS:
            recount = sum(1 for e in self.episodes
                          if e["condition"] == cond and e["valid"] and e["grade"]["correct"])
            self.assertEqual(s["conditions"][cond]["correct"], recount)
        self.assertEqual(s["model_invocations"], sum(len(e["turns"]) for e in self.episodes))

    def test_unattempted_and_invalid_episodes_stay_in_the_denominator(self):
        partial = [e for e in self.episodes if e["case_id"] != "s-12"]
        if partial:
            partial = partial[:-1] + [dict(partial[-1], valid=False,
                                           grade={"correct": None, "outcome": "invalid_run", "abs_error": None})]
        s = analyze.summarize(self.plan, self.keys, self.cases, partial)
        self.assertEqual(s["planned_episodes"], 24)
        statuses = [r["status"] for r in s["episodes"]]
        self.assertGreaterEqual(statuses.count("not_attempted"), 2)
        for cond in analyze.CONDITIONS:
            self.assertEqual(s["conditions"][cond]["of_planned_cases"], 12)
            self.assertEqual(sum(s["conditions"][cond]["outcome_counts"].values()), 12)
        if partial:
            self.assertIn("invalid_run", statuses)


if __name__ == "__main__":
    unittest.main()
