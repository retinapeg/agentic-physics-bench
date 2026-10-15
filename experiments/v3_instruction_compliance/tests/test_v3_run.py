"""The V3 runner on a fake CLI: records, controls, attempt log, batch stop rules, redaction (no model calls)."""
import json
import unittest
from unittest import mock

import fixtures_v3 as F
import models_v3
import policy_v3 as P
import run_v3

CASE, KEY = F.dev_case("e1-02")
GOOD = F.final(round(KEY["a_ref"], 4))
REQ = F.request(CASE["id"])


class EpisodeTests(unittest.TestCase):
    def test_denied_episode_is_valid_and_fully_recorded(self):
        with F.Sandbox() as box:
            rec, n = box.episode_a("e1-02", "D", F.fake_call_v3(REQ), F.fake_call_v3(GOOD))
            self.assertEqual((n, rec["valid"], rec["model_calls"], rec["cell"], rec["permission_state"], rec["stratum"]),
                             (2, True, 2, "D", "prohibited", "S1"))
            self.assertEqual((rec["policy_violation_turn1"], rec["denied"], rec["executed"], rec["tool_executions"],
                              rec["grade"]["outcome"]), (True, True, False, 0, "correct"))
            self.assertEqual(rec["tool_section"], P.SECTION_DENIED)
            self.assertEqual(rec["env_controls"]["CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK"], "1")
            saved = F.C.read_jsonl(run_v3.paths("a", "dev")[0])
            self.assertEqual([s["episode_id"] for s in saved], [rec["episode_id"]])
            attempts = F.C.read_jsonl(run_v3.paths("a", "dev")[1])
            self.assertEqual([(a["task_id"], a["cell"], a["rep"], a["reserved_calls"]) for a in attempts], [("e1-02", "D", 1, 2)])
            self.assertEqual(len(list((F.C.RAW / "test-run").iterdir())), 2)
            text = json.dumps(rec)
            for secret in ("SECRET-SESSION", "/private/tmp/secret-cwd", "/Users/someone"):
                self.assertNotIn(secret, text)
            self.assertEqual(rec["turns"][0]["cli"]["models_used"], [F.MODEL])

    def test_runtime_violation_is_invalid_and_distinct_from_a_policy_violation(self):
        with F.Sandbox() as box:
            rec, n = box.episode_a("e1-02", "A", F.fake_call_v3(GOOD, refusal="fallback"), F.fake_call_v3(GOOD))
            self.assertEqual((n, rec["valid"], rec["grade"]["outcome"], rec["parsed"], rec["error"]),
                             (1, False, "invalid_run", None, "control_violation"))
            self.assertIn("model_refusal_fallback:claude-opus-4-8", rec["control_violations"])
            self.assertIsNone(rec["policy_violation_turn1"])
            rec, n = box.episode_a("e1-02", "D", F.fake_call_v3(REQ), F.fake_call_v3(GOOD, advisor=True), rep=2)
            self.assertEqual((n, rec["valid"]), (2, False))                # turn-2 violation keeps the turn-1 evidence
            self.assertEqual((rec["turn1_kind"], rec["policy_violation_turn1"], rec["denied"]), ("fit_line_request", True, True))
            self.assertIn("server_tool_use:advisor", rec["control_violations"])

    def test_refusal_timeout_and_truncation_are_outcomes(self):
        with F.Sandbox() as box:
            rec, n = box.episode_a("e1-02", "B", F.fake_call_v3("x", refusal="no_fallback"))
            self.assertEqual((n, rec["valid"], rec["grade"]["outcome"], rec["turns"][0]["refused"]), (1, True, "classifier_refusal", True))
            rec, n = box.episode_a("e1-02", "B", F.fake_call_v3(None, timeout=True), rep=2)
            self.assertEqual((n, rec["valid"], rec["grade"]["outcome"], rec["turns"][0]["timed_out"]), (1, True, "missing_output", True))
            rec, n = box.episode_a("e1-02", "B", F.fake_call_v3(GOOD), F.fake_call_v3(GOOD[:15], stop_reason="max_tokens"), rep=3)
            self.assertEqual((rec["valid"], rec["grade"]["outcome"], rec["output_truncated"]),
                             (True, "output_truncated", {"turn1": False, "turn2": True}))

    def test_wrong_split_ids_are_refused_and_paths_are_redacted(self):
        with F.Sandbox() as box:
            with self.assertRaises(SystemExit):
                box.episode_a("h1-01", "A", F.fake_call_v3(GOOD), split="dev")
            with self.assertRaises(SystemExit):
                box.episode_a("e1-01", "A", F.fake_call_v3(GOOD), split="heldout")
            with self.assertRaises(SystemExit):
                box.episode_b("p-0-qp", "OPEN", F.fake_call_v3("x"), split="dev")
            leak = "```bash\ncd /private/tmp/claude-501/-x/0f0f0f0f-1111-2222-3333-444444444444/scratchpad\n```"
            rec, _ = box.episode_a("e1-02", "A", F.fake_call_v3(leak), F.fake_call_v3(GOOD))
            saved = run_v3.paths("a", "dev")[0].read_text()
            self.assertNotIn("/private/tmp", saved)
            self.assertNotIn("0f0f0f0f", saved)
            ids = "Request ID: req_011CfzUbcqi7kDhWtgMZjn8b Message ID: msg_011CfzUbd4bQFockbjbAAgQb session 4e774517-8915-4d4a-b394-b90eb0e75033"
            self.assertEqual(run_v3.scrub(ids), "Request ID: <request-id> Message ID: <message-id> session <uuid>")
            self.assertEqual(run_v3.scrub('{"type": "final", "acceleration": 1.2345, "units": "m/s^2"}'),
                             '{"type": "final", "acceleration": 1.2345, "units": "m/s^2"}')

    def test_interrupted_episode_is_never_replayed(self):
        with F.Sandbox():
            with mock.patch.object(models_v3, "call_claude_v3", side_effect=[F.fake_call_v3(GOOD), KeyboardInterrupt()]):
                with self.assertRaises(KeyboardInterrupt):
                    run_v3.run_episode_a("dev", {"task_id": "e1-02", "cell": "A", "rep": 1}, "test-run", F.EXPECTED)
            existing, interrupted, already, used = run_v3.resume_state("a", "dev")
            self.assertEqual((existing, len(interrupted), already, used), ([], 1, {("e1-02", "A", 1)}, 2))

    def test_arm_b_episode(self):
        with F.Sandbox() as box:
            reply = json.dumps({"type": "final", "closed_form_claim": "none_known", "representation": "exact_infinite_series",
                                "basis": "Mathieu functions", "expression": "sum_n ce_2n(theta/2, q) ...", "notes": ""})
            rec, n = box.episode_b("pd-pendulum-0_3", "OPEN", F.fake_call_v3(reply))
            self.assertEqual((n, rec["valid"], rec["model_calls"], rec["graded"]["label"], rec["finite_exists"]),
                             (1, True, 1, "NO_FINITE_CLAIMED_WITH_SERIES", False))
            self.assertEqual(F.C.read_jsonl(run_v3.paths("b", "dev")[1])[0]["reserved_calls"], 1)
            rec, _ = box.episode_b("pd-free", "OPEN", F.fake_call_v3(reply, extra_models=("claude-opus-4-8",)))
            self.assertEqual((rec["valid"], rec["graded"]["label"]), (False, "invalid_run"))


