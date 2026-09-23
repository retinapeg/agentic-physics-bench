"""V2 runner: control enforcement, timeouts, resume/dedup, caps and the freeze check (no model calls).
Verification code written by Claude (2026-09-23). Run from the repo root: python3 -m unittest -v tests.test_v2_run
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
import run_v2  # noqa: E402

VERSION = "2.1.280"
GOOD_INIT = {"type": "system", "subtype": "init", "model": "claude-opus-5", "tools": [], "mcp_servers": [],
             "claude_code_version": VERSION, "session_id": "SECRET-SESSION", "cwd": "/private/tmp/secret"}
CASE, KEY = run_v2.load_task("dev", "d1-01")
TOOL_REQ = json.dumps({"type": "tool", "name": "fit_line", "arguments": {"case_id": "d1-01"}})
FINAL = json.dumps({"type": "final", "acceleration": round(KEY["a_ref"], 4), "units": "m/s^2"})
WRONG = json.dumps({"type": "final", "acceleration": round(KEY["a_ref"], 4) + 1, "units": "m/s^2"})


def fake_call(text, init=GOOD_INIT, tool_use=False, stderr="", overage=False, status="allowed", timeout=False,
              thinking=321, server_tool=False, extra_model=False, advisor_iteration=False):
    if timeout:
        return {"argv": models.CLAUDE_ARGV, "returncode": None, "elapsed_s": 600.0, "events": [],
                "non_json_stdout": [], "stderr": "timeout after 600 s"}
    content = [{"type": "text", "text": text}]
    if tool_use:
        content.append({"type": "tool_use", "name": "Bash"})
    if server_tool:
        content.insert(0, {"type": "server_tool_use", "name": "advisor", "input": "{}"})
        content.insert(1, {"type": "advisor_tool_result", "content": {"type": "advisor_redacted_result"}})
    model_usage = {"claude-opus-5": {"outputTokens": 400}}
    if extra_model:
        model_usage["claude-fable-5-1"] = {"outputTokens": 1976}
    iterations = [{"type": "message"}] + ([{"type": "advisor_message", "model": "claude-fable-5-1"}] if advisor_iteration else [])
    events = [e for e in [init] if e] + [
        {"type": "assistant", "message": {"model": init["model"] if init else "claude-opus-5", "content": content}},
        {"type": "rate_limit_event", "rate_limit_info": {"status": status, "isUsingOverage": overage,
                                                         "unifiedWindows": {"five_hour": {"utilization": 0.03},
                                                                            "seven_day": {"utilization": 0.2}}}},
        {"type": "result", "subtype": "success", "is_error": False, "result": text, "duration_ms": 1234,
         "modelUsage": model_usage,
         "usage": {"output_tokens": 400, "output_tokens_details": {"thinking_tokens": thinking}, "iterations": iterations}},
    ]
    return {"argv": models.CLAUDE_ARGV, "returncode": 0, "elapsed_s": 1.5, "events": events,
            "non_json_stdout": [], "stderr": stderr}


class EpisodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.patches = [mock.patch.object(run_v2, "RAW_DIR", tmp / "raw"),
                        mock.patch.dict(run_v2.EPISODES, {"dev": tmp / "episodes.jsonl"}),
                        mock.patch.dict(run_v2.ATTEMPTS, {"dev": tmp / "attempts.jsonl"})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def episode(self, condition, *calls, version=VERSION):
        with mock.patch.object(models, "call_claude", side_effect=list(calls)) as fake:
            rec = run_v2.run_episode("dev", "d1-01", condition, 1, "test-run", version)
        return rec, fake.call_count

    def test_clean_two_call_episode_is_valid_graded_and_saved(self):
        rec, n = self.episode("optional_tool", fake_call(TOOL_REQ), fake_call(FINAL))
        self.assertEqual((rec["valid"], rec["grade"]["correct"], n, rec["model_calls"], rec["tool_executions"]),
                         (True, True, 2, 2, 1))
        self.assertEqual((rec["schema"], rec["run_id"], rec["group"], rec["rep"], rec["cli_version_expected"]),
                         (run_v2.SCHEMA, "test-run", "easy", 1, VERSION))
        self.assertEqual(rec["turn1"]["kind"], "tool")
        self.assertIsNone(rec["turn1"]["grade"])
        saved = [json.loads(l) for l in run_v2.EPISODES["dev"].read_text().splitlines()]
        self.assertEqual([s["episode_id"] for s in saved], [rec["episode_id"]])
        self.assertEqual(len(list(run_v2.RAW_DIR.iterdir())), 2)
        turn = rec["turns"][0]
        self.assertEqual((turn["cli"]["thinking_tokens"], turn["cli"]["usage_windows"]["seven_day"]), (321, 0.2))
        self.assertNotIn("SECRET-SESSION", json.dumps(rec))  # sanitised: no session id or working directory
        self.assertNotIn("/private/tmp/secret", json.dumps(rec))

    def test_turn1_final_answer_is_graded_separately(self):
        rec, _ = self.episode("no_tool", fake_call(WRONG), fake_call(FINAL))
        self.assertEqual((rec["turn1"]["grade"]["correct"], rec["grade"]["correct"]), (False, True))
        rec, _ = self.episode("required_tool", fake_call(FINAL), fake_call(FINAL))
        self.assertEqual((rec["required_compliant"], rec["grade"]["correct"], rec["tool_executions"]), (False, True, 0))

    def test_violations_invalidate_even_a_correct_answer(self):
        cases = {
            "native_tools_present": fake_call(FINAL, init=dict(GOOD_INIT, tools=["Bash"])),
            "mcp_servers_present": fake_call(FINAL, init=dict(GOOD_INIT, mcp_servers=[{"name": "x"}])),
            "missing_init": fake_call(FINAL, init=None),
            "unexpected_model": fake_call(FINAL, init=dict(GOOD_INIT, model="other-model")),
            "native_tool_use": fake_call(FINAL, tool_use=True),
            "overage_used": fake_call(FINAL, overage=True),
            "stderr_warning": fake_call(FINAL, stderr="Warning: Unknown --effort value 'x'"),
            "cli_version_mismatch": fake_call(FINAL, init=dict(GOOD_INIT, claude_code_version="2.1.278")),
            # Found in development stage 1 (2026-09-23): a server-side advisor consulted a second model inside the call.
            "server_tool_use:advisor": fake_call(FINAL, server_tool=True),
            "unexpected_model_usage:claude-fable-5-1": fake_call(FINAL, extra_model=True),
            "unexpected_iteration:advisor_message": fake_call(FINAL, advisor_iteration=True),
        }
        for expected, call in cases.items():
            rec, n = self.episode("no_tool", call, fake_call(FINAL))
            self.assertFalse(rec["valid"], expected)
            self.assertIn(expected, rec["control_violations"])
            self.assertEqual((n, rec["model_calls"]), (1, 1))  # the batch-stopping violation ends the episode
            self.assertEqual(rec["grade"], {"correct": None, "outcome": "invalid_run", "abs_error": None})
            self.assertEqual((rec["parsed"], rec["error"]), (None, "control_violation"))
            self.assertEqual(rec["turns"][0]["response_text"], FINAL)  # evidence preserved

    def test_violation_on_turn_2_keeps_the_turn_1_and_tool_evidence(self):
        # Review finding (2026-09-23): the loop's state was lost when turn 2 raised, so the invalid record
        # said tool_executions=1 next to tool.executed=false and turn1.kind=null.
        rec, n = self.episode("required_tool", fake_call(TOOL_REQ), fake_call(FINAL, stderr="Warning"))
        self.assertEqual((rec["valid"], n, rec["model_calls"], rec["tool_executions"]), (False, 2, 2, 1))
        self.assertEqual((rec["tool"]["executed"], rec["turn1"]["kind"], rec["required_compliant"], rec["turn_kinds"]),
                         (True, "tool", True, ["tool"]))
        self.assertIn("Tool result (fit_line):", rec["tool_section"])
        rec, n = self.episode("optional_tool", fake_call(WRONG), fake_call(FINAL, tool_use=True))
        self.assertEqual((rec["valid"], rec["model_calls"], rec["tool_executions"], rec["turn1"]["kind"]), (False, 2, 0, "final"))

    def test_environment_control_is_set_and_recorded(self):
        import os
        os.environ.pop("CLAUDE_CODE_DISABLE_ADVISOR_TOOL", None)
        rec, _ = self.episode("no_tool", fake_call(FINAL), fake_call(FINAL))
        self.assertEqual(os.environ.get("CLAUDE_CODE_DISABLE_ADVISOR_TOOL"), "1")
        self.assertEqual(rec["env_controls"], {"CLAUDE_CODE_DISABLE_ADVISOR_TOOL": "1"})

    def test_echoed_paths_are_redacted_everywhere_in_the_record(self):
        # Seen in development stage 3: a reply quoted the CLI's per-session scratchpad path.
        leak = '```bash\ncd /private/tmp/claude-501/-x-y/0f0f0f0f-1111-2222-3333-444444444444/scratchpad && python3 -c "..."\n```'
        rec, _ = self.episode("no_tool", fake_call(leak), fake_call(FINAL))
        text = json.dumps(rec) + run_v2.EPISODES["dev"].read_text()
        self.assertNotIn("/private/tmp", text)
        self.assertNotIn("0f0f0f0f", text)
        self.assertIn("<path>", rec["turns"][0]["response_text"])
        self.assertIn("<path>", rec["turns"][1]["prompt"])  # the echoed reply inside the turn-2 prompt
        self.assertEqual(rec["turn1"]["error"], "malformed_json")
        self.assertEqual(run_v2.redact("/var/folders/ab/xyz/T/apb-episode-1/f.json and /Users/someone/x"), "<path> and <path>")

    def test_stderr_line_is_redacted(self):
        rec, _ = self.episode("no_tool", fake_call(FINAL, stderr="Error: EACCES: permission denied, open '/Users/someone/.claude/settings.json'"))
        self.assertFalse(rec["valid"])
        self.assertNotIn("/Users/", rec["turns"][0]["stderr_first_line"])
        self.assertIn("permission denied", rec["turns"][0]["stderr_first_line"])

    def test_timeout_is_missing_output_not_a_control_violation(self):
        rec, n = self.episode("no_tool", fake_call(None, timeout=True))
        self.assertEqual((rec["valid"], n, rec["model_calls"], rec["grade"]["outcome"]), (True, 1, 1, "missing_output"))
        self.assertTrue(rec["turns"][0]["timed_out"])
        self.assertEqual(rec["turns"][0]["control_violations"], [])
        rec, n = self.episode("optional_tool", fake_call(TOOL_REQ), fake_call(None, timeout=True))
        self.assertEqual((rec["valid"], rec["model_calls"], rec["tool_executions"], rec["grade"]["outcome"]),
                         (True, 2, 1, "missing_output"))

    def test_timeout_with_positively_observed_violations_is_invalid(self):
        # Regression (Codex review, 2026-09-23): a partial trace before the timeout showed native tool use and
        # overage, but the timeout branch replaced every control check with an empty list.
        partial = dict(fake_call(FINAL, tool_use=True, overage=True), returncode=None, stderr="timeout after 600 s")
        rec, n = self.episode("no_tool", partial)
        self.assertEqual((rec["valid"], rec["grade"]["outcome"], n), (False, "invalid_run", 1))
        self.assertIn("native_tool_use", rec["control_violations"])
        self.assertIn("overage_used", rec["control_violations"])
        self.assertNotIn("stderr_warning", rec["control_violations"])
        partial = dict(fake_call(FINAL, init=dict(GOOD_INIT, claude_code_version="2.1.278")), returncode=None, stderr="timeout")
        rec, _ = self.episode("no_tool", partial)
        self.assertIn("cli_version_mismatch", rec["control_violations"])
        partial = dict(fake_call(FINAL, init=None), returncode=None, stderr="timeout after 600 s")  # no init yet: not a violation
        rec, _ = self.episode("no_tool", partial)
        self.assertEqual((rec["valid"], rec["grade"]["outcome"]), (True, "missing_output"))

    def test_interrupted_episode_leaves_an_attempt_record_and_is_never_replayed(self):
        # Regression (Codex review, 2026-09-23): the record was written only after both calls, so an interrupt
        # during turn 2 left no trace, and resume repeated the episode and its turn-1 call.
        with mock.patch.object(models, "call_claude", side_effect=[fake_call(FINAL), KeyboardInterrupt()]) as fake:
            with self.assertRaises(KeyboardInterrupt):
                run_v2.run_episode("dev", "d1-01", "no_tool", 1, "test-run", VERSION)
        self.assertEqual(fake.call_count, 2)
        attempts = [json.loads(l) for l in run_v2.ATTEMPTS["dev"].read_text().splitlines()]
        self.assertEqual([(a["task_id"], a["condition"], a["rep"], a["reserved_calls"]) for a in attempts],
                         [("d1-01", "no_tool", 1, 2)])
        self.assertFalse(run_v2.EPISODES["dev"].exists())
        existing, interrupted, already, calls_used = run_v2.resume_state("dev")
        self.assertEqual((existing, len(interrupted), already, calls_used), ([], 1, {("d1-01", "no_tool", 1)}, 2))
        rec, n = self.episode("optional_tool", fake_call(FINAL), fake_call(FINAL))  # a completed episode, another key
        existing, interrupted, already, calls_used = run_v2.resume_state("dev")
        self.assertEqual((len(existing), len(interrupted), calls_used), (1, 1, 4))
        self.assertEqual(already, {("d1-01", "no_tool", 1), ("d1-01", "optional_tool", 1)})
        self.assertEqual(len(run_v2.ATTEMPTS["dev"].read_text().splitlines()), 2)

    def test_nonzero_exit_with_stderr_is_invalid(self):
        call = dict(fake_call(FINAL, stderr="Error: not logged in"), returncode=1)
        rec, _ = self.episode("no_tool", call)
        self.assertEqual((rec["valid"], rec["grade"]["outcome"]), (False, "invalid_run"))
        self.assertIn("stderr_warning", rec["control_violations"])

    def test_wrong_split_or_v1_ids_refused(self):
        for split, task_id in (("dev", "g1-01"), ("scored", "d1-01"), ("dev", "s-01"), ("dev", "dev-01")):
            with self.assertRaises(SystemExit):
                run_v2.load_task(split, task_id)


class BatchTests(unittest.TestCase):
    PLAN = [{"seq": i + 1, "rep": 1 + i // 6, "task_id": f"d1-0{1 + (i // 3) % 2}", "condition": c}
            for i, c in enumerate(["no_tool", "optional_tool", "required_tool"] * 4)]

    def runner(self, outcomes):
        seen = []

        def run_one(item):
            k = run_v2.episode_key(item)
            seen.append(k)
            valid, status, timed_out = outcomes.get(k, (True, "allowed", False))
            turns = [{"cli": {"rate_limit": {"status": status}}, "timed_out": timed_out}] * 2
            return {"valid": valid, "model_calls": 2, "turns": turns}
        return run_one, seen

    def test_attempted_episodes_are_skipped_and_the_cap_holds(self):
        run_one, seen = self.runner({})
        already = {("d1-01", "no_tool", 1), ("d1-01", "optional_tool", 1)}
        recs, reason = run_v2.run_batch(self.PLAN, run_one, already, 4, cap=10)
        self.assertEqual(seen, [("d1-01", "required_tool", 1), ("d1-02", "no_tool", 1), ("d1-02", "optional_tool", 1)])
        self.assertEqual(reason, "invocation_cap")

    def test_max_episodes_invalid_run_and_rate_limit_stop(self):
        run_one, seen = self.runner({})
        self.assertEqual(run_v2.run_batch(self.PLAN, run_one, set(), 0, cap=100, max_episodes=2)[1], "max_episodes")
        self.assertEqual(len(seen), 2)
        run_one, seen = self.runner({("d1-01", "optional_tool", 1): (False, "allowed", False)})
        recs, reason = run_v2.run_batch(self.PLAN, run_one, set(), 0, cap=100)
        self.assertEqual((reason, len(seen)), ("control_violation", 2))
        run_one, seen = self.runner({("d1-01", "no_tool", 1): (True, "rejected", False)})
        self.assertEqual(run_v2.run_batch(self.PLAN, run_one, set(), 0, cap=100)[1], "rate_limit")

    def test_three_consecutive_timeouts_stop_but_isolated_ones_do_not(self):
        keys = [run_v2.episode_key(p) for p in self.PLAN]
        run_one, seen = self.runner({keys[i]: (True, "allowed", True) for i in (0, 1, 2)})
        self.assertEqual(run_v2.run_batch(self.PLAN, run_one, set(), 0, cap=100)[1], "repeated_timeouts")
        self.assertEqual(len(seen), 3)
        run_one, seen = self.runner({keys[i]: (True, "allowed", True) for i in (0, 1, 3, 4, 6)})
        self.assertEqual(run_v2.run_batch(self.PLAN, run_one, set(), 0, cap=100)[1], "completed")
        self.assertEqual(len(seen), 12)

    def test_full_scored_plan_fits_the_cap(self):
        plan = json.loads((run_v2.DATA / "scored_plan.json").read_text())
        run_one, seen = self.runner({})
        recs, reason = run_v2.run_batch(plan, run_one, set(), 0, cap=len(plan) * 2)
        self.assertEqual((reason, len(seen), sum(r["model_calls"] for r in recs)), ("completed", 162, 324))


class RestageTests(unittest.TestCase):
    def test_restage_archives_and_optionally_carries_over_unchanged_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "results" / "v2").mkdir(parents=True)
            with mock.patch.object(run_v2, "ROOT", root), mock.patch.object(run_v2, "RAW_DIR", root / "raw"), \
                    mock.patch.dict(run_v2.EPISODES, {"dev": root / "results" / "v2" / "episodes_dev.jsonl"}), \
                    mock.patch.dict(run_v2.ATTEMPTS, {"dev": root / "results" / "v2" / "attempts_dev.jsonl"}):
                with mock.patch.object(models, "call_claude", side_effect=[fake_call(FINAL), fake_call(FINAL)]):
                    run_v2.run_episode("dev", "d1-01", "no_tool", 1, "dev", VERSION)
                info = run_v2.restage_dev("one", keep_unchanged=True)
                self.assertEqual((info["archived_to"], info["carried_over"]), ("results/v2/dev_one", 1))
                self.assertTrue((root / "results" / "v2" / "dev_one" / "episodes_dev.jsonl").exists())
                self.assertTrue((root / "results" / "v2" / "dev_one" / "dev_tasks.jsonl").exists())
                self.assertEqual(len(run_v2.EPISODES["dev"].read_text().splitlines()), 1)
                with mock.patch.object(models, "call_claude", side_effect=[fake_call(FINAL), fake_call(FINAL)]):
                    run_v2.run_episode("dev", "d1-01", "optional_tool", 1, "dev", VERSION)
                info = run_v2.restage_dev("one-b", keep_unchanged=True, rerun_conditions=("no_tool",))
                self.assertEqual(info["carried_over"], 1)  # the optional_tool record only
                self.assertEqual(json.loads(run_v2.EPISODES["dev"].read_text())["condition"], "optional_tool")
                info = run_v2.restage_dev("two")  # no carry-over: a fresh start
                self.assertEqual(info["carried_over"], 0)
                self.assertFalse(run_v2.EPISODES["dev"].exists())
                with self.assertRaises(SystemExit):
                    run_v2.restage_dev("two")


class FreezeTests(unittest.TestCase):
    def test_scored_batch_refuses_without_a_manifest(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(run_v2, "MANIFEST", Path(tmp) / "none.json"):
            with self.assertRaises(SystemExit):
                run_v2.verify_freeze()

    def test_manifest_written_once_then_verified_and_tampering_detected(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(run_v2, "MANIFEST", Path(tmp) / "m.json"), \
                mock.patch.object(run_v2, "cli_version", return_value=VERSION):
            m = run_v2.write_manifest("test-run")
            self.assertEqual((m["run_id"], m["claude_code_version"], m["limits"]["planned_episodes"],
                              m["limits"]["max_scored_invocations"]), ("test-run", VERSION, 162, 324))
            self.assertEqual(set(m["sha256"]), set(run_v2.FROZEN_FILES))
            with self.assertRaises(SystemExit):
                run_v2.write_manifest("second")  # never overwrite a freeze
            self.assertEqual(run_v2.verify_freeze()["run_id"], "test-run")
            with mock.patch.object(run_v2, "cli_version", return_value="9.9.9"), self.assertRaises(SystemExit):
                run_v2.verify_freeze()
            with mock.patch.object(run_v2, "TIMEOUT_S", 1), self.assertRaises(SystemExit):
                run_v2.verify_freeze()
            self.assertEqual(m["env_controls"], {"CLAUDE_CODE_DISABLE_ADVISOR_TOOL": "1"})
            with mock.patch.object(run_v2, "ENV_CONTROLS", {}), self.assertRaises(SystemExit):
                run_v2.verify_freeze()
            tampered = json.loads(run_v2.MANIFEST.read_text())
            tampered["sha256"]["prompts/v2/turn2.txt"] = "0" * 64
            run_v2.MANIFEST.write_text(json.dumps(tampered))
            with self.assertRaises(SystemExit):
                run_v2.verify_freeze()


if __name__ == "__main__":
    unittest.main()
