"""Create a fresh, minimal V3 answer-turn directory and invoke its fixed tool.

Only the public task is staged. The host owns the audit directory and never
passes its path to a model-facing prompt or file. This module deliberately
exposes a fixed JSON tool interface, not arbitrary shell execution.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_TEMPLATE = ROOT / "tools_v3" / "qm_tool.py"
SANDBOX_PARENT = ROOT / "results" / "v3" / "sandboxes"
CONDITIONS = ("A", "B", "C", "D")
PUBLIC_FIELDS = {"id", "family", "group", "kind", "parameters", "question"}
LOG_ENV = "APB_V3_TOOL_LOG"
EPISODE_ENV = "APB_V3_EPISODE_ID"


class EpisodeSandbox:
    """Context-managed episode files; the audit log persists in ``audit_dir``."""

    def __init__(self, task, condition, episode_id, audit_dir):
        if condition not in CONDITIONS:
            raise ValueError("unknown V3 condition")
        if not isinstance(task, dict) or set(task) != PUBLIC_FIELDS:
            raise ValueError("task must contain only the public task fields")
        if not isinstance(task["parameters"], dict) or not isinstance(task["question"], str):
            raise ValueError("invalid public task")
        if not isinstance(episode_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", episode_id):
            raise ValueError("invalid episode id")
        self.task = task
        self.condition = condition
        self.episode_id = episode_id
        self.audit_dir = Path(audit_dir).resolve(strict=True)
        if not self.audit_dir.is_dir():
            raise ValueError("audit_dir must be an existing directory")
        self._temporary = None
        self.path = None
        self.log_path = self.audit_dir / f"{episode_id}-{uuid.uuid4().hex}.jsonl"

    def __enter__(self):
        SANDBOX_PARENT.mkdir(parents=True, exist_ok=True)
        self._temporary = tempfile.TemporaryDirectory(prefix="apb-v3-episode-", dir=SANDBOX_PARENT)
        self.path = Path(self._temporary.name).resolve()
        if self.audit_dir == self.path or self.path in self.audit_dir.parents or self.audit_dir in self.path.parents:
            self._temporary.cleanup()
            self._temporary = None
            raise ValueError("audit log must be outside the sandbox")
        (self.path / "task.json").write_text(json.dumps(self.task, sort_keys=True) + "\n")
        if self.condition != "A":
            tool_dir = self.path / "tools"
            tool_dir.mkdir()
            shutil.copyfile(TOOL_TEMPLATE, tool_dir / "qm_tool.py")
        return self

    def __exit__(self, *_):
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
        self.path = None

    def invoke_tool(self, args, timeout=30):
        """Execute one JSON request through the staged tool; A has no tool."""
        if self.path is None:
            raise RuntimeError("episode sandbox is closed")
        if self.condition == "A":
            raise PermissionError("condition A has no computational tool")
        if not isinstance(args, dict):
            raise ValueError("tool arguments must be a JSON object")
        env = {"PATH": os.defpath, "PYTHONNOUSERSITE": "1",
               LOG_ENV: str(self.log_path), EPISODE_ENV: self.episode_id}
        return subprocess.run(
            [sys.executable, str(self.path / "tools" / "qm_tool.py")],
            input=json.dumps(args), text=True, capture_output=True,
            cwd=self.path, env=env, timeout=timeout, check=False,
        )
