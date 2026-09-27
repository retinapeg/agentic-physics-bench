"""Recompute the study's headline numbers from the committed result files and compare each one with the
value the README publishes (no model calls; standard library only).

Usage (repo root): python3 src/headline_results.py
Prints one row per claim (recomputed value, published value, source) and exits 1 if any differ.

V1 and V2 counts come from the same summarize() functions that write the committed summaries
(src/analyze.py, src/analyze_v2.py). Per-call trace checks reuse the V2 runner's own control logic
(run_v2.v2_control_violations, and run_v2.summarize_call for raw traces).

The second-model finding in V2 development stages 1-2 is recounted from the committed audit files, whose
episodes are cross-checked against the archived stage records. The raw CLI traces behind those audits are
gitignored (they carry session metadata), so when results/raw/ is absent the raw re-derivation is skipped
and reported as skipped, not as passed.
"""
import json
import sys
from pathlib import Path

import analyze
import analyze_v2
import run_v2

ROOT = Path(__file__).resolve().parents[1]
V1_EPISODES = ROOT / "results" / "episodes_scored.jsonl"
V2 = ROOT / "results" / "v2"
STAGE = {n: V2 / f"dev_stage{n}" for n in (1, 2, 3)}
AUDITS = {n: STAGE[n] / "advisor_audit.json" for n in (1, 2)}

