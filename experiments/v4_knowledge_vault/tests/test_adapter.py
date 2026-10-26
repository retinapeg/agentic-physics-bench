import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import common
from adapter import ClaudeAdapter,environment
from engine import Run
from test_core import ScriptedAdapter


def events(turns=1,extra_model=False):
    model="claude-fable-5-1"
    usage={model:{"canonicalModel":model,"maxOutputTokens":64000}}
    if extra_model:
        usage["auxiliary"]={"canonicalModel":"auxiliary"}
    return [
        {"type":"system","subtype":"init","model":model,"tools":[],"mcp_servers":[],"claude_code_version":"test","fast_mode_state":"off"},
        {"type":"assistant","message":{"model":model,"content":[{"type":"text","text":"{}"}]}},
        {"type":"result","subtype":"success","result":"{}","is_error":False,"num_turns":turns,"fast_mode_state":"off","stop_reason":"end_turn",
         "usage":{"input_tokens":10,"output_tokens":5},"modelUsage":usage,"total_cost_usd":.001}]


class AdapterTests(unittest.TestCase):
    def fake_cli(self,folder,rows,delay=False):
        script=folder/"fake-cli"
        body="import sys,time\nsys.stdin.read()\n"+("time.sleep(30)\n" if delay else "")
        body+="print("+repr("\n".join(json.dumps(row) for row in rows))+")\n"
        script.write_text("#!"+sys.executable+"\n"+body);script.chmod(0o700)
        return {"ready":True,"version":"test","binary":str(script),"binary_sha256":common.file_hash(script)}

    def test_environment_drops_parent_agent_controls_and_api_keys(self):
        with patch.dict(os.environ,{"ANTHROPIC_API_KEY":"test-never-pass","CLAUDE_CODE_EFFORT_LEVEL":"max","CLAUDECODE":"parent"}):
            env=environment()
            self.assertNotIn("ANTHROPIC_API_KEY",env)
            self.assertNotIn("CLAUDE_CODE_EFFORT_LEVEL",env)
            self.assertNotIn("CLAUDECODE",env)
            self.assertEqual(env["CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK"],"1")
            self.assertEqual(os.environ["CLAUDECODE"],"parent")

    def test_adapter_runs_isolated_process_and_captures_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            identity=self.fake_cli(Path(d),events())
            call,summary,violations=ClaudeAdapter(identity).call("defender","claude-fable-5-1","private system","public prompt",.1,2,threading.Event())
            self.assertEqual(violations,[])
            self.assertIn("--max-turns",call["argv"])
            self.assertIn("--max-budget-usd",call["argv"])
            self.assertEqual(summary["models_used"],["claude-fable-5-1"])

    def test_extra_model_and_multiturn_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            identity=self.fake_cli(Path(d),events(turns=2,extra_model=True))
            _,_,violations=ClaudeAdapter(identity).call("attacker","claude-fable-5-1","system","prompt",.1,2,threading.Event())
            self.assertIn("v4_single_turn_required",violations)
            self.assertIn("unexpected_model_usage:auxiliary",violations)

    def test_timeout_terminates_and_is_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            identity=self.fake_cli(Path(d),events(),delay=True)
            call,_,violations=ClaudeAdapter(identity).call("defender","claude-fable-5-1","system","prompt",.1,.05,threading.Event())
            self.assertIn("timeout",violations)
            self.assertIsNone(call["returncode"])
            self.assertLess(call["elapsed_s"],3)

    def test_overshoot_stops_before_next_call(self):
        class OverBudget(ScriptedAdapter):
            def call(self,*args):
                call,summary,violations=super().call(*args)
                summary["result"]["list_price_estimate_usd"]=.2
                return call,summary,violations
        with tempfile.TemporaryDirectory() as d:
            adapter=OverBudget()
            r=Run({"turn_budget":1,"max_cost_usd":.4},{},adapter,Path(d)).execute()
            self.assertEqual(len(adapter.calls),1)
            self.assertFalse(r["verdict"]["valid"])
            self.assertEqual(r["metrics"]["observed_cost_usd"],.2)


if __name__ == "__main__":
    unittest.main()
