"""Local V3 sandbox checks; no model calls or scored runs."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import sandbox_v3  # noqa: E402


TASK = {"id": "d-01", "family": "numeric_qm", "group": "easy", "kind": "ground",
        "parameters": {"n": 2}, "question": "Find an eigenvalue."}


class SandboxTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "results" / "v3"
        parent.mkdir(parents=True, exist_ok=True)
        self.audit = tempfile.TemporaryDirectory(prefix="test-audit-", dir=parent)

    def tearDown(self):
        self.audit.cleanup()

    def test_only_public_task_and_tool_are_staged_and_log_is_external(self):
        for condition in "BCD":
            with self.subTest(condition=condition):
                with sandbox_v3.EpisodeSandbox(TASK, condition, "episode-1", self.audit.name) as box:
                    self.assertEqual({p.relative_to(box.path).as_posix() for p in box.path.rglob("*")},
                                     {"task.json", "tools", "tools/qm_tool.py"})
                    self.assertEqual(json.loads((box.path / "task.json").read_text()), TASK)
                    self.assertFalse(any("key" in p.name or "answer" in p.name for p in box.path.rglob("*")))
                    self.assertFalse(box.log_path.is_relative_to(box.path))
                    self.assertFalse(box.log_path.exists())
                    result = box.invoke_tool({"operation": "eigenvalues", "matrix": [[1, 0], [0, 2]]})
                    self.assertEqual(result.returncode, 0, result.stderr)
                    values = json.loads(result.stdout)["eigenvalues"]
                    self.assertEqual({v["real"] for v in values}, {1.0, 2.0})
                    lines = box.log_path.read_text().splitlines()
                    self.assertEqual(len(lines), 1)
                    event = json.loads(lines[0])
                    self.assertEqual(event["episode_id"], "episode-1")
                    self.assertEqual(event["args"]["operation"], "eigenvalues")
                    self.assertIn("timestamp", event)
                    self.assertEqual({p.relative_to(box.path).as_posix() for p in box.path.rglob("*")},
                                     {"task.json", "tools", "tools/qm_tool.py"})

    def test_condition_a_has_no_tool_file_or_execution(self):
        with sandbox_v3.EpisodeSandbox(TASK, "A", "episode-a", self.audit.name) as box:
            self.assertEqual([p.name for p in box.path.iterdir()], ["task.json"])
            with self.assertRaises(PermissionError):
                box.invoke_tool({"operation": "eigenvalues", "matrix": [[1]]})
            self.assertFalse(box.log_path.exists())

    def test_rejects_private_task_fields_and_fresh_directories(self):
        with self.assertRaises(ValueError):
            sandbox_v3.EpisodeSandbox({**TASK, "answer": 1}, "B", "episode", self.audit.name)
        with sandbox_v3.EpisodeSandbox(TASK, "B", "one", self.audit.name) as first:
            first_path = first.path
        with sandbox_v3.EpisodeSandbox(TASK, "B", "two", self.audit.name) as second:
            self.assertNotEqual(second.path, first_path)
            self.assertFalse(first_path.exists())

    def test_remaining_operations_and_logged_failure(self):
        with sandbox_v3.EpisodeSandbox(TASK, "B", "operations", self.audit.name) as box:
            cases = [
                ({"operation": "root", "expression": "x**2 - 2", "bracket": [1, 2]}, "root"),
                ({"operation": "expm", "matrix": [[0, 0], [0, 0]], "time": 1,
                  "state": [1, 0]}, "state"),
                ({"operation": "simplify", "expression": "x + x", "variables": ["x"]}, "result"),
                ({"operation": "integrate", "expression": "x", "variables": ["x"],
                  "variable": "x", "bounds": [0, 1]}, "result"),
            ]
            for args, field in cases:
                result = box.invoke_tool(args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(field, json.loads(result.stdout))
            bad = box.invoke_tool({"operation": "simplify", "expression": "__import__('os').getcwd()",
                                   "variables": []})
            self.assertNotEqual(bad.returncode, 0)
            self.assertEqual(len(box.log_path.read_text().splitlines()), len(cases) + 1)


if __name__ == "__main__":
    unittest.main()
