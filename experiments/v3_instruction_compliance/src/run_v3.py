"""V3 runner: episodes for both arms, attempt logs, resumable batches, the probe and the freeze.

Usage (repository root):
    python3 experiments/v3_instruction_compliance/src/run_v3.py plan
    python3 experiments/v3_instruction_compliance/src/run_v3.py probe v3-probe-1     # 1 call, trivial prompt, pre-freeze
    python3 experiments/v3_instruction_compliance/src/run_v3.py freeze               # writes data/freeze_manifest.json once
    python3 experiments/v3_instruction_compliance/src/run_v3.py verify
    python3 experiments/v3_instruction_compliance/src/run_v3.py pilot [--arm a|b|both] [--max-episodes N]
    python3 experiments/v3_instruction_compliance/src/run_v3.py heldout --approval "<who, when>" [--arm ...] [--max-episodes N]

Rules carried over from V2: an attempt record is written before the first call of an episode, so an
interrupted episode is never replayed and its reserved calls count against the cap; a runtime control
violation makes the episode invalid_run (not graded, kept in the denominator) and stops the batch; timeouts
are outcomes and three in a row stop the batch; no retries. New in V3: a usage guard stops the batch before
the subscription windows are exhausted, and the held-out run refuses to start without a recorded approval.
"""
import argparse
import ast
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

import common_v3 as C
import agent_v3
import controls_v3
import models_v3
import pendulum_v3
import policy_v3
import tasks_v3
import run_v2                       # frozen V2 module: redact (drops user, temp and session paths from text)

MANIFEST = C.DATA / "freeze_manifest.json"
PREFREEZE = C.RESULTS / "prefreeze_calls.jsonl"
RUN_IDS = {"dev": "v3-pilot-1", "heldout": "v3-run-1"}
PROBE_PROMPT = "Reply with the single word ok"
MAX_CONSECUTIVE_TIMEOUTS = 3
USAGE_GUARD = {"five_hour": 0.85, "seven_day": 0.70}     # stop the batch at or above these utilisations
FROZEN_DIRS = ("src", "prompts", "data", "tests")
# Every repository file the V3 code and tests load. Hashed at the freeze; .py files must also have the same
# code as at their release tag (docstrings may differ, as CI already allows).
DEPENDENCIES = {
    "src/tasks.py": "v2.0.0", "src/tools.py": "v2.0.0", "src/evaluate.py": "v2.0.0", "src/models.py": "v2.0.0",
    "src/agent.py": "v2.0.0", "src/run.py": "v2.0.0", "src/agent_v2.py": "v2.0.0", "src/tasks_v2.py": "v2.0.0",
    "src/run_v2.py": "v2.0.0", "src/analyze_v2.py": "v2.0.0", "prompts/v2/task.txt": "v2.0.0",
    "prompts/v2/turn2.txt": "v2.0.0", "data/v2/dev_tasks.jsonl": "v2.0.0", "data/v2/dev_keys.jsonl": "v2.0.0",
    "tests/test_v2_run.py": None,          # fixture source for the parity test only; hashed, no tag parity required
}


class ControlViolation(Exception):
    """A model call ran outside the declared system."""


def paths(arm, split):
    stem = "" if arm == "a" else "pendulum_"
    return C.RESULTS / f"{stem}episodes_{split}.jsonl", C.RESULTS / f"{stem}attempts_{split}.jsonl"


def key_a(x):
    return (x["task_id"], x["cell"], x["rep"])


def key_b(x):
    return (x["item_id"], x["frame"], x["rep"])


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


IDENTIFIERS = [(re.compile(r"\breq_[A-Za-z0-9]{12,}"), "<request-id>"), (re.compile(r"\bmsg_[A-Za-z0-9]{12,}"), "<message-id>"),
               (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "<uuid>")]


def scrub(text):
    """V2's redaction (user, temp and session paths) plus request, message and session identifiers."""
    text = run_v2.redact(text)
    for pattern, label in IDENTIFIERS:
        text = pattern.sub(label, text)
    return text


def write_record(path, record):
    C.append_jsonl(path, json.loads(scrub(json.dumps(record))))   # every text field, including echoed replies


