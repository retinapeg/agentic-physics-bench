"""V2 runner: episodes, enforced controls, resumable batches and the freeze check.

Usage (repo root):
    python3 src/run_v2.py plan [dev|scored]           # counts and call budget, no model calls
    python3 src/run_v2.py dev [--max-episodes N]      # the development plan (resumable, never repeats an episode)
    python3 src/run_v2.py dev-restage <name> [--keep-unchanged]  # archive the dev files under results/v2/dev_<name>/ and start afresh
    python3 src/run_v2.py freeze <run_id>             # write data/v2/freeze_manifest.json (before any scored call)
    python3 src/run_v2.py scored-batch [--max-episodes N]  # the frozen scored plan; refuses to run unless the manifest matches
Written by Claude at Leo's direction (2026-09-23). V1's runner (src/run.py) is
frozen; this module reuses its control checks and the V1 CLI adapter.

Controls are enforced per call, as in V1: missing or unexpected initialization
metadata, native tool use, overage, an unexpected model or any stderr output
invalidates the episode (not graded, kept in the denominator) and stops the
batch. V2 adds a per-call CLI-version check against the manifest. A CLI timeout
is an outcome (missing_output), not a control violation; three consecutive
timeouts stop the batch.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from string import Template

import agent_v2
import evaluate
import models
import run
import tasks_v2

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "v2"
PROMPT_DIR = ROOT / "prompts" / "v2"
PROMPT_FILES = {name: PROMPT_DIR / f"{name}.txt"
                for name in ("task", "no_tool_turn1", "optional_tool_turn1", "required_tool_turn1", "turn2")}
RAW_DIR = ROOT / "results" / "raw" / "v2"  # full CLI output; gitignored (session metadata)
EPISODES = {"dev": ROOT / "results" / "v2" / "episodes_dev.jsonl",        # append-only
            "scored": ROOT / "results" / "v2" / "episodes_scored.jsonl"}  # append-only
ATTEMPTS = {"dev": ROOT / "results" / "v2" / "attempts_dev.jsonl",        # append-only; written BEFORE the first call
            "scored": ROOT / "results" / "v2" / "attempts_scored.jsonl"}  # so an interrupted episode is never replayed
MANIFEST = DATA / "freeze_manifest.json"
SCHEMA = "v2.2"
TIMEOUT_S = 600            # per CLI call; harder tasks may think for minutes (V1 used 180 s)
# The CLI can run a server-side "advisor" tool that consults a second model inside one call, even with
# --tools "". It is switched off by environment variable and its absence is enforced per call (see
# v2_control_violations). Discovered in development stage 1 on 2026-09-23 (EXPERIMENT_V2.md section 6).
ENV_CONTROLS = {"CLAUDE_CODE_DISABLE_ADVISOR_TOOL": "1"}
MAX_CONSECUTIVE_TIMEOUTS = 3
FROZEN_FILES = [           # everything the scored run depends on, hashed into the manifest
    "src/tasks.py", "src/tools.py", "src/evaluate.py", "src/models.py", "src/run.py",   # V1 modules reused
    "src/tasks_v2.py", "src/agent_v2.py", "src/run_v2.py", "src/analyze_v2.py", "src/chart_v2.py",
    "prompts/v2/task.txt", "prompts/v2/no_tool_turn1.txt", "prompts/v2/optional_tool_turn1.txt",
    "prompts/v2/required_tool_turn1.txt", "prompts/v2/turn2.txt",
    "data/v2/scored_tasks.jsonl", "data/v2/scored_keys.jsonl", "data/v2/scored_plan.json",
    "data/v2/dev_tasks.jsonl", "data/v2/dev_keys.jsonl", "data/v2/dev_plan.json",
]


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def load_rows(path):
    return {r["id"]: r for r in map(json.loads, path.read_text().splitlines())}


def load_task(split, task_id):
    prefix = tasks_v2.ID_PREFIX[split]
    if not task_id.startswith(prefix) or task_id[1] not in "123":
        raise SystemExit(f"{task_id} is not a {split} task.")
    return (load_rows(DATA / f"{split}_tasks.jsonl")[task_id], load_rows(DATA / f"{split}_keys.jsonl")[task_id])


def render_prompts(case, condition):
    """Return (template hashes, turn-1 prompt, turn-2 template) for one case and condition."""
    templates = {name: path.read_text() for name, path in PROMPT_FILES.items()}
    task = Template(templates["task"]).substitute(case_id=case["id"], t=", ".join(case["t_s"]),
                                                  v=", ".join(case["v_m_per_s"]))
    turn1_name = f"{condition}_turn1"
    prompt1 = Template(templates[turn1_name]).substitute(task=task.rstrip("\n"), case_id=case["id"])
    hashes = {name: sha256(templates[name]) for name in ("task", turn1_name, "turn2")}
    return hashes, prompt1, templates["turn2"]


def summarize_call(call):
    """V1's reviewed CLI summary plus thinking tokens, usage-window utilisation, server-side tool use
    and every model the CLI reports having used (no identifiers)."""
    s = models.summarize_claude(call["events"])
    s["thinking_tokens"] = None
    s["usage_windows"] = None
    s["server_tool_uses"] = []
    s["models_used"] = []
    s["iteration_types"] = []
    for e in call["events"]:
        if e.get("type") == "result":
            usage = e.get("usage") or {}
            s["thinking_tokens"] = (usage.get("output_tokens_details") or {}).get("thinking_tokens")
            s["models_used"] = sorted((e.get("modelUsage") or {}).keys())
            s["iteration_types"] = sorted({i.get("type") for i in usage.get("iterations") or []})
        elif e.get("type") == "rate_limit_event":
            windows = (e.get("rate_limit_info") or {}).get("unifiedWindows") or {}
            s["usage_windows"] = {k: (v or {}).get("utilization") for k, v in windows.items()}
        elif e.get("type") == "assistant":
            for c in e.get("message", {}).get("content", []):
                if c.get("type") == "server_tool_use":
                    s["server_tool_uses"].append(str(c.get("name")))
                elif c.get("type") == "advisor_tool_result":  # the advisor's result block carries no name
                    s["server_tool_uses"].append("advisor")
    return s


def v2_control_violations(summary, expected_cli_version):
    """V2's additions to V1's control checks: the CLI version per call, no server-side tools, and no
    model other than the expected one anywhere in the reported usage."""
    v = []
    if summary["init"] and summary["init"].get("claude_code_version") != expected_cli_version:
        v.append("cli_version_mismatch")
    if summary["server_tool_uses"]:
        v.append("server_tool_use:" + ",".join(sorted(set(map(str, summary["server_tool_uses"])))))
    extra = sorted(m for m in summary["models_used"] if m != models.CLAUDE_MODEL)
    if extra:
        v.append("unexpected_model_usage:" + ",".join(extra))
    odd = sorted(t for t in summary["iteration_types"] if t != "message")
    if odd:
        v.append("unexpected_iteration:" + ",".join(map(str, odd)))
    return v


PATH_PATTERN = re.compile(r"(?:/private)?/(?:Users|home|var/folders|tmp)/[^\s\"'`<>]*")


def redact(text):
    """Replace absolute user, temp and per-session directories before text enters a tracked file.
    The model can echo its working directory into a reply (seen in development stage 3), and CLI error
    lines carry home-directory paths. Raw traces (gitignored) keep the original text."""
    return PATH_PATTERN.sub("<path>", text.replace(str(Path.home()), "~"))


def make_model_caller(episode_id, turns, expected_cli_version):
    """Return call_model(prompt, turn): one CLI call, raw output saved, controls enforced."""
    def call_model(prompt, turn):
        call = models.call_claude(prompt)
        raw_path = RAW_DIR / f"{episode_id}-turn{turn}.json"
        raw_path.write_text(json.dumps(call, indent=1))
        summary = summarize_call(call)
        timed_out = call["returncode"] is None
        if timed_out:  # the synthetic timeout stderr and evidence that is merely missing are not violations
            violations = [v for v in run.control_violations(dict(call, stderr=""), summary)
                          if not v.startswith("missing_init")]
        else:
            violations = run.control_violations(call, summary)
        violations += v2_control_violations(summary, expected_cli_version)
        text = summary["result_text"] if call["returncode"] == 0 else None
        turns.append({
            "turn": turn, "prompt_sha256": sha256(prompt), "prompt": prompt,
            "argv": call["argv"], "returncode": call["returncode"], "timed_out": timed_out,
            "elapsed_s": call["elapsed_s"], "cli": summary, "response_text": text,
            "control_violations": violations,
            "stderr_first_line": redact(call["stderr"].strip().splitlines()[0])[:200] if call["stderr"].strip() else None,
            "raw_trace": str(raw_path.relative_to(ROOT)) if raw_path.is_relative_to(ROOT) else raw_path.name,
        })
        if violations:
            raise run.ControlViolation(violations)
        return text
    return call_model


def run_episode(split, task_id, condition, rep, run_id, expected_cli_version):
    case, key = load_task(split, task_id)
    started_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    episode_id = f"{task_id}-{condition}-r{rep}-claude-{started_at[:19].replace(':', '')}"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    EPISODES[split].parent.mkdir(parents=True, exist_ok=True)
    hashes, prompt1, turn2_template = render_prompts(case, condition)
    with ATTEMPTS[split].open("a") as f:  # before any model call: a crash or interrupt still leaves a record
        f.write(json.dumps({"episode_id": episode_id, "started_at": started_at, "split": split, "task_id": task_id,
                            "condition": condition, "rep": rep, "run_id": run_id,
                            "reserved_calls": agent_v2.MAX_MODEL_CALLS}) + "\n")
    turns = []
    call_model = make_model_caller(episode_id, turns, expected_cli_version)
    violations = None
    models.TIMEOUT_S = TIMEOUT_S
    os.environ.update(ENV_CONTROLS)
    loop = agent_v2.new_state(condition)  # filled in place, so a turn-2 violation keeps the turn-1 evidence
    try:
        agent_v2.run_episode_v2(case, condition, prompt1, turn2_template, call_model, state=loop)
    except run.ControlViolation as exc:
        violations = exc.args[0]

    valid = violations is None
    a_ref = key["a_ref"]
    if valid:
        grade = evaluate.grade(loop["answer"], loop["error"], a_ref)
        t1 = loop["turn1"]
        turn1_grade = evaluate.grade(t1["answer"], None, a_ref) if t1["kind"] == "final" else None
    else:
        grade = {"correct": None, "outcome": "invalid_run", "abs_error": None}
        turn1_grade = None
    record = {
        "schema": SCHEMA, "run_id": run_id, "episode_id": episode_id, "started_at": started_at, "split": split,
        "task_id": task_id, "group": key["group"], "condition": condition, "rep": rep,
        "system": "claude-code-cli", "model_requested": models.CLAUDE_MODEL, "effort": models.EFFORT,
        "cli_version_expected": expected_cli_version, "timeout_s": TIMEOUT_S, "env_controls": ENV_CONTROLS,
        "prompt_template_sha256": hashes,
        "limits": {"max_model_calls": agent_v2.MAX_MODEL_CALLS, "max_tool_executions": agent_v2.MAX_TOOL_EXECUTIONS,
                   "retries": 0},
        "valid": valid, "control_violations": violations,
        "model_calls": len(turns), "tool_executions": loop["tool_executions"], "turn_kinds": loop["turn_kinds"],
        "tool": loop["tool"], "required_compliant": loop["required_compliant"], "tool_section": loop["tool_section"],
        "turn1": dict(loop["turn1"], grade=turn1_grade), "turns": turns,
        "parsed": loop["answer"] if valid else None, "error": loop["error"] if valid else "control_violation",
        "a_ref": a_ref, "tolerance": evaluate.TOLERANCE, "accepted_units": list(evaluate.ACCEPTED_UNITS),
        "grade": grade,
    }
    record = json.loads(redact(json.dumps(record)))  # every text field, including echoed replies
    with EPISODES[split].open("a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def episode_key(item):
    return (item["task_id"], item["condition"], item["rep"])


def run_batch(plan, runner, already, calls_used, cap, max_episodes=None):
    """Run planned episodes in order; never repeat an attempted (task, condition, rep).

    Stops on an invalid run, a rate-limit status other than "allowed", three
    consecutive timeouts, the invocation cap, or max_episodes. Returns (records, stop_reason).
    """
    records, consecutive_timeouts = [], 0
    for item in plan:
        if episode_key(item) in already:
            continue
        if max_episodes is not None and len(records) >= max_episodes:
            return records, "max_episodes"
        if calls_used + agent_v2.MAX_MODEL_CALLS > cap:
            return records, "invocation_cap"
        rec = runner(item)
        records.append(rec)
        calls_used += rec["model_calls"]
        if not rec["valid"]:
            return records, "control_violation"
        if any(t.get("timed_out") for t in rec["turns"]):
            consecutive_timeouts += 1
            if consecutive_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
                return records, "repeated_timeouts"
        else:
            consecutive_timeouts = 0
        statuses = [(t["cli"]["rate_limit"] or {}).get("status") for t in rec["turns"] if not t.get("timed_out")]
        if any(s not in (None, "allowed") for s in statuses):
            return records, "rate_limit"
    return records, "completed"


def existing_records(split):
    path = EPISODES[split]
    return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []


def load_attempts(split):
    path = ATTEMPTS[split]
    return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []


def resume_state(split):
    """Return (completed records, interrupted attempts, keys never to run again, calls already used or reserved)."""
    existing = existing_records(split)
    completed = {episode_key(r) for r in existing}
    interrupted = [a for a in load_attempts(split) if episode_key(a) not in completed]
    already = completed | {episode_key(a) for a in interrupted}
    calls_used = sum(r["model_calls"] for r in existing) + sum(a["reserved_calls"] for a in interrupted)
    return existing, interrupted, already, calls_used


def cli_version():
    return subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.split()[0]


def file_hashes():
    return {rel: sha256((ROOT / rel).read_text()) for rel in FROZEN_FILES}


def write_manifest(run_id):
    """Freeze: hash every file the scored run depends on and record the CLI/model settings."""
    if MANIFEST.exists():
        raise SystemExit(f"{MANIFEST.name} exists; a protocol change needs a new run identity, not an overwrite.")
    plan = json.loads((DATA / "scored_plan.json").read_text())
    manifest = {
        "run_id": run_id, "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "sha256": file_hashes(), "claude_code_version": cli_version(), "claude_argv": models.CLAUDE_ARGV,
        "model": models.CLAUDE_MODEL, "effort": models.EFFORT, "timeout_s": TIMEOUT_S, "env_controls": ENV_CONTROLS,
        "python": sys.version.split()[0],
        "groups": tasks_v2.GROUPS, "seeds": tasks_v2.SEEDS, "plan_seed": tasks_v2.PLAN_SEEDS["scored"],
        "conditions": list(agent_v2.CONDITIONS), "reps": tasks_v2.REPS["scored"],
        "tolerance_m_per_s2": evaluate.TOLERANCE, "accepted_units": list(evaluate.ACCEPTED_UNITS),
        "limits": {"model_calls_per_episode": agent_v2.MAX_MODEL_CALLS,
                   "tool_executions_per_episode": agent_v2.MAX_TOOL_EXECUTIONS, "retries": 0,
                   "planned_episodes": len(plan), "max_scored_invocations": len(plan) * agent_v2.MAX_MODEL_CALLS,
                   "max_consecutive_timeouts": MAX_CONSECUTIVE_TIMEOUTS},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def verify_freeze():
    """Refuse scored inference unless every frozen file and the CLI/model settings match the manifest."""
    if not MANIFEST.exists():
        raise SystemExit("No V2 freeze manifest: scored inference is not allowed.")
    manifest = json.loads(MANIFEST.read_text())
    for rel, digest in manifest["sha256"].items():
        if sha256((ROOT / rel).read_text()) != digest:
            raise SystemExit(f"{rel} differs from the V2 freeze manifest.")
    version = cli_version()
    if version != manifest["claude_code_version"]:
        raise SystemExit(f"Claude Code {version} != frozen {manifest['claude_code_version']}.")
    if models.CLAUDE_ARGV != manifest["claude_argv"] or models.CLAUDE_MODEL != manifest["model"] \
            or models.EFFORT != manifest["effort"] or TIMEOUT_S != manifest["timeout_s"] \
            or ENV_CONTROLS != manifest.get("env_controls"):
        raise SystemExit("CLI arguments, model, effort, timeout or environment controls differ from the V2 freeze manifest.")
    return manifest


def run_split(split, max_episodes=None):
    if split == "scored":
        manifest = verify_freeze()
        run_id, expected_version = manifest["run_id"], manifest["claude_code_version"]
    else:
        run_id, expected_version = "dev", cli_version()
    plan = json.loads((DATA / f"{split}_plan.json").read_text())
    cap = len(plan) * agent_v2.MAX_MODEL_CALLS
    existing, interrupted, already, calls_used = resume_state(split)
    if split == "scored" and any(not r["valid"] for r in existing):
        raise SystemExit("A previous scored episode was invalid; Leo must decide before any further inference.")
    if interrupted:
        print(f"{len(interrupted)} interrupted episode(s) stay attempted and are not replayed: "
              + ", ".join(a["episode_id"] for a in interrupted))
    runner = lambda item: run_episode(split, item["task_id"], item["condition"], item["rep"], run_id, expected_version)
    return run_batch(plan, runner, already, calls_used, cap, max_episodes)


def restage_dev(name, keep_unchanged=False, rerun_conditions=()):
    """Archive the current development files under results/v2/dev_<name>/ and start a fresh development
    episode file. With keep_unchanged, records whose displayed task table is identical to the current
    task file are carried over (their prompt hashes stay in the records), so only changed tasks rerun;
    records of any condition named in rerun_conditions are never carried over (a prompt change that
    affects one condition only). The gate (EXPERIMENT_V2.md section 9) documents when this is allowed."""
    out = ROOT / "results" / "v2" / f"dev_{name}"
    if out.exists():
        raise SystemExit(f"{out.relative_to(ROOT)} exists; choose a new stage name.")
    out.mkdir(parents=True)
    moved = []
    for path in [EPISODES["dev"], ATTEMPTS["dev"], *(ROOT / "results" / "v2").glob("summary_dev.*"),
                 *(ROOT / "results" / "v2").glob("chart_dev.svg")]:
        if path.exists():
            path.rename(out / path.name)
            moved.append(path.name)
    for name_ in ("dev_tasks.jsonl", "dev_keys.jsonl", "dev_plan.json"):
        (out / name_).write_text((DATA / name_).read_text())
    kept = []
    if keep_unchanged and (out / "episodes_dev.jsonl").exists():
        cases = load_rows(DATA / "dev_tasks.jsonl")
        for line in (out / "episodes_dev.jsonl").read_text().splitlines():
            r = json.loads(line)
            if r["condition"] in rerun_conditions:
                continue
            case = cases.get(r["task_id"])
            table = f"t (s): {', '.join(case['t_s'])}\nv (m/s): {', '.join(case['v_m_per_s'])}" if case else None
            if table and table in r["turns"][0]["prompt"]:
                kept.append(line)
        EPISODES["dev"].write_text("".join(l + "\n" for l in kept))
    return {"archived_to": str(out.relative_to(ROOT)), "moved": moved, "carried_over": len(kept)}


def describe_plan(split):
    plan = json.loads((DATA / f"{split}_plan.json").read_text())
    existing, interrupted, already, calls_used = resume_state(split)
    remaining = [p for p in plan if episode_key(p) not in already]
    print(f"{split}: {len(plan)} planned episodes, {len(existing)} completed, {len(interrupted)} interrupted, "
          f"{len(remaining)} remaining; {calls_used} calls used or reserved of a cap of "
          f"{len(plan) * agent_v2.MAX_MODEL_CALLS}; {len(remaining) * agent_v2.MAX_MODEL_CALLS} for the remaining "
          f"episodes; timeout {TIMEOUT_S} s per call.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["plan", "dev", "dev-restage", "freeze", "scored-batch"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--max-episodes", type=int, default=None)
    ap.add_argument("--keep-unchanged", action="store_true", help="dev-restage: carry over records of unchanged tasks")
    ap.add_argument("--rerun-condition", action="append", default=[], help="dev-restage: never carry over this condition")
    a = ap.parse_args()
    if a.command == "plan":
        describe_plan(a.arg or "dev")
    elif a.command == "dev-restage":
        if not a.arg:
            raise SystemExit("usage: python3 src/run_v2.py dev-restage <stage-name> [--keep-unchanged]")
        print(json.dumps(restage_dev(a.arg, a.keep_unchanged, tuple(a.rerun_condition))))
    elif a.command == "freeze":
        if not a.arg:
            raise SystemExit("usage: python3 src/run_v2.py freeze <run_id>")
        m = write_manifest(a.arg)
        print(f"frozen {m['run_id']} at {m['frozen_at']}: {len(m['sha256'])} files, Claude Code {m['claude_code_version']}")
    else:
        recs, reason = run_split("dev" if a.command == "dev" else "scored", a.max_episodes)
        for r in recs:
            print(f"{r['task_id']:6} {r['condition']:14} r{r['rep']} valid={r['valid']} calls={r['model_calls']} "
                  f"tool={'exec' if r['tool_executions'] else ('req' if r['tool']['requested'] else '-'):4} "
                  f"outcome={r['grade']['outcome']} err={r['grade']['abs_error']}")
        print("stop reason:", reason)
