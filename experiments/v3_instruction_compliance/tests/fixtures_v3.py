"""Shared fixtures for the V3 tests (no model calls). Trace shapes follow real Claude Code 2.1.296 output."""
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = EXP.parents[1]
for p in (str(EXP / "src"), str(ROOT / "src"), str(ROOT / "tests"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import common_v3 as C  # noqa: E402
import models_v3  # noqa: E402
import run_v3  # noqa: E402
import tasks_v3  # noqa: E402

MODEL = models_v3.MODEL
VERSION = models_v3.CLI_VERSION
INVENTORY = {"skills": ["a-skill", "b-skill"], "plugins": ["a-plugin"], "agents": ["Explore", "general-purpose"],
             "slash_commands": ["a-skill", "b-skill", "help"]}
EXPECTED = None  # filled below


def init_event(model=MODEL, version=VERSION, tools=None, mcp=None, fast="off", inventory=INVENTORY):
    return {"type": "system", "subtype": "init", "model": model, "tools": [] if tools is None else tools,
            "mcp_servers": [] if mcp is None else mcp, "claude_code_version": version, "apiKeySource": "none",
            "permissionMode": "default", "fast_mode_state": fast, "session_id": "SECRET-SESSION",
            "cwd": "/private/tmp/secret-cwd", "skills": inventory["skills"],
            "plugins": [{"name": n, "path": f"/Users/someone/.claude/plugins/{n}"} for n in inventory["plugins"]],
            "agents": inventory["agents"], "slash_commands": inventory["slash_commands"]}


def fake_call_v3(text, model=MODEL, version=VERSION, init=True, tools=None, mcp=None, fast="off", result_fast="off",
                 inventory=INVENTORY, native_tool=False, advisor=False, advisor_model=None, extra_models=(),
                 iterations=(), num_turns=1, stop_reason="end_turn", stderr="", overage=False, status="allowed",
                 windows=(0.05, 0.05), timeout=False, refusal=None, is_error=False, api_error_status=None,
                 subagents=0, permission_denials=(), canonical=None, drop_usage=False, returncode=0, thinking=120,
                 assistant_model=None):
    """One CLI call's event stream. refusal: None, "no_fallback" (explicit refusal) or "fallback" (model switched)."""
    if timeout:
        return {"argv": models_v3.ARGV_RECORDED, "returncode": None, "elapsed_s": 900.0, "events": [],
                "non_json_stdout": [], "stderr": "timeout after 900 s"}
    events = [init_event(model, version, tools, mcp, fast, inventory)] if init else []
    events.append({"type": "rate_limit_event", "rate_limit_info": {
        "status": status, "overageStatus": "rejected", "isUsingOverage": overage,
        "unifiedWindows": {"five_hour": {"utilization": windows[0]}, "seven_day": {"utilization": windows[1]}}}})
    usage_models = {model: {"canonicalModel": canonical or model, "maxOutputTokens": 64000, "outputTokens": 10}}
    answer_model = assistant_model or model
    if refusal == "no_fallback":
        events.append({"type": "system", "subtype": "model_refusal_no_fallback", "original_model": model,
                       "api_refusal_category": "cyber"})
        events.append({"type": "assistant", "message": {"model": "<synthetic>", "content": [{"type": "text", "text": "API Error"}]}})
        events.append({"type": "result", "subtype": "success", "is_error": True, "result": "API Error: safeguards flagged this message",
                       "num_turns": 2, "stop_reason": "refusal", "terminal_reason": "api_error", "fast_mode_state": result_fast,
                       "api_error_status": None, "permission_denials": [], "safety_stops": 2,
                       "subagent_stats": {"spawned": 0, "by_type": {}},
                       "usage": {"output_tokens": 0, "output_tokens_details": {"thinking_tokens": 0}, "iterations": []},
                       "modelUsage": usage_models})
        return {"argv": models_v3.ARGV_RECORDED, "returncode": 1, "elapsed_s": 3.0, "events": events,
                "non_json_stdout": [], "stderr": ""}
    if refusal == "fallback":
        events.append({"type": "system", "subtype": "model_refusal_fallback", "original_model": model,
                       "fallback_model": "claude-opus-4-8", "api_refusal_category": "cyber"})
        answer_model, num_turns = "claude-opus-4-8", 2
        usage_models["claude-opus-4-8"] = {"canonicalModel": "claude-opus-4-8", "maxOutputTokens": 64000, "outputTokens": 4}
    for extra in extra_models:
        usage_models[extra] = {"canonicalModel": extra, "maxOutputTokens": 64000, "outputTokens": 99}
    content = [{"type": "thinking", "thinking": "", "signature": "sig"}]
    iters = [{"type": t} for t in iterations]
    if advisor:      # real shape: a server-side tool block with an id and a dict input, then its redacted result
        content += [{"type": "server_tool_use", "id": "srvtoolu_1", "name": "advisor", "input": {}},
                    {"type": "advisor_tool_result", "tool_use_id": "srvtoolu_1",
                     "content": {"type": "advisor_redacted_result", "encrypted_content": "xxxx"}}]
        iters = [{"type": "message"}, {"type": "advisor_message", "model": advisor_model or model}, {"type": "message"}]
    if native_tool:
        content.append({"type": "tool_use", "name": "Bash", "input": {}})
    content.append({"type": "text", "text": text})
    events.append({"type": "assistant", "message": {"model": answer_model, "content": content}})
    events.append({"type": "result", "subtype": "success", "is_error": is_error, "result": text, "num_turns": num_turns,
                   "stop_reason": stop_reason, "terminal_reason": "completed", "duration_ms": 1234,
                   "fast_mode_state": result_fast, "api_error_status": api_error_status,
                   "permission_denials": list(permission_denials), "safety_stops": 0,
                   "subagent_stats": {"spawned": subagents, "by_type": {"x": subagents} if subagents else {}},
                   "usage": {"input_tokens": 2, "cache_creation_input_tokens": 800, "cache_read_input_tokens": 0,
                             "output_tokens": 300, "output_tokens_details": {"thinking_tokens": thinking}, "iterations": iters},
                   "modelUsage": {} if drop_usage else usage_models})
    return {"argv": models_v3.ARGV_RECORDED, "returncode": returncode, "elapsed_s": 1.5, "events": events,
            "non_json_stdout": [], "stderr": stderr}


import controls_v3  # noqa: E402
EXPECTED = {"model": MODEL, "cli_version": VERSION,
            "inventory": controls_v3.inventory_of(init_event())}


def request(case_id, name="fit_line", arguments=None, **extra):
    obj = {"type": "tool", "name": name, "arguments": {"case_id": case_id} if arguments is None else arguments}
    obj.update(extra)
    return json.dumps(obj)


def final(value, units="m/s^2", **extra):
    obj = {"type": "final", "acceleration": value, "units": units}
    obj.update(extra)
    return json.dumps(obj)


def scripted(*replies):
    """A fake call_model for agent_v3: each reply is text, None, or (text, meta)."""
    prompts = []

    def call_model(prompt, turn):
        prompts.append((turn, prompt))
        r = replies[len(prompts) - 1]
        if isinstance(r, tuple):
            return r
        return r, {"truncated": False, "refused": False}
    return call_model, prompts


class Sandbox:
    """Redirects every V3 output path to a temporary directory for one test."""
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.results = root / "results"
        self.patches = [mock.patch.object(C, "RESULTS", self.results), mock.patch.object(C, "RAW", self.results / "raw"),
                        mock.patch.object(run_v3, "PREFREEZE", self.results / "prefreeze_calls.jsonl")]

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def episode_a(self, task_id, cell, *calls, rep=1, split="dev", expected=None):
        with mock.patch.object(models_v3, "call_claude_v3", side_effect=list(calls)) as fake:
            rec = run_v3.run_episode_a(split, {"task_id": task_id, "cell": cell, "rep": rep}, "test-run", expected or EXPECTED)
        return rec, fake.call_count

    def episode_b(self, item_id, frame, *calls, rep=1, split="dev", expected=None):
        with mock.patch.object(models_v3, "call_claude_v3", side_effect=list(calls)) as fake:
            rec = run_v3.run_episode_b(split, {"item_id": item_id, "frame": frame, "rep": rep}, "test-run", expected or EXPECTED)
        return rec, fake.call_count


def dev_case(task_id="e1-02"):
    cases, keys, _ = tasks_v3.load("dev")
    return cases[task_id], keys[task_id]