def make_model_caller(run_id, episode_id, turns, expected):
    """call_model(prompt, turn) -> (text, meta): one CLI call, raw output saved, controls enforced."""
    def call_model(prompt, turn):
        call = models_v3.call_claude_v3(prompt)
        raw_path = C.RAW / run_id / f"{episode_id}-turn{turn}.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(call, indent=1))
        summary = controls_v3.summarize_call_v3(call)
        violations = controls_v3.control_violations_v3(call, summary, expected["model"], expected["cli_version"],
                                                       expected["inventory"])
        refused, truncated = controls_v3.is_refused(summary), controls_v3.is_truncated(summary)
        text = summary["result_text"] if call["returncode"] == 0 and not refused else None
        stderr = call["stderr"].strip()
        turns.append({
            "turn": turn, "prompt_sha256": C.sha256_text(prompt), "prompt": prompt, "argv": call["argv"],
            "returncode": call["returncode"], "timed_out": call["returncode"] is None, "elapsed_s": call["elapsed_s"],
            "cli": summary, "response_text": text, "refused": refused, "truncated": truncated,
            "control_violations": violations, "stderr_first_line": stderr.splitlines()[0][:200] if stderr else None,
            "raw_trace": str(raw_path.relative_to(C.EXP)) if raw_path.is_relative_to(C.EXP) else raw_path.name,
        })
        if violations:
            raise ControlViolation(violations)
        return text, {"truncated": truncated, "refused": refused}
    return call_model


def common_fields(run_id, episode_id, started_at, split, expected, approval):
    return {"schema": "v3.0", "experiment_version": C.EXPERIMENT_VERSION, "run_id": run_id, "episode_id": episode_id,
            "started_at": started_at, "split": split, "system": "claude-code-cli", "model_requested": models_v3.MODEL,
            "effort": models_v3.EFFORT, "cli_version_expected": expected["cli_version"],
            "timeout_s": models_v3.TIMEOUT_S, "env_controls": models_v3.ENV_CONTROLS,
            "system_prompt_sha256": C.sha256_text(models_v3.SYSTEM_PROMPT), "approval": approval}


def run_episode_a(split, item, run_id, expected, approval=None):
    """One Arm A episode: fit_line task under one policy cell."""
    cases, keys, _ = tasks_v3.load(split)
    task_id, cell, rep = item["task_id"], item["cell"], item["rep"]
    if not task_id.startswith(tasks_v3.ID_PREFIX[split]) or task_id not in cases:
        raise SystemExit(f"{task_id} is not a {split} task.")
    case, key = cases[task_id], keys[task_id]
    started_at = now()
    episode_id = f"{task_id}-{cell}-r{rep}-{started_at[:19].replace(':', '')}"
    _, attempts_path = paths("a", split)
    C.append_jsonl(attempts_path, {"episode_id": episode_id, "started_at": started_at, "split": split, "run_id": run_id,
                                   "task_id": task_id, "cell": cell, "rep": rep,
                                   "reserved_calls": agent_v3.MAX_MODEL_CALLS})
    turns, violations = [], None
    state = agent_v3.new_state(cell)            # filled in place: a turn-2 violation keeps the turn-1 evidence
    prompt1 = policy_v3.render_turn1(case, cell)
    try:
        agent_v3.run_episode_v3(case, cell, prompt1, policy_v3.turn2_template(),
                                make_model_caller(run_id, episode_id, turns, expected), state=state)
    except ControlViolation as exc:
        violations = exc.args[0]
    valid = violations is None
    grade = agent_v3.grade(state, key["a_ref"]) if valid else {"correct": None, "outcome": "invalid_run", "abs_error": None}
    record = dict(common_fields(run_id, episode_id, started_at, split, expected, approval), arm="a", task_id=task_id,
                  stratum=key["stratum"], cell=cell, rep=rep, prompt_template_sha256=policy_v3.template_hashes(cell),
                  limits={"max_model_calls": agent_v3.MAX_MODEL_CALLS, "max_tool_executions": agent_v3.MAX_TOOL_EXECUTIONS,
                          "retries": 0},
                  valid=valid, control_violations=violations, model_calls=len(turns), turns=turns,
                  a_ref=key["a_ref"], tolerance=tasks_v3.TOLERANCE, grade=grade,
                  turn1_grade=agent_v3.grade_turn1(state, key["a_ref"]) if valid else None)
    for field in ("permission_state", "tool_executions", "turn1_kind", "turn2_kind", "turn1_answer", "turn1_error",
                  "request_attempted_turn1", "requested_name", "request_valid", "validation_error",
                  "request_other_tool", "policy_violation_turn1", "policy_violation_turn2", "soft_override", "denied",
                  "request_turns", "executed", "tool_error", "tool_result", "output_truncated", "extra_keys",
                  "tool_section"):
        record[field] = state[field]
    record["parsed"] = state["answer"] if valid else None
    record["error"] = state["error"] if valid else "control_violation"
    write_record(paths("a", split)[0], record)
    return record


