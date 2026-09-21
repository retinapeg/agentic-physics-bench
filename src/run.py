"""Run episodes and save their traces.

Usage (repo root):
    python3 src/run.py direct dev-01      # one development episode
    python3 src/run.py workflow dev-01
    python3 src/run.py scored-batch       # the frozen 12 x 2 matrix; needs data/freeze_manifest.json
Written by Claude at Leo's direction (2026-09-21).

Controls are enforced, not just recorded: a call whose initialization metadata
is missing or unexpected, or that shows native tool use, overage or a stderr
warning, invalidates the episode (it is not graded) and stops the batch.
"""
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from string import Template

import agent
import evaluate
import models

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = {name: ROOT / "prompts" / f"{name}.txt"
           for name in ("direct", "workflow_turn1", "workflow_turn2")}
RAW_DIR = ROOT / "results" / "raw"  # full CLI output; gitignored (session metadata)
EPISODES = {"dev": ROOT / "results" / "episodes_dev.jsonl",        # append-only
            "scored": ROOT / "results" / "episodes_scored.jsonl"}  # append-only
MANIFEST = ROOT / "data" / "freeze_manifest.json"
PLAN = ROOT / "data" / "scored_plan.json"
SCHEMA = 3  # 3: adds validity and control enforcement; line 1 of episodes_dev is schema 1, line 2 schema 2
MAX_SCORED_INVOCATIONS = 36
REQUIRED_INIT = ("model", "tools", "mcp_servers", "claude_code_version")


class ControlViolation(Exception):
    """A model call ran outside the verified experimental conditions."""


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def load_row(path, case_id):
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if row["id"] == case_id:
            return row
    raise KeyError(f"{case_id} not in {path.name}")


def render_prompt(name, case):
    template = PROMPTS[name].read_text()
    text = Template(template).substitute(t=", ".join(case["t_s"]), v=", ".join(case["v_m_per_s"]),
                                         case_id=case["id"])
    return template, text


def load_case(split, case_id):
    prefix = {"dev": "dev-", "scored": "s-"}[split]
    if not case_id.startswith(prefix):
        raise SystemExit(f"{case_id} is not a {split} case.")
    return (load_row(ROOT / "data" / f"{split}_cases.jsonl", case_id),
            load_row(ROOT / "data" / f"{split}_keys.jsonl", case_id))


def load_dev_case(case_id):
    return load_case("dev", case_id)


def control_violations(call, summary):
    """Return a list of violated controls for one CLI call (empty list = OK)."""
    v = []
    init = summary["init"]
    if init is None:
        v.append("missing_init")
    else:
        missing = [k for k in REQUIRED_INIT if init.get(k) is None]
        if missing:
            v.append("missing_init_fields:" + ",".join(missing))
        if init.get("tools") != []:
            v.append("native_tools_present")
        if init.get("mcp_servers") != []:
            v.append("mcp_servers_present")
        if init.get("model") != models.CLAUDE_MODEL:
            v.append("unexpected_model")
    if summary["tool_use_blocks"]:
        v.append("native_tool_use")
    if any(m != models.CLAUDE_MODEL for m in summary["assistant_models"]):
        v.append("unexpected_assistant_model")
    if (summary["rate_limit"] or {}).get("isUsingOverage"):
        v.append("overage_used")
    if call["stderr"].strip():
        v.append("stderr_warning")  # e.g. an ignored --effort value falls back silently
    return v


def make_model_caller(episode_id, turns):
    """Return call_model(prompt, turn): one CLI call; raw output saved; controls enforced."""
    def call_model(prompt, turn):
        call = models.call_claude(prompt)
        raw_path = RAW_DIR / f"{episode_id}-turn{turn}.json"
        raw_path.write_text(json.dumps(call, indent=1))
        summary = models.summarize_claude(call["events"])
        violations = control_violations(call, summary)
        text = summary["result_text"] if call["returncode"] == 0 else None
        turns.append({
            "turn": turn, "prompt_sha256": sha256(prompt), "prompt": prompt,
            "argv": call["argv"], "returncode": call["returncode"], "elapsed_s": call["elapsed_s"],
            "cli": summary, "response_text": text, "control_violations": violations,
            "stderr_first_line": call["stderr"].strip().splitlines()[0][:200] if call["stderr"].strip() else None,
            "raw_trace": str(raw_path.relative_to(ROOT)) if raw_path.is_relative_to(ROOT) else str(raw_path),
        })
        if violations:
            raise ControlViolation(violations)
        return text
    return call_model


