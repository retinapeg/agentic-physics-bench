"""Checks for the bounded tool workflow, using scripted model replies (no model calls).

Run from the repo root: python3 -m unittest -v tests.test_agent
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import agent  # noqa: E402
import run  # noqa: E402
import tools  # noqa: E402

TOOL_REQ = '{"type": "tool", "name": "fit_line", "arguments": {"case_id": "dev-01"}}'
FINAL = '{"type": "final", "acceleration": -1.9458, "units": "m/s^2"}'


def scripted(*replies):
    """A fake model that returns the given replies in order and records its prompts."""
    prompts = []

    def call_model(prompt, turn):
        prompts.append((turn, prompt))
        return replies[len(prompts) - 1]
    return call_model, prompts


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.case, self.key = run.load_dev_case("dev-01")
        _, self.prompt1 = run.render_prompt("workflow_turn1", self.case)
        self.template2 = run.PROMPTS["workflow_turn2"].read_text()

    def episode(self, *replies):
        call_model, prompts = scripted(*replies)
        return agent.run_workflow(self.case, self.prompt1, self.template2, call_model), prompts

    def test_tool_then_final(self):
        out, prompts = self.episode(TOOL_REQ, FINAL)
        self.assertEqual((out["model_calls"], out["tool_executions"], out["error"]), (2, 1, None))
        self.assertEqual(out["answer"]["acceleration"], -1.9458)
        turn2 = prompts[1][1]
        self.assertIn(self.prompt1.rstrip("\n"), turn2)  # the original task
        self.assertIn(TOOL_REQ, turn2)  # the model's previous public reply
        self.assertIn(json.dumps(out["tool"]["result"]), turn2)  # the tool result
        self.assertNotIn("$", turn2)

    def test_final_without_tool_ends_after_one_call(self):
        out, _ = self.episode(FINAL)
        self.assertEqual((out["model_calls"], out["tool_executions"], out["error"]), (1, 0, None))

    def test_invalid_requests_are_not_executed(self):
        for reply, code in [
            ('{"type": "tool", "name": "fit_line", "arguments": {"case_id": "dev-02"}}', "wrong_case_id"),
            ('{"type": "tool", "name": "shell", "arguments": {"case_id": "dev-01"}}', "unknown_tool"),
            ('{"type": "tool", "name": "fit_line", "arguments": {"t": [0, 1], "v": [0, 1]}}', "bad_arguments"),
        ]:
            out, _ = self.episode(reply)
            self.assertEqual((out["model_calls"], out["tool_executions"]), (1, 0), reply)
            self.assertEqual((out["error"], out["tool"]["error"]), ("invalid_tool_request", code))

    def test_malformed_request_fields_are_recorded_not_crashes(self):
        # Regression: review reproduced a TypeError for "name": [] (unhashable in the allowlist lookup).
        for reply, code in [
            ('{"type": "tool", "name": [], "arguments": {"case_id": "dev-01"}}', "bad_tool_name"),
            ('{"type": "tool", "name": {}, "arguments": {"case_id": "dev-01"}}', "bad_tool_name"),
            ('{"type": "tool", "arguments": {"case_id": "dev-01"}}', "bad_tool_name"),
            ('{"type": "tool", "name": "fit_line", "arguments": ["dev-01"]}', "bad_arguments"),
            ('{"type": "tool", "name": "fit_line", "arguments": {"case_id": ["dev-01"]}}', "bad_arguments"),
            ('{"type": "tool", "name": "fit_line"}', "bad_arguments"),
        ]:
            out, _ = self.episode(reply)
            self.assertEqual((out["model_calls"], out["tool_executions"]), (1, 0), reply)
            self.assertEqual((out["error"], out["tool"]["error"], out["tool"]["executed"]),
                             ("invalid_tool_request", code, False), reply)

    def test_tool_exception_is_a_recorded_outcome(self):
        original = tools.TOOLS["fit_line"]
        tools.TOOLS["fit_line"] = lambda case: 1 / 0
        try:
            out, prompts = self.episode(TOOL_REQ, FINAL)
        finally:
            tools.TOOLS["fit_line"] = original
        self.assertEqual((out["error"], out["model_calls"], len(prompts)), ("tool_error", 1, 1))
        self.assertFalse(out["tool"]["executed"])

    def test_second_tool_request_exceeds_limit(self):
        out, _ = self.episode(TOOL_REQ, TOOL_REQ)
        self.assertEqual((out["model_calls"], out["tool_executions"], out["error"]),
                         (2, 1, "tool_limit_exceeded"))

    def test_malformed_and_missing_replies_end_the_episode(self):
        self.assertEqual(self.episode("The slope is -1.95")[0]["error"], "malformed_json")
        self.assertEqual(self.episode(None)[0]["error"], "missing_output")
        out, _ = self.episode(TOOL_REQ, "```json\n" + FINAL + "\n```")
        self.assertEqual((out["model_calls"], out["error"]), (2, "malformed_json"))


class ToolTests(unittest.TestCase):
    def test_fit_line_uses_displayed_data_and_no_key_fields(self):
        case, key = run.load_dev_case("dev-01")
        result = tools.fit_line(case)
        self.assertAlmostEqual(result["slope"], key["a_ref"], places=12)
        self.assertEqual(set(result), {"slope", "slope_units", "intercept", "intercept_units", "n_points"})
        self.assertNotIn(f"{key['a_true']:.4f}", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