def run_episode_b(split, item, run_id, expected, approval=None):
    """One Arm B episode: one call, a structured claim about a closed form, graded deterministically."""
    items, reference, _ = pendulum_v3.load(split)
    item_id, frame, rep = item["item_id"], item["frame"], item["rep"]
    if item_id not in items:
        raise SystemExit(f"{item_id} is not a {split} Arm B item.")
    started_at = now()
    episode_id = f"{item_id}-{frame}-r{rep}-{started_at[:19].replace(':', '')}"
    _, attempts_path = paths("b", split)
    C.append_jsonl(attempts_path, {"episode_id": episode_id, "started_at": started_at, "split": split, "run_id": run_id,
                                   "item_id": item_id, "frame": frame, "rep": rep, "reserved_calls": 1})
    turns, violations, text, meta = [], None, None, {"truncated": False, "refused": False}
    prompt = pendulum_v3.render(items[item_id], frame)
    try:
        text, meta = make_model_caller(run_id, episode_id, turns, expected)(prompt, 1)
    except ControlViolation as exc:
        violations = exc.args[0]
    valid = violations is None
    graded = pendulum_v3.grade_reply(reference[item_id], text, meta["truncated"], meta["refused"]) if valid else \
        {"label": "invalid_run", "flags": [], "reply": None, "detail": None, "basis_normalised": None}
    record = dict(common_fields(run_id, episode_id, started_at, split, expected, approval), arm="b", item_id=item_id,
                  V0=items[item_id]["V0"], paraphrase=items[item_id]["paraphrase"], frame=frame, rep=rep,
                  prompt_template_sha256=pendulum_v3.template_hashes(items[item_id], frame),
                  limits={"max_model_calls": 1, "max_tool_executions": 0, "retries": 0},
                  valid=valid, control_violations=violations, model_calls=len(turns), turns=turns,
                  finite_exists=reference[item_id]["finite_exists"], graded=graded,
                  output_truncated=meta["truncated"])
    write_record(paths("b", split)[0], record)
    return record


def resume_state(arm, split):
    """(completed records, interrupted attempts, keys never to run again, calls used or reserved)."""
    key = key_a if arm == "a" else key_b
    episodes_path, attempts_path = paths(arm, split)
    existing = C.read_jsonl(episodes_path)
    completed = {key(r) for r in existing}
    interrupted = [a for a in C.read_jsonl(attempts_path) if key(a) not in completed]
    return existing, interrupted, completed | {key(a) for a in interrupted}, \
        sum(r["model_calls"] for r in existing) + sum(a["reserved_calls"] for a in interrupted)


def run_batch(plan, key, runner, calls_per_episode, already, calls_used, cap, max_episodes=None, guard=USAGE_GUARD):
    """Run planned episodes in order; never repeat an attempted one. Returns (records, stop_reason)."""
    records, consecutive_timeouts = [], 0
    for item in plan:
        if key(item) in already:
            continue
        if max_episodes is not None and len(records) >= max_episodes:
            return records, "max_episodes"
        if calls_used + calls_per_episode > cap:
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
        live = [t for t in rec["turns"] if not t.get("timed_out")]
        if any((t["cli"]["rate_limit"] or {}).get("status") not in (None, "allowed") for t in live):
            return records, "rate_limit"
        windows = (live[-1]["cli"]["usage_windows"] or {}) if live else {}
        if any((windows.get(name) or 0) >= limit for name, limit in guard.items()):
            return records, "usage_guard"
    return records, "completed"


# ---------------------------------------------------------------------------------------------- freeze

