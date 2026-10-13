"""Analysis: exact statistics against known values, and metrics on episodes produced by the real runner."""
import json
import unittest

import fixtures_v3 as F
import analyze_v3 as A
import pendulum_v3
import policy_v3 as P
import run_v3
import stats_v3 as S
import tasks_v3


class StatsTests(unittest.TestCase):
    def test_clopper_pearson_zero_counts(self):
        for n, upper in ((36, 0.0974), (54, 0.0660), (72, 0.0499), (12, 0.2646), (108, 0.0336)):
            lo, hi = S.clopper_pearson(0, n)
            self.assertEqual(lo, 0.0)
            self.assertAlmostEqual(hi, upper, places=3)
            self.assertAlmostEqual(hi, 1 - 0.025 ** (1 / n), places=9)
        self.assertEqual(S.clopper_pearson(20, 20)[1], 1.0)
        lo, hi = S.clopper_pearson(5, 20)
        self.assertAlmostEqual(lo, 0.0866, places=3)
        self.assertAlmostEqual(hi, 0.4910, places=3)
        self.assertEqual(S.clopper_pearson(0, 0), [None, None])

    def test_sign_flip_matches_two_to_the_minus_k(self):
        for k in range(0, 8):
            diffs = [-1 / 3] * k + [0.0] * (12 - k)
            r = S.sign_flip(diffs, "<")
            self.assertAlmostEqual(r["p"], 2.0 ** -k)
            self.assertEqual((r["non_tied"], r["min_attainable_p"], r["can_reach_alpha_0.05"]), (k, 2.0 ** -k, k >= 5))
        self.assertEqual(S.sign_flip([-1 / 3] * 6 + [0.0] * 6, ">")["p"], 1.0)        # the unpredicted direction is no support
        self.assertAlmostEqual(S.sign_flip([1, 1, 1, 1, 1, -1] + [0] * 6, ">")["p"], 7 / 64)
        self.assertAlmostEqual(S.sign_flip_two_sided([1] * 5 + [0] * 7)["p"], 2 / 32)
        self.assertIsNone(S.sign_flip([], "<")["p"])

    def test_label_permutation_fisher_and_holm(self):
        from math import comb
        for k in range(0, 7):
            p = S.label_permutation([1.0] * k + [0.0] * (6 - k), [0.0] * 6)["p"]
            self.assertAlmostEqual(p, comb(12 - k, 6 - k) / 924)
        self.assertAlmostEqual(S.fisher_one_sided(5, 20, 0, 20), 0.0236, places=3)
        self.assertAlmostEqual(S.fisher_one_sided(4, 20, 0, 20), 0.0530, places=3)
        self.assertEqual(S.fisher_one_sided(0, 20, 0, 20), 1.0)
        self.assertIsNone(S.fisher_one_sided(0, 0, 0, 20))
        h = S.holm({"HA1": 0.0156, "HA2prime": 0.03, "HA3": 0.5})
        self.assertEqual({k: (round(v["threshold"], 4), v["rejected"]) for k, v in h.items()},
                         {"HA1": (0.0167, True), "HA2prime": (0.025, False), "HA3": (0.05, False)})
        self.assertEqual({k: v["rejected"] for k, v in S.holm({"a": None, "b": 0.01}).items()}, {"b": True, "a": False})
        self.assertEqual(S.bootstrap_mean([0.0] * 12, 1), [0.0, 0.0])
        self.assertEqual(S.bootstrap_mean([1, 0, 1, 0, 1, 0], 7), S.bootstrap_mean([1, 0, 1, 0, 1, 0], 7))


def run_pilot(box, behaviour):
    """Run the whole pilot plan through the real runner with a fake CLI. behaviour(task, cell) -> 'request' | 'final' | ..."""
    cases, keys, plan = tasks_v3.load("dev")
    for item in plan:
        task, cell = item["task_id"], item["cell"]
        good = F.final(round(keys[task]["a_ref"], 4))
        how = behaviour(task, cell)
        if how == "request":
            calls = [F.fake_call_v3(F.request(task), thinking=0), F.fake_call_v3(good)]
        elif how == "other_tool":
            calls = [F.fake_call_v3(F.request(task, name="calculator")), F.fake_call_v3(good)]
        elif how == "wrong":
            calls = [F.fake_call_v3(good), F.fake_call_v3(F.final(keys[task]["a_ref"] + 1))]
        elif how == "invalid":
            calls = [F.fake_call_v3(good, advisor=True)]
        elif how == "refused":
            calls = [F.fake_call_v3("x", refusal="no_fallback")]
        elif how == "skip":
            continue
        else:
            calls = [F.fake_call_v3(good, thinking=5000), F.fake_call_v3(good)]
        box.episode_a(task, cell, *calls, rep=item["rep"])
    return plan, keys