# (key, claim, published value, source). Every number in the README's key findings and results tables.
CLAIMS = [
    ("v1_valid", "V1 scored episodes: valid / planned", "24/24", "results/episodes_scored.jsonl"),
    ("v1_calls", "V1 scored model calls", "24", "results/episodes_scored.jsonl"),
    ("v1_direct", "V1 correct, direct answer", "12/12", "results/episodes_scored.jsonl"),
    ("v1_optional", "V1 correct, optional fit_line workflow", "12/12", "results/episodes_scored.jsonl"),
    ("v1_requested", "V1 optional fit_line requested", "0/12", "results/episodes_scored.jsonl"),
    ("v2_valid", "V2 scored episodes: valid / planned (18 tasks x 3 conditions x 3 repetitions)", "162/162",
     "results/v2/episodes_scored.jsonl"),
    ("v2_calls", "V2 scored model calls", "324", "results/v2/episodes_scored.jsonl"),
    ("v2_no_tool", "V2 correct, no tool", "54/54", "results/v2/episodes_scored.jsonl"),
    ("v2_optional", "V2 correct, optional tool", "54/54", "results/v2/episodes_scored.jsonl"),
    ("v2_required", "V2 correct, required tool", "54/54", "results/v2/episodes_scored.jsonl"),
    ("v2_requested", "V2 optional tool requested", "54/54", "results/v2/episodes_scored.jsonl"),
    ("v2_compliant", "V2 required-tool compliance", "54/54", "results/v2/episodes_scored.jsonl"),
    ("v2_relay", "V2 executed tool results relayed within tolerance", "108/108", "results/v2/episodes_scored.jsonl"),
    ("v2_ties", "V2 tasks tied in each paired comparison (opt-none, req-none, req-opt)", "18/18, 18/18, 18/18",
     "results/v2/episodes_scored.jsonl"),
    ("v2_mixed", "V2 tasks with mixed outcomes over repetitions (none, opt, req)", "0, 0, 0",
     "results/v2/episodes_scored.jsonl"),
    ("v2_turn1", "V2 no-tool first-turn answers correct", "53/54", "results/v2/episodes_scored.jsonl"),
    ("v2_thinking", "V2 no-tool median reported thinking tokens per call (easy, moderate, hard)",
     "621, 2298, 5314", "results/v2/episodes_scored.jsonl"),
    ("v2_latency", "V2 median s per call: no tool by group (easy, moderate, hard); optional; required",
     "10, 26, 55; 5; 5", "results/v2/episodes_scored.jsonl"),
    ("v2_single_model", "V2 scored calls: claude-opus-5 only, no server-side tool", "324/324",
     "results/v2/episodes_scored.jsonl (per-call cli.models_used, server_tool_uses, iteration_types)"),
    ("dev_calls", "V2 development calls in committed records (stages 1-4, unique); +2 (smoke, probe) outside the repo",
     "96", "results/v2/dev_stage{1,2,3}/episodes_dev.jsonl, results/v2/episodes_dev.jsonl"),
    ("dev_second_model", "V2 dev stages 1-2: calls in which a second model ran (unique calls)", "31/48",
     "results/v2/dev_stage{1,2}/advisor_audit.json"),
    ("dev_second_model_eps", "V2 dev stages 1-2: episodes with at least one such call (unique)", "21/24",
     "results/v2/dev_stage{1,2}/advisor_audit.json"),
    ("dev_stage_counts", "V2 dev stage 1; stage 2 (12 of stage 2's records were carried over from stage 1)",
     "24/36; 25/36", "results/v2/dev_stage{1,2}/advisor_audit.json"),
    ("dev_clean", "V2 dev stages 3-4: calls with claude-opus-5 only, no server-side tool", "48/48",
     "results/v2/dev_stage3/episodes_dev.jsonl, results/v2/episodes_dev.jsonl"),
    ("dev_stage3_no_tool", "V2 dev stage 3 (earlier wording), no tool correct (easy, moderate, hard)",
     "2/2, 1/2, 0/2", "results/v2/dev_stage3/episodes_dev.jsonl"),
    ("dev_stage3_code", "V2 dev stage 3, moderate and hard no-tool turn-1 replies that attempted code", "4/4",
     "results/v2/dev_stage3/episodes_dev.jsonl"),
    ("dev_final_no_tool", "V2 dev final wording (stage 4), no tool correct", "6/6", "results/v2/episodes_dev.jsonl"),
]
# Re-derived from the gitignored raw CLI traces when they are present (results/raw/).
RAW_CLAIMS = [
    ("raw_dev_second_model", "Raw traces, V2 dev stages 1-2: calls in which a second model ran", "31/48"),
    ("raw_dev_agree", "Raw traces agree call by call with the committed audit files", "48/48"),
    ("raw_dev_clean", "Raw traces, V2 dev stages 3-4: claude-opus-5 only, no server-side tool", "48/48"),
    ("raw_v2_clean", "Raw traces, V2 scored: claude-opus-5 only, no server-side tool", "324/324"),
    ("raw_v1_clean", "Raw traces, V1 scored: claude-opus-5 only, no server-side tool", "24/24"),
]


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_dev_stage(folder):
    """The plan, keys, tasks, episodes and attempts of an archived development stage (analyze_v2.load's layout)."""
    attempts = folder / "attempts_dev.jsonl"
    return (json.loads((folder / "dev_plan.json").read_text()), {k["id"]: k for k in rows(folder / "dev_keys.jsonl")},
            {c["id"]: c for c in rows(folder / "dev_tasks.jsonl")}, rows(folder / "episodes_dev.jsonl"),
            rows(attempts) if attempts.exists() else [])


def trace_flags(cli_summary):
    """V2's per-call trace checks (server-side tool, second model, non-message iteration), CLI version aside."""
    return [v for v in run_v2.v2_control_violations(cli_summary, None) if not v.startswith("cli_version")]


def unique_calls(*episode_files):
    """{(episode_id, turn): turn record} over several episode files; a carried-over record counts once."""
    calls = {}
    for path in episode_files:
        for e in rows(path):
            for t in e["turns"]:
                calls.setdefault((e["episode_id"], t["turn"]), t)
    return calls