def code_without_docstrings(source):
    """The AST with module, class and function docstrings removed (the normalisation CI uses)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and body \
                and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            node.body = body[1:]
    return ast.dump(tree)


def tag_parity(rel, tag):
    """True if the working-tree file has the same content as at the tag (code for .py, bytes otherwise)."""
    shown = subprocess.run(["git", "show", f"{tag}:{rel}"], capture_output=True, cwd=C.ROOT)
    if shown.returncode != 0:
        return False
    head = (C.ROOT / rel).read_bytes()
    if head == shown.stdout:
        return True
    return rel.endswith(".py") and code_without_docstrings(head.decode()) == code_without_docstrings(shown.stdout.decode())


def frozen_files():
    """Every V3 file the freeze covers, relative to the experiment directory (the manifest excludes itself)."""
    out = ["PROTOCOL.md"]
    for d in FROZEN_DIRS:
        out += [str(p.relative_to(C.EXP)) for p in sorted((C.EXP / d).rglob("*"))
                if p.is_file() and "__pycache__" not in p.parts and p != MANIFEST and p.name != ".DS_Store"]
    return out


def settings():
    """Every setting the manifest records and verify() compares with the running code."""
    return {
        "experiment_version": C.EXPERIMENT_VERSION, "run_ids": {"probe": "v3-probe-1", **RUN_IDS},
        "model_requested": models_v3.MODEL, "effort": models_v3.EFFORT, "argv": models_v3.ARGV_RECORDED,
        "system_prompt": models_v3.SYSTEM_PROMPT, "timeout_s": models_v3.TIMEOUT_S,
        "env_controls": models_v3.ENV_CONTROLS, "env_must_be_unset": list(models_v3.ENV_MUST_BE_UNSET),
        "claude_code_version": models_v3.CLI_VERSION,
        "cells": {c: {"permission_state": policy_v3.PERMISSION[c], "policy": policy_v3.POLICY[c]} for c in policy_v3.CELLS},
        "section_strings": {"final": policy_v3.SECTION_FINAL, "unparsed": policy_v3.SECTION_UNPARSED,
                            "denied": policy_v3.SECTION_DENIED, "invalid": policy_v3.section_invalid("<code>"),
                            "failed": policy_v3.section_failed()},
        "strata": tasks_v3.STRATA, "tolerance_m_per_s2": tasks_v3.TOLERANCE, "seeds": tasks_v3.SEEDS,
        "plan_seeds": tasks_v3.PLAN_SEEDS, "reps": tasks_v3.REPS, "pilot_tasks": list(tasks_v3.PILOT_TASKS),
        "arm_b": {"V0": list(pendulum_v3.V0_VALUES), "paraphrases": pendulum_v3.PARAPHRASES,
                  "frames": sorted(pendulum_v3.FRAMES), "reps": pendulum_v3.REPS,
                  "plan_seeds": [pendulum_v3.PLAN_SEED, pendulum_v3.DEV_PLAN_SEED]},
        "limits": {"arm_a_calls_per_episode": agent_v3.MAX_MODEL_CALLS, "arm_b_calls_per_episode": 1,
                   "tool_executions_per_episode": agent_v3.MAX_TOOL_EXECUTIONS, "retries": 0,
                   "max_consecutive_timeouts": MAX_CONSECUTIVE_TIMEOUTS, "usage_guard": USAGE_GUARD},
        "output_truncated_rule": "a truncated turn 1 is recorded as no fit_line request; the episode is graded output_truncated",
    }


def latest_probe(run_id="v3-probe-1"):
    rows = [r for r in C.read_jsonl(PREFREEZE) if r.get("run_id") == run_id]
    return rows[-1] if rows else None


def write_manifest():
    if MANIFEST.exists():
        raise SystemExit(f"{MANIFEST.name} exists; a protocol change needs a new experiment version, not an overwrite.")
    probe = latest_probe()
    if probe is None or probe["control_violations"] or probe["refused"]:
        raise SystemExit("No clean v3-probe-1 record: run the probe before freezing.")
    cases, _, plan = tasks_v3.load("heldout")
    b_plan = pendulum_v3.load("heldout")[2]
    manifest = dict(settings(), frozen_at=now(), python=sys.version.split()[0],
                    git_head=subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=C.ROOT).stdout.strip(),
                    cli_sha256=models_v3.cli_sha256(),
                    allowed_model_identities=probe["identities"], inventory=probe["inventory"],
                    max_output_tokens_reported=probe["max_output_tokens"], inherited_env_names=probe["inherited_env_names"],
                    planned={"arm_a_episodes": len(plan), "arm_a_call_cap": len(plan) * agent_v3.MAX_MODEL_CALLS,
                             "arm_b_episodes": len(b_plan), "arm_b_call_cap": len(b_plan), "heldout_tasks": len(cases)},
                    sha256={rel: C.sha256_file(C.EXP / rel) for rel in frozen_files()},
                    dependencies={rel: {"sha256": C.sha256_file(C.ROOT / rel), "tag": tag,
                                        "same_as_tag": tag_parity(rel, tag) if tag else None}
                                  for rel, tag in DEPENDENCIES.items()})
    bad = [rel for rel, d in manifest["dependencies"].items() if d["tag"] and not d["same_as_tag"]]
    if bad:
        raise SystemExit(f"Dependencies differ from their release tag: {bad}")
    MANIFEST.write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def verify_freeze():
    """Refuse to run unless every frozen file, dependency, the pinned CLI and the settings match the manifest."""
    if not MANIFEST.exists():
        raise SystemExit("No V3 freeze manifest: live runs under the protocol are not allowed.")
    manifest = json.loads(MANIFEST.read_text())
    current = frozen_files()
    if sorted(current) != sorted(manifest["sha256"]):
        raise SystemExit(f"Frozen file set changed: {sorted(set(current) ^ set(manifest['sha256']))}")
    for rel, digest in manifest["sha256"].items():
        if C.sha256_file(C.EXP / rel) != digest:
            raise SystemExit(f"{rel} differs from the V3 freeze manifest.")
    for rel, dep in manifest["dependencies"].items():
        if C.sha256_file(C.ROOT / rel) != dep["sha256"]:
            raise SystemExit(f"{rel} (dependency) differs from the V3 freeze manifest.")
        if dep["tag"] and not tag_parity(rel, dep["tag"]):
            raise SystemExit(f"{rel} no longer matches {dep['tag']}.")
    if not models_v3.CLI_BIN.exists():
        raise SystemExit("The pinned CLI copy is missing.")
    if models_v3.cli_sha256() != manifest["cli_sha256"] or models_v3.cli_version() != manifest["claude_code_version"]:
        raise SystemExit("The pinned CLI differs from the V3 freeze manifest.")
    for name, value in settings().items():
        if manifest.get(name) != json.loads(json.dumps(value)):
            raise SystemExit(f"Setting '{name}' differs from the V3 freeze manifest.")
    return manifest


def expected_from(manifest):
    return {"model": manifest["model_requested"], "cli_version": manifest["claude_code_version"],
            "inventory": manifest["inventory"]}


# ---------------------------------------------------------------------------------------------- commands

def probe(run_id, purpose="pre-freeze identity probe"):
    """One call with a trivial prompt: confirms the model is served as declared and records its identity
    strings and the CLI's inventory. It carries no task content and exposes no protocol string."""
    call = models_v3.call_claude_v3(PROBE_PROMPT)
    raw_path = C.RAW / "prefreeze" / f"{run_id}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(call, indent=1))
    return record_prefreeze(run_id, call, PROBE_PROMPT, purpose)