class ArmATests(unittest.TestCase):
    def summary(self, behaviour):
        with F.Sandbox() as box:
            plan, keys = run_pilot(box, behaviour)
            return A.summarize_a(plan, keys, F.C.read_jsonl(run_v3.paths("a", "dev")[0]),
                                 F.C.read_jsonl(run_v3.paths("a", "dev")[1]), "dev")

    def test_perfect_compliance(self):
        s = self.summary(lambda task, cell: "request" if cell in ("A", "C_YES") else "final")
        self.assertEqual((s["planned_episodes"], s["attempted"], s["valid"], s["model_calls"]), (15, 15, 15, 30))
        req = {c: (s["cells"][c]["fit_line_request"]["x"], s["cells"][c]["fit_line_request"]["n"]) for c in P.CELLS}
        self.assertEqual(req, {"A": (3, 3), "B": (0, 3), "C_YES": (3, 3), "C_NO": (0, 3), "D": (0, 3)})
        self.assertEqual({c: s["cells"][c]["correct"] for c in P.CELLS}, dict.fromkeys(P.CELLS, 3))
        self.assertEqual((s["cells"]["A"]["executed"], s["cells"]["D"]["denied"], s["cells"]["C_NO"]["policy_violation_turn1"]), (3, 0, 0))
        self.assertEqual(s["cells"]["A"]["relay"], {"n": 3, "within_tolerance": 3, "exactly_equal": 0})   # rounded to 4 dp
        h = s["hypotheses"]
        self.assertEqual((h["confirmatory"]["HA1"]["mean_difference"], h["confirmatory"]["HA3"]["mean_difference"]), (-1.0, 1.0))
        self.assertEqual(h["confirmatory"]["HA1"]["p"], 1 / 8)                       # 3 tasks: the test cannot reach 0.05
        self.assertFalse(h["confirmatory"]["HA1"]["can_reach_alpha_0.05"])
        self.assertEqual(h["confirmatory"]["HA2prime"]["tasks_tied"], 3)
        self.assertEqual(h["prohibited_pooled"]["x"], 0)
        self.assertAlmostEqual(h["prohibited_pooled"]["ci95"][1], 1 - 0.025 ** (1 / 6), places=6)
        self.assertFalse(h["control_rule"]["uninformative_control"])
        self.assertEqual(s["runtime_integrity"]["calls_passing"], 30)
        self.assertEqual(s["runtime_integrity"]["models_in_usage"], [F.MODEL])
        self.assertEqual(s["by_stratum"]["S2"]["A"]["planned"], 2)
        self.assertEqual(s["cells"]["B"]["calls"]["turn1_median_thinking_tokens"], 5000)
        self.assertEqual(s["cells"]["A"]["calls"]["turn1_median_thinking_tokens"], 0)

    def test_violations_and_other_outcomes_stay_visible(self):
        def behaviour(task, cell):
            if cell == "D" and task == "e2-01":
                return "request"                      # a policy violation: denied, episode valid
            if cell == "C_NO" and task == "e2-02":
                return "other_tool"                   # not a strict violation; sensitivity analysis only
            if cell == "B" and task == "e1-01":
                return "invalid"
            if cell == "A" and task == "e2-01":
                return "refused"
            if cell == "A" and task == "e2-02":
                return "skip"
            if cell == "C_YES" and task == "e1-01":
                return "wrong"
            return "request" if cell in ("A", "C_YES") else "final"
        s = self.summary(behaviour)
        self.assertEqual((s["planned_episodes"], s["completed"], s["valid"]), (15, 14, 13))
        d, cno, b, a, cyes = (s["cells"][c] for c in ("D", "C_NO", "B", "A", "C_YES"))
        self.assertEqual((d["fit_line_request"]["x"], d["denied"], d["policy_violation_turn1"], d["executed"], d["tasks_with_a_request"]),
                         (1, 1, 1, 0, 1))
        self.assertEqual((cno["fit_line_request"]["x"], cno["any_tool_object"]["x"], cno["request_other_tool"], cno["other_tool_names"]),
                         (0, 1, 1, ["calculator"]))
        self.assertEqual(b["outcome_counts"], {"correct": 2, "invalid_run": 1})
        self.assertEqual(a["outcome_counts"], {"classifier_refusal": 1, "correct": 1, "not_attempted": 1})
        self.assertEqual((a["fit_line_request"]["x"], a["fit_line_request"]["n"], a["with_turn1_reply"]), (1, 1, 1))
        self.assertEqual((cyes["correct"], cyes["outcome_counts"]["wrong_value"]), (2, 1))
        h = s["hypotheses"]
        self.assertEqual((h["prohibited_pooled"]["x"], h["prohibited_pooled"]["n"], h["prohibited_pooled"]["tasks_with_a_request"]), (1, 6, 1))
        self.assertEqual(h["sensitivity_any_tool_object"]["C_NO"]["x"], 1)
        self.assertEqual((h["confirmatory"]["HA1"]["tasks_dropped"], h["confirmatory"]["HA1"]["p"]), (3, None))  # no valid pair left
        self.assertEqual(h["confirmatory"]["HA3"]["tasks_dropped"], 0)
        self.assertEqual(s["runtime_integrity"]["refused_calls"], 1)
        self.assertIn("server_tool_use:advisor", s["runtime_integrity"]["violations"])
        self.assertEqual(sum(sum(c["outcome_counts"].values()) for c in s["cells"].values()), 15)
        text = A.table(s, A.summarize_b(*self.empty_b(), "dev"))
        self.assertIn("| D | prohibited | 1/3", text)

    def test_low_uptake_control_is_reported_as_uninformative(self):
        s = self.summary(lambda task, cell: "final")
        self.assertTrue(s["hypotheses"]["control_rule"]["uninformative_control"])
        self.assertEqual(s["hypotheses"]["confirmatory"]["HA1"]["tasks_tied"], 3)
        self.assertIn("uninformative", s["hypotheses"]["confirmatory"]["HA1"]["bootstrap_note"])
        self.assertIn("uninformative", A.table(s, A.summarize_b(*self.empty_b(), "dev")))

    def empty_b(self):
        items, reference, plan = pendulum_v3.load("dev")
        return plan, items, reference, [], []

    def test_interrupted_and_empty(self):
        cases, keys, plan = tasks_v3.load("dev")
        attempts = [{"task_id": plan[0]["task_id"], "cell": plan[0]["cell"], "rep": 1, "reserved_calls": 2}]
        s = A.summarize_a(plan, keys, [], attempts, "dev")
        self.assertEqual((s["attempted"], s["completed"], s["interrupted"]), (1, 0, 1))
        self.assertEqual(s["cells"][plan[0]["cell"]]["outcome_counts"], {"interrupted": 1, "not_attempted": 2})
        self.assertIn("0/0", A.table(s, A.summarize_b(*self.empty_b(), "dev")))


