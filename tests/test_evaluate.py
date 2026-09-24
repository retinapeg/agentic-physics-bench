"""Checks for answer parsing, grading and prompt rendering (no model calls).

Run from the repo root: python3 -m unittest -v tests.test_evaluate
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import evaluate  # noqa: E402
import run  # noqa: E402

REF = -1.9458


class ParseAndGradeTests(unittest.TestCase):
    def check(self, text, outcome, correct=False):
        answer, error = evaluate.parse_final(text)
        result = evaluate.grade(answer, error, REF)
        self.assertEqual((result["outcome"], result["correct"]), (outcome, correct), text)

    def test_outcomes(self):
        self.check('{"type": "final", "acceleration": -1.95, "units": "m/s^2"}', "correct", True)
        self.check('  {"type": "final", "acceleration": -1.95, "units": "m/s²"}\n', "correct", True)
        self.check('{"type": "final", "acceleration": -1.93, "units": "m/s^2"}', "wrong_value")
        self.check('{"type": "final", "acceleration": 1.95, "units": "m/s^2"}', "wrong_value")
        self.check('{"type": "final", "acceleration": -1.95, "units": "m/s"}', "wrong_units")
        self.check('```json\n{"type": "final", "acceleration": -1.95, "units": "m/s^2"}\n```', "malformed_json")
        self.check('The slope is -1.95 m/s^2', "malformed_json")
        self.check('{"type": "final", "acceleration": NaN, "units": "m/s^2"}', "bad_acceleration")
        self.check('{"type": "final", "acceleration": "-1.95", "units": "m/s^2"}', "bad_acceleration")
        self.check('{"type": "final", "acceleration": true, "units": "m/s^2"}', "bad_acceleration")
        self.check('{"type": "tool", "name": "fit_line"}', "wrong_type")
        self.check('[1, 2]', "not_an_object")
        self.check('', "missing_output")
        self.check(None, "missing_output")

    def test_tolerance_boundary(self):
        # abs(1.0 - 1.01) is 0.010000000000000009 in floating point, so test inside and outside, not on, the edge.
        self.assertTrue(evaluate.grade({"acceleration": 1.0, "units": "m/s^2"}, None, 1.0099)["correct"])
        self.assertFalse(evaluate.grade({"acceleration": 1.0, "units": "m/s^2"}, None, 1.0101)["correct"])


class PromptTests(unittest.TestCase):
    def test_direct_prompt_shows_only_the_table(self):
        case = run.load_row(ROOT / "data" / "dev_cases.jsonl", "dev-01")
        key = run.load_row(ROOT / "data" / "dev_keys.jsonl", "dev-01")
        _, prompt = run.render_prompt("direct", case)
        self.assertIn("t (s): " + ", ".join(case["t_s"]), prompt)
        self.assertIn("v (m/s): " + ", ".join(case["v_m_per_s"]), prompt)
        self.assertNotIn("$", prompt)
        for value in (key["a_ref"], key["a_true"], key["v0"]):
            self.assertNotIn(f"{value:.2f}", prompt.replace(", ".join(case["v_m_per_s"]), ""))

    def test_scored_ids_refused(self):
        with self.assertRaises(SystemExit):
            run.run_episode("direct", "s-01")


if __name__ == "__main__":
    unittest.main()
