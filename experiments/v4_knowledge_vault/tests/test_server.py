import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import common
import server
from engine import Run
from test_core import ScriptedAdapter


class ServerBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.results=patch.object(common,"RESULTS",Path(self.temp.name));self.results.start()
        with patch.object(server,"preflight",return_value={"ready":False,"reason":"offline test"}):
            self.lab=server.Lab()
        self.http=ThreadingHTTPServer(("127.0.0.1",0),server.handler_for(self.lab))
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join()
        self.results.stop();self.temp.cleanup()

    def request(self,path,body=None,headers=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.http.server_port)
        defaults={"Content-Type":"application/json","X-Vault-CSRF":self.lab.token}
        conn.request("GET" if body is None else "POST",path,body=None if body is None else json.dumps(body),headers={**defaults,**(headers or {})})
        response=conn.getresponse();data=response.read();status=response.status;conn.close()
        return status,data

    def test_static_bootstrap_and_no_private_files(self):
        self.assertEqual(self.request("/")[0],200)
        self.assertEqual(len(json.loads(self.request("/api/bootstrap")[1])["catalog"]),5)
        for path in ("/../src/engine.py","/results/raw/private.json","/api/runs/../../private.json","/data/campaigns"):
            self.assertEqual(self.request(path)[0],404)

    def test_inference_requires_opt_in_and_csrf(self):
        self.assertEqual(self.request("/api/runs",{"config":{}})[0],400)
        self.assertEqual(self.request("/api/runs",{"opt_in":True},{"X-Vault-CSRF":"wrong"})[0],403)
        self.assertEqual(self.request("/api/runs",{"opt_in":True},{"Origin":"https://attacker.invalid"})[0],403)
        self.assertEqual(self.request("/api/bootstrap",headers={"Host":"attacker.invalid"})[0],403)
        self.assertIsNone(self.lab.current)

    def test_saved_replay_never_calls_model_and_detects_tampering(self):
        adapter=ScriptedAdapter()
        job=Run({"turn_budget":1},{},adapter,Path(self.temp.name))
        job.execute();call_count=len(adapter.calls)
        self.assertEqual(self.request("/api/runs/"+job.id)[0],200)
        replay=json.loads(self.request("/api/runs/"+job.id)[1])
        self.assertTrue(replay["integrity_verified"])
        self.assertEqual(len(adapter.calls),call_count)
        self.assertEqual(json.loads(self.request("/api/compare")[1])[0]["valid_complete"],1)
        rows=(job.directory/"events.jsonl").read_text().splitlines()
        first=json.loads(rows[0]);first["text"]="tampered";rows[0]=json.dumps(first)
        (job.directory/"events.jsonl").write_text("\n".join(rows)+"\n")
        self.assertFalse(json.loads(self.request("/api/runs/"+job.id)[1])["integrity_verified"])
        self.assertEqual(json.loads(self.request("/api/compare")[1]),[])

    def test_interrupted_run_remains_visible_unscored(self):
        job=Run({"turn_budget":1},{},ScriptedAdapter(),Path(self.temp.name))
        record=json.loads(self.request("/api/runs/"+job.id)[1])
        self.assertEqual(record["status"],"interrupted")
        self.assertIsNone(record["verdict"])

    def test_baseline_is_explicitly_non_llm_and_needs_no_inference_opt_in(self):
        status,data=self.request("/api/baseline",{"config":{"family":"permitted_outputs","turn_budget":1}})
        self.assertEqual(status,201)
        result=json.loads(data)
        self.assertEqual(result["source"],"deterministic_baseline")
        self.assertEqual(result["metrics"]["inference_calls"],0)
        self.assertEqual(result["metrics"]["observed_cost_usd"],0)
        self.assertTrue(result["verdict"]["policy_leakage"])
        self.assertFalse(any(e["kind"].startswith("call_") for e in result["events"]))
        self.assertTrue(json.loads(self.request("/api/runs/"+result["id"])[1])["integrity_verified"])


if __name__ == "__main__":
    unittest.main()
