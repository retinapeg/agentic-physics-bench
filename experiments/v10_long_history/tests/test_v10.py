import contextlib,importlib.util,io,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parents[1]/'src'
spec=importlib.util.spec_from_file_location('_test_v10',HERE/'run_v10.py');run=importlib.util.module_from_spec(spec);spec.loader.exec_module(run)
class FakeAdapter:
    instances=[];all_calls=[];request_tool=False;unknown_usage=False
    def __init__(self,model,effort,raw_dir,**kwargs):self.model=model;self.raw_dir=Path(raw_dir);self.raw_dir.mkdir(parents=True,exist_ok=True);self.session_id='fake-'+str(len(self.instances));self.calls=0;self.__class__.instances.append(self)
    def __call__(self,prompt):
        self.calls+=1;self.__class__.all_calls.append((self.session_id,prompt));case=json.loads(prompt.split('Current task (data): ',1)[1]);value=run.tasks.ls_slope(list(map(float,case['t_s'])),list(map(float,case['v_m_per_s'])))
        obj=dict(type='tool',name='fit_line',arguments={'case_id':case['id']}) if self.request_tool else dict(type='final',value=value,units='m/s^2',used_fit_line=False)
        prior=None if self.calls==1 else self.session_id;usage={'input_tokens':100*self.calls,'cached_input_tokens':10*self.calls,'output_tokens':20*self.calls,'reasoning_output_tokens':15*self.calls,'cache_write_input_tokens':0}
        if self.unknown_usage:usage.pop('output_tokens')
        prefix=self.raw_dir/f'call-{self.calls:04d}';manifest=Path(str(prefix)+'-manifest.json');stdout=Path(str(prefix)+'-stdout.jsonl')
        manifest.write_text(json.dumps(dict(native_session=dict(resumed_session_id=prior,persistent=True),argv=['codex','exec']+(['resume'] if prior else []),call_index=self.calls)))
        stdout.write_text(json.dumps(dict(type='thread.started',thread_id=self.session_id))+'\n'+json.dumps(dict(type='turn.completed',usage=usage))+'\n')
        return dict(status='ok',text=json.dumps(obj),meta=dict(returncode=0,session_id=self.session_id,prior_session_id=prior,usage={k:usage.get(k) for k in run.U.REQUIRED},raw_manifest=str(manifest),raw_stdout=str(stdout)))
    def close(self):pass