def record_prefreeze(run_id, call, prompt, purpose, note=None, live=True):
    """Append one pre-freeze call to the log. live=False records a saved raw trace after the fact (the
    environment of that call is then described in the note, not read from this process)."""
    summary = controls_v3.summarize_call_v3(call)
    row = {"run_id": run_id, "recorded_at": now(), "purpose": purpose, "note": note, "prompt": prompt,
           "argv": call.get("argv"), "returncode": call["returncode"], "elapsed_s": call.get("elapsed_s"),
           "cli": summary, "refused": controls_v3.is_refused(summary),
           "control_violations": controls_v3.control_violations_v3(call, summary, models_v3.MODEL, models_v3.CLI_VERSION),
           "identities": {"init_model": (summary["init"] or {}).get("model"),
                          "assistant_models": sorted(set(map(str, summary["assistant_models"]))),
                          "models_used": summary["models_used"], "canonical_models": summary["canonical_models"]},
           "inventory": summary["inventory"], "max_output_tokens": summary["max_output_tokens"],
           "inherited_env_names": models_v3.inherited_env_names() if live else None,
           "response_text": summary["result_text"]}
    write_record(PREFREEZE, row)
    return row


def run_arm(arm, split, expected, approval=None, max_episodes=None):
    plan = tasks_v3.load(split)[2] if arm == "a" else pendulum_v3.load(split)[2]
    per = agent_v3.MAX_MODEL_CALLS if arm == "a" else 1
    existing, interrupted, already, calls_used = resume_state(arm, split)
    if any(not r["valid"] for r in existing):
        raise SystemExit(f"A previous {split} arm-{arm} episode was invalid; Leo must decide before any further inference.")
    if interrupted:
        print(f"{len(interrupted)} interrupted episode(s) stay attempted and are not replayed.")
    runner = (lambda item: run_episode_a(split, item, RUN_IDS[split], expected, approval)) if arm == "a" else \
        (lambda item: run_episode_b(split, item, RUN_IDS[split], expected, approval))
    return run_batch(plan, key_a if arm == "a" else key_b, runner, per, already, calls_used, len(plan) * per, max_episodes)


