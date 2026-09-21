"""Checks for Leo's ls_slope in src/tasks.py.

Verification code written by Claude (2026-09-21). It is not part of the
implementation. Run from the repo root: python3 -m unittest -v tests.test_ls_slope
"""
import statistics
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tasks import ls_slope  # noqa: E402


class LsSlopeTests(unittest.TestCase):
    def test_known_example(self):
        # Hand calculation: Sxy = -2.75, Sxx = 1.25 (LEARNING_REVIEW.md W1).
        self.assertAlmostEqual(ls_slope([0, 0.5, 1.0, 1.5], [5, 2, 3, 1]), -2.2, places=12)

    def test_matches_statistics_linear_regression(self):
        # Noisy, negative slope, nonzero intercept, on the dev time grid.
        t = [0.5 * i for i in range(10)]
        v = [3.17, 1.02, 0.35, -1.48, -2.91, -4.06, -5.87, -6.52, -8.44, -9.13]
        expected = statistics.linear_regression(t, v).slope
        self.assertAlmostEqual(ls_slope(t, v), expected, places=12)

    def test_returns_float_and_leaves_inputs_unchanged(self):
        t, v = [0, 1, 2], [1, 3, 4]
        result = ls_slope(t, v)
        self.assertIs(type(result), float)
        self.assertEqual((t, v), ([0, 1, 2], [1, 3, 4]))

    def test_rejects_bad_input(self):
        cases = {
            "equal times": ([1.0, 1.0], [2.0, 3.0]),
            "equal times, inexact mean": ([0.1, 0.1, 0.1], [1.0, 2.0, 3.0]),
            "nan in v": ([0, 1], [0, float("nan")]),
            "inf in t": ([0, float("inf")], [0, 1]),
            "length mismatch": ([0, 1, 2], [0, 1]),
            "single point": ([0], [0]),
        }
        for name, (t, v) in cases.items():
            with self.subTest(name), self.assertRaises(ValueError):
                ls_slope(t, v)


if __name__ == "__main__":
    unittest.main()
