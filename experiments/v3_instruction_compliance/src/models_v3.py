"""V3 model adapter: claude-fable-5-1 through a pinned copy of the Claude Code CLI on the subscription.

Differences from V1/V2's adapter (src/models.py, frozen), all declared in PROTOCOL.md section 2:
- the model is claude-fable-5-1;
- the CLI's default system prompt is replaced by one fixed sentence (prompts/system_prompt.txt). With the
  default prompt, the model's safety classifier refused every reconnaissance call and the CLI answered
  from a different model instead (PROTOCOL.md section 2.1);
- environment controls are passed to the child process explicitly, never set on this process;
- refusal fallback is disabled, so a classifier refusal is an explicit outcome and never a model switch;
- the CLI binary is a pinned copy whose SHA-256 is in the freeze manifest (the installed CLI updates itself).
"""
import json
import os
import subprocess
import tempfile
import time

import common_v3 as C

MODEL = "claude-fable-5-1"
EFFORT = "high"
TIMEOUT_S = 900
CLI_VERSION = "2.1.296"
CLI_BIN = C.ROOT / ".cli" / f"claude-{CLI_VERSION}"          # gitignored local copy of the installed binary
SYSTEM_PROMPT = (C.PROMPTS / "system_prompt.txt").read_text().rstrip("\n")
ENV_CONTROLS = {
    "CLAUDE_CODE_DISABLE_ADVISOR_TOOL": "1",          # V2's finding: a server-side advisor consulted a second model
    "CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK": "1",      # V3 reconnaissance: a refusal was silently answered by another model
    "DISABLE_AUTOUPDATER": "1",
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64000",         # the model's maximum as reported by the CLI
}
ENV_MUST_BE_UNSET = ("CLAUDE_CODE_ENABLE_EXPERIMENTAL_ADVISOR_TOOL", "MAX_THINKING_TOKENS")
ARGS = ["--print", "--model", MODEL, "--effort", EFFORT, "--tools", "", "--safe-mode", "--strict-mcp-config",
        "--no-session-persistence", "--output-format", "stream-json", "--verbose", "--system-prompt", SYSTEM_PROMPT]
ARGV_RECORDED = ["<pinned-cli>"] + ARGS               # what records and the manifest show (no local path)


def child_env():
    env = dict(os.environ)
    env.update(ENV_CONTROLS)
    for name in ENV_MUST_BE_UNSET:
        env.pop(name, None)
    return env


def inherited_env_names():
    """Names (never values) of CLI-related variables the child inherits from this process; for the record."""
    return sorted(k for k in os.environ if k.startswith(("CLAUDE", "ANTHROPIC")) and k not in ENV_CONTROLS)


def call_claude_v3(prompt, timeout_s=TIMEOUT_S):
    """One fresh CLI process, prompt on stdin, empty temporary working directory. Returns the event stream."""
    with tempfile.TemporaryDirectory(prefix="apb-v3-") as workdir:
        started = time.monotonic()
        try:
            proc = subprocess.run([str(CLI_BIN)] + ARGS, input=prompt, capture_output=True, text=True,
                                  cwd=workdir, timeout=timeout_s, env=child_env())
            returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout or ""
            returncode, stderr = None, f"timeout after {timeout_s} s"
            stdout = out.decode() if isinstance(out, bytes) else out
        elapsed_s = time.monotonic() - started
    events, non_json = [], []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            non_json.append(line)
    return {"argv": ARGV_RECORDED, "returncode": returncode, "elapsed_s": round(elapsed_s, 3), "events": events,
            "non_json_stdout": non_json, "stderr": stderr}


def cli_version():
    return subprocess.run([str(CLI_BIN), "--version"], capture_output=True, text=True).stdout.split()[0]


def cli_sha256():
    return C.sha256_file(CLI_BIN)