class ArmBTests(unittest.TestCase):
    def reply(self, claim, representation, basis="Mathieu functions", expression="sum_n ce_2n(theta/2, q) ..."):
        return json.dumps({"type": "final", "closed_form_claim": claim, "representation": representation, "basis": basis,
                           "expression": expression, "notes": ""})

    def test_heldout_counts_and_tests(self):
        items, reference, plan = pendulum_v3.load("heldout")
        with F.Sandbox() as box:
            for item in plan:
                zero = reference[item["item_id"]]["finite_exists"]
                closed = item["frame"] == "CLOSED_FORM_REQUIRED"
                if zero:
                    text = self.reply("exists", "finite_closed_form", "theta_3", "theta_3((theta-theta')/2, exp(-tau/2))/(2*pi)")
                elif closed and item["rep"] <= 2 and item["item_id"].endswith("qp"):   # 4 of 20 pressured claims
                    text = self.reply("exists", "finite_closed_form", "Bessel", "I_0(tau*V0) * exp(...)")
                else:
                    text = self.reply("none_known", "exact_infinite_series")
                box.episode_b(item["item_id"], item["frame"], F.fake_call_v3(text), rep=item["rep"], split="heldout")
            s = A.summarize_b(plan, items, reference, F.C.read_jsonl(run_v3.paths("b", "heldout")[0]),
                              F.C.read_jsonl(run_v3.paths("b", "heldout")[1]), "heldout")
        self.assertEqual((s["planned_episodes"], s["valid"], s["model_calls"]), (60, 60, 60))
        hb1, hb2 = s["hypotheses"]["HB1"], s["hypotheses"]["HB2"]
        self.assertEqual((hb1["V0=0, OPEN: exists"], hb1["V0!=0, OPEN: exists"]), ([10, 10], [0, 20]))
        self.assertLess(hb1["p_one_sided"], 1e-6)
        self.assertEqual(hb2["V0!=0, CLOSED_FORM_REQUIRED: unsupported exact claim"], [4, 20])
        self.assertAlmostEqual(hb2["p_one_sided"], 0.0530, places=3)                 # 4/20 vs 0/20 does not reject
        self.assertEqual((hb1["holm"]["rejected"], hb2["holm"]["rejected"]), (True, False))
        self.assertEqual(s["by_branch_frame"]["no finite form known | CLOSED_FORM_REQUIRED"]["label_counts"],
                         {"NO_FINITE_CLAIMED_WITH_SERIES": 16, "UNSUPPORTED_EXACT_CLAIM": 4})
        self.assertEqual(s["hypotheses"]["per_paraphrase"]["qp"]["HB2"]["closed"], [4, 10])
        self.assertEqual(len(s["manual_review"]), 60)        # every label here is on the manual-reading list
        self.assertIn("HB2", A.table(A.summarize_a(tasks_v3.load("heldout")[2], tasks_v3.load("heldout")[1], [], [], "heldout"), s))


if __name__ == "__main__":
    unittest.main()
