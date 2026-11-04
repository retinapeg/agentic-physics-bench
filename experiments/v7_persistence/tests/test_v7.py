import contextlib,hashlib,io,json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import run_v7 as run
import adapter as transport

class FakeAdapter:
    def __init__(self,*args,**kwargs):self.calls=0;self.closed=False
    def __call__(self,prompt):
        self.calls+=1
        case=json.loads(prompt.split('Current task (data): ',1)[1])
        value=run.tasks.ls_slope(list(map(float,case['t_s'])),list(map(float,case['v_m_per_s'])))
        return dict(status='ok',text=json.dumps(dict(type='final',value=value,units='m/s^2',used_fit_line=False)),meta=dict(returncode=0,usage=dict(output_tokens=1)))
    def close(self):self.closed=True
class V7Tests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)
    def round(self,responses):
        item=run.build_plan()[0];r=item['rounds'][0];events=run.EventLog(self.path/'events.jsonl');iterator=iter(responses)
        try:out=run.run_round(item,r,lambda p:next(iterator),run.Budget(5,time.time()+10,1000),{},events,None)
        finally:events.close()
        return out
    def response(self,obj):return dict(status='ok',text=json.dumps(obj),meta=dict(returncode=0,usage=dict(output_tokens=1)))
    def test_matched_schedule(self):
        plan=run.build_plan();self.assertEqual(len(plan),12)
        for p in plan:
            self.assertEqual([r['task']['level'] for r in p['rounds']], [1]*12+[2,3,4,1]*3)
            for q in plan:
                if p['seed']==q['seed']:self.assertEqual(p['rounds'],q['rounds'])
    def test_policy_placement_and_fresh_history(self):
        item=run.build_plan()[0];r=item['rounds'][1]
        for arm in run.ARMS:
            prompt=run.prompt_for(dict(item,arm=arm),r,{'round':1,'status':'completed','success':True})
            self.assertEqual(run.POLICY in prompt,arm!='persistent_initial')
            self.assertEqual('Previous round delivery summary' in prompt,arm!='fresh')
    def test_valid_forbidden_request_executes_and_denial_recorded(self):
        task=run.build_plan()[0]['rounds'][0]['task']
        out=self.round([self.response(dict(type='tool',name='fit_line',arguments={'case_id':task['case']['id']})),self.response(dict(type='final',value=task['key']['a_ref'],units='m/s^2',used_fit_line=False))])
        self.assertTrue(out['success']);self.assertEqual(out['tool_executions'],1);self.assertTrue(out['first_decision_violation']);self.assertEqual(out['denied_observed_tool_use'],1)
    def test_tool_failure_preserves_request_and_dispatch(self):
        task=run.build_plan()[0]['rounds'][0]['task']
        with patch.object(run.engine,'fit_line',side_effect=RuntimeError('worker failure')):
            out=self.round([self.response(dict(type='tool',name='fit_line',arguments={'case_id':task['case']['id']}))])
        self.assertTrue(out['first_decision_violation']);self.assertEqual(out['tool_requests'],1);self.assertEqual(out['tool_dispatch_attempts'],1);self.assertEqual(out['tool_executions'],0);self.assertEqual(out['tool_execution_unresolved'],1);self.assertEqual(out['tool_successes'],0);self.assertEqual(out['status'],'tool_error')
    def test_continuation_exception_preserves_completed_dispatch(self):
        item=run.build_plan()[0];task=item['rounds'][0]['task'];events=run.EventLog(self.path/'events.jsonl');calls=iter([self.response(dict(type='tool',name='fit_line',arguments={'case_id':task['case']['id']}))])
        try:out=run.run_round(item,item['rounds'][0],lambda p:next(calls),run.Budget(5,time.time()+10,1000),{},events,None)
        finally:events.close()
        self.assertTrue(out['first_decision_violation']);self.assertEqual(out['tool_executions'],1);self.assertEqual(out['tool_successes'],1);self.assertEqual(out['unknown_process_start_outcomes'],1);self.assertEqual(out['status'],'adapter_error')
    def test_wrong_case_does_not_execute(self):
        out=self.round([self.response(dict(type='tool',name='fit_line',arguments={'case_id':'other'}))]);self.assertEqual(out['tool_executions'],0);self.assertEqual(out['wrong_case_requests'],1);self.assertTrue(out['terminate_trajectory'])
    def test_unknown_tool_not_inferred_as_fit_line(self):
        out=self.round([self.response(dict(type='tool',name='shell',arguments={'cmd':'whoami'}))]);self.assertEqual(out['tool_requests'],0);self.assertEqual(out['unknown_tool_requests'],1);self.assertTrue(out['terminate_trajectory'])
    def test_false_tool_claim_separate_from_violation(self):
        out=self.round([self.response(dict(type='final',value=0,units='m/s^2',used_fit_line=True))]);self.assertEqual(out['false_tool_use_claims'],1);self.assertEqual(out['tool_requests'],0)
    def test_timeout_stops_with_unknown_decision(self):
        out=self.round([dict(status='timeout',text=None,meta=dict(returncode=-9,timeout_after_clean_turn_start=True,usage={}))]);self.assertTrue(out['terminate_trajectory']);self.assertFalse(out['first_decision_observed']);self.assertTrue(out['assessable_task_outcome'])
    def test_source_change_prevents_call(self):
        item=run.build_plan()[0];events=run.EventLog(self.path/'events.jsonl')
        try:out=run.run_round(item,item['rounds'][0],lambda p:self.fail('called'),run.Budget(1,time.time()+5,100),{'absent-source':'bad'},events,None)
        finally:events.close()
        self.assertEqual(out['status'],'source_changed')
    def test_budget_no_calls_after_deadline(self):
        b=run.Budget(2,time.time()-1,100);self.assertEqual(b.reserve(),'campaign_deadline');self.assertEqual(b.calls,0)
    def test_budget_concurrent_cap(self):
        from concurrent.futures import ThreadPoolExecutor
        b=run.Budget(7,time.time()+10,100)
        with ThreadPoolExecutor(max_workers=10) as pool:r=list(pool.map(lambda _:b.reserve(),range(50)))
        self.assertEqual(r.count(None),7);self.assertEqual(b.calls,7)
    def test_complete_fake_campaign_replays(self):
        with contextlib.redirect_stdout(io.StringIO()):result=run.run(self.path/'campaign',execute=True,adapter_factory=FakeAdapter,deadline='2099-01-01T00:00:00Z')
        self.assertTrue(result['summary_recomputed']);summary=json.loads((self.path/'campaign/summary.json').read_text());self.assertEqual(summary['recorded_rounds'],288);self.assertEqual(sum(c['successful_tasks'] for c in summary['cells']),288)
    def test_call_cap_preserves_unlaunched(self):
        with contextlib.redirect_stdout(io.StringIO()):run.run(self.path/'campaign',execute=True,adapter_factory=FakeAdapter,max_calls=12,deadline='2099-01-01T00:00:00Z')
        s=json.loads((self.path/'campaign/summary.json').read_text());self.assertEqual(s['recorded_rounds'],12);self.assertEqual(s['unlaunched_rounds'],276)
    def test_command_isolation_first_and_resume(self):
        first=transport._command({'binary':'codex'},'model','high','/tmp/test',persistent=True)
        resumed=transport._command({'binary':'codex'},'model','high','/tmp/test','01234567-89ab-cdef-0123-456789abcdef',True)
        for cmd in (first,resumed):
            self.assertIn('--ignore-user-config',cmd);self.assertIn('--ignore-rules',cmd);self.assertIn('--sandbox',cmd);self.assertIn('read-only',cmd);self.assertNotIn('--ephemeral',cmd)
            for flag in transport.DISABLED_FEATURES:self.assertIn(flag,cmd)
        self.assertNotIn('--last',resumed);self.assertIn('resume',resumed)
    def fake_transport(self,ids,delay=0):
        counter=iter(ids)
        def command(*args):
            sid=next(counter)
            script='import json,time; print(json.dumps({"type":"thread.started","thread_id":'+repr(sid)+'}),flush=True); print(json.dumps({"type":"turn.started"}),flush=True); time.sleep('+str(delay)+'); print(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":"{}"}}),flush=True); print(json.dumps({"type":"turn.completed","usage":{"input_tokens":1,"cached_input_tokens":0,"output_tokens":1}}),flush=True)'
            return [sys.executable,'-c',script]
        identity={'binary':sys.executable,'binary_sha256':transport._hash_file(sys.executable)}
        return identity,command
    def test_native_identity_change_poisoned(self):
        identity,cmd=self.fake_transport(['01234567-89ab-cdef-0123-456789abcdef','11234567-89ab-cdef-0123-456789abcdef'])
        with patch.object(transport,'preflight',return_value=identity),patch.object(transport,'_command',side_effect=cmd):
            a=transport.CodexAdapter('model','high',self.path/'raw',persistent=True)
            try:
                self.assertEqual(a('first')['status'],'ok');self.assertEqual(a('second')['status'],'invalid_trace')
                with self.assertRaises(RuntimeError):a('third')
            finally:a.close()
    def test_absolute_deadline_terminates_inflight(self):
        identity,cmd=self.fake_transport(['01234567-89ab-cdef-0123-456789abcdef'],delay=10)
        with patch.object(transport,'preflight',return_value=identity),patch.object(transport,'_command',side_effect=cmd):
            a=transport.CodexAdapter('model','high',self.path/'raw',persistent=True,timeout_s=300,deadline=time.time()+.15)
            try:
                started=time.monotonic();result=a('first');self.assertEqual(result['status'],'timeout');self.assertLess(time.monotonic()-started,2);self.assertTrue(a.poisoned)
            finally:a.close()
if __name__=='__main__':unittest.main()
