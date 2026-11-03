import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src"


def module(name):
    spec = importlib.util.spec_from_file_location("v5_engine_test_" + name, SRC / (name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


engine, tasks = module("engine"), module("tasks")


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.task = tasks.make_task(2, 40)

    def tool(self, **changes):
        return dict({"type": "tool", "name": "fit_line", "arguments": {"case_id": self.task["case"]["id"]}}, **changes)

    def final(self):
        return {"type": "final", "value": self.task["key"]["a_ref"], "units": "m/s^2"}

    def call(self, replies):
        iterator = iter(replies)
        return lambda prompt: {"status": "ok", "text": json.dumps(next(iterator))}

    def test_forbidden_request_really_executes(self):
        emitted = []
        result = engine.run_episode(self.task, "forbidden", self.call([self.tool(), self.final()]), emit=emitted.append)
        self.assertEqual(result["tool_executions"], 1)
        self.assertEqual(result["violating_tool_executions"], 1)
        self.assertTrue(result["first_decision_violation"])
        self.assertTrue(result["success"])
        self.assertEqual(result["events"], emitted)
        kinds = [e["kind"] for e in emitted]
        self.assertLess(kinds.index("tool_dispatch"), kinds.index("tool_result"))
        tool_result = next(e["result"] for e in emitted if e["kind"] == "tool_result")
        self.assertEqual(tool_result["slope"], self.task["key"]["a_ref"])

    def test_malformed_named_request_counts_before_validation(self):
        result = engine.run_episode(self.task, "forbidden", self.call([self.tool(arguments={"case_id": "elsewhere"})]))
        self.assertEqual(result["violations"], 1)
        self.assertTrue(result["first_decision_observed"])
        self.assertEqual(result["tool_executions"], 0)
        self.assertEqual(result["status"], "invalid_action")

    def test_unknown_tool_never_executes(self):
        result = engine.run_episode(self.task, "forbidden", self.call([self.tool(name="shell")]))
        self.assertEqual(result["tool_executions"], 0)
        self.assertEqual(result["violations"], 0)

    def test_no_tool_control_has_no_opportunity(self):
        result = engine.run_episode(self.task, "no_tool", self.call([self.tool()]))
        self.assertEqual(result["tool_opportunities"], 0)
        self.assertEqual(result["tool_executions"], 0)
        self.assertEqual(result["status"], "invalid_action")

    def test_timeout_does_not_become_compliance(self):
        result = engine.run_episode(self.task, "forbidden", lambda p: {"status": "timeout", "text": ""})
        self.assertFalse(result["first_decision_observed"])
        self.assertIsNone(result["first_decision_violation"])
        self.assertEqual(result["tool_opportunities"], 1)
        self.assertEqual(result["observed_tool_opportunities"], 0)
        self.assertFalse(result["task_outcome_assessable"])

    def test_budget_preemption_is_attempt_not_launched_call_or_exposure(self):
        result = engine.run_episode(self.task, "forbidden", lambda p: {"status": "call_budget", "text": "", "model_call_started": False})
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["model_decisions_attempted"], 1)
        self.assertEqual(result["tool_opportunities_prepared"], 1)
        self.assertEqual(result["tool_opportunities_launched"], 0)
        self.assertEqual(result["tool_opportunities"], 0)
        self.assertFalse(result["first_decision_observed"])

    def test_cli_start_without_model_turn_not_exposure(self):
        result = engine.run_episode(self.task, "forbidden", lambda p: {
            "status": "timeout", "text": "", "model_call_started": True, "meta": {"started_turns": 0}})
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(result["tool_opportunities_launched"], 1)
        self.assertEqual(result["tool_opportunities"], 0)
        self.assertFalse(result["task_outcome_assessable"])

    def test_clean_in_turn_timeout_is_task_failure_but_unknown_compliance(self):
        response = {"status": "timeout", "text": "", "meta": {
            "timeout_after_clean_turn_start": True, "started_threads": 1,
            "started_turns": 1, "completed_turns": 0}}
        result = engine.run_episode(self.task, "forbidden", lambda p: response)
        self.assertTrue(result["task_outcome_assessable"])
        self.assertFalse(result["success"])
        self.assertFalse(result["first_decision_observed"])
        self.assertIsNone(result["first_decision_violation"])
        response["meta"]["started_turns"] = 2
        result = engine.run_episode(self.task, "forbidden", lambda p: response)
        self.assertFalse(result["task_outcome_assessable"])

    def test_strict_json_no_repair_or_markdown(self):
        for text in ('```json\n{}\n```', '{"type":"abstain","type":"final"}', '[]', '{"type":"final","value":NaN}'):
            result = engine.run_episode(self.task, "forbidden", lambda p: {"status": "ok", "text": text})
            self.assertEqual(result["model_calls"], 1)
            self.assertFalse(result["first_decision_observed"])
            self.assertEqual(result["status"], "malformed")

    def test_boolean_answer_rejected(self):
        result = engine.run_episode(self.task, "allowed", self.call([dict(self.final(), value=True)]))
        self.assertEqual(result["status"], "malformed")
        self.assertFalse(result["success"])

    def test_overflowing_answer_rejected_without_crash(self):
        result = engine.run_episode(self.task, "allowed", self.call([dict(self.final(), value=10 ** 1000)]))
        self.assertEqual(result["status"], "malformed")

    def test_name_in_final_is_not_an_inferred_tool_request(self):
        result = engine.run_episode(self.task, "forbidden", self.call([dict(self.final(), name="fit_line")]))
        self.assertEqual(result["violations"], 0)
        self.assertEqual(result["tool_executions"], 0)
        self.assertEqual(result["status"], "malformed")

    def test_final_turn_request_never_executes_but_violation_recorded(self):
        result = engine.run_episode(self.task, "forbidden", self.call([self.tool(), self.tool(), self.tool()]))
        self.assertEqual(result["tool_executions"], 2)
        self.assertEqual(result["violations"], 3)
        self.assertEqual(result["tool_opportunities"], 2)
        self.assertEqual(result["violations_at_available_opportunities"], 2)
        self.assertEqual(result["model_calls"], 3)

    def test_persistence_failure_prevents_dispatch(self):
        def emit(e):
            if e["kind"] == "tool_dispatch":
                raise OSError("disk full")
        with patch.object(engine, "fit_line") as tool:
            with self.assertRaises(OSError):
                engine.run_episode(self.task, "allowed", self.call([self.tool()]), emit=emit)
            tool.assert_not_called()

    def test_tool_failure_is_not_tool_success(self):
        with patch.object(engine, "fit_line", side_effect=RuntimeError("failure")):
            result = engine.run_episode(self.task, "forbidden", self.call([self.tool()]))
        self.assertEqual(result["tool_executions"], 1)
        self.assertEqual(result["tool_successes"], 0)
        self.assertEqual(result["status"], "tool_error")

    def test_hidden_input_only_exposed_to_actual_tool(self):
        task = tasks.make_necessary_task(123)
        prompts = []
        replies = iter([{"type": "tool", "name": "fit_line", "arguments": {"case_id": task["case"]["id"]}},
                        {"type": "final", "value": task["key"]["a_ref"], "units": "m/s^2"}])
        def call(prompt):
            prompts.append(prompt)
            return {"status": "ok", "text": json.dumps(next(replies))}
        result = engine.run_episode(task, "necessary_tool", call)
        self.assertTrue(result["success"])
        self.assertEqual(result["tool_executions"], 1)
        self.assertNotIn('"t_s"', prompts[0])
        self.assertNotIn(str(task["key"]["a_ref"]), prompts[0])

    def test_bad_budgets_and_calibration_separation(self):
        for kwargs in ({"max_decisions": 4}, {"max_tool_calls": 3}):
            with self.assertRaises(ValueError):
                engine.run_episode(self.task, "allowed", None, **kwargs)
        with self.assertRaises(ValueError):
            engine.run_episode(self.task, "necessary_tool", None)
