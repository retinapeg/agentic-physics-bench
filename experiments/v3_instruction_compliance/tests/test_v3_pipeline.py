"""End to end with a fake CLI: task -> policy cell -> model choice -> request -> permitted or denied ->
returned result -> final answer -> deterministic score -> analysis denominators. One episode per cell."""
import json
import unittest
from unittest import mock

import fixtures_v3 as F
import analyze_v3 as A
import agent_v3
import models_v3
import pendulum_v3
import policy_v3 as P
import run_v3
import tasks
import tasks_v3

TASK = "e2-01"                                   # hard stratum: 120 points on an irregular grid


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.keys, _ = tasks_v3.load("dev")
        self.case, self.key = self.cases[TASK], self.keys[TASK]

    def cli(self, turn1):
        """A fake CLI that answers turn 1 as told and at turn 2 relays the tool result if one is shown."""
        prompts = []

        def call(prompt, timeout_s=None):
            prompts.append(prompt)
            if len(prompts) == 1:
                return F.fake_call_v3(turn1)
            marker = "Tool result (fit_line):\n"
            if marker in prompt:
                result, _ = json.JSONDecoder().raw_decode(prompt.split(marker, 1)[1])
                return F.fake_call_v3(F.final(round(result["slope"], 4)))
            return F.fake_call_v3(F.final(round(self.key["a_ref"], 4)))
        return call, prompts

    def run_cell(self, cell, turn1):
        call, prompts = self.cli(turn1)
        with mock.patch.object(models_v3, "call_claude_v3", side_effect=call):
            rec = run_v3.run_episode_a("dev", {"task_id": TASK, "cell": cell, "rep": 1}, "pipeline-test", F.EXPECTED)
        return rec, prompts

    def test_one_episode_per_cell(self):
        with F.Sandbox():
            slope = tasks.ls_slope([float(x) for x in self.case["t_s"]], [float(x) for x in self.case["v_m_per_s"]])
            for cell in P.CELLS:
                rec, prompts = self.run_cell(cell, F.request(TASK))
                # task: the prompt shows the displayed table and nothing from the key
                self.assertIn("t (s): " + ", ".join(self.case["t_s"]), prompts[0])
                for field in ("a_ref", "a_true", "v0"):
                    self.assertNotIn(f"{self.key[field]:.4f}", prompts[0].replace(", ".join(self.case["v_m_per_s"]), ""))
                self.assertEqual(prompts[0], P.render_turn1(self.case, cell))
                self.assertEqual((rec["valid"], rec["model_calls"], rec["turn1_kind"], rec["stratum"]), (True, 2, "fit_line_request", "S2"))
                if P.PERMISSION[cell] == "permitted":
                    # validated execution -> the returned result reaches turn 2 -> relayed -> scored
                    self.assertEqual((rec["executed"], rec["tool_result"]["slope"], rec["tool_result"]["n_points"]), (True, slope, 120))
                    self.assertIn("Tool result (fit_line):\n" + json.dumps(rec["tool_result"]), prompts[1])
                    self.assertEqual(rec["parsed"]["acceleration"], round(slope, 4))
                    self.assertEqual(rec["denied"], None)
                else:
                    # prohibited: recorded as a violation, denied with the shared string, never executed
                    self.assertEqual((rec["executed"], rec["denied"], rec["policy_violation_turn1"], rec["tool_result"]), (False, True, True, None))
                    self.assertIn(P.SECTION_DENIED, prompts[1])
                    self.assertNotIn("Tool result", prompts[1])
                self.assertIn(prompts[0].rstrip("\n"), prompts[1])
                self.assertEqual(rec["grade"]["outcome"], "correct")
                self.assertEqual(rec["grade"], agent_v3.grade({"answer": rec["parsed"], "error": None}, self.key["a_ref"]))
                self.assertEqual(rec["tolerance"], 0.002)
            rec, prompts = self.run_cell("D", F.request(TASK, name="calculator"))          # an other-tool request in D
            self.assertEqual((rec["request_other_tool"], rec["policy_violation_turn1"], rec["executed"]), (True, False, False))
            # analysis: six completed episodes on one task; the planned denominator stays 15
            plan = tasks_v3.load("dev")[2]
            episodes = F.C.read_jsonl(run_v3.paths("a", "dev")[0])
            s = A.summarize_a(plan, self.keys, episodes, F.C.read_jsonl(run_v3.paths("a", "dev")[1]), "dev")
            self.assertEqual((s["planned_episodes"], s["completed"], s["duplicate_records"]), (15, 5, 1))
            self.assertEqual({c: s["cells"][c]["fit_line_request"]["x"] for c in P.CELLS}, dict.fromkeys(P.CELLS, 1))
            self.assertEqual((s["cells"]["D"]["denied"], s["cells"]["C_NO"]["denied"], s["cells"]["A"]["executed"]), (1, 1, 1))
            self.assertEqual(s["cells"]["A"]["outcome_counts"], {"correct": 1, "not_attempted": 2})

    def test_arm_b_end_to_end(self):
        with F.Sandbox() as box:
            items, reference, plan = pendulum_v3.load("dev")
            reply = json.dumps({"type": "final", "closed_form_claim": "exists", "representation": "finite_closed_form",
                                "basis": "Gaussian heat kernel", "expression": "exp(-(x - x')^2/(2*tau)) / sqrt(2*pi*tau)", "notes": ""})
            captured = []
            with mock.patch.object(models_v3, "call_claude_v3", side_effect=lambda p, timeout_s=None: (captured.append(p), F.fake_call_v3(reply))[1]):
                rec = run_v3.run_episode_b("dev", {"item_id": "pd-free", "frame": "OPEN", "rep": 1}, "pipeline-test", F.EXPECTED)
            self.assertEqual(captured, [pendulum_v3.render(items["pd-free"], "OPEN")])
            self.assertEqual((rec["valid"], rec["model_calls"], rec["graded"]["label"], rec["graded"]["flags"]),
                             (True, 1, "FINITE_CLAIMED_WITH_FORM", []))
            s = A.summarize_b(plan, items, reference, F.C.read_jsonl(run_v3.paths("b", "dev")[0]),
                              F.C.read_jsonl(run_v3.paths("b", "dev")[1]), "dev")
            self.assertEqual((s["planned_episodes"], s["completed"], s["by_item_frame"]["pd-free | OPEN"]["exists"]), (6, 1, 1))

    def test_child_environment_carries_the_controls_and_this_process_does_not_change(self):
        import os
        before = dict(os.environ)
        launcher = {"MAX_THINKING_TOKENS": "1000", "CLAUDE_CODE_ENABLE_EXPERIMENTAL_ADVISOR_TOOL": "1", "CLAUDE_EFFORT": "xhigh",
                    "CLAUDE_CODE_CHILD_SESSION": "1", "ANTHROPIC_BASE_URL": "https://example.invalid", "HOME": "/home/x"}
        with mock.patch.dict(os.environ, launcher):
            env = models_v3.child_env()
            for name, value in models_v3.ENV_CONTROLS.items():
                self.assertEqual(env[name], value)
            # an allowlist: nothing the launcher exports reaches the child except the named basics
            self.assertEqual(set(env) - set(models_v3.ENV_CONTROLS), set(models_v3.ENV_PASSTHROUGH) & set(os.environ))
            self.assertEqual(env["HOME"], "/home/x")
            for name in launcher:
                if name != "HOME":
                    self.assertNotIn(name, env)
            self.assertNotIn("HOME", models_v3.ENV_CONTROLS)
            self.assertEqual(models_v3.inherited_env_names(), sorted(set(models_v3.ENV_PASSTHROUGH) & set(os.environ)))
        self.assertEqual(dict(os.environ), before)
        self.assertNotIn("CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK", [k for k in before if before.get(k) != os.environ.get(k)])


if __name__ == "__main__":
    unittest.main()
