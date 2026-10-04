"""V3 offline grading checks; no model calls or scored episodes."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import grade_v3  # noqa: E402


class NumericGradingTests(unittest.TestCase):
    def setUp(self):
        self.key = {"answer_type": "numeric", "answer": 0.25}

    def test_correct_wrong_and_relative_boundary(self):
        self.assertTrue(grade_v3.grade({"answer": 0.25, "units": "1"}, self.key)["correct"])
        self.assertEqual(grade_v3.grade(0.26, self.key)["outcome"], "wrong_value")
        self.assertTrue(grade_v3.grade(0.2500024, self.key)["correct"])
        self.assertEqual(grade_v3.grade(0.250003, self.key)["outcome"], "wrong_value")

    def test_absolute_floor_for_six_decimal_rounding(self):
        key = {"answer_type": "numeric", "answer": 0.00024078791578981086}
        self.assertTrue(grade_v3.grade("0.000241", key)["correct"])
        self.assertEqual(grade_v3.grade("0.000250", key)["outcome"], "wrong_value")
        significant_figures = dict(key, kind="barrier")
        self.assertTrue(grade_v3.grade("0.000240788", significant_figures)["correct"])
        self.assertEqual(grade_v3.grade("0.000241", significant_figures)["outcome"], "wrong_value")

    def test_units_and_malformed_values(self):
        self.assertEqual(grade_v3.grade({"answer": 0.25, "units": "m/s"}, self.key)["outcome"],
                         "wrong_units")
        for bad in (None, "", "not a number", "NaN", "Infinity", True, 10**400,
                    {"answer": []}, {"answer": 0.25, "extra": "x"}, "{bad json"):
            with self.subTest(bad=repr(bad)[:40]):
                self.assertFalse(grade_v3.grade(bad, self.key)["correct"])


class SymbolicGradingTests(unittest.TestCase):
    def setUp(self):
        self.key = {"answer_type": "sympy", "answer": "x**2 - 1"}

    def test_correct_equivalent_wrong_and_json(self):
        self.assertEqual(grade_v3.grade("x**2 - 1", self.key)["method"], "simplify")
        self.assertTrue(grade_v3.grade(json.dumps({"type": "final", "answer": "(x-1)*(x+1)"}),
                                       self.key)["correct"])
        self.assertEqual(grade_v3.grade("x**2 + 1", self.key)["outcome"], "wrong_value")

    def test_numeric_backup_when_simplification_is_inconclusive(self):
        with mock.patch.object(grade_v3.sp, "simplify", return_value=grade_v3.sp.Symbol("unknown")):
            result = grade_v3.grade("(x-1)*(x+1)", self.key)
        self.assertEqual((result["correct"], result["method"]), (True, "numeric_backup"))

    def test_actual_v3_expression_forms(self):
        commutator = {"answer_type": "sympy", "answer": "18*hbar**2*x**3 + 9*I*hbar*p*x**4"}
        self.assertTrue(grade_v3.grade("9*hbar*x**3*(2*hbar + I*p*x)", commutator)["correct"])
        normalization = {"answer_type": "sympy", "answer": "sqrt(5)/pi"}
        self.assertTrue(grade_v3.grade("5**(1/2)/pi", normalization)["correct"])

    def test_malformed_expressions_are_wrong_without_execution(self):
        for bad in ("", "x+", "unknown + 1", "__import__('os').system('true')",
                    "x.__class__", "[x]", "x**100000", "sqrt(x, 2)", "1/0", 4, None):
            with self.subTest(bad=bad):
                self.assertFalse(grade_v3.grade(bad, self.key)["correct"])


class StoredKeyCompatibilityTests(unittest.TestCase):
    def test_all_existing_private_references_grade_correctly(self):
        for split in ("dev", "heldout"):
            path = ROOT / "data" / "v3" / f"{split}_keys.jsonl"
            for line in path.read_text().splitlines():
                key = json.loads(line)
                with self.subTest(task_id=key["id"]):
                    self.assertTrue(grade_v3.grade(key["answer"], key)["correct"])


if __name__ == "__main__":
    unittest.main()
