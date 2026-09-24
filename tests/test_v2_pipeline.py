"""End-to-end V2 pipeline with a scripted CLI (no model calls).

One test per condition walks the whole chain and checks each stage's record:
    task -> model choice (turn 1) -> tool request -> validated execution -> returned result
         -> final answer (turn 2) -> deterministic score -> analysis denominators.
Run from the repo root: python3 -m unittest -v tests.test_v2_pipeline
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
import analyze_v2  # noqa: E402
import evaluate  # noqa: E402
import models  # noqa: E402
import run_v2  # noqa: E402
import tasks  # noqa: E402
from tests.test_v2_run import GOOD_INIT, VERSION, fake_call  # noqa: E402

TASK_ID = "d3-01"  # hard group: 40 points on an irregular grid


def cli(reply_for):
    """A fake Claude CLI: reply_for(prompt, turn) returns the model's text; the trace is well-formed."""
    calls = []

    def call_claude(prompt):
        calls.append(prompt)
        return fake_call(reply_for(prompt, len(calls)))
    return call_claude, calls


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.patches = [mock.patch.object(run_v2, "RAW_DIR", tmp / "raw"),
                        mock.patch.dict(run_v2.EPISODES, {"dev": tmp / "episodes.jsonl"}),
                        mock.patch.dict(run_v2.ATTEMPTS, {"dev": tmp / "attempts.jsonl"})]
        for p in self.patches:
            p.start()
        self.case, self.key = run_v2.load_task("dev", TASK_ID)
        self.a_ref = self.key["a_ref"]

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def run_episode(self, condition, reply_for, rep=1):
        call_claude, calls = cli(reply_for)
        with mock.patch.object(models, "call_claude", side_effect=call_claude):
            rec = run_v2.run_episode("dev", TASK_ID, condition, rep, "pipeline-test", VERSION)
        return rec, calls

    def check_task_stage(self, prompt):
        # 1. task: the prompt shows exactly the displayed table and nothing from the key
        self.assertIn("t (s): " + ", ".join(self.case["t_s"]), prompt)
        self.assertIn("v (m/s): " + ", ".join(self.case["v_m_per_s"]), prompt)
        for field in ("a_ref", "a_true", "v0"):
            self.assertNotIn(f"{self.key[field]:.4f}", prompt.replace(", ".join(self.case["v_m_per_s"]), ""))

    def test_required_tool_full_chain(self):
        def reply_for(prompt, turn):
            if turn == 1:
                return json.dumps({"type": "tool", "name": "fit_line", "arguments": {"case_id": TASK_ID}})
            result, _ = json.JSONDecoder().raw_decode(prompt.split("Tool result (fit_line):\n", 1)[1])
            return json.dumps({"type": "final", "acceleration": result["slope"], "units": "m/s^2"})
        rec, calls = self.run_episode("required_tool", reply_for)
        self.check_task_stage(calls[0])
        # 2. model choice: a tool request at turn 1
        self.assertEqual(rec["turn1"]["kind"], "tool")
        self.assertEqual(rec["turn_kinds"], ["tool", "final"])
        # 3. tool request recorded verbatim, 4. validated and executed exactly once
        tool = rec["tool"]
        self.assertEqual(tool["request"]["arguments"], {"case_id": TASK_ID})
        self.assertEqual((tool["requested"], tool["valid"], tool["validation_error"], tool["executed"]), (True, True, None, True))
        self.assertEqual((rec["tool_executions"], rec["required_compliant"]), (1, True))
        # 5. returned result: the least-squares slope of the displayed data, reaching the turn-2 prompt verbatim
        t = [float(x) for x in self.case["t_s"]]
        v = [float(x) for x in self.case["v_m_per_s"]]
        self.assertEqual(tool["result"]["slope"], tasks.ls_slope(t, v))
        self.assertIn("Tool result (fit_line):\n" + json.dumps(tool["result"]), calls[1])
        self.assertIn(calls[0].rstrip("\n"), calls[1])  # the original task travels with it
        # 6. final answer = turn 2's reply, 7. deterministic score against the key file
        self.assertEqual(rec["parsed"]["acceleration"], tool["result"]["slope"])
        self.assertEqual(rec["grade"], {"correct": True, "outcome": "correct", "abs_error": 0.0})
        self.assertEqual(rec["grade"], evaluate.grade(rec["parsed"], None, self.a_ref))
        self.assertEqual((rec["valid"], rec["model_calls"], rec["control_violations"]), (True, 2, None))

    def test_optional_tool_declined_then_revised(self):
        first, second = round(self.a_ref, 1), round(self.a_ref, 3)  # 1 dp is outside +/-0.01 for this task

        def reply_for(prompt, turn):
            return json.dumps({"type": "final", "acceleration": first if turn == 1 else second, "units": "m/s^2"})
        rec, calls = self.run_episode("optional_tool", reply_for)
        self.assertIn("fit_line", calls[0])  # the tool was offered
        self.assertEqual((rec["turn1"]["kind"], rec["tool"]["requested"], rec["tool_executions"]), ("final", False, 0))
        self.assertEqual(rec["turn1"]["grade"]["correct"], abs(first - self.a_ref) <= evaluate.TOLERANCE)  # secondary
        self.assertIn("No tool was requested", calls[1])
        self.assertEqual((rec["parsed"]["acceleration"], rec["grade"]["correct"]), (second, True))  # final = turn 2
        self.assertIsNone(rec["required_compliant"])

    def test_no_tool_request_is_recorded_but_never_executed(self):
        def reply_for(prompt, turn):
            if turn == 1:
                return json.dumps({"type": "tool", "name": "fit_line", "arguments": {"case_id": TASK_ID}})
            return json.dumps({"type": "final", "acceleration": self.a_ref + 0.5, "units": "m/s^2"})
        rec, calls = self.run_episode("no_tool", reply_for)
        self.assertNotIn("fit_line", calls[0])
        self.assertEqual((rec["tool"]["requested"], rec["tool"]["valid"], rec["tool"]["validation_error"],
                          rec["tool"]["executed"], rec["tool_executions"]), (True, False, "no_tool_condition", False, 0))
        self.assertIn("No tool is available", calls[1])
        self.assertEqual((rec["grade"]["outcome"], round(rec["grade"]["abs_error"], 6)), ("wrong_value", 0.5))

    def test_repeated_runs_are_separate_episodes_and_the_analysis_counts_them_once_each(self):
        def reply_for(prompt, turn):
            if turn == 1:
                return json.dumps({"type": "tool", "name": "fit_line", "arguments": {"case_id": TASK_ID}})
            return json.dumps({"type": "final", "acceleration": self.a_ref, "units": "m/s^2"})
        for rep in (1, 2):
            self.run_episode("required_tool", reply_for, rep=rep)
        existing, interrupted, already, calls_used = run_v2.resume_state("dev")
        self.assertEqual((len(existing), already, calls_used), (2, {(TASK_ID, "required_tool", 1), (TASK_ID, "required_tool", 2)}, 4))
        plan = [{"seq": 3 * (r - 1) + i + 1, "rep": r, "task_id": TASK_ID, "condition": c}
                for r in (1, 2, 3) for i, c in enumerate(analyze_v2.CONDITIONS)]  # a full 3 x 3 plan for one task
        keys = {TASK_ID: self.key}
        s = analyze_v2.summarize(plan, keys, {TASK_ID: self.case}, existing, run_v2.load_attempts("dev"), "dev")
        cell = s["groups"]["hard"]["conditions"]["required_tool"]
        self.assertEqual((s["planned_episodes"], s["attempted"], cell["correct"], cell["of_planned"],
                          cell["tool"]["executed"], cell["required_compliant"], cell["outcome_counts"]),
                         (9, 2, 2, 3, 2, 2, {"correct": 2, "not_attempted": 1}))
        self.assertEqual(s["task_table"][0]["proportion_correct"], {"no_tool": 0.0, "optional_tool": 0.0, "required_tool": 2 / 3})


if __name__ == "__main__":
    unittest.main()
