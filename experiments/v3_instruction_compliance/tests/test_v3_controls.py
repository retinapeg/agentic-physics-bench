"""Per-call controls: parity with V2's checks on V2's own fixtures, then the V3 additions."""
import unittest

import fixtures_v3 as F
import controls_v3 as K
import run
import run_v2
import test_v2_run as V2T          # V2's test module: its fake_call builds V2-shaped traces

OK = "ok"


def v3(call, expected=None, **kw):
    e = expected or F.EXPECTED
    return K.control_violations_v3(call, K.summarize_call_v3(call), e["model"], e["cli_version"], e["inventory"], **kw)


class ParityTests(unittest.TestCase):
    def test_v3_checker_in_parity_mode_reproduces_v2_on_v2_fixtures(self):
        g = V2T.GOOD_INIT
        fixtures = {
            "clean": V2T.fake_call(OK),
            "native_tools_present": V2T.fake_call(OK, init=dict(g, tools=["Bash"])),
            "mcp_servers_present": V2T.fake_call(OK, init=dict(g, mcp_servers=[{"name": "x"}])),
            "missing_init": V2T.fake_call(OK, init=None),
            "missing_init_fields": V2T.fake_call(OK, init={k: v for k, v in g.items() if k != "claude_code_version"}),
            "unexpected_model": V2T.fake_call(OK, init=dict(g, model="other-model")),
            "native_tool_use": V2T.fake_call(OK, tool_use=True),
            "overage_used": V2T.fake_call(OK, overage=True),
            "stderr_warning": V2T.fake_call(OK, stderr="Warning: Unknown --effort value 'x'"),
            "cli_version_mismatch": V2T.fake_call(OK, init=dict(g, claude_code_version="2.1.278")),
            "server_tool_use": V2T.fake_call(OK, server_tool=True),
            "unexpected_model_usage": V2T.fake_call(OK, extra_model=True),
            "unexpected_iteration": V2T.fake_call(OK, advisor_iteration=True),
        }
        for name, call in fixtures.items():
            s2 = run_v2.summarize_call(call)
            v2 = run.control_violations(call, s2) + run_v2.v2_control_violations(s2, V2T.VERSION)
            mine = K.control_violations_v3(call, K.summarize_call_v3(call), "claude-opus-5", V2T.VERSION, v3_checks=False)
            self.assertEqual(mine, v2, name)
            if name != "clean":
                self.assertTrue(v2, name)


