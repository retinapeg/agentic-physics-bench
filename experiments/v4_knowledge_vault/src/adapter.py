"""V4 extension of the existing Claude CLI adapter and V3 provenance checks."""
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time

import common
from models_v3 import child_env
from controls_v3 import summarize_call_v3, control_violations_v3

MODELS = ["claude-fable-5-1", "claude-opus-5"]
REQUIRED_FLAGS = ["--safe-mode", "--tools", "--strict-mcp-config", "--system-prompt",
                  "--no-session-persistence", "--max-budget-usd", "--output-format", "--effort"]


def environment():
    env = child_env()
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "512"
    return env


def preflight():
    binary = shutil.which("claude")
    if not binary:
        return {"ready": False, "reason": "Claude CLI is not installed. Historical replay remains available."}
    try:
        version = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10, env=environment())
        help_result = subprocess.run([binary, "--help"], capture_output=True, text=True, timeout=10, env=environment())
        turns_probe = subprocess.run([binary, "--max-turns", "1", "--help"], capture_output=True, text=True, timeout=10, env=environment())
        missing = [flag for flag in REQUIRED_FLAGS if flag not in help_result.stdout]
        return {"ready": not missing and version.returncode == help_result.returncode == turns_probe.returncode == 0,
                "version": version.stdout.split()[0], "binary": str(os.path.realpath(binary)),
                "binary_sha256": common.file_hash(binary), "help_sha256": common.digest(help_result.stdout),
                "missing_flags": missing, "checked_at": common.now(),
                "advisor_replication": "Not enabled. Current help does not establish an advisor-enable contract.",
                "cost_semantics": "CLI list-price estimates, not billed charges. CLI USD limits may overshoot within a call; calls, output tokens and time are independently bounded."}
    except (OSError, subprocess.SubprocessError, IndexError) as exc:
        return {"ready": False, "reason": str(exc)}


class ClaudeAdapter:
    def __init__(self, identity):
        self.identity = identity
        self.inventories = {}

    def call(self, role, model, system, prompt, usd_limit, timeout_s, cancelled):
        if model not in MODELS or not self.identity.get("ready"):
            raise ValueError("Model configuration is unavailable")
        binary = self.identity["binary"]
        if common.file_hash(binary) != self.identity["binary_sha256"]:
            raise ValueError("CLI binary changed since the run was frozen")
        args = [binary, "--print", "--model", model, "--effort", "low", "--tools", "",
                "--safe-mode", "--strict-mcp-config", "--no-session-persistence",
                "--output-format", "stream-json", "--verbose", "--system-prompt", system,
                "--max-budget-usd", f"{usd_limit:.6f}", "--max-turns", "1"]
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="apb-v4-") as directory:
            process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, cwd=directory, env=environment(), start_new_session=True)
            timed_out = False
            initial = True
            while True:
                try:
                    stdout, stderr = process.communicate(input=prompt if initial else None, timeout=.25)
                    break
                except subprocess.TimeoutExpired:
                    initial = False
                    if cancelled.is_set() or time.monotonic() - started >= timeout_s:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        stdout, stderr = process.communicate()
                        timed_out = True
                        break
        events, non_json = [], []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
                if isinstance(event, dict):
                    events.append(event)
                else:
                    non_json.append(line)
            except ValueError:
                non_json.append(line)
        call = {"argv": ["<sha256-pinned-cli>"] + args[1:], "returncode": None if timed_out else process.returncode,
                "elapsed_s": round(time.monotonic()-started, 3), "events": events,
                "non_json_stdout": non_json, "stderr": stderr, "timed_out": timed_out}
        summary = summarize_call_v3(call)
        violations = control_violations_v3(call, summary, model, self.identity["version"], self.inventories.get(role))
        if summary.get("result", {}) and summary["result"].get("num_turns") != 1:
            violations.append("v4_single_turn_required")
        if summary["inventory"] and role not in self.inventories:
            self.inventories[role] = summary["inventory"]
        if non_json:
            violations.append("non_json_stdout")
        if summary["result_matches_assistant_text"] is False:
            violations.append("result_text_mismatch")
        output_tokens=(summary.get("result") or {}).get("output_tokens")
        if type(output_tokens) is int and output_tokens > 512:
            violations.append("output_token_budget_exceeded")
        if summary.get("content_types") and any(t not in ("text", "thinking") for t in summary["content_types"]):
            violations.append("unexpected_content_type")
        if timed_out:
            violations.append("cancelled" if cancelled.is_set() else "timeout")
        return call, summary, sorted(set(violations))
