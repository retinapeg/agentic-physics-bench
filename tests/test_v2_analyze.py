"""Checks for the V2 deterministic analysis (no model calls). Verification code written by Claude (2026-09-23).
Run from the repo root: python3 -m unittest -v tests.test_v2_analyze
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import analyze_v2  # noqa: E402


def record(task_id, condition, rep, a_ref, outcome="correct", requested=None, executed=None, compliant=None,
           valid=True, turn1_kind="final", answer=None, timed_out=False, run_id="test", turn1_text="{}", turn1_error=None):
    if requested is None:
        requested = condition != "no_tool" and turn1_kind == "tool"
    if executed is None:
        executed = requested and condition != "no_tool"
    if compliant is None:
        compliant = (executed if condition == "required_tool" and turn1_kind is not None else None)
    parsed = None if outcome in ("missing_output", "malformed_json", "tool_request_at_final_turn") or not valid else \
        {"acceleration": a_ref if answer is None else answer, "units": "m/s^2"}
    abs_error = None if parsed is None else abs(parsed["acceleration"] - a_ref)
    grade = {"correct": None, "outcome": "invalid_run", "abs_error": None} if not valid else \
        {"correct": outcome == "correct", "outcome": outcome, "abs_error": abs_error}
    t1_answer = {"acceleration": a_ref + 0.5, "units": "m/s^2"} if turn1_kind == "final" else None
    return {"run_id": run_id, "episode_id": f"{task_id}-{condition}-r{rep}", "task_id": task_id, "condition": condition,
            "rep": rep, "valid": valid, "model_calls": 2, "parsed": parsed, "grade": grade,
            "required_compliant": compliant, "tool_executions": 1 if executed else 0,
            "tool": {"requested": requested, "request": None, "valid": executed or None,
                     "validation_error": None if not requested or executed else "wrong_case_id",
                     "executed": executed, "result": {"slope": a_ref} if executed else None, "execution_error": None},
            "turn1": {"kind": turn1_kind, "answer": t1_answer, "error": turn1_error,
                      "grade": {"correct": False, "outcome": "wrong_value", "abs_error": 0.5} if t1_answer else None},
            "turns": [{"elapsed_s": 3.0, "timed_out": timed_out, "response_text": turn1_text,
                       "cli": {"result": {"output_tokens": 100}, "thinking_tokens": 50}}] * 2}


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.keys, self.cases, _, _ = analyze_v2.load("dev")
        self.a = {k: v["a_ref"] for k, v in self.keys.items()}

    def full(self, overrides=None):
        overrides = overrides or {}
        eps = []
        for p in self.plan:
            k = (p["task_id"], p["condition"], p["rep"])
            kw = overrides.get(k, {})
            eps.append(record(p["task_id"], p["condition"], p["rep"], self.a[p["task_id"]], **kw))
        return eps

    def test_complete_run_counts(self):
        s = analyze_v2.summarize(self.plan, self.keys, self.cases, self.full(), [], "dev")
        self.assertEqual((s["planned_episodes"], s["attempted"], s["valid"], s["model_invocations"]), (18, 18, 18, 36))
        for g in analyze_v2.GROUPS:
            for c in analyze_v2.CONDITIONS:
                self.assertEqual(s["groups"][g]["conditions"][c]["correct"], 2)
        self.assertEqual(s["deterministic_solver"], {"correct": 6, "of_tasks": 6, "max_abs_error": 0.0})
        for name, d in s["paired"]["all_tasks"].items():
            self.assertEqual((d["mean_difference"], d["tasks_tied"], d["bootstrap_95pct"]), (0.0, 6, [0.0, 0.0]), name)

    def test_missing_invalid_duplicate_and_unplanned_records_stay_visible(self):
        eps = self.full({("d3-01", "no_tool", 1): {"valid": False}, ("d3-02", "no_tool", 1): {"outcome": "wrong_value", "answer": 1.0}})
        eps = [e for e in eps if not (e["task_id"] == "d1-01" and e["condition"] == "optional_tool")]  # never attempted
        eps.append(record("d2-01", "required_tool", 1, self.a["d2-01"]))  # duplicate (task, condition, rep)
        eps.append(record("d2-01", "required_tool", 7, self.a["d2-01"]))  # not in the plan
        s = analyze_v2.summarize(self.plan, self.keys, self.cases, eps, [], "dev")
        self.assertEqual((s["planned_episodes"], s["attempted"], s["valid"], s["duplicate_records"], s["unplanned_records"]),
                         (18, 17, 16, 1, 1))
        hard_no_tool = s["groups"]["hard"]["conditions"]["no_tool"]
        self.assertEqual(hard_no_tool["outcome_counts"], {"invalid_run": 1, "wrong_value": 1})
        self.assertEqual((hard_no_tool["correct"], hard_no_tool["of_planned"]), (0, 2))
        easy_opt = s["groups"]["easy"]["conditions"]["optional_tool"]
        self.assertEqual(easy_opt["outcome_counts"], {"correct": 1, "not_attempted": 1})
        self.assertEqual(sum(sum(s["groups"][g]["conditions"][c]["outcome_counts"].values())
                             for g in analyze_v2.GROUPS for c in analyze_v2.CONDITIONS), 18)
        self.assertIn("not completed", s["stop_conditions"])
        d = s["paired"]["all_tasks"]["optional_tool_minus_no_tool"]
        self.assertEqual((d["tasks_favouring_first"], d["tasks_favouring_second"], d["tasks_tied"]), (2, 1, 3))
        self.assertAlmostEqual(d["mean_difference"], (1 + 1 - 1) / 6)

    def test_tool_accounting_and_taxonomy(self):
        eps = self.full({
            ("d1-01", "optional_tool", 1): {"turn1_kind": "tool"},                                   # executed, correct
            ("d1-02", "optional_tool", 1): {"turn1_kind": "tool", "executed": False, "outcome": "wrong_value", "answer": 5.0},  # invalid request
            ("d2-01", "required_tool", 1): {"turn1_kind": "tool"},                                   # compliant
            ("d2-02", "required_tool", 1): {"turn1_kind": "final"},                                  # noncompliant
            ("d3-01", "required_tool", 1): {"turn1_kind": "tool", "outcome": "wrong_value", "answer": 9.0},  # executed then wrong
            ("d3-02", "required_tool", 1): {"turn1_kind": "tool", "outcome": "missing_output"},
            ("d3-01", "no_tool", 1): {"turn1_kind": "tool", "requested": True, "executed": False},
        })
        s = analyze_v2.summarize(self.plan, self.keys, self.cases, eps, [], "dev")
        opt, req = s["conditions"]["optional_tool"], s["conditions"]["required_tool"]
        self.assertEqual((opt["tool"]["requested"], opt["tool"]["valid_request"], opt["tool"]["executed"]), (2, 1, 1))
        self.assertEqual(opt["tool"]["invalid_request_errors"], ["wrong_case_id"])
        self.assertEqual((req["required_compliant"], req["required_compliant_of_valid"]), (3, 6))
        self.assertEqual((req["tool"]["executed"], req["tool"]["relay"]["n"], req["tool"]["relay"]["faithful_within_tol"]), (3, 2, 1))
        self.assertEqual(s["conditions"]["no_tool"]["tool"], dict(requested=1, valid_request=0, executed=0,
                                                                  invalid_request_errors=["wrong_case_id"],
                                                                  relay={"n": 0, "faithful_within_tol": 0, "max_abs_diff": None}))
        tax = s["tool_failure_taxonomy"]
        self.assertEqual((tax["malformed_or_invalid_request"], tax["executed_then_wrong_value"], tax["executed_then_correct"],
                          tax["executed_then_no_parseable_answer"], tax["required_noncompliant"]), (1, 1, 2, 1, 3))
        self.assertEqual(s["conditions"]["no_tool"]["turn1"], {"final_answers": 5, "correct": 0, "revised_at_turn2": 5,
                                                              "unparsed": {"attempted_code_execution": 0, "other_text": 0}})

    def test_turn1_no_reply_is_not_noncompliance_and_wrong_units_after_execution_is_counted(self):
        eps = self.full({("d2-01", "required_tool", 1): {"turn1_kind": None, "outcome": "missing_output", "requested": False, "executed": False},
                         ("d2-02", "required_tool", 1): {"turn1_kind": "tool"},
                         ("d1-01", "optional_tool", 1): {"turn1_kind": "tool", "outcome": "wrong_units"}})
        s = analyze_v2.summarize(self.plan, self.keys, self.cases, eps, [], "dev")
        req = s["conditions"]["required_tool"]
        self.assertEqual((req["required_compliant"], req["required_compliant_of_valid"]), (1, 5))  # 6 valid, one never replied
        self.assertEqual(s["tool_failure_taxonomy"]["required_noncompliant"], 4)
        self.assertEqual(s["tool_failure_taxonomy"]["executed_then_wrong_units"], 1)
        tax = s["tool_failure_taxonomy"]
        executed_total = s["conditions"]["optional_tool"]["tool"]["executed"] + req["tool"]["executed"]
        self.assertEqual(executed_total, tax["executed_then_no_parseable_answer"] + tax["executed_then_wrong_units"]
                         + tax["executed_then_wrong_value"] + tax["executed_then_correct"])  # the rows partition executed episodes

    def test_unparsed_turn1_replies_are_classified(self):
        eps = self.full({("d3-01", "no_tool", 1): {"turn1_kind": None, "turn1_error": "malformed_json", "turn1_text": "```bash\npython3 -c 'x'\n```"},
                         ("d3-02", "no_tool", 1): {"turn1_kind": None, "turn1_error": "malformed_json", "turn1_text": "The slope is about 2.6"},
                         ("d2-01", "no_tool", 1): {"turn1_kind": None, "turn1_error": "missing_output", "turn1_text": None, "outcome": "missing_output"}})
        s = analyze_v2.summarize(self.plan, self.keys, self.cases, eps, [], "dev")
        self.assertEqual(s["conditions"]["no_tool"]["turn1"]["unparsed"], {"attempted_code_execution": 1, "other_text": 1})
        self.assertIn("code attempt", analyze_v2.table(s))

    def test_bootstrap_is_seeded_and_brackets_the_mean(self):
        eps = self.full({("d1-01", "no_tool", 1): {"outcome": "wrong_value", "answer": 3.0},
                           ("d2-02", "optional_tool", 1): {"outcome": "malformed_json"}})
        s1 = analyze_v2.summarize(self.plan, self.keys, self.cases, eps, [], "dev")
        s2 = analyze_v2.summarize(self.plan, self.keys, self.cases, eps, [], "dev")
        d = s1["paired"]["all_tasks"]["optional_tool_minus_no_tool"]
        self.assertEqual(d, s2["paired"]["all_tasks"]["optional_tool_minus_no_tool"])
        self.assertLessEqual(d["bootstrap_95pct"][0], d["mean_difference"])
        self.assertGreaterEqual(d["bootstrap_95pct"][1], d["mean_difference"])
        self.assertEqual(d["bootstrap"], {"seed": analyze_v2.BOOTSTRAP_SEED, "resamples": analyze_v2.BOOTSTRAP_B, "unit": "task"})
        self.assertEqual(s1["within_task_variation"]["no_tool"], {"tasks_all_correct": 5, "tasks_all_incorrect": 1, "tasks_mixed": 0})

    def test_interrupted_attempts_are_attempted_but_not_correct(self):
        eps = [e for e in self.full() if not (e["task_id"] == "d3-02" and e["condition"] == "required_tool")]
        attempts = [{"episode_id": "x", "task_id": t, "condition": c, "rep": 1, "reserved_calls": 2}
                    for t, c in (("d3-02", "required_tool"), ("d1-01", "no_tool"))]  # the second one completed normally
        s = analyze_v2.summarize(self.plan, self.keys, self.cases, eps, attempts, "dev")
        self.assertEqual((s["attempted"], s["completed"], s["interrupted"], s["interrupted_reserved_calls"]), (18, 17, 1, 2))
        cell = s["groups"]["hard"]["conditions"]["required_tool"]
        self.assertEqual((cell["correct"], cell["outcome_counts"]), (1, {"correct": 1, "interrupted": 1}))
        self.assertEqual([r["status"] for r in s["episodes"] if r["task_id"] == "d3-02" and r["condition"] == "required_tool"], ["interrupted"])
        self.assertIn("not completed", s["stop_conditions"])

    def test_table_renders_for_empty_and_full_runs(self):
        for eps in ([], self.full()):
            s = analyze_v2.summarize(self.plan, self.keys, self.cases, eps, [], "dev")
            text = analyze_v2.table(s)
            self.assertIn("| easy (10) | no_tool |", text)
            self.assertIn("Per-task outcomes", text)

    def test_saved_episode_files_recount(self):
        for split in ("dev", "scored"):
            plan, keys, cases, episodes, attempts = analyze_v2.load(split)
            if not episodes:
                continue
            s = analyze_v2.summarize(plan, keys, cases, episodes, attempts, split)
            seen = set()
            firsts = [e for e in episodes if not (analyze_v2.key_of(e) in seen or seen.add(analyze_v2.key_of(e)))]
            for c in analyze_v2.CONDITIONS:
                recount = sum(1 for e in firsts if e["condition"] == c and e["valid"] and e["grade"]["correct"]
                              and analyze_v2.key_of(e) in {analyze_v2.key_of(p) for p in plan})
                self.assertEqual(s["conditions"][c]["correct"], recount, (split, c))
            self.assertEqual(s["model_invocations"], sum(len(e["turns"]) for e in firsts
                                                         if analyze_v2.key_of(e) in {analyze_v2.key_of(p) for p in plan}))


if __name__ == "__main__":
    unittest.main()