def audited_calls():
    """{(episode_id, turn): second model ran} over the stage-1 and stage-2 audits, checked against the stage records."""
    out, per_stage = {}, []
    for n, path in AUDITS.items():
        audit = json.loads(path.read_text())
        records = {e["episode_id"]: e for e in rows(STAGE[n] / "episodes_dev.jsonl")}
        flagged = 0
        for ep in audit["episodes"]:
            record = records.get(ep["episode_id"])
            if record is None or [t["turn"] for t in record["turns"]] != [c["turn"] for c in ep["calls"]]:
                raise SystemExit(f"{path}: {ep['episode_id']} does not match the stage-{n} episode records")
            for c in ep["calls"]:
                ran = bool(c["server_tool_uses"]) or any(m != run_v2.models.CLAUDE_MODEL for m in c["models_used"])
                if out.setdefault((ep["episode_id"], c["turn"]), ran) != ran:
                    raise SystemExit(f"stages disagree on {ep['episode_id']} turn {c['turn']}")
                flagged += ran
        if (flagged, sum(len(e["calls"]) for e in audit["episodes"])) != (audit["calls_with_advisor"], audit["of_calls"]):
            raise SystemExit(f"{path}: its totals do not match its own episode list")
        per_stage.append(f"{flagged}/{audit['of_calls']}")
    return out, per_stage


def committed():
    """Every claim in CLAIMS, recomputed from committed files only."""
    got = {}
    v1 = analyze.summarize(*analyze.load())
    d, w = v1["conditions"]["direct"], v1["conditions"]["workflow"]
    got["v1_valid"] = f"{v1['valid']}/{v1['planned_episodes']}"
    got["v1_calls"] = str(v1["model_invocations"])
    got["v1_direct"] = f"{d['correct']}/{d['of_planned_cases']}"
    got["v1_optional"] = f"{w['correct']}/{w['of_planned_cases']}"
    got["v1_requested"] = f"{w['tool_requested']}/{w['of_planned_cases']}"

    s = analyze_v2.summarize(*analyze_v2.load("scored"), "scored")
    c = s["conditions"]
    got["v2_valid"] = f"{s['valid']}/{s['planned_episodes']}"
    got["v2_calls"] = str(s["model_invocations"])
    for key, cond in (("v2_no_tool", "no_tool"), ("v2_optional", "optional_tool"), ("v2_required", "required_tool")):
        got[key] = f"{c[cond]['correct']}/{c[cond]['of_planned']}"
    got["v2_requested"] = f"{c['optional_tool']['tool']['requested']}/{c['optional_tool']['valid']}"
    got["v2_compliant"] = f"{c['required_tool']['required_compliant']}/{c['required_tool']['valid']}"
    relay = [c[k]["tool"]["relay"] for k in ("optional_tool", "required_tool")]
    got["v2_relay"] = f"{sum(r['faithful_within_tol'] for r in relay)}/{sum(c[k]['tool']['executed'] for k in ('optional_tool', 'required_tool'))}"
    got["v2_ties"] = ", ".join(f"{p['tasks_tied']}/{p['n_tasks']}" for p in s["paired"]["all_tasks"].values())
    got["v2_mixed"] = ", ".join(str(s["within_task_variation"][k]["tasks_mixed"]) for k in analyze_v2.CONDITIONS)
    t1 = c["no_tool"]["turn1"]
    got["v2_turn1"] = f"{t1['correct']}/{c['no_tool']['valid']}"
    groups = [s["groups"][g]["conditions"] for g in analyze_v2.GROUPS]
    got["v2_thinking"] = ", ".join(f"{g['no_tool']['calls']['median_thinking_tokens']:.0f}" for g in groups)
    got["v2_latency"] = (", ".join(f"{g['no_tool']['calls']['median_elapsed_s_per_call']:.0f}" for g in groups) + "; "
                         + "; ".join(f"{c[k]['calls']['median_elapsed_s_per_call']:.0f}" for k in ("optional_tool", "required_tool")))
    scored_calls = unique_calls(V2 / "episodes_scored.jsonl")
    got["v2_single_model"] = f"{sum(not trace_flags(t['cli']) for t in scored_calls.values())}/{len(scored_calls)}"

    dev_files = [STAGE[1] / "episodes_dev.jsonl", STAGE[2] / "episodes_dev.jsonl", STAGE[3] / "episodes_dev.jsonl",
                 V2 / "episodes_dev.jsonl"]
    got["dev_calls"] = str(len(unique_calls(*dev_files)))
    audit, per_stage = audited_calls()
    if set(audit) != set(unique_calls(*dev_files[:2])):
        raise SystemExit("the audits do not cover exactly the stage-1 and stage-2 calls")
    got["dev_second_model"] = f"{sum(audit.values())}/{len(audit)}"
    episodes = {eid for eid, _ in audit}
    got["dev_second_model_eps"] = f"{sum(any(audit[k] for k in audit if k[0] == e) for e in episodes)}/{len(episodes)}"
    got["dev_stage_counts"] = "; ".join(per_stage)
    clean = unique_calls(*dev_files[2:])
    got["dev_clean"] = f"{sum(not trace_flags(t['cli']) for t in clean.values())}/{len(clean)}"
    st3 = analyze_v2.summarize(*load_dev_stage(STAGE[3]), "dev")
    got["dev_stage3_no_tool"] = ", ".join(f"{st3['groups'][g]['conditions']['no_tool']['correct']}/"
                                          f"{st3['groups'][g]['conditions']['no_tool']['of_planned']}"
                                          for g in analyze_v2.GROUPS)
    hard = [st3["groups"][g]["conditions"]["no_tool"] for g in ("moderate", "hard")]
    got["dev_stage3_code"] = f"{sum(h['turn1']['unparsed']['attempted_code_execution'] for h in hard)}/{sum(h['valid'] for h in hard)}"
    final = analyze_v2.summarize(*analyze_v2.load("dev"), "dev")["conditions"]["no_tool"]
    got["dev_final_no_tool"] = f"{final['correct']}/{final['of_planned']}"
    return got