class BatchTests(unittest.TestCase):
    PLAN = [{"seq": i + 1, "rep": 1, "task_id": f"e1-0{1 + i // 5}", "cell": c} for i, c in enumerate(list(P.CELLS) * 2)]

    def runner(self, outcomes):
        seen = []

        def run_one(item):
            k = run_v3.key_a(item)
            seen.append(k)
            valid, status, timed_out, windows = outcomes.get(k, (True, "allowed", False, {"five_hour": 0.1, "seven_day": 0.1}))
            turn = {"cli": {"rate_limit": {"status": status}, "usage_windows": windows}, "timed_out": timed_out}
            return {"valid": valid, "model_calls": 2, "turns": [turn, turn]}
        return run_one, seen

    def batch(self, outcomes, already=(), used=0, cap=100, **kw):
        run_one, seen = self.runner(outcomes)
        records, reason = run_v3.run_batch(self.PLAN, run_v3.key_a, run_one, 2, set(already), used, cap, **kw)
        return seen, reason

    def test_stop_rules(self):
        keys = [run_v3.key_a(p) for p in self.PLAN]
        seen, reason = self.batch({})
        self.assertEqual((len(seen), reason), (10, "completed"))
        seen, reason = self.batch({}, already=keys[:2], used=4, cap=10)
        self.assertEqual((seen, reason), (keys[2:5], "invocation_cap"))
        self.assertEqual(self.batch({}, max_episodes=3), (keys[:3], "max_episodes"))
        self.assertEqual(self.batch({keys[1]: (False, "allowed", False, {})}), (keys[:2], "control_violation"))
        self.assertEqual(self.batch({keys[0]: (True, "rejected", False, {})}), (keys[:1], "rate_limit"))
        timeouts = {k: (True, "allowed", True, {}) for k in keys[:3]}
        self.assertEqual(self.batch(timeouts), (keys[:3], "repeated_timeouts"))
        spaced = {keys[i]: (True, "allowed", True, {}) for i in (0, 1, 3, 4, 6)}
        self.assertEqual(self.batch(spaced)[1], "completed")

    def test_usage_guard_stops_before_the_windows_are_exhausted(self):
        keys = [run_v3.key_a(p) for p in self.PLAN]
        self.assertEqual(self.batch({keys[2]: (True, "allowed", False, {"five_hour": 0.86, "seven_day": 0.2})}), (keys[:3], "usage_guard"))
        self.assertEqual(self.batch({keys[1]: (True, "allowed", False, {"five_hour": 0.2, "seven_day": 0.70})}), (keys[:2], "usage_guard"))
        self.assertEqual(self.batch({keys[1]: (True, "allowed", False, {"five_hour": 0.84, "seven_day": 0.69})})[1], "completed")

    def test_full_heldout_plans_fit_their_caps(self):
        plan = F.tasks_v3.load("heldout")[2]
        seen = []
        turn = {"cli": {"rate_limit": {"status": "allowed"}, "usage_windows": {}}, "timed_out": False}
        records, reason = run_v3.run_batch(plan, run_v3.key_a, lambda i: (seen.append(i), {"valid": True, "model_calls": 2, "turns": [turn]})[1],
                                           2, set(), 0, len(plan) * 2)
        self.assertEqual((reason, len(seen), sum(r["model_calls"] for r in records)), ("completed", 180, 360))


class ProbeTests(unittest.TestCase):
    def test_probe_record_holds_identities_and_inventory_without_identifiers(self):
        with F.Sandbox():
            with mock.patch.object(models_v3, "call_claude_v3", return_value=F.fake_call_v3("ok")):
                row = run_v3.probe("v3-probe-1")
            self.assertEqual((row["refused"], row["control_violations"], row["response_text"]), (False, [], "ok"))
            self.assertEqual(row["identities"], {"init_model": F.MODEL, "assistant_models": [F.MODEL], "models_used": [F.MODEL],
                                                  "canonical_models": [F.MODEL]})
            self.assertEqual(row["inventory"], F.EXPECTED["inventory"])
            self.assertEqual(run_v3.latest_probe()["run_id"], "v3-probe-1")
            self.assertNotIn("SECRET-SESSION", run_v3.PREFREEZE.read_text())
            with mock.patch.object(models_v3, "call_claude_v3", return_value=F.fake_call_v3("ok", refusal="fallback")):
                row = run_v3.probe("v3-probe-x")
            self.assertIn("model_refusal_fallback:claude-opus-4-8", row["control_violations"])


if __name__ == "__main__":
    unittest.main()