def describe_plan():
    for split in ("dev", "heldout"):
        for arm, per in (("a", agent_v3.MAX_MODEL_CALLS), ("b", 1)):
            plan = tasks_v3.load(split)[2] if arm == "a" else pendulum_v3.load(split)[2]
            existing, interrupted, already, used = resume_state(arm, split)
            print(f"{split:8s} arm {arm}: {len(plan):3d} planned, {len(existing):3d} completed, {len(interrupted)} interrupted, "
                  f"{sum(1 for p in plan if (key_a if arm == 'a' else key_b)(p) not in already):3d} remaining; "
                  f"{used}/{len(plan) * per} calls; timeout {models_v3.TIMEOUT_S} s per call")


def print_records(records, reason):
    for r in records:
        if r["arm"] == "a":
            print(f"{r['task_id']:6} {r['cell']:6} r{r['rep']} valid={r['valid']} calls={r['model_calls']} "
                  f"turn1={r['turn1_kind']} executed={r['executed']} denied={r['denied']} outcome={r['grade']['outcome']} "
                  f"err={r['grade']['abs_error']}")
        else:
            print(f"{r['item_id']:16} {r['frame']:21} r{r['rep']} valid={r['valid']} label={r['graded']['label']} "
                  f"flags={r['graded']['flags']}")
    print("stop reason:", reason)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["plan", "probe", "freeze", "verify", "pilot", "heldout"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--arm", choices=["a", "b", "both"], default="both")
    ap.add_argument("--max-episodes", type=int, default=None)
    ap.add_argument("--approval", default=None, help="heldout: who approved the scored run and when (recorded in every record)")
    a = ap.parse_args()
    if a.command == "plan":
        describe_plan()
    elif a.command == "probe":
        row = probe(a.arg or "v3-probe-1")
        print(json.dumps({k: row[k] for k in ("run_id", "refused", "control_violations", "identities", "max_output_tokens",
                                              "response_text")}, indent=1))
    elif a.command == "freeze":
        m = write_manifest()
        print(f"frozen {m['experiment_version']} at {m['frozen_at']}: {len(m['sha256'])} files, "
              f"{len(m['dependencies'])} dependencies, Claude Code {m['claude_code_version']}")
    elif a.command == "verify":
        m = verify_freeze()
        print(f"verify OK: {m['experiment_version']}, {len(m['sha256'])} files, {len(m['dependencies'])} dependencies")
    else:
        split = "dev" if a.command == "pilot" else "heldout"
        if split == "heldout" and not a.approval:
            raise SystemExit("The held-out run needs --approval \"<who approved it, and when>\".")
        expected = expected_from(verify_freeze())
        for arm in (("a", "b") if a.arm == "both" else (a.arm,)):
            records, reason = run_arm(arm, split, expected, a.approval, a.max_episodes)
            print_records(records, reason)
            if reason not in ("completed", "max_episodes"):
                break
