"""Model adapter: Claude Code CLI on the user's subscription (no API key).

Written by Claude at Leo's direction (2026-09-21).
Isolation: built-in tools off, customizations off (CLAUDE.md, skills, plugins,
hooks, MCP), no saved session, and an empty temporary working directory.
"""
import json
import subprocess
import tempfile
import time

CLAUDE_MODEL = "claude-opus-5"
CLAUDE_ARGV = [
    "claude", "--print",
    "--model", CLAUDE_MODEL,
    "--tools", "",
    "--safe-mode",
    "--strict-mcp-config",
    "--no-session-persistence",
    "--output-format", "stream-json", "--verbose",
]
TIMEOUT_S = 180


def call_claude(prompt):
    """Send one prompt on stdin. Return the argv, exit status, timing and parsed events."""
    with tempfile.TemporaryDirectory(prefix="apb-episode-") as workdir:
        started = time.monotonic()
        try:
            proc = subprocess.run(CLAUDE_ARGV, input=prompt, capture_output=True,
                                  text=True, cwd=workdir, timeout=TIMEOUT_S)
            returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout or ""
            returncode, stderr = None, f"timeout after {TIMEOUT_S} s"
            stdout = out.decode() if isinstance(out, bytes) else out
        elapsed_s = time.monotonic() - started

    events, non_json = [], []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            non_json.append(line)
    return {"argv": CLAUDE_ARGV, "returncode": returncode, "elapsed_s": round(elapsed_s, 3),
            "events": events, "non_json_stdout": non_json, "stderr": stderr}


def summarize_claude(events):
    """Pick the reviewed, non-identifying fields from the CLI event stream."""
    s = {"init": None, "assistant_models": [], "tool_use_blocks": 0,
         "result_text": None, "result": None, "rate_limit": None}
    for e in events:
        kind = e.get("type")
        if kind == "system" and e.get("subtype") == "init":
            s["init"] = {
                "model": e.get("model"),
                "tools": e.get("tools"),
                "mcp_servers": e.get("mcp_servers"),
                "claude_code_version": e.get("claude_code_version"),
                "apiKeySource": e.get("apiKeySource"),
                "permissionMode": e.get("permissionMode"),
                "n_slash_commands": len(e.get("slash_commands") or []),
                "n_skills": len(e.get("skills") or []),
                "n_plugins": len(e.get("plugins") or []),
                "n_agents": len(e.get("agents") or []),
            }
        elif kind == "assistant":
            msg = e.get("message", {})
            s["assistant_models"].append(msg.get("model"))
            s["tool_use_blocks"] += sum(1 for c in msg.get("content", []) if c.get("type") == "tool_use")
        elif kind == "rate_limit_event":
            info = e.get("rate_limit_info", {})
            s["rate_limit"] = {k: info.get(k) for k in ("status", "overageStatus", "isUsingOverage")}
        elif kind == "result":
            usage = e.get("usage") or {}
            s["result_text"] = e.get("result")
            s["result"] = {
                "subtype": e.get("subtype"),
                "is_error": e.get("is_error"),
                "num_turns": e.get("num_turns"),
                "duration_ms": e.get("duration_ms"),
                "reported_input_tokens": sum(usage.get(k) or 0 for k in (
                    "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
                "output_tokens": usage.get("output_tokens"),
                "list_price_estimate_usd": e.get("total_cost_usd"),
            }
    return s
