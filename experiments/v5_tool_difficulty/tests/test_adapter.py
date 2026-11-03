"""Offline adapter checks. Fake local executables never call a model."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


MODULE = Path(__file__).resolve().parents[1] / "src" / "adapter.py"
spec = importlib.util.spec_from_file_location("v5_adapter_test_subject", MODULE)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def trace(text='{"type":"final","acceleration":1.0,"units":"m/s^2"}'):
    return [
        {"type": "thread.started", "thread_id": "fixture"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"id": "x", "type": "agent_message", "text": text}},
        {"type": "turn.completed", "usage": {"input_tokens": 12, "cached_input_tokens": 2, "output_tokens": 8}},
    ]


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.binary = self.root / "fake-codex"

    def make(self, source, timeout=2):
        self.binary.write_text("#!" + sys.executable + "\n" + source)
        self.binary.chmod(0o700)
        identity = {"binary": str(self.binary), "binary_sha256": adapter._hash_file(self.binary),
                    "version": "fixture", "requested_model": "test-model", "requested_effort": "low"}
        with patch.object(adapter, "preflight", return_value=identity):
            return adapter.CodexAdapter("test-model", "low", self.root / "raw", timeout_s=timeout)

    def emitting(self, events):
        return "import json\nfor e in " + repr(events) + ":\n print(json.dumps(e), flush=True)\n"

    def test_clean_call_records_identity_usage_and_exclusive_evidence(self):
        runner = self.make(self.emitting(trace()))
        response = runner("fixture prompt")
        self.assertEqual(response["status"], "ok")
        self.assertIn('"type":"final"', response["text"])
        self.assertEqual(runner.totals["output_tokens"], 8)
        meta = response["meta"]
        manifest = json.loads(Path(meta["raw_manifest"]).read_text())
        self.assertIn("--ignore-user-config", manifest["argv"])
        self.assertIn("--ignore-rules", manifest["argv"])
        self.assertIn("shell_tool", manifest["argv"])
        self.assertIn('web_search="disabled"', manifest["argv"])
        self.assertIn("agents.enabled=false", manifest["argv"])
        self.assertIn("read-only", manifest["argv"])
        self.assertNotIn("CODEX_THREAD_ID", manifest["environment_names"])
        self.assertFalse(Path(manifest["cwd"]).exists())
        self.assertEqual(Path(meta["raw_stdout"]).stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            adapter._write_new(Path(meta["raw_stdout"]), b"replacement")

    def test_fresh_work_directory_every_call(self):
        runner = self.make(self.emitting(trace()))
        first, second = runner("one"), runner("two")
        manifests = [json.loads(Path(value["meta"]["raw_manifest"]).read_text()) for value in (first, second)]
        self.assertNotEqual(manifests[0]["cwd"], manifests[1]["cwd"])
        self.assertEqual(runner.totals["calls"], 2)
        self.assertEqual(runner.totals["input_tokens"], 24)

    def test_native_tool_attempt_kills_before_later_output(self):
        events = trace()[:2] + [{"type": "item.started", "item": {"type": "command_execution", "command": "fixture"}}]
        runner = self.make(self.emitting(events) + "import time\ntime.sleep(5)\nprint('should not run', flush=True)\n")
        response = runner("fixture")
        self.assertEqual(response["status"], "invalid_trace")
        self.assertIsNone(response["text"])
        self.assertIn("native_or_unknown_item", response["meta"]["status_detail"])
        self.assertLess(response["meta"]["elapsed_s"], 2)
        self.assertNotIn("should not run", Path(response["meta"]["raw_stdout"]).read_text())

    def test_timeout_preserves_partial_trace(self):
        # Print the readiness evidence before importing anything or blocking;
        # allow realistic interpreter startup while keeping the test bounded.
        ready = "".join("print(" + repr(json.dumps(event)) + ", flush=True)\n" for event in trace()[:2])
        runner = self.make(ready + "import time\ntime.sleep(5)\n", timeout=1.5)
        response = runner("fixture")
        self.assertEqual(response["status"], "timeout")
        self.assertIsNone(response["text"])
        self.assertIn("thread.started", Path(response["meta"]["raw_stdout"]).read_text())
        self.assertTrue(Path(response["meta"]["raw_manifest"]).exists())
        self.assertTrue(response["meta"]["timeout_after_clean_turn_start"])
        self.assertEqual(response["meta"]["started_turns"], 1)
        self.assertEqual(response["meta"]["completed_turns"], 0)

    def test_output_cap_stops_and_bounds_persisted_bytes(self):
        runner = self.make("import sys,time\nsys.stderr.write('z'*10000)\nsys.stderr.flush()\ntime.sleep(5)\n")
        with patch.object(adapter, "MAX_OUTPUT_BYTES", 512):
            response = runner("fixture")
        self.assertEqual(response["status"], "output_limit")
        self.assertEqual(response["meta"]["captured_bytes"], 512)
        self.assertIsNone(response["text"])

    def test_malformed_output_and_retry_diagnostic_are_invalid(self):
        for source in ("print('not JSON', flush=True)\n", "import sys\nprint('Reconnecting... retrying', file=sys.stderr, flush=True)\n"):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as raw:
                runner = self.make(source)
                runner.raw_dir = Path(raw)
                response = runner("fixture")
                self.assertEqual(response["status"], "invalid_trace")
                self.assertIsNone(response["text"])

    def test_changed_binary_refuses_before_call(self):
        runner = self.make(self.emitting(trace()))
        self.binary.write_text("changed")
        with self.assertRaisesRegex(RuntimeError, "changed"):
            runner("fixture")
        self.assertEqual(runner.calls, 0)

    def test_kill_reaps_exited_child_without_signalling(self):
        process = Mock(pid=123, returncode=0)
        process.poll.return_value = 0
        with patch.object(adapter.os, "killpg") as killpg:
            adapter.CodexAdapter._kill(process)
        killpg.assert_not_called()

    def test_kill_exit_race_eperm_is_reaped_but_live_eperm_is_error(self):
        exited = Mock(pid=123)
        exited.poll.return_value = None
        exited.wait.return_value = 0
        with patch.object(adapter.os, "killpg", side_effect=PermissionError("exit race")) as killpg:
            adapter.CodexAdapter._kill(exited)
        killpg.assert_called_once()
        exited.wait.assert_called_once_with(timeout=.1)
        live = Mock(pid=124)
        live.poll.return_value = None
        live.wait.side_effect = adapter.subprocess.TimeoutExpired("fixture", .1)
        with patch.object(adapter.os, "killpg", side_effect=PermissionError("live")):
            with self.assertRaisesRegex(PermissionError, "live CLI"):
                adapter.CodexAdapter._kill(live)

    @unittest.skipUnless(hasattr(os, "fork"), "POSIX inherited-pipe regression")
    def test_exited_leader_with_inherited_pipe_has_bounded_drain(self):
        runner = self.make("import os,time\n"
                           "if os.fork() == 0:\n time.sleep(10)\n os._exit(0)\n"
                           "print('not JSON', flush=True)\nos._exit(0)\n")
        spawned = []
        actual_popen = adapter.subprocess.Popen

        def spawn(*args, **kwargs):
            child = actual_popen(*args, **kwargs)
            spawned.append(child)
            return child

        try:
            with patch.object(adapter.subprocess, "Popen", side_effect=spawn), \
                    patch.object(adapter.CodexAdapter, "_kill", side_effect=lambda child: child.wait(timeout=1)):
                response = runner("fixture")
            self.assertEqual(response["status"], "adapter_error")
            self.assertEqual(response["meta"]["status_detail"], "termination_pipe_drain_timeout")
            self.assertLess(response["meta"]["elapsed_s"], 2)
        finally:
            # The fixture deliberately left a descendant in the original group.
            for child in spawned:
                try:
                    os.killpg(child.pid, adapter.signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_all_native_or_unknown_items_rejected(self):
        for item_type in ("mcp_tool_call", "web_search", "file_change", "collab_agent_tool_call", "new_native_tool"):
            events = trace()
            events.insert(2, {"type": "item.completed", "item": {"type": item_type}})
            result = adapter.summarize(events, 0, "test-model")
            self.assertIsNone(result["text"])
            self.assertTrue(result["native_tool_events"])

    def test_unknown_usage_is_not_zero_evidence(self):
        events = trace()
        events[-1].pop("usage")
        result = adapter.summarize(events, 0, "test-model")
        self.assertIsNone(result["reported_tokens"]["output_tokens"])

    def test_extra_turn_or_model_mismatch_invalidates(self):
        for extra in ({"type": "turn.started"}, {"type": "turn.completed", "model": "other-model"}):
            with self.subTest(extra=extra):
                result = adapter.summarize(trace() + [extra], 0, "test-model")
                self.assertIsNone(result["text"])
                self.assertTrue(result["problems"])


if __name__ == "__main__":
    unittest.main()
