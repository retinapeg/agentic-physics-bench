"""Deterministic analysis of the saved V2 episodes (no model calls).

Usage (repo root): python3 src/analyze_v2.py [dev|scored]
Writes results/v2/summary_<split>.json and results/v2/summary_<split>.md.
Written by Claude at Leo's direction (2026-09-23).

Every count is computed from the episode file against the plan, so unattempted,
invalid and duplicate episodes stay visible. Repeated calls on one task are
clustered observations: condition differences are task-level paired differences
of per-task proportions, with a seeded cluster bootstrap over tasks.
"""
import json
import random
import statistics
import sys
from pathlib import Path

import tasks_v2
from tasks import ls_slope

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "v2"
RESULTS = ROOT / "results" / "v2"
CONDITIONS = tasks_v2.CONDITIONS
GROUPS = tasks_v2.GROUP_ORDER
PAIRS = (("optional_tool", "no_tool"), ("required_tool", "no_tool"), ("required_tool", "optional_tool"))
BOOTSTRAP_SEED = 20260923
BOOTSTRAP_B = 2000
TOL = 0.01


def load(split):
    plan = json.loads((DATA / f"{split}_plan.json").read_text())
    keys = {k["id"]: k for k in map(json.loads, (DATA / f"{split}_keys.jsonl").read_text().splitlines())}
    cases = {c["id"]: c for c in map(json.loads, (DATA / f"{split}_tasks.jsonl").read_text().splitlines())}
    path = RESULTS / f"episodes_{split}.jsonl"
    episodes = [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []
    apath = RESULTS / f"attempts_{split}.jsonl"
    attempts = [json.loads(l) for l in apath.read_text().splitlines()] if apath.exists() else []
    return plan, keys, cases, episodes, attempts


def key_of(x):
    return (x["task_id"], x["condition"], x["rep"])


def median(xs):
    return statistics.median(xs) if xs else None


CODE_MARKERS = ("```", "<invoke", "python3", "import ", "#!/", "\"command\"")


def unparsed_kind(text):
    """Heuristic label for a turn-1 reply that did not parse: an attempt to run code (the model reaching
    for a code tool it does not have) or something else. Recorded separately from the strict outcome."""
    if text is None:
        return "no_text"
    return "attempted_code_execution" if any(m in text for m in CODE_MARKERS) else "other_text"


def cell_summary(cells, by, status, condition):
    """Counts for a set of planned (task, condition, rep) cells."""
    outcomes = [status[c] for c in cells]
    eps = [by[c] for c in cells if c in by]
    valid = [e for e in eps if e["valid"]]
    errs = [e["grade"]["abs_error"] for e in valid
            if e["grade"]["abs_error"] is not None and e["grade"]["outcome"] != "wrong_units"]
    turns = [t for e in eps for t in e["turns"]]
    executed = [e for e in valid if e["tool"]["executed"]]
    relay = [abs(e["parsed"]["acceleration"] - e["tool"]["result"]["slope"]) for e in executed if e["parsed"]]
    t1 = [e for e in valid if e["turn1"]["kind"] == "final"]
    out = {
        "correct": outcomes.count("correct"), "of_planned": len(cells),
        "proportion": outcomes.count("correct") / len(cells) if cells else None,
        "attempted": len(eps), "valid": len(valid),
        "outcome_counts": {o: outcomes.count(o) for o in sorted(set(outcomes))},
        "abs_error_m_per_s2": {"n_parseable_with_units": len(errs), "median": median(errs),
                               "max": max(errs) if errs else None},
        "tool": {"requested": sum(e["tool"]["requested"] for e in valid),
                 "valid_request": sum(e["tool"]["valid"] is True for e in valid),
                 "executed": len(executed),
                 "invalid_request_errors": sorted(e["tool"]["validation_error"] for e in valid
                                                  if e["tool"]["requested"] and e["tool"]["valid"] is not True),
                 "relay": {"n": len(relay), "faithful_within_tol": sum(r <= TOL for r in relay),
                           "max_abs_diff": max(relay) if relay else None}},
        "turn1": {"final_answers": len(t1),
                  "correct": sum(bool(e["turn1"]["grade"] and e["turn1"]["grade"]["correct"]) for e in t1),
                  "revised_at_turn2": sum(1 for e in t1 if e["parsed"] and
                                          e["parsed"]["acceleration"] != e["turn1"]["answer"]["acceleration"]),
                  "unparsed": {k: sum(1 for e in valid if e["turn1"]["kind"] is None and e["turn1"]["error"] != "missing_output"
                                      and unparsed_kind(e["turns"][0].get("response_text")) == k)
                               for k in ("attempted_code_execution", "other_text")}},
        "calls": {"model_calls": sum(e["model_calls"] for e in eps),
                  "timeouts": sum(1 for t in turns if t.get("timed_out")),
                  "median_elapsed_s_per_call": median([t["elapsed_s"] for t in turns]),
                  "median_output_tokens": median([t["cli"]["result"]["output_tokens"] for t in turns
                                                  if t["cli"]["result"] and t["cli"]["result"]["output_tokens"] is not None]),
                  "median_thinking_tokens": median([t["cli"]["thinking_tokens"] for t in turns
                                                    if t["cli"].get("thinking_tokens") is not None])},
    }
    if condition == "required_tool":
        out["required_compliant"] = sum(e["required_compliant"] is True for e in valid)
        out["required_compliant_of_valid"] = sum(e["required_compliant"] is not None for e in valid)  # turn 1 replied
    return out


def task_proportions(task_ids, reps, status):
    """p[task][condition] = correct / planned reps (missing or invalid count as not correct)."""
    return {t: {c: sum(status[(t, c, r)] == "correct" for r in reps) / len(reps) for c in CONDITIONS}
            for t in task_ids}


def paired(task_ids, p, c1, c2, rng_seed=BOOTSTRAP_SEED, b=BOOTSTRAP_B):
    """Task-level paired difference of proportions, c1 - c2, with a cluster bootstrap over tasks."""
    d = [p[t][c1] - p[t][c2] for t in task_ids]
    if not d:
        return None
    rng = random.Random(rng_seed)
    boots = []
    for _ in range(b):
        sample = [d[rng.randrange(len(d))] for _ in d]
        boots.append(sum(sample) / len(sample))
    boots.sort()
    lo, hi = boots[int(0.025 * b)], boots[int(0.975 * b) - 1]
    return {"n_tasks": len(d), "mean_difference": sum(d) / len(d),
            "tasks_favouring_first": sum(x > 0 for x in d), "tasks_favouring_second": sum(x < 0 for x in d),
            "tasks_tied": sum(x == 0 for x in d),
            "bootstrap_95pct": [lo, hi], "bootstrap": {"seed": rng_seed, "resamples": b, "unit": "task"}}


def summarize(plan, keys, cases, episodes, attempts, split):
    by = {}
    duplicates = 0
    for e in episodes:
        if key_of(e) in by:
            duplicates += 1  # append-only files never overwrite; a repeat is reported, and the first record counts
            continue
        by[key_of(e)] = e
    planned = [key_of(p) for p in plan]
    unplanned = sum(1 for k in by if k not in set(planned))
    interrupted = {key_of(a) for a in attempts if key_of(a) not in by}  # started, never completed: attempted, not correct
    status = {c: ("invalid_run" if not by[c]["valid"] else by[c]["grade"]["outcome"]) if c in by
              else ("interrupted" if c in interrupted else "not_attempted") for c in planned}
    task_ids = sorted({p["task_id"] for p in plan})
    reps = sorted({p["rep"] for p in plan})
    group = {t: keys[t]["group"] for t in task_ids}

    out = {"split": split, "run_ids": sorted({e.get("run_id") for e in episodes}),
           "planned_episodes": len(planned), "attempted": sum(c in by or c in interrupted for c in planned),
           "completed": sum(c in by for c in planned), "interrupted": sum(c in interrupted for c in planned),
           "valid": sum(1 for c in planned if c in by and by[c]["valid"]),
           "model_invocations": sum(by[c]["model_calls"] for c in planned if c in by),
           "interrupted_reserved_calls": sum(a["reserved_calls"] for a in attempts if key_of(a) in interrupted),
           "duplicate_records": duplicates, "unplanned_records": unplanned,
           "stop_conditions": "none: all planned episodes completed" if all(c in by for c in planned)
           else f"{sum(c not in by for c in planned)} planned episodes not completed",
           "tolerance_m_per_s2": TOL, "tasks": len(task_ids), "reps": len(reps), "groups": {}, "conditions": {}}
    for g in GROUPS:
        out["groups"][g] = {"n_tasks": sum(group[t] == g for t in task_ids), "parameters": tasks_v2.GROUPS[g],
                            "conditions": {c: cell_summary([x for x in planned if group[x[0]] == g and x[1] == c],
                                                           by, status, c) for c in CONDITIONS}}
    for c in CONDITIONS:
        out["conditions"][c] = cell_summary([x for x in planned if x[1] == c], by, status, c)

    p = task_proportions(task_ids, reps, status)
    out["paired"] = {"all_tasks": {f"{a}_minus_{b}": paired(task_ids, p, a, b) for a, b in PAIRS},
                     "by_group": {g: {f"{a}_minus_{b}": paired([t for t in task_ids if group[t] == g], p, a, b)
                                      for a, b in PAIRS} for g in GROUPS}}
    out["within_task_variation"] = {
        c: {"tasks_all_correct": sum(p[t][c] == 1.0 for t in task_ids),
            "tasks_all_incorrect": sum(p[t][c] == 0.0 for t in task_ids),
            "tasks_mixed": sum(0.0 < p[t][c] < 1.0 for t in task_ids)} for c in CONDITIONS}

    valid_tool = [by[c] for c in planned if c in by and by[c]["valid"] and c[1] != "no_tool"]
    executed = [e for e in valid_tool if e["tool"]["executed"]]
    out["tool_failure_taxonomy"] = {
        "malformed_or_invalid_request": sum(e["tool"]["requested"] and e["tool"]["valid"] is not True for e in valid_tool),
        "execution_failure": sum(e["tool"]["valid"] is True and not e["tool"]["executed"] for e in valid_tool),
        "executed_then_no_parseable_answer": sum(e["parsed"] is None for e in executed),
        "executed_then_wrong_units": sum(e["grade"]["outcome"] == "wrong_units" for e in executed),
        "executed_then_wrong_value": sum(e["grade"]["outcome"] == "wrong_value" for e in executed),
        "executed_then_correct": sum(e["grade"]["outcome"] == "correct" for e in executed),
        "required_noncompliant": sum(e["condition"] == "required_tool" and e["required_compliant"] is False
                                     for e in valid_tool),  # turn 1 replied with something other than a valid request
        "note": "One tool exists, so 'bad tool selection' can only appear as unknown_tool in the invalid requests.",
    }
    det = [abs(ls_slope([float(x) for x in cases[t]["t_s"]], [float(x) for x in cases[t]["v_m_per_s"]]) - keys[t]["a_ref"])
           for t in task_ids]
    out["deterministic_solver"] = {"correct": sum(e <= TOL for e in det), "of_tasks": len(task_ids),
                                   "max_abs_error": max(det) if det else None}
    out["task_table"] = [{"task_id": t, "group": group[t], "a_ref": keys[t]["a_ref"], "n_points": keys[t]["n_points"],
                          "proportion_correct": p[t],
                          "tool_requested": {c: sum(1 for r in reps if (t, c, r) in by and by[(t, c, r)]["tool"]["requested"])
                                             for c in CONDITIONS}} for t in task_ids]
    out["episodes"] = [{"task_id": c[0], "group": group[c[0]], "condition": c[1], "rep": c[2], "status": status[c],
                        "answer": (by[c]["parsed"] or {}).get("acceleration") if c in by else None,
                        "a_ref": keys[c[0]]["a_ref"], "abs_error": by[c]["grade"]["abs_error"] if c in by else None,
                        "turn1_kind": by[c]["turn1"]["kind"] if c in by else None,
                        "tool_requested": bool(c in by and by[c]["tool"]["requested"]),
                        "tool_executed": bool(c in by and (by[c]["tool"]["executed"] or by[c]["tool_executions"])),
                        "required_compliant": by[c]["required_compliant"] if c in by else None,
                        "model_calls": by[c]["model_calls"] if c in by else 0,
                        "elapsed_s": round(sum(t["elapsed_s"] for t in by[c]["turns"]), 1) if c in by else None,
                        "thinking_tokens": sum(t["cli"].get("thinking_tokens") or 0 for t in by[c]["turns"]) if c in by else None,
                        "episode_id": by[c]["episode_id"] if c in by else None} for c in planned]
    return out


def fmt(x, nd=4):
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def table(s):
    L = [f"# V2 results ({s['split']} split): table view", "",
         f"Generated by `src/analyze_v2.py` from `results/v2/episodes_{s['split']}.jsonl`. Units: m/s². Tolerance ±{s['tolerance_m_per_s2']}.",
         f"Planned {s['planned_episodes']} episodes; attempted {s['attempted']} (completed {s['completed']}, interrupted {s['interrupted']}); "
         f"valid {s['valid']}; {s['model_invocations']} model invocations; duplicates {s['duplicate_records']}; unplanned {s['unplanned_records']}. "
         f"Stop conditions: {s['stop_conditions']}.", "",
         "## Correctness by difficulty group and condition", "",
         "| Group (n points) | Condition | Correct | Tool requested / valid / executed | Required compliant (of turn-1 replies) | Median \\|error\\| | Timeouts | Median thinking tokens / call | Median s / call |",
         "|---|---|---|---|---|---|---|---|---|"]
    for g in GROUPS:
        for c in CONDITIONS:
            x = s["groups"][g]["conditions"][c]
            tl = x["tool"]
            comp = f"{x['required_compliant']}/{x['required_compliant_of_valid']}" if c == "required_tool" else "—"
            L.append(f"| {g} ({s['groups'][g]['parameters']['n']}) | {c} | **{x['correct']}/{x['of_planned']}** | "
                     f"{tl['requested']} / {tl['valid_request']} / {tl['executed']} | {comp} | "
                     f"{fmt(x['abs_error_m_per_s2']['median'])} (n={x['abs_error_m_per_s2']['n_parseable_with_units']}) | "
                     f"{x['calls']['timeouts']} | {fmt(x['calls']['median_thinking_tokens'], 0)} | {fmt(x['calls']['median_elapsed_s_per_call'], 1)} |")
    L += ["", "| All groups | Condition | Correct | Tool requested / valid / executed | Required compliant | Turn-1 final answers correct | Revised at turn 2 | Turn-1 unparsed: code attempt / other |", "|---|---|---|---|---|---|---|---|"]
    for c in CONDITIONS:
        x = s["conditions"][c]
        comp = f"{x['required_compliant']}/{x['required_compliant_of_valid']}" if c == "required_tool" else "—"
        u = x["turn1"]["unparsed"]
        L.append(f"| all | {c} | **{x['correct']}/{x['of_planned']}** | {x['tool']['requested']} / {x['tool']['valid_request']} / "
                 f"{x['tool']['executed']} | {comp} | {x['turn1']['correct']}/{x['turn1']['final_answers']} | {x['turn1']['revised_at_turn2']} | "
                 f"{u['attempted_code_execution']} / {u['other_text']} |")
    L += ["", "## Paired differences (task-level proportions over repetitions; cluster bootstrap over tasks, seed "
          f"{BOOTSTRAP_SEED}, {BOOTSTRAP_B} resamples)", "",
          "| Tasks | Comparison | Mean difference | Tasks favouring first / second / tied | Bootstrap 95% interval |", "|---|---|---|---|---|"]
    for scope, block in [("all", s["paired"]["all_tasks"])] + [(g, s["paired"]["by_group"][g]) for g in GROUPS]:
        for name, d in block.items():
            if d:
                L.append(f"| {scope} ({d['n_tasks']}) | {name.replace('_minus_', ' − ')} | {d['mean_difference']:+.3f} | "
                         f"{d['tasks_favouring_first']} / {d['tasks_favouring_second']} / {d['tasks_tied']} | "
                         f"[{d['bootstrap_95pct'][0]:+.3f}, {d['bootstrap_95pct'][1]:+.3f}] |")
    L += ["", "## Tool-use failure taxonomy (tool conditions, valid episodes)", ""]
    L += [f"- {k.replace('_', ' ')}: {v}" for k, v in s["tool_failure_taxonomy"].items() if k != "note"]
    L += ["", f"Deterministic least-squares solver: {s['deterministic_solver']['correct']}/{s['deterministic_solver']['of_tasks']} "
          f"tasks, max |error| {fmt(s['deterministic_solver']['max_abs_error'], 2)}.", "",
          "## Per-task outcomes (proportion of repetitions correct; tool requests in brackets)", "",
          "| Task | Group | n | a_ref | no_tool | optional_tool | required_tool |", "|---|---|---|---|---|---|---|"]
    for t in s["task_table"]:
        cells = [f"{t['proportion_correct'][c]:.2f} [{t['tool_requested'][c]}]" for c in CONDITIONS]
        L.append(f"| {t['task_id']} | {t['group']} | {t['n_points']} | {t['a_ref']:.4f} | " + " | ".join(cells) + " |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    split = sys.argv[1] if len(sys.argv) > 1 else "scored"
    s = summarize(*load(split), split)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"summary_{split}.json").write_text(json.dumps(s, indent=1) + "\n")
    (RESULTS / f"summary_{split}.md").write_text(table(s))
    print(json.dumps({k: v for k, v in s.items() if k not in ("episodes", "task_table", "groups")}, indent=1))
