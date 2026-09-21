"""Run one development episode and save its trace.

Usage (repo root):
    python3 src/run.py direct dev-01
    python3 src/run.py workflow dev-01
Written by Claude at Leo's direction (2026-09-21). Development cases only.
"""
import datetime
import hashlib
import json
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
EPISODES = ROOT / "results" / "episodes_dev.jsonl"  # reviewed summaries; append-only
SCHEMA = 2  # line 1 of episodes_dev.jsonl predates the turns list (schema 1)


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


def load_dev_case(case_id):
    if not case_id.startswith("dev-"):
        raise SystemExit("Only development cases may be run before the protocol is frozen.")
    return (load_row(ROOT / "data" / "dev_cases.jsonl", case_id),
            load_row(ROOT / "data" / "dev_keys.jsonl", case_id))


def make_model_caller(episode_id, turns):
    """Return call_model(prompt, turn): one CLI call, raw output saved, summary kept in `turns`."""
    def call_model(prompt, turn):
        call = models.call_claude(prompt)
        raw_path = RAW_DIR / f"{episode_id}-turn{turn}.json"
        raw_path.write_text(json.dumps(call, indent=1))
        summary = models.summarize_claude(call["events"])
        init = summary["init"] or {}
        text = summary["result_text"] if call["returncode"] == 0 else None
        turns.append({
            "turn": turn, "prompt_sha256": sha256(prompt), "prompt": prompt,
            "argv": call["argv"], "returncode": call["returncode"], "elapsed_s": call["elapsed_s"],
            "cli": summary, "response_text": text,
            "controls": {"init_tools_empty": init.get("tools") == [],
                         "no_native_tool_use": summary["tool_use_blocks"] == 0},
            "stderr_nonempty": bool(call["stderr"].strip()),
            "raw_trace": str(raw_path.relative_to(ROOT)),
        })
        return text
    return call_model


def run_episode(condition, case_id):
    case, key = load_dev_case(case_id)
    started_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    episode_id = f"{case_id}-{condition}-claude-{started_at[:19].replace(':', '')}"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    turns = []
    call_model = make_model_caller(episode_id, turns)

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

    record = {
        "schema": SCHEMA, "episode_id": episode_id, "started_at": started_at, "split": "dev",
        "case_id": case_id, "condition": condition, "system": "claude-code-cli",
        "model_requested": models.CLAUDE_MODEL, "prompt_template_sha256": templates,
        "limits": {"max_model_calls": 1 if condition == "direct" else agent.MAX_MODEL_CALLS,
                   "max_tool_executions": 0 if condition == "direct" else agent.MAX_TOOL_EXECUTIONS,
                   "retries": 0},
        "model_calls": loop["model_calls"], "tool_executions": loop["tool_executions"],
        "turn_kinds": loop["turn_kinds"], "tool": loop["tool"], "turns": turns,
        "parsed": answer, "error": error,
        "a_ref": key["a_ref"], "tolerance": evaluate.DEV_TOLERANCE, "tolerance_status": "provisional",
        "accepted_units": list(evaluate.ACCEPTED_UNITS),
        "grade": evaluate.grade(answer, error, key["a_ref"]),
        "controls_ok": all(t["controls"]["init_tools_empty"] and t["controls"]["no_native_tool_use"]
                           for t in turns),
    }
    with EPISODES.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return record


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("direct", "workflow"):
        raise SystemExit("usage: python3 src/run.py {direct|workflow} <dev-case-id>")
    rec = run_episode(sys.argv[1], sys.argv[2])
    print(json.dumps({k: rec[k] for k in ("episode_id", "model_calls", "tool_executions", "turn_kinds",
                                          "tool", "parsed", "error", "grade", "a_ref", "controls_ok")},
                     indent=1))
    for t in rec["turns"]:
        print(f"turn {t['turn']}: {t['response_text']!r}")
        print(f"  result: {t['cli']['result']}  rate_limit: {t['cli']['rate_limit']}")
