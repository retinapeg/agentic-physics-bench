"""Checks for the V2 two-turn loop, using scripted replies (no model calls).
Run from the repo root: python3 -m unittest -v tests.test_v2_agent
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import agent_v2  # noqa: E402
import run_v2  # noqa: E402
import tasks_v2  # noqa: E402
import tools  # noqa: E402

CASE, KEY = run_v2.load_task("dev", "d2-01")
TOOL_REQ = json.dumps({"type": "tool", "name": "fit_line", "arguments": {"case_id": CASE["id"]}})
FINAL = json.dumps({"type": "final", "acceleration": round(KEY["a_ref"], 3), "units": "m/s^2"})
FINAL_OTHER = json.dumps({"type": "final", "acceleration": round(KEY["a_ref"], 3) + 0.5, "units": "m/s^2"})


def scripted(*replies):
    prompts = []

    def call_model(prompt, turn):
        prompts.append((turn, prompt))
        return replies[len(prompts) - 1]
    return call_model, prompts


def episode(condition, *replies):
    _, prompt1, template2 = run_v2.render_prompts(CASE, condition)
    call_model, prompts = scripted(*replies)
    return agent_v2.run_episode_v2(CASE, condition, prompt1, template2, call_model), prompts


class PolicyTests(unittest.TestCase):
    def test_every_condition_uses_exactly_two_calls_when_turn1_is_a_final_answer(self):
        for condition in agent_v2.CONDITIONS:
            out, prompts = episode(condition, FINAL_OTHER, FINAL)
            self.assertEqual((out["model_calls"], out["tool_executions"], out["error"]), (2, 0, None), condition)
            self.assertEqual(out["answer"]["acceleration"], round(KEY["a_ref"], 3))  # final answer = turn 2
            self.assertEqual(out["turn1"]["answer"]["acceleration"], round(KEY["a_ref"], 3) + 0.5)
            self.assertIn(FINAL_OTHER, prompts[1][1])  # the previous reply is shown
            self.assertIn(prompts[0][1].rstrip("\n"), prompts[1][1])  # the original task is shown
            self.assertNotIn("$", prompts[1][1])
            self.assertFalse(out["tool"]["requested"])
        self.assertEqual(episode("required_tool", FINAL_OTHER, FINAL)[0]["required_compliant"], False)
        self.assertIsNone(episode("no_tool", FINAL_OTHER, FINAL)[0]["required_compliant"])

    def test_valid_request_executes_once_and_the_result_reaches_turn_2(self):
        for condition in agent_v2.TOOL_CONDITIONS:
            out, prompts = episode(condition, TOOL_REQ, FINAL)
            self.assertEqual((out["model_calls"], out["tool_executions"], out["error"]), (2, 1, None), condition)
            tool = out["tool"]
            self.assertEqual((tool["requested"], tool["valid"], tool["executed"]), (True, True, True))
            self.assertAlmostEqual(tool["result"]["slope"], KEY["a_ref"], places=12)
            self.assertIn("Tool result (fit_line):\n" + json.dumps(tool["result"]), prompts[1][1])
            self.assertIn(TOOL_REQ, prompts[1][1])
            self.assertEqual(out["required_compliant"], True if condition == "required_tool" else None)

    def test_no_tool_condition_never_executes_a_request(self):
        out, prompts = episode("no_tool", TOOL_REQ, FINAL)
        self.assertEqual((out["model_calls"], out["tool_executions"]), (2, 0))
        self.assertEqual((out["tool"]["requested"], out["tool"]["valid"], out["tool"]["validation_error"]),
                         (True, False, "no_tool_condition"))
        self.assertIn("No tool is available", prompts[1][1])
        self.assertNotIn("slope", prompts[1][1].split("Your previous reply")[1])

    def test_invalid_and_malformed_requests_are_recorded_not_executed(self):
        for reply, code in [
            (json.dumps({"type": "tool", "name": "fit_line", "arguments": {"case_id": "d2-02"}}), "wrong_case_id"),
            (json.dumps({"type": "tool", "name": "shell", "arguments": {"case_id": CASE["id"]}}), "unknown_tool"),
            (json.dumps({"type": "tool", "name": "fit_line", "arguments": {"t": [0, 1]}}), "bad_arguments"),
            (json.dumps({"type": "tool", "name": [], "arguments": {"case_id": CASE["id"]}}), "bad_tool_name"),
            (json.dumps({"type": "tool", "name": "fit_line"}), "bad_arguments"),
        ]:
            for condition in agent_v2.TOOL_CONDITIONS:
                out, prompts = episode(condition, reply, FINAL)
                self.assertEqual((out["model_calls"], out["tool_executions"], out["error"]), (2, 0, None), reply)
                self.assertEqual((out["tool"]["requested"], out["tool"]["valid"], out["tool"]["validation_error"]),
                                 (True, False, code))
                self.assertIn(f"not valid ({code})", prompts[1][1])
                if condition == "required_tool":
                    self.assertFalse(out["required_compliant"])  # an invalid request is not compliance

    def test_tool_exception_is_an_outcome_and_turn_2_still_happens(self):
        original = tools.TOOLS["fit_line"]
        tools.TOOLS["fit_line"] = lambda case: 1 / 0
        try:
            out, prompts = episode("required_tool", TOOL_REQ, FINAL)
        finally:
            tools.TOOLS["fit_line"] = original
        self.assertEqual((out["model_calls"], out["tool_executions"], out["tool"]["executed"]), (2, 1, False))
        self.assertEqual(out["tool"]["execution_error"], "tool_error:ZeroDivisionError")
        self.assertTrue(out["required_compliant"])
        self.assertIn("failed to run", prompts[1][1])

    def test_second_request_at_final_turn_is_an_error_not_an_execution(self):
        out, _ = episode("optional_tool", TOOL_REQ, TOOL_REQ)
        self.assertEqual((out["model_calls"], out["tool_executions"], out["error"], out["answer"]),
                         (2, 1, "tool_request_at_final_turn", None))
        out, _ = episode("no_tool", FINAL, TOOL_REQ)
        self.assertEqual((out["tool_executions"], out["error"]), (0, "tool_request_at_final_turn"))

    def test_missing_turn1_ends_the_episode_and_malformed_turn1_continues(self):
        for condition in agent_v2.CONDITIONS:
            out, prompts = episode(condition, None)
            self.assertEqual((out["model_calls"], out["error"], len(prompts)), (1, "missing_output", 1), condition)
            self.assertIsNone(out["required_compliant"])  # no reply at all: compliance is undefined, not False
            out, prompts = episode(condition, "The slope is about -1.3", FINAL)
            self.assertEqual((out["model_calls"], out["error"], out["turn1"]["error"]), (2, None, "malformed_json"))
            self.assertIn("not a valid JSON object", prompts[1][1])
            self.assertEqual(out["answer"]["acceleration"], round(KEY["a_ref"], 3))
        out, _ = episode("optional_tool", TOOL_REQ, "```json\n" + FINAL + "\n```")
        self.assertEqual((out["model_calls"], out["error"]), (2, "malformed_json"))
        out, _ = episode("optional_tool", TOOL_REQ, None)
        self.assertEqual((out["model_calls"], out["error"]), (2, "missing_output"))

    def test_numeric_overflow_is_a_recorded_outcome_not_a_crash(self):
        # Regression (code review, 2026-09-23): 10**400 as a JSON integer raised OverflowError in the inherited parser.
        huge = json.dumps({"type": "final", "acceleration": 10 ** 400, "units": "m/s^2"})
        out, prompts = episode("no_tool", huge, FINAL)
        self.assertEqual((out["model_calls"], out["turn1"]["error"], out["error"]), (2, "bad_acceleration", None))
        out, _ = episode("optional_tool", TOOL_REQ, huge)
        self.assertEqual((out["model_calls"], out["error"], out["answer"]), (2, "bad_acceleration", None))

    def test_parser_exceptions_are_outcomes(self):
        for text in ("[" * 1000, "1" * 4301):
            out, _ = episode("no_tool", text, FINAL)
            self.assertEqual((out["turn1"]["error"], out["error"]), ("malformed_json", None), text[:10])

    def test_lone_surrogate_in_a_reply_is_made_encodable_for_the_next_prompt(self):
        odd = '{"type": "final", "acceleration": 1.2, "units": "m/s^2\udc80"}'
        out, prompts = episode("no_tool", odd, FINAL)
        prompts[1][1].encode("utf-8")  # must not raise
        self.assertEqual(out["turn1"]["kind"], "final")

    def test_state_survives_an_exception_at_turn_2(self):
        # The runner passes its own state dict; a control violation raised inside call_model at turn 2 must
        # leave the turn-1 and tool evidence in it.
        _, prompt1, template2 = run_v2.render_prompts(CASE, "required_tool")
        state = agent_v2.new_state("required_tool")

        def call_model(prompt, turn):
            if turn == 2:
                raise RuntimeError("control violation")
            return TOOL_REQ
        with self.assertRaises(RuntimeError):
            agent_v2.run_episode_v2(CASE, "required_tool", prompt1, template2, call_model, state=state)
        self.assertEqual((state["turn1"]["kind"], state["tool"]["executed"], state["tool_executions"],
                          state["required_compliant"], state["turn_kinds"]), ("tool", True, 1, True, ["tool"]))
        self.assertIn("Tool result (fit_line):", state["turn2_prompt"])

    def test_unknown_condition_rejected(self):
        with self.assertRaises(ValueError):
            agent_v2.run_episode_v2(CASE, "tools_on", "p", "$original_task", lambda p, t: FINAL)


class IsolationTests(unittest.TestCase):
    def test_prompts_show_only_the_table_and_never_a_key_value(self):
        for split, ids in (("dev", ["d1-01", "d2-01", "d3-02"]), ("scored", ["g1-02", "g2-04", "g3-06"])):
            for task_id in ids:
                case, key = run_v2.load_task(split, task_id)
                for condition in agent_v2.CONDITIONS:
                    _, prompt1, template2 = run_v2.render_prompts(case, condition)
                    out, prompts = (lambda cm: (agent_v2.run_episode_v2(case, condition, prompt1, template2, cm[0]), cm[1]))(
                        scripted(FINAL, FINAL))
                    for _, p in prompts:
                        self.assertIn("t (s): " + ", ".join(case["t_s"]), p)
                        self.assertIn("v (m/s): " + ", ".join(case["v_m_per_s"]), p)
                        self.assertNotIn("$", p)
                        stripped = p.replace(", ".join(case["v_m_per_s"]), "").replace(FINAL, "")
                        for field in ("a_ref", "a_true", "v0"):
                            self.assertNotIn(f"{key[field]:.4f}", stripped, (task_id, condition, field))
                        for word in ("a_ref", "a_true", "key", "answer key", "reference"):
                            self.assertNotIn(word, p.lower().replace("previous reply", ""))

    def test_tool_receives_only_the_displayed_case(self):
        case, key = run_v2.load_task("dev", "d3-01")
        result = tools.fit_line(case)
        self.assertEqual(set(result), {"slope", "slope_units", "intercept", "intercept_units", "n_points"})
        self.assertEqual(result["n_points"], tasks_v2.GROUPS["hard"]["n"])
        self.assertNotIn(f"{key['a_true']:.4f}", json.dumps(result))

    def test_tool_and_final_formats_in_prompts_match_the_parser(self):
        for condition in agent_v2.TOOL_CONDITIONS:
            _, prompt1, _ = run_v2.render_prompts(CASE, condition)
            self.assertIn(TOOL_REQ, prompt1)  # the exact request text the validator accepts
            self.assertIsNone(tools.validate_request(json.loads(TOOL_REQ), CASE["id"]))
        _, prompt1, _ = run_v2.render_prompts(CASE, "no_tool")
        self.assertNotIn("fit_line", prompt1)
        self.assertIn("No tools or code execution are available. Compute the answer from the table.", prompt1)  # V2-4b (Leo)


if __name__ == "__main__":
    unittest.main()