class Tests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name);FakeAdapter.instances=[];FakeAdapter.all_calls=[];FakeAdapter.request_tool=False;FakeAdapter.unknown_usage=False
    def usage(self,out=10):return dict(input_tokens=100,cached_input_tokens=0,output_tokens=out)
    def test_saved_audited_snapshots_match_deltas(self):
        fixture=json.loads((Path(__file__).parent/'audited_usage_fixture.json').read_text());ledger=run.UsageLedger()
        for c in fixture['calls']:
            observed=ledger.observe(c['native_session_id'],c['resumed_session_id'],c['argv_has_resume'],c['raw_usage'],call_index=c['call_index']);self.assertEqual(observed['delta'],c['deduplicated_delta'])
        self.assertEqual(ledger.known_totals,fixture['calls'][-1]['raw_usage'])
    def test_interleaved_sessions_and_identical_snapshot(self):
        l=run.UsageLedger();self.assertEqual(l.observe('a',None,False,self.usage(10),call_index=1)['delta']['output_tokens'],10);l.observe('b',None,False,self.usage(20),call_index=1)
        self.assertEqual(l.observe('a','a',True,self.usage(10),call_index=2)['delta']['output_tokens'],0);self.assertEqual(l.observe('b','b',True,self.usage(25),call_index=2)['delta']['output_tokens'],5);self.assertEqual(l.known_totals['output_tokens'],35)
    def test_unknown_initial_resume_is_not_zero_baseline(self):
        result=run.UsageLedger().observe('a','a',True,self.usage(100),call_index=5);self.assertEqual(result['status'],'unknown');self.assertIsNone(result['delta'])
    def test_reset_and_missing_never_clamped(self):
        l=run.UsageLedger();l.observe('a',None,False,self.usage(10),call_index=1);r=l.observe('a','a',True,self.usage(2),call_index=2);self.assertEqual(r['diagnostic'],'counter_decreased_or_reset');self.assertIsNone(r['delta']);self.assertEqual(l.known_totals['output_tokens'],10)
        r=l.observe('b',None,False,{'input_tokens':1},call_index=1);self.assertEqual(r['status'],'unknown');self.assertEqual(l.unknown_observations,2)
    def test_new_session_requires_unique_id(self):
        l=run.UsageLedger();l.observe('a',None,False,self.usage(),call_index=1);r=l.observe('a',None,False,self.usage(),call_index=1);self.assertEqual(r['status'],'unknown')
    def test_directory_relocation_keeps_session_counter(self):
        a=FakeAdapter('m','high',self.path/'one');l=run.UsageLedger();item=run.build_plan()[0];r=item['rounds'][0];first=l.observe_response(a(run.prompt_for(item,r,None)));a.raw_dir=self.path/'two';a.raw_dir.mkdir();second=l.observe_response(a(run.prompt_for(item,r,None)));self.assertEqual(first['delta']['output_tokens'],20);self.assertEqual(second['delta']['output_tokens'],20);self.assertEqual(l.known_totals['output_tokens'],40)
    def test_all_matched64_easy_cases(self):
        p=run.build_plan();self.assertEqual(len(p),4)
        for item in p:self.assertEqual(len(item['rounds']),64);self.assertTrue(all(r['task']['level']==1 for r in item['rounds']));self.assertEqual(item['rounds'],p[0]['rounds'])
    def test_feedback_and_policy_placement(self):
        p=run.build_plan();item=p[0];feedback={'previous_case_id':'old','action':'tool','tool_result':{'slope':1}}
        for arm in run.ARMS:
            prompt=run.prompt_for(dict(item,arm=arm),item['rounds'][1],feedback);self.assertEqual(run.POLICY in prompt,arm=='fresh_one_step');self.assertIn(json.dumps(feedback,separators=(',',':')),prompt)
        result=dict(case_id='case',action='final',model_final_value=1,model_final_success=True);self.assertEqual(run.feedback_for(result),dict(previous_case_id='case',action='final',tool_result=None))
    def test_single_callback_tool_executes_and_resolves_as_dispatcher(self):
        FakeAdapter.request_tool=True;item=run.build_plan()[0];a=FakeAdapter('m','high',self.path/'raw');events=run.EventLog(self.path/'events.jsonl')
        try:r=run.run_round(item,item['rounds'][0],a,run.Budget(256,time.time()+10),{},events,None)
        finally:events.close()
        self.assertEqual(a.calls,1);self.assertEqual(r['tool_executions'],1);self.assertTrue(r['dispatcher_success']);self.assertIsNone(r['model_final_success']);self.assertTrue(r['first_decision_violation']);self.assertEqual(r['status'],'dispatcher_result')
    def test_worker_failure_keeps_known_request(self):
        FakeAdapter.request_tool=True;item=run.build_plan()[0];a=FakeAdapter('m','high',self.path/'raw');events=run.EventLog(self.path/'events.jsonl')
        try:
            with patch.object(run.engine,'fit_line',side_effect=RuntimeError('worker failed')):r=run.run_round(item,item['rounds'][0],a,run.Budget(256,time.time()+10),{},events,None)
        finally:events.close()
        self.assertEqual(a.calls,1);self.assertEqual(r['tool_requests'],1);self.assertEqual(r['tool_dispatch_attempts'],1);self.assertEqual(r['tool_execution_unresolved'],1);self.assertEqual(r['tool_executions'],0)
    def test_unknown_usage_preserves_behavior_and_stops_campaign(self):
        FakeAdapter.unknown_usage=True;FakeAdapter.request_tool=True;item=run.build_plan()[0];a=FakeAdapter('m','high',self.path/'raw');events=run.EventLog(self.path/'events.jsonl');budget=run.Budget(256,time.time()+10)
        try:r=run.run_round(item,item['rounds'][0],a,budget,{},events,None)
        finally:events.close()
        self.assertEqual(r['tool_requests'],1);self.assertTrue(r['dispatcher_success']);self.assertTrue(r['terminate_trajectory']);self.assertEqual(budget.reserve(),'usage_accounting_unknown')
    def test_full_mock_horizon_and_deduplicated_ledger(self):
        with contextlib.redirect_stdout(io.StringIO()):checked=run.run(self.path/'run',execute=True,adapter_factory=FakeAdapter,deadline='2099-01-01T00:00:00Z')
        self.assertTrue(checked['summary_recomputed']);s=json.loads((self.path/'run/summary.json').read_text());e=json.loads((self.path/'run/execution.json').read_text());self.assertEqual(s['recorded_rounds'],256);self.assertEqual(e['actual_process_starts'],256);self.assertEqual(e['known_deduplicated_usage']['output_tokens'],5120);self.assertEqual(len(FakeAdapter.instances),130);self.assertTrue((self.path/'run/checkpoint48.json').exists())
        counts=Counter(sid for sid,_ in FakeAdapter.all_calls);self.assertEqual(sorted(counts.values()).count(64),2);self.assertEqual(sorted(counts.values()).count(1),128)
    def test_unknown_usage_campaign_seals_and_replays(self):
        FakeAdapter.unknown_usage=True
        with contextlib.redirect_stdout(io.StringIO()):checked=run.run(self.path/'run',execute=True,adapter_factory=FakeAdapter,deadline='2099-01-01T00:00:00Z')
        self.assertTrue(checked['summary_recomputed']);execution=json.loads((self.path/'run/execution.json').read_text());summary=json.loads((self.path/'run/summary.json').read_text())
        self.assertEqual(execution['usage_stop_reason'],'usage_accounting_unknown');self.assertGreater(execution['unknown_usage_observations'],0);self.assertLessEqual(execution['actual_process_starts'],2);self.assertGreater(summary['unlaunched_rounds'],0)
    def test_global_cap_is_atomic(self):
        from concurrent.futures import ThreadPoolExecutor
        b=run.Budget(7,time.time()+10)
        with ThreadPoolExecutor(max_workers=20) as pool:r=list(pool.map(lambda _:b.reserve(),range(50)))
        self.assertEqual(r.count(None),7);self.assertEqual(b.calls,7)
    def test_deadline_no_callback(self):
        item=run.build_plan()[0];events=run.EventLog(self.path/'events.jsonl')
        try:r=run.run_round(item,item['rounds'][0],lambda _:self.fail('called'),run.Budget(256,time.time()-1),{},events,None)
        finally:events.close()
        self.assertEqual(r['status'],'campaign_deadline');self.assertEqual(r['model_call_attempts'],0)
    def test_reduced_plan_not_silently_allowed(self):
        with self.assertRaises(ValueError):run.run(self.path/'run',execute=False,max_calls=128)
from collections import Counter
if __name__=='__main__':unittest.main()
