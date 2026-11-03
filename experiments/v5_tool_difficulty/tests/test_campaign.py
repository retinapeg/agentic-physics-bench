import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys
import types
from unittest.mock import patch, Mock

SRC=Path(__file__).resolve().parents[1]/'src'
spec=importlib.util.spec_from_file_location('v5_campaign',SRC/'run_v5.py')
C=importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

class EvidenceTests(unittest.TestCase):
    def test_hash_chain_and_file_seal_detect_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); e=p/'episode-001';e.mkdir()
            log=C.EventLog(e/'events.jsonl')
            log({'kind':'opportunity'});log({'kind':'dispatch'});log.close()
            C.seal(p)
            self.assertEqual(C.verify_campaign(p)['event_logs'],1)
            with (e/'events.jsonl').open('a') as f:f.write('{}\n')
            with self.assertRaises((RuntimeError,KeyError)):C.verify_campaign(p)

    def test_exclusive_save_prevents_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'evidence.json'
            C.save(p,{'original':True})
            with self.assertRaises(FileExistsError):C.save(p,{'original':False})
            self.assertEqual(json.loads(p.read_text()),{'original':True})

    def test_call_and_observed_token_budget(self):
        b=C.Budget(1,100,60)
        self.assertIsNone(b.reserve())
        self.assertEqual(b.reserve(),'call_budget')
        b=C.Budget(10,100,60)
        b.record({'usage':{'output_tokens':101}})
        self.assertEqual(b.reserve(),'observed_token_budget')

    def test_unsealed_incomplete_cannot_verify(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):C.verify_campaign(td)

    def test_preflight_failure_is_sealed_without_inference(self):
        modules={}
        for name in ('engine','tasks','analyze'):
            spec=importlib.util.spec_from_file_location('campaign_fixture_'+name,SRC/(name+'.py'))
            mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);modules[name]=mod
        fake_adapter=types.ModuleType('adapter')
        fake_adapter.preflight=Mock(side_effect=RuntimeError('no available account'))
        fake_adapter.CodexAdapter=Mock()
        modules['adapter']=fake_adapter
        task=modules['tasks'].make_task(1,40)
        plan=[dict(task=task,condition='forbidden',model='gpt-6.1-sol',effort='high',episode_id='episode-001')]
        with tempfile.TemporaryDirectory() as td, patch.dict(sys.modules,modules), patch.object(C,'build_plan',return_value=plan):
            out=Path(td)/'run'
            C.run(out,execute=True)
            result=json.loads((out/'episode-001/result.json').read_text())
            self.assertEqual(result['status'],'preflight_error')
            self.assertEqual(result['model_calls'],0)
            self.assertTrue(C.verify_campaign(out)['summary_recomputed'])
            fake_adapter.CodexAdapter.assert_not_called()

if __name__=='__main__':unittest.main()
