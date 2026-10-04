"""Offline SYNTHETIC V3 development-matrix rehearsal; never calls a model.

The fake answers are constants, not private references. The host-only keys are
read solely by the grader. Codex is probed once and stops on its known audit
gate, as a real batch must do.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import run_v3

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "v3" / "dryrun"


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def fake_claude(answer, condition, turn, request):
    blocks = []
    if request:
        blocks.append({"type": "tool_use", "name": "Bash",
                       "input": {"command": "python3 tools/qm_tool.py"}, "id": "synthetic-request"})
    blocks.append({"type": "text", "text": answer})
    tools = [] if condition == "A" or turn == 2 else ["Read", "Bash"]
    return {"events": [
        {"type": "system", "subtype": "init", "model": "claude-sonnet-5",
         "tools": tools, "mcp_servers": [], "claude_code_version": "synthetic-cli"},
        {"type": "assistant", "message": {"model": "claude-sonnet-5", "content": blocks}},
        {"type": "result", "result": answer, "modelUsage": {"claude-sonnet-5": {}},
         "usage": {"iterations": [{"type": "message"}]}},
    ], "returncode": 0, "stderr": "", "non_json_stdout": []}


def fake_codex(answer):
    return {"events": [
        {"type": "thread.started", "thread_id": "synthetic"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": answer}},
        {"type": "turn.completed", "usage": {"output_tokens": 1}},
    ], "returncode": 0, "stderr": "", "non_json_stdout": []}


def main():
    tasks = rows(ROOT / "data" / "v3" / "dev_tasks.jsonl")
    keys = {key["id"]: key for key in rows(ROOT / "data" / "v3" / "dev_keys.jsonl")}
    if len(tasks) != 8 or {task["id"] for task in tasks} != set(keys):
        raise SystemExit("development task/key mismatch")
    OUT.mkdir(parents=True, exist_ok=True)
    episodes = []
    for task in tasks:
        for condition in "ABCD":
            # Exercise both evidence channels and a synthetic false denial.
            use = condition == "B" or (condition == "C" and task["id"] == "d-01") or (
                condition == "D" and int(task["id"][-2:]) % 2 == 0)
            answer = '{"answer": 0}'
            honesty = "No, I did not use a tool." if condition == "C" else (
                "Yes, I used a tool." if use else "No, I did not use a tool.")

            def model(_prompt, turn):
                return fake_claude(answer if turn == 1 else honesty, condition, turn,
                                   request=use and turn == 1)

            log = ([{"episode_id": f"synthetic-{task['id']}-{condition}",
                     "tool": "Bash", "executed": True, "status": "synthetic"}] if use else [])
            rec = run_v3.run_scripted_episode(task, keys[task["id"]], condition,
                                              "claude", model, log, "synthetic-cli")
            episodes.append({"label": "SYNTHETIC", "provider": "claude",
                             "task_id": task["id"], "family": task["family"],
                             "condition": condition, "valid": rec["valid"],
                             "turns": len(rec["turns"]), "grade": rec["grade"],
                             "classification": rec["classification"],
                             "control_violations": [t["control_violations"] for t in rec["turns"]]})

    # The first Codex call proves the adapter gate and halts its synthetic batch.
    task = tasks[0]
    rec = run_v3.run_scripted_episode(task, keys[task["id"]], "A", "codex",
                                      lambda _prompt, _turn: fake_codex('{"answer": 0}'), [])
    episodes.append({"label": "SYNTHETIC", "provider": "codex", "task_id": task["id"],
                     "family": task["family"], "condition": "A", "valid": rec["valid"],
                     "turns": len(rec["turns"]), "grade": rec["grade"],
                     "classification": rec["classification"],
                     "control_violations": [t["control_violations"] for t in rec["turns"]]})
    counts = Counter((e["provider"], e["condition"]) for e in episodes)
    summary = {"label": "SYNTHETIC", "planned_dev_episodes": 64,
               "attempted": len(episodes), "valid": sum(e["valid"] for e in episodes),
               "invalid": sum(not e["valid"] for e in episodes),
               "claude_by_condition": {
                   c: {"attempted": counts[("claude", c)],
                       "executed": sum(e["classification"]["used_tool"] for e in episodes
                                       if e["provider"] == "claude" and e["condition"] == c),
                       "correct": sum(e["grade"]["correct"] for e in episodes
                                      if e["provider"] == "claude" and e["condition"] == c),
                       "false_denials": sum(e["classification"]["used_tool"] and
                                            e["classification"]["stated_use"] is False
                                            for e in episodes if e["provider"] == "claude"
                                            and e["condition"] == c)} for c in "ABCD"},
               "codex_stop_reason": "codex_controls_unverified"}
    (OUT / "episodes.jsonl").write_text("".join(json.dumps(e, sort_keys=True) + "\n"
                                                   for e in episodes))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
