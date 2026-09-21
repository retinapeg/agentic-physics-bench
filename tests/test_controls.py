"""Control enforcement and batch stopping (no model calls).

Verification code written by Claude (2026-09-21). Regression for a defect Codex
reproduced: the runner could record controls_ok=false alongside grade.correct=true.
Run from the repo root: python3 -m unittest -v tests.test_controls
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import models  # noqa: E402
import run  # noqa: E402

GOOD_INIT = {"type": "system", "subtype": "init", "model": "claude-opus-5", "tools": [],
             "mcp_servers": [], "claude_code_version": "2.1.278"}
TOOL_REQ = '{"type": "tool", "name": "fit_line", "arguments": {"case_id": "dev-01"}}'
FINAL = '{"type": "final", "acceleration": -1.9458, "units": "m/s^2"}'


def fake_call(text, init=GOOD_INIT, tool_use=False, stderr="", overage=False, status="allowed"):
    content = [{"type": "text", "text": text}]
    if tool_use:
        content.append({"type": "tool_use", "name": "Bash"})
    events = [e for e in [init] if e] + [
        {"type": "assistant", "message": {"model": "claude-opus-5", "content": content}},
        {"type": "rate_limit_event", "rate_limit_info": {"status": status, "isUsingOverage": overage}},
        {"type": "result", "subtype": "success", "is_error": False, "result": text, "usage": {}},
    ]
    return {"argv": models.CLAUDE_ARGV, "returncode": 0, "elapsed_s": 0.0, "events": events,
            "non_json_stdout": [], "stderr": stderr}


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.patches = [mock.patch.object(run, "RAW_DIR", tmp / "raw"),
                        mock.patch.dict(run.EPISODES, {"dev": tmp / "episodes.jsonl"})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def episode(self, condition, *calls):
        with mock.patch.object(run.models, "call_claude", side_effect=list(calls)) as fake:
            rec = run.run_episode(condition, "dev-01")
        return rec, fake.call_count

    def test_clean_call_is_valid_and_graded(self):
        rec, n = self.episode("direct", fake_call(FINAL))
        self.assertEqual((rec["valid"], rec["grade"]["correct"], n), (True, True, 1))

    def test_violations_invalidate_even_a_correct_answer(self):
        bad_init = dict(GOOD_INIT, tools=["Bash"])
        cases = {
            "native_tools_present": fake_call(FINAL, init=bad_init),
            "mcp_servers_present": fake_call(FINAL, init=dict(GOOD_INIT, mcp_servers=[{"name": "x"}])),
            "missing_init": fake_call(FINAL, init=None),
            "missing_init_fields:claude_code_version": fake_call(
                FINAL, init={k: v for k, v in GOOD_INIT.items() if k != "claude_code_version"}),
            "unexpected_model": fake_call(FINAL, init=dict(GOOD_INIT, model="other-model")),
            "native_tool_use": fake_call(FINAL, tool_use=True),
            "overage_used": fake_call(FINAL, overage=True),
            "stderr_warning": fake_call(FINAL, stderr="Warning: Unknown --effort value 'x'"),
        }
        for expected, call in cases.items():
            rec, n = self.episode("direct", call)
            self.assertFalse(rec["valid"], expected)
            self.assertIn(expected, rec["control_violations"])
            self.assertEqual(rec["grade"], {"correct": None, "outcome": "invalid_run", "abs_error": None})
            self.assertIsNone(rec["parsed"])
            self.assertEqual(rec["turns"][0]["response_text"], FINAL)  # evidence preserved

    def test_violation_on_turn_1_prevents_the_tool_and_turn_2(self):
        rec, n = self.episode("workflow", fake_call(TOOL_REQ, tool_use=True), fake_call(FINAL))
        self.assertEqual((rec["valid"], n, rec["model_calls"], rec["tool_executions"]), (False, 1, 1, 0))

    def test_violation_on_turn_2_records_the_executed_tool(self):
        rec, n = self.episode("workflow", fake_call(TOOL_REQ), fake_call(FINAL, stderr="Warning"))
        self.assertEqual((rec["valid"], n, rec["model_calls"], rec["tool_executions"]), (False, 2, 2, 1))


class BatchTests(unittest.TestCase):
    PLAN = [{"case_id": f"s-{i:02d}", "order": ["direct", "workflow"]} for i in range(1, 4)]

    def runner(self, outcomes):
        seen = []

        def run_one(condition, case_id):
            seen.append((case_id, condition))
            valid, status = outcomes.get((case_id, condition), (True, "allowed"))
            calls = 1 if condition == "direct" else 2
            return {"valid": valid, "model_calls": calls,
                    "turns": [{"cli": {"rate_limit": {"status": status}}}] * calls}
        return run_one, seen

    def test_invalid_run_stops_the_batch_and_later_episodes_stay_unattempted(self):
        run_one, seen = self.runner({("s-02", "direct"): (False, "allowed")})
        recs, reason = run.run_batch(self.PLAN, run_one, set(), 0)
        self.assertEqual(reason, "control_violation")
        self.assertEqual(seen, [("s-01", "direct"), ("s-01", "workflow"), ("s-02", "direct")])

    def test_rate_limit_stops_the_batch(self):
        run_one, seen = self.runner({("s-01", "workflow"): (True, "rejected")})
        self.assertEqual(run.run_batch(self.PLAN, run_one, set(), 0)[1], "rate_limit")
        self.assertEqual(len(seen), 2)

    def test_attempted_episodes_are_never_repeated_and_the_cap_holds(self):
        run_one, seen = self.runner({})
        recs, reason = run.run_batch(self.PLAN, run_one, {("s-01", "direct")}, 0, cap=4)
        self.assertEqual(seen, [("s-01", "workflow"), ("s-02", "direct")])
        self.assertEqual(reason, "invocation_cap")

    def test_full_matrix_fits_the_36_call_cap(self):
        plan = json.loads(run.PLAN.read_text()) if run.PLAN.exists() else [
            {"case_id": f"s-{i:02d}", "order": ["direct", "workflow"]} for i in range(1, 13)]
        run_one, seen = self.runner({})
        recs, reason = run.run_batch(plan, run_one, set(), 0)
        self.assertEqual((reason, len(seen), sum(r["model_calls"] for r in recs)), ("completed", 24, 36))


if __name__ == "__main__":
    unittest.main()
