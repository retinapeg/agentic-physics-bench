"""Run one development episode and save its trace.

Usage (repo root): python3 src/run.py direct dev-01
Written by Claude at Leo's direction (2026-09-21). Development cases only.
"""
import datetime
import hashlib
import json
import sys
from pathlib import Path
from string import Template

import evaluate
import models

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = {"direct": ROOT / "prompts" / "direct.txt"}
RAW_DIR = ROOT / "results" / "raw"  # full CLI output; gitignored (session metadata)
EPISODES = ROOT / "results" / "episodes_dev.jsonl"  # reviewed summaries; append-only


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def load_row(path, case_id):
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if row["id"] == case_id:
            return row
    raise KeyError(f"{case_id} not in {path.name}")


def render_prompt(condition, case):
    template = PROMPTS[condition].read_text()
    text = Template(template).substitute(t=", ".join(case["t_s"]), v=", ".join(case["v_m_per_s"]))
    return template, text


def run_direct(case_id):
    if not case_id.startswith("dev-"):
        raise SystemExit("Only development cases may be run before the protocol is frozen.")
    case = load_row(ROOT / "data" / "dev_cases.jsonl", case_id)
    key = load_row(ROOT / "data" / "dev_keys.jsonl", case_id)
    template, prompt = render_prompt("direct", case)

    started_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    call = models.call_claude(prompt)
    summary = models.summarize_claude(call["events"])
    answer, error = evaluate.parse_final(summary["result_text"])
    result = evaluate.grade(answer, error, key["a_ref"])

    init = summary["init"] or {}
    episode_id = f"{case_id}-direct-claude-{started_at[:19].replace(':', '')}"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"{episode_id}.json"
    raw_path.write_text(json.dumps(call, indent=1))

    record = {
        "episode_id": episode_id, "started_at": started_at, "split": "dev", "case_id": case_id,
        "condition": "direct", "system": "claude-code-cli", "model_requested": models.CLAUDE_MODEL,
        "argv": call["argv"], "returncode": call["returncode"], "elapsed_s": call["elapsed_s"],
        "prompt_template_sha256": sha256(template), "prompt_sha256": sha256(prompt), "prompt": prompt,
        "model_turns": 1, "tool_calls": summary["tool_use_blocks"],
        "controls": {"init_tools_empty": init.get("tools") == [], "no_tool_use": summary["tool_use_blocks"] == 0},
        "cli": summary, "response_text": summary["result_text"], "parsed": answer, "parse_error": error,
        "a_ref": key["a_ref"], "tolerance": evaluate.DEV_TOLERANCE, "tolerance_status": "provisional",
        "accepted_units": list(evaluate.ACCEPTED_UNITS), "grade": result,
        "raw_trace": str(raw_path.relative_to(ROOT)), "stderr_nonempty": bool(call["stderr"].strip()),
    }
    with EPISODES.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return record


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "direct":
        raise SystemExit("usage: python3 src/run.py direct <dev-case-id>")
    rec = run_direct(sys.argv[2])
    print(json.dumps({k: rec[k] for k in ("episode_id", "response_text", "parse_error", "grade",
                                          "a_ref", "tool_calls", "controls")}, indent=1))
    print("init:", rec["cli"]["init"])
    print("result:", rec["cli"]["result"], "rate_limit:", rec["cli"]["rate_limit"])
