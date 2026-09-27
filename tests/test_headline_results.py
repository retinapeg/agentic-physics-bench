"""The README's headline numbers equal the values recomputed from the committed result files (no model calls).
Run from the repo root: python3 -m unittest -v tests.test_headline_results
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import headline_results  # noqa: E402


class HeadlineTests(unittest.TestCase):
    def test_every_published_claim_is_recomputed_from_committed_files(self):
        got = headline_results.committed()
        for key, claim, published, _ in headline_results.CLAIMS:
            with self.subTest(claim):
                self.assertEqual(got[key], published)

    def test_a_wrong_published_value_fails_the_check(self):
        key, claim, _, source = headline_results.CLAIMS[0]
        wrong = [(key, claim, "23/24", source)] + headline_results.CLAIMS[1:]
        with mock.patch.object(headline_results, "CLAIMS", wrong), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(headline_results.main(), 1)
        self.assertIn("**NO**", out.getvalue())

    def test_missing_raw_traces_are_reported_as_skipped_not_passed(self):
        with tempfile.TemporaryDirectory() as empty, mock.patch.object(headline_results, "ROOT", Path(empty)):
            self.assertIsNone(headline_results.from_raw())
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(headline_results.main(), 0)
        self.assertIn("skipped, not passed", out.getvalue())
        self.assertNotIn("Raw-trace check", out.getvalue())


if __name__ == "__main__":
    unittest.main()