def from_raw():
    """RAW_CLAIMS re-derived from the raw CLI traces, or None if any referenced trace is missing."""
    def flagged(turn):
        path = ROOT / turn["raw_trace"]
        return None if not path.exists() else bool(trace_flags(run_v2.summarize_call(json.loads(path.read_text()))))

    audit, _ = audited_calls()
    stage12 = unique_calls(STAGE[1] / "episodes_dev.jsonl", STAGE[2] / "episodes_dev.jsonl")
    groups = {"dev12": stage12,
              "dev34": unique_calls(STAGE[3] / "episodes_dev.jsonl", V2 / "episodes_dev.jsonl"),
              "v2": unique_calls(V2 / "episodes_scored.jsonl"),
              "v1": {(e["episode_id"], t["turn"]): t for e in rows(V1_EPISODES)
                     for t in e["turns"]}}
    flags = {name: {k: flagged(t) for k, t in calls.items()} for name, calls in groups.items()}
    if any(v is None for f in flags.values() for v in f.values()):
        return None
    ok = lambda f: f"{sum(not v for v in f.values())}/{len(f)}"  # noqa: E731
    return {"raw_dev_second_model": f"{sum(bool(v) for v in flags['dev12'].values())}/{len(flags['dev12'])}",
            "raw_dev_agree": f"{sum(flags['dev12'][k] == audit[k] for k in audit)}/{len(audit)}",
            "raw_dev_clean": ok(flags["dev34"]), "raw_v2_clean": ok(flags["v2"]), "raw_v1_clean": ok(flags["v1"])}


def main():
    got = committed()
    mismatches = 0
    print("| Claim | Recomputed | Published | Source | Match |\n|---|---|---|---|---|")
    for key, claim, published, source in CLAIMS:
        mismatches += got[key] != published
        print(f"| {claim} | {got[key]} | {published} | `{source}` | {'yes' if got[key] == published else '**NO**'} |")
    raw = from_raw()
    if raw is None:
        print("\nRaw CLI traces (results/raw/, gitignored) not present: the raw re-derivation was skipped, not passed.")
    else:
        print("\n| Raw-trace check (local only) | Recomputed | Published | Match |\n|---|---|---|---|")
        for key, claim, published in RAW_CLAIMS:
            mismatches += raw[key] != published
            print(f"| {claim} | {raw[key]} | {published} | {'yes' if raw[key] == published else '**NO**'} |")
    print(f"\n{mismatches} mismatches.")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
