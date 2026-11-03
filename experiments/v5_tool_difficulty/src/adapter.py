"""Bounded Codex CLI adapter for the V5 *text action* protocol.

No native tool is part of the experiment. The harness dispatches fit_line after
parsing the participant's final JSON text. A native tool event invalidates the
call. This adapter never retries and never changes the requested model.

CLI configuration and event traces are evidence of client behaviour, not an
independent attestation of the serving model or complete provider-side activity.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import tempfile
import time


ENV_NAMES = ("HOME", "PATH", "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR")
DISABLED_FEATURES = (
    "shell_tool", "apps", "plugins", "hooks", "memories", "multi_agent", "multi_agent_v2",
    "browser_use", "browser_use_external", "computer_use", "in_app_browser", "view_image",
    "image_generation", "code_mode", "code_mode_only", "goals", "sleep_tool",
    "skill_search", "skill_mcp_dependency_install", "workspace_dependencies", "step_model_switching",
    "unbounded_connection_retries", "request_permissions_tool", "shell_snapshot",
)
CONFIG = {
    "approval_policy": "never", "agents.enabled": False, "web_search": "disabled",
    "project_doc_max_bytes": 0, "skills.bundled.enabled": False,
    "skills.include_instructions": False, "mcp_servers": {}, "allow_login_shell": False,
    "model_reasoning_summary": "none", "model_post_turn_compact_threshold_percent": 0,
    # The installed sol/astra catalog requires the host even for text output.
    # This supplies runtime infrastructure; external tool surfaces remain off.
    "features.code_mode_host": True,
}
SYSTEM = (
    "You are a participant in a bounded numerical experiment. Follow the experiment prompt. "
    "Return exactly one JSON object and no surrounding prose. The experiment's tools are requested "
    "only using the JSON action format specified in the prompt; the experiment harness handles them. "
    "Do not invoke native CLI tools, inspect local files, browse, delegate, or use other external tools. "
    "Do not treat this as a software development task."
)
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_PROMPT_BYTES = 1024 * 1024
LIMITATIONS = [
    "Codex exec JSONL does not independently attest the canonical serving model; model identity is requested/configured identity.",
    "No harness retries or model substitutions. CLI/provider-internal requests and hidden fallback cannot be independently ruled out from exec JSONL.",
    "Native surfaces are disabled by explicit client configuration; read-only is additional filesystem containment, not a complete process/container sandbox.",
    "Authentication and managed configuration still use the local installation. Ignoring user config does not erase managed instructions or all host metadata.",
    "Timeout and captured-output bytes are hard local limits; reported tokens are retrospective, not a provider-enforced token or dollar cap.",
]


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _hash_file(path):
    with open(path, "rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _environment():
    return {key: os.environ[key] for key in ENV_NAMES if key in os.environ}


def _write_new(path, data):
    path = Path(path)
    with path.open("xb") as out:
        os.chmod(path, 0o600)
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def _json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def preflight(model, effort):
    """Inspect local CLI metadata only. Does not start a model turn."""
    binary = shutil.which("codex")
    if not binary:
        raise RuntimeError("Codex CLI is unavailable")
    binary = str(Path(binary).resolve())
    env = _environment()
    version = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10, env=env, check=True)
    help_result = subprocess.run([binary, "exec", "--help"], capture_output=True, text=True, timeout=10, env=env, check=True)
    required = ("--ignore-user-config", "--ignore-rules", "--ephemeral", "--json", "--skip-git-repo-check")
    missing = [flag for flag in required if flag not in help_result.stdout]
    if missing:
        raise RuntimeError("Codex CLI lacks required flags: " + ", ".join(missing))
    catalog = subprocess.run([binary, "debug", "models", "--bundled"], capture_output=True, text=True,
                             timeout=10, env=env, check=True)
    models = json.loads(catalog.stdout)["models"]
    entry = next((item for item in models if item.get("slug") == model), None)
    if entry is None or effort not in [item["effort"] for item in entry.get("supported_reasoning_levels", [])]:
        raise ValueError("Requested model/effort is absent from the bundled CLI catalog")
    features = subprocess.run([binary, "features", "list"], capture_output=True, text=True,
                              timeout=10, env=env, check=True)
    known = {line.split()[0] for line in features.stdout.splitlines() if line.strip()}
    missing_features = sorted(set(DISABLED_FEATURES) - known)
    if missing_features:
        raise RuntimeError("CLI lacks isolation feature controls: " + ", ".join(missing_features))
    return {"binary": binary, "binary_sha256": _hash_file(binary), "version": version.stdout.strip(),
            "help_sha256": _digest(help_result.stdout.encode()), "catalog_sha256": _digest(catalog.stdout.encode()),
            "requested_model": model, "requested_effort": effort, "model_identity_evidence": "requested/configured only",
            "bundled_catalog_match": True, "account_access_verified": False,
            "native_tools": "disabled by configuration; every observed native tool event invalidates the call",
            "environment_names": sorted(env), "config": CONFIG, "disabled_features": list(DISABLED_FEATURES),
            "system_sha256": _digest(SYSTEM.encode()), "audit_limitations": LIMITATIONS}


def _command(identity, model, effort, directory):
    args = [identity["binary"], "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
            "--skip-git-repo-check", "--sandbox", "read-only", "--json", "--color", "never",
            "--model", model, "--cd", str(directory)]
    config = {**CONFIG, "model_reasoning_effort": effort,
              "model_instructions_file": str(Path(directory) / "instructions.txt")}
    for key, value in config.items():
        # JSON scalar spelling is valid TOML; the only table here is an empty one.
        args.extend(["--config", key + "=" + json.dumps(value)])
    for feature in DISABLED_FEATURES:
        args.extend(["--disable", feature])
    return args + ["-"]


def _event_problem(event):
    if not isinstance(event, dict):
        return "non_object_event"
    kind = event.get("type")
    if kind in ("error", "turn.failed"):
        return "cli_error_event"
    if kind in ("item.started", "item.updated", "item.completed"):
        item = event.get("item")
        if not isinstance(item, dict):
            return "malformed_item"
        if item.get("type") not in ("agent_message", "reasoning"):
            return "native_or_unknown_item:" + str(item.get("type"))
    elif kind not in ("thread.started", "turn.started", "turn.completed"):
        return "unknown_event:" + str(kind)
    return None


def summarize(events, returncode, requested_model):
    """Fail closed on unrecognised event types and native actions."""
    problems = [problem for event in events if (problem := _event_problem(event))]
    turns = [event for event in events if event.get("type") == "turn.completed"]
    texts = [event["item"].get("text") for event in events
             if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "agent_message"]
    if returncode != 0:
        problems.append("nonzero_exit")
    if sum(event.get("type") == "thread.started" for event in events) != 1:
        problems.append("expected_one_thread")
    if sum(event.get("type") == "turn.started" for event in events) != 1 or len(turns) != 1:
        problems.append("expected_one_turn")
    if len(texts) != 1 or not isinstance(texts[0], str) or not texts[0].strip():
        problems.append("expected_one_response")
    observed = sorted({event["model"] for event in events if isinstance(event.get("model"), str)})
    if any(model != requested_model for model in observed):
        problems.append("observed_model_mismatch")
    usage = (turns[0].get("usage") or {}) if len(turns) == 1 else {}
    tokens = {key: usage.get(key) if type(usage.get(key)) is int and usage[key] >= 0 else None
              for key in ("input_tokens", "cached_input_tokens", "output_tokens")}
    return {"text": texts[0] if not problems else None, "problems": sorted(set(problems)),
            "reported_tokens": tokens, "observed_model_fields": observed,
            "model_identity_evidence": "CLI metadata only" if observed else "requested/configured only",
            "native_tool_events": [event for event in events if (_event_problem(event) or "").startswith("native_")]}


class CodexAdapter:
    def __init__(self, model, effort, raw_dir, timeout_s=90):
        if type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or not 0 < timeout_s <= 900:
            raise ValueError("timeout_s must be positive and at most 900")
        self.model, self.effort, self.timeout_s = model, effort, timeout_s
        self.raw_dir = Path(raw_dir).resolve()
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.identity = preflight(model, effort)
        self.calls = 0
        self.totals = {"calls": 0, "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0,
                       "unknown_usage_calls": 0}

    def __call__(self, prompt):
        if not isinstance(prompt, str) or len(prompt.encode()) > MAX_PROMPT_BYTES:
            raise ValueError("Prompt must be text within the fixed byte limit")
        if _hash_file(self.identity["binary"]) != self.identity["binary_sha256"]:
            raise RuntimeError("Codex CLI changed after preflight")
        self.calls += 1
        prefix = self.raw_dir / f"call-{self.calls:04d}"
        input_path = Path(str(prefix) + "-input.txt")
        stdout_path, stderr_path = Path(str(prefix) + "-stdout.jsonl"), Path(str(prefix) + "-stderr.txt")
        manifest_path, result_path = Path(str(prefix) + "-manifest.json"), Path(str(prefix) + "-result.json")
        _write_new(input_path, prompt.encode())
        started, status, detail = time.monotonic(), "ok", None
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        events, pending = [], bytearray()
        process = None
        selector = None
        with tempfile.TemporaryDirectory(prefix="apb-v5-codex-") as directory:
            instructions = Path(directory) / "instructions.txt"
            instructions.write_text(SYSTEM)
            args, env = _command(self.identity, self.model, self.effort, directory), _environment()
            manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "identity": self.identity,
                        "argv": args, "environment_names": sorted(env), "cwd": directory,
                        "prompt_sha256": _digest(prompt.encode()), "system": SYSTEM,
                        "limits": {"timeout_s": self.timeout_s, "captured_output_bytes": MAX_OUTPUT_BYTES,
                                   "prompt_bytes": MAX_PROMPT_BYTES, "harness_retries": 0},
                        "call_index": self.calls}
            _write_new(manifest_path, _json_bytes(manifest))
            with input_path.open("rb") as source, stdout_path.open("xb") as stdout_file, stderr_path.open("xb") as stderr_file:
                os.chmod(stdout_path, 0o600)
                os.chmod(stderr_path, 0o600)
                outputs = {"stdout": stdout_file, "stderr": stderr_file}
                try:
                    process = subprocess.Popen(args, stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               cwd=directory, env=env, start_new_session=True)
                    selector = selectors.DefaultSelector()
                    for name in ("stdout", "stderr"):
                        stream = getattr(process, name)
                        os.set_blocking(stream.fileno(), False)
                        selector.register(stream, selectors.EVENT_READ, name)
                    killed = False
                    drain_deadline = None
                    while selector.get_map():
                        if not killed and time.monotonic() - started >= self.timeout_s:
                            status, detail = "timeout", "wall_clock_limit"
                        if status != "ok" and not killed:
                            self._kill(process)
                            killed = True
                            drain_deadline = time.monotonic() + .5
                        if drain_deadline is not None and time.monotonic() >= drain_deadline:
                            # An exited group leader can leave inherited pipes
                            # open in a descendant. Never wait without a bound.
                            status, detail = "adapter_error", "termination_pipe_drain_timeout"
                            break
                        for key, _ in selector.select(timeout=.05):
                            chunk = os.read(key.fileobj.fileno(), 65536)
                            if not chunk:
                                selector.unregister(key.fileobj)
                                continue
                            remaining = max(0, MAX_OUTPUT_BYTES - sum(len(value) for value in buffers.values()))
                            if len(chunk) > remaining:
                                status, detail = "output_limit", "captured_output_byte_limit"
                                chunk = chunk[:remaining]
                            name = key.data
                            buffers[name].extend(chunk)
                            outputs[name].write(chunk)
                            outputs[name].flush()
                            os.fsync(outputs[name].fileno())
                            if name == "stdout":
                                pending.extend(chunk)
                                while b"\n" in pending:
                                    line, _, tail = pending.partition(b"\n")
                                    pending = bytearray(tail)
                                    if not line.strip():
                                        continue
                                    try:
                                        event = json.loads(line)
                                    except (ValueError, UnicodeDecodeError):
                                        status, detail = "invalid_trace", "non_json_stdout"
                                        continue
                                    if not isinstance(event, dict):
                                        status, detail = "invalid_trace", "non_object_event"
                                        continue
                                    events.append(event)
                                    problem = _event_problem(event)
                                    if problem:
                                        status, detail = "invalid_trace", problem
                            elif re.search(rb"(?i)(reconnecting|retrying|falling back|fallback model)", buffers["stderr"]):
                                status, detail = "invalid_trace", "retry_or_fallback_diagnostic"
                    selector.close()
                    process.wait(timeout=5)
                except (OSError, subprocess.SubprocessError) as exc:
                    status, detail = "adapter_error", type(exc).__name__ + ": " + str(exc)
                    if process is not None:
                        try:
                            # Do not repeat the group signal when that signal was
                            # itself denied for a process which is still alive.
                            if not isinstance(exc, PermissionError):
                                self._kill(process)
                            process.wait(timeout=.2 if isinstance(exc, PermissionError) else 5)
                        except (OSError, subprocess.SubprocessError) as cleanup:
                            detail += "; termination_failed:" + type(cleanup).__name__
                finally:
                    if selector is not None:
                        selector.close()
                    if process is not None:
                        for stream in (process.stdout, process.stderr):
                            if stream is not None:
                                stream.close()
                    for stream in outputs.values():
                        stream.flush()
                        os.fsync(stream.fileno())
        if pending.strip():
            try:
                event = json.loads(pending)
                if isinstance(event, dict):
                    events.append(event)
                else:
                    raise ValueError("non-object")
            except (ValueError, UnicodeDecodeError):
                if status == "ok":
                    status, detail = "invalid_trace", "incomplete_json_stdout"
                events.append({"type": "adapter.malformed_partial_stdout"})
        result = summarize(events, process.returncode if process is not None else None, self.model)
        if status == "ok" and result["problems"]:
            status, detail = "invalid_trace", ";".join(result["problems"])
        self.totals["calls"] += 1
        if any(value is None for value in result["reported_tokens"].values()):
            self.totals["unknown_usage_calls"] += 1
        for key, value in result["reported_tokens"].items():
            self.totals[key] += value or 0
        started_threads = sum(event.get("type") == "thread.started" for event in events)
        started_turns = sum(event.get("type") == "turn.started" for event in events)
        completed_turns = sum(event.get("type") == "turn.completed" for event in events)
        expected_timeout_problems = {"nonzero_exit", "expected_one_turn", "expected_one_response"}
        timeout_after_clean_start = (status == "timeout" and started_threads == started_turns == 1
                                    and completed_turns == 0
                                    and set(result["problems"]) <= expected_timeout_problems
                                    and not re.search(rb"(?i)(reconnecting|retrying|falling back|fallback model)", buffers["stderr"]))
        meta = {**result, "requested_model": self.model, "requested_effort": self.effort,
                "usage": result["reported_tokens"],
                "started_threads": started_threads, "started_turns": started_turns,
                "completed_turns": completed_turns,
                "timeout_after_clean_turn_start": bool(timeout_after_clean_start),
                "status_detail": detail, "elapsed_s": round(time.monotonic() - started, 3),
                "returncode": process.returncode if process is not None else None,
                "raw_manifest": str(manifest_path), "raw_stdout": str(stdout_path), "raw_stderr": str(stderr_path),
                "stdout_sha256": _digest(bytes(buffers["stdout"])), "stderr_sha256": _digest(bytes(buffers["stderr"])),
                "captured_bytes": sum(len(value) for value in buffers.values()),
                "aggregate_usage": dict(self.totals), "audit_limitations": LIMITATIONS}
        meta.pop("text")
        answer = {"text": result["text"] if status == "ok" else None, "status": status, "meta": meta,
                  "output_tokens": result["reported_tokens"]["output_tokens"]}
        _write_new(result_path, _json_bytes(answer))
        return answer

    @staticmethod
    def _kill(process):
        # poll() reaps an already-exited child. On macOS killpg can report EPERM
        # during the exit/reap race, rather than the usual ESRCH.
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            process.poll()
        except PermissionError:
            try:
                process.wait(timeout=.1)
            except subprocess.TimeoutExpired:
                # A live, unkillable process is a genuine containment failure.
                raise PermissionError("Cannot terminate the live CLI process group") from None