def run_episode(condition, case_id, split="dev"):
    case, key = load_case(split, case_id)
    started_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    episode_id = f"{case_id}-{condition}-claude-{started_at[:19].replace(':', '')}"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    turns = []
    call_model = make_model_caller(episode_id, turns)
    violations = None
    templates = {}
    loop = {"model_calls": 0, "tool_executions": 0, "tool": None, "turn_kinds": None}
    answer = error = None
    try:
        if condition == "direct":
            template, prompt = render_prompt("direct", case)
            templates = {"direct": sha256(template)}
            answer, error = evaluate.parse_final(call_model(prompt, 1))
            loop = {"model_calls": 1, "tool_executions": 0, "tool": None, "turn_kinds": None}
        elif condition == "workflow":
            template1, prompt1 = render_prompt("workflow_turn1", case)
            template2 = PROMPTS["workflow_turn2"].read_text()
            templates = {"workflow_turn1": sha256(template1), "workflow_turn2": sha256(template2)}
            loop = agent.run_workflow(case, prompt1, template2, call_model)
            answer, error = loop["answer"], loop["error"]
        else:
            raise SystemExit(f"unknown condition {condition}")
    except ControlViolation as exc:
        violations = exc.args[0]
        # A turn-2 violation means the tool ran after turn 1 (turn 2 exists only then).
        loop["tool_executions"] = 1 if condition == "workflow" and len(turns) == 2 else 0

    valid = violations is None
    if valid:
        grade = evaluate.grade(answer, error, key["a_ref"])
    else:  # not graded: a harness/control failure, distinct from a wrong answer
        grade = {"correct": None, "outcome": "invalid_run", "abs_error": None}
    record = {
        "schema": SCHEMA, "episode_id": episode_id, "started_at": started_at, "split": split,
        "case_id": case_id, "condition": condition, "system": "claude-code-cli",
        "model_requested": models.CLAUDE_MODEL, "effort": models.EFFORT,
        "prompt_template_sha256": templates,
        "limits": {"max_model_calls": 1 if condition == "direct" else agent.MAX_MODEL_CALLS,
                   "max_tool_executions": 0 if condition == "direct" else agent.MAX_TOOL_EXECUTIONS,
                   "retries": 0},
        "valid": valid, "control_violations": violations,
        "model_calls": len(turns), "tool_executions": loop["tool_executions"],
        "turn_kinds": loop["turn_kinds"], "tool": loop["tool"], "turns": turns,
        "parsed": answer if valid else None, "error": error if valid else "control_violation",
        "a_ref": key["a_ref"], "tolerance": evaluate.TOLERANCE,
        "tolerance_status": "frozen" if split == "scored" else "dev",
        "accepted_units": list(evaluate.ACCEPTED_UNITS), "grade": grade,
    }
    with EPISODES[split].open("a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def run_batch(plan, runner, already, calls_used, cap=MAX_SCORED_INVOCATIONS):
    """Run planned (case, condition) episodes in order; never repeat an attempted one.

    Stops on an invalid run, a rate-limit status other than "allowed", or when the
    next episode could exceed the invocation cap. Returns (records, stop_reason).
    """
    records = []
    for item in plan:
        for condition in item["order"]:
            if (item["case_id"], condition) in already:
                continue
            worst = 1 if condition == "direct" else agent.MAX_MODEL_CALLS
            if calls_used + worst > cap:
                return records, "invocation_cap"
            rec = runner(condition, item["case_id"])
            records.append(rec)
            calls_used += rec["model_calls"]
            if not rec["valid"]:
                return records, "control_violation"
            statuses = [(t["cli"]["rate_limit"] or {}).get("status") for t in rec["turns"]]
            if any(s not in (None, "allowed") for s in statuses):
                return records, "rate_limit"
    return records, "completed"


def verify_freeze():
    """Refuse scored inference unless every frozen file and the CLI version match the manifest."""
    if not MANIFEST.exists():
        raise SystemExit("No freeze manifest: scored inference is not allowed.")
    manifest = json.loads(MANIFEST.read_text())
    for rel, digest in manifest["sha256"].items():
        if sha256((ROOT / rel).read_text()) != digest:
            raise SystemExit(f"{rel} differs from the freeze manifest.")
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.split()[0]
    if version != manifest["claude_code_version"]:
        raise SystemExit(f"Claude Code {version} != frozen {manifest['claude_code_version']}.")
    if models.CLAUDE_ARGV != manifest["claude_argv"]:
        raise SystemExit("CLI arguments differ from the freeze manifest.")
    return manifest


def run_scored_batch():
    verify_freeze()
    plan = json.loads(PLAN.read_text())
    path = EPISODES["scored"]
    existing = [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []
    if any(not r["valid"] for r in existing):
        raise SystemExit("A previous scored episode was invalid; Leo must decide before any further inference.")
    already = {(r["case_id"], r["condition"]) for r in existing}
    calls_used = sum(r["model_calls"] for r in existing)
    return run_batch(plan, lambda c, cid: run_episode(c, cid, "scored"), already, calls_used)


if __name__ == "__main__":
    if sys.argv[1:] == ["scored-batch"]:
        recs, reason = run_scored_batch()
        for r in recs:
            print(f"{r['case_id']:6} {r['condition']:8} valid={r['valid']} calls={r['model_calls']} "
                  f"tools={r['tool_executions']} outcome={r['grade']['outcome']}")
        print("stop reason:", reason)
    elif len(sys.argv) == 3 and sys.argv[1] in ("direct", "workflow"):
        rec = run_episode(sys.argv[1], sys.argv[2], "dev")
        print(json.dumps({k: rec[k] for k in ("episode_id", "valid", "control_violations", "model_calls",
                                              "tool_executions", "parsed", "error", "grade")}, indent=1))
    else:
        raise SystemExit("usage: python3 src/run.py {direct|workflow} <dev-case-id> | scored-batch")
