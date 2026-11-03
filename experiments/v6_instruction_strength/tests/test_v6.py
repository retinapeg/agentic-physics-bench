import concurrent.futures
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))
import engine
import analyze
import run_v6
from shared import tasks


class StrengthStudyTests(unittest.TestCase):
    def test_schedule_complete_matched_and_fixed(self):
        plan = run_v6.build_plan([2026110501,2026110502],[('gpt-6.1-sol','high'),('gpt-6-astra','ultra')])
        self.assertEqual(len(plan),80)
        self.assertEqual(plan,run_v6.build_plan([2026110501,2026110502],[('gpt-6.1-sol','high'),('gpt-6-astra','ultra')]))
        self.assertEqual(len({r['episode_id'] for r in plan}),80)
        groups={}
        for row in plan:
            groups.setdefault((row['model'],row['task']['seed'],row['task']['level']),[]).append(row)
        self.assertEqual(len(groups),16)
        for rows in groups.values():
            self.assertEqual(len({r['task']['case_sha256'] for r in rows}),1)
            self.assertEqual({(r['condition'],r['instruction_strength']) for r in rows},
                             {('allowed','not_applicable'),('no_tool','not_applicable'),('forbidden','soft'),('forbidden','medium'),('forbidden','firm')})

    def test_actual_and_logged_prompts_match_concurrently(self):
        original = dict(engine.POLICIES)
        task=tasks.make_task(1,2026110501)
        def trial(strength):
            prompts=[]
            def call(prompt):
                prompts.append(prompt)
                return {'status':'ok','text':'{"type":"abstain","reason":"cannot solve"}'}
            result=engine.run_episode(task,'forbidden',call,instruction_strength=strength)
            logged=[e['prompt'] for e in result['events'] if e['kind']=='decision_opportunity']
            self.assertEqual(prompts,logged)
            self.assertIn(engine.STRENGTHS[strength],prompts[0])
            self.assertIn('fit_line is available:',prompts[0])
            self.assertEqual(result['instruction_strength'],strength)
            return result
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            rows=list(pool.map(trial,engine.STRENGTHS))
        self.assertEqual(engine.POLICIES,original)
        self.assertEqual({c['instruction_strength'] for c in analyze.summarize(rows)['cells']},set(engine.STRENGTHS))

    def test_forbidden_tool_executes_in_all_strengths(self):
        task=tasks.make_task(1,2026110501)
        for strength in engine.STRENGTHS:
            replies=iter([
                {'status':'ok','text':json.dumps({'type':'tool','name':'fit_line','arguments':{'case_id':task['case']['id']}})},
                {'status':'ok','text':json.dumps({'type':'final','value':task['key']['a_ref'],'units':'m/s^2'})}])
            result=engine.run_episode(task,'forbidden',lambda p:next(replies),instruction_strength=strength)
            self.assertTrue(result['success'])
            self.assertTrue(result['first_decision_violation'])
            self.assertEqual(result['violating_tool_executions'],1)

    def test_matched_prompt_difference_is_only_policy(self):
        task=tasks.make_task(3,2026110501)
        normalized=[]
        for strength,policy in engine.STRENGTHS.items():
            prompt=engine._prompt(task,'forbidden',[],1,3,True,policy)
            normalized.append(prompt.replace(policy,'POLICY',1))
        self.assertEqual(len(set(normalized)),1)

    def test_malformed_request_counted_without_execution_and_controls(self):
        task=tasks.make_task(1,2026110501)
        malformed={'status':'ok','text':'{"type":"tool","name":"fit_line","arguments":{"case_id":"wrong"}}'}
        for strength in engine.STRENGTHS:
            with patch.object(engine,'fit_line',side_effect=AssertionError('must not dispatch')):
                result=engine.run_episode(task,'forbidden',lambda p:malformed,instruction_strength=strength)
            self.assertTrue(result['first_decision_violation'])
            self.assertEqual(result['tool_executions'],0)
        valid={'status':'ok','text':json.dumps({'type':'tool','name':'fit_line','arguments':{'case_id':task['case']['id']}})}
        with patch.object(engine,'fit_line',side_effect=AssertionError('no-tool must not dispatch')):
            result=engine.run_episode(task,'no_tool',lambda p:valid)
        self.assertEqual(result['tool_executions'],0)
        self.assertEqual(result['tool_opportunities'],0)
        self.assertFalse(result['first_decision_violation'])
        self.assertIn('fit_line is available:',engine._prompt(task,'allowed',[],1,3,True,engine.POLICIES['allowed']))

    def test_invalid_strength_rejected_before_call(self):
        task=tasks.make_task(1,2026110501)
        def never(prompt): self.fail('should not call model')
        for condition,strength in [('forbidden','not_applicable'),('allowed','soft'),('forbidden','unknown')]:
            with self.assertRaises(ValueError):
                engine.run_episode(task,condition,never,instruction_strength=strength)

    def test_stratification_never_pools_strengths(self):
        task=tasks.make_task(1,2026110501)
        rows=[]
        for strength in engine.STRENGTHS:
            rows.append(engine.run_episode(task,'forbidden',lambda p:{'status':'ok','text':'{"type":"abstain","reason":"x"}'},instruction_strength=strength))
        summary=analyze.summarize(rows)
        self.assertEqual(summary['total_attempts'],3)
        self.assertEqual(len(summary['cells']),3)
        self.assertTrue(all(c['attempts']==1 and not c['duplicate_seeds'] for c in summary['cells']))

    def test_sources_include_shared_code_and_plan_seals(self):
        hashes=run_v6.source_hashes()
        self.assertIn('experiments/v5_tool_difficulty/src/adapter.py',hashes)
        self.assertIn('experiments/v6_instruction_strength/src/engine.py',hashes)
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)/'plan'
            result=run_v6.run(directory,execute=False)
            self.assertEqual(result['planned'],80)
            self.assertFalse(run_v6.verify_campaign(directory)['summary_recomputed'])
            with self.assertRaises(FileExistsError): run_v6.run(directory,execute=False)
            (directory/'manifest.json').write_text('{}')
            with self.assertRaises(RuntimeError): run_v6.verify_campaign(directory)

    def test_complete_campaign_replay_without_inference(self):
        from shared import adapter
        class FakeAdapter:
            def __init__(self,model,effort,out,timeout_s): self.identity={'fixture':True}
            def __call__(self,prompt):
                return {'status':'ok','text':'{"type":"abstain","reason":"fixture"}',
                        'meta':{'returncode':0,'usage':{'output_tokens':1}}}
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)/'campaign'
            with patch.object(adapter,'preflight',return_value={'fixture':True}), patch.object(adapter,'CodexAdapter',FakeAdapter), patch('builtins.print'):
                result=run_v6.run(directory,execute=True)
            self.assertTrue(result['summary_recomputed'])
            self.assertEqual(result['event_logs'],80)
            summary=json.loads((directory/'summary.json').read_text())
            self.assertEqual(summary['total_attempts'],80)
            self.assertEqual(len(summary['cells']),40)
            self.assertEqual(json.loads((directory/'execution.json').read_text())['calls_started'],80)

    def test_audited_timeout_task_failure_compliance_unknown(self):
        task=tasks.make_task(4,2026110501)
        reply={'status':'timeout','text':'','model_call_started':True,'meta':{
            'timeout_after_clean_turn_start':True,'started_threads':1,'started_turns':1,'completed_turns':0}}
        result=engine.run_episode(task,'forbidden',lambda p:reply,instruction_strength='soft')
        self.assertTrue(result['task_outcome_assessable'])
        self.assertFalse(result['first_decision_observed'])
        self.assertIsNone(result['first_decision_violation'])
        self.assertEqual(analyze.summarize([result])['cells'][0]['first_decision_violation_all_attempt_bounds'],[0,1])

if __name__=='__main__': unittest.main()