class V3ControlTests(unittest.TestCase):
    def test_clean_call_passes_and_summary_carries_no_identifier(self):
        call = F.fake_call_v3(OK)
        self.assertEqual(v3(call), [])
        s = K.summarize_call_v3(call)
        text = __import__("json").dumps(s)
        for secret in ("SECRET-SESSION", "/private/tmp/secret-cwd", "/Users/someone"):
            self.assertNotIn(secret, text)
        self.assertEqual((s["models_used"], s["canonical_models"], s["max_output_tokens"], s["iteration_count"]),
                         ([F.MODEL], [F.MODEL], [64000], 0))
        self.assertEqual(s["inventory"]["plugins"], ["a-plugin"])
        self.assertIs(s["result_matches_assistant_text"], True)

    def test_result_text_that_is_not_the_models_message_is_recorded(self):
        call = F.fake_call_v3(OK)
        for e in call["events"]:
            if e["type"] == "result":
                e["result"] = "something else"
        s = K.summarize_call_v3(call)
        self.assertIs(s["result_matches_assistant_text"], False)
        self.assertIsNone(K.summarize_call_v3(F.fake_call_v3(None, timeout=True))["result_matches_assistant_text"])

    def test_same_model_advisor_is_caught_without_a_second_usage_key(self):
        # V2's main signal (a second modelUsage key) is silent when the advisor's model is the tested model.
        call = F.fake_call_v3(OK, advisor=True, advisor_model=F.MODEL)
        s = K.summarize_call_v3(call)
        self.assertEqual(s["models_used"], [F.MODEL])
        violations = v3(call)
        self.assertIn("server_tool_use:advisor", violations)
        self.assertIn("unexpected_iteration:advisor_message", violations)
        self.assertIn("iteration_count:3", violations)

    def test_each_v3_addition(self):
        cases = {
            "missing_expected_model_usage": F.fake_call_v3(OK, drop_usage=True),
            "unexpected_num_turns:2": F.fake_call_v3(OK, num_turns=2),
            "iteration_count:2": F.fake_call_v3(OK, iterations=("message", "message")),
            "unexpected_canonical_model:claude-opus-5": F.fake_call_v3(OK, canonical="claude-opus-5"),
            "fast_mode_not_off:on": F.fake_call_v3(OK, fast="on"),
            "subagents_spawned": F.fake_call_v3(OK, subagents=1),
            "api_error_status:529": F.fake_call_v3(OK, api_error_status=529),
            "permission_denials": F.fake_call_v3(OK, permission_denials=[{"tool": "Bash"}]),
            "inventory_changed": F.fake_call_v3(OK, inventory=dict(F.INVENTORY, skills=["a-skill", "b-skill", "new-skill"])),
            "unexpected_model_usage:claude-opus-5": F.fake_call_v3(OK, extra_models=("claude-opus-5",)),
            "unexpected_assistant_model": F.fake_call_v3(OK, assistant_model="claude-opus-5"),
            "unexpected_model": F.fake_call_v3(OK, model="claude-opus-5"),
            "cli_version_mismatch": F.fake_call_v3(OK, version="2.1.297"),
            "native_tools_present": F.fake_call_v3(OK, tools=["Bash"]),
            "mcp_servers_present": F.fake_call_v3(OK, mcp=[{"name": "x"}]),
            "native_tool_use": F.fake_call_v3(OK, native_tool=True),
            "overage_used": F.fake_call_v3(OK, overage=True),
            "stderr_warning": F.fake_call_v3(OK, stderr="Warning: something"),
            "cli_error": F.fake_call_v3(OK, is_error=True, returncode=1),
            "missing_init": F.fake_call_v3(OK, init=False),
        }
        for expected, call in cases.items():
            self.assertIn(expected, v3(call), expected)
        self.assertIn("fast_mode_not_off:on", v3(F.fake_call_v3(OK, result_fast="on")))

    def test_refusal_fallback_is_a_violation_but_an_explicit_refusal_is_an_outcome(self):
        switched = F.fake_call_v3(OK, refusal="fallback")       # the shape observed in reconnaissance on 2026-10-13
        violations = v3(switched)
        for expected in ("model_refusal_fallback:claude-opus-4-8", "unexpected_assistant_model",
                         "unexpected_model_usage:claude-opus-4-8", "unexpected_num_turns:2"):
            self.assertIn(expected, violations)
        refused = F.fake_call_v3(OK, refusal="no_fallback")
        s = K.summarize_call_v3(refused)
        self.assertEqual((v3(refused), K.is_refused(s), K.is_truncated(s)), ([], True, False))
        self.assertIn("native_tools_present", v3(F.fake_call_v3(OK, refusal="no_fallback", tools=["Bash"])))

    def test_truncation_and_timeout_are_outcomes(self):
        cut = F.fake_call_v3('{"type": "fin', stop_reason="max_tokens")
        s = K.summarize_call_v3(cut)
        self.assertEqual((v3(cut), K.is_truncated(s), K.is_refused(s)), ([], True, False))
        self.assertEqual(v3(F.fake_call_v3(None, timeout=True)), [])
        partial = dict(F.fake_call_v3(OK, native_tool=True, overage=True, version="2.1.297"), returncode=None, stderr="timeout after 900 s")
        got = v3(partial)                                       # V2's regression: a timeout must not hide positive evidence
        for expected in ("native_tool_use", "overage_used", "cli_version_mismatch"):
            self.assertIn(expected, got)
        self.assertNotIn("stderr_warning", got)

    def test_inventory_is_names_only_and_order_independent(self):
        a = K.inventory_of(F.init_event())
        b = K.inventory_of(F.init_event(inventory=dict(F.INVENTORY, skills=list(reversed(F.INVENTORY["skills"])))))
        self.assertEqual(a, b)
        self.assertNotIn("/Users", __import__("json").dumps(a))
        self.assertEqual(v3(F.fake_call_v3(OK), expected=dict(F.EXPECTED, inventory=None)), [])


if __name__ == "__main__":
    unittest.main()
