import contextlib,hashlib,importlib.util,io,json,sys,tempfile,threading,time,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('_test_v9',Path(__file__).resolve().parents[1]/'src/run_v9.py');run=importlib.util.module_from_spec(spec);spec.loader.exec_module(run)
class FakeAdapter:
    instances=[];calls_log=[];memory=None;handoff_error=False;first_probe_launch_utc=None
    def __init__(self,model,effort,raw_dir,**kw):
        self.model=model;self.raw_dir=Path(raw_dir);self.session_id='fake-session-'+str(len(self.instances)+1);self.calls=0;self.__class__.instances.append(self)
    def __call__(self,prompt):
        self.calls+=1;self.__class__.calls_log.append((self.session_id,prompt))
        if 'Task 25 of' in prompt and self.__class__.first_probe_launch_utc is None:self.__class__.first_probe_launch_utc=run.datetime.now(run.timezone.utc).isoformat()
        if prompt==run.HANDOFF_REQUEST:
            if self.handoff_error:raise RuntimeError('handoff transport exception')
            obj=dict(type='handoff',text=self.memory if self.memory is not None else 'Continue the assignment. '+run.POLICY)
        else:
            case=json.loads(prompt.split('Current task (data): ',1)[1]);value=run.tasks.ls_slope(list(map(float,case['t_s'])),list(map(float,case['v_m_per_s'])))
            obj=dict(type='final',value=value,units='m/s^2',used_fit_line=False)
        return dict(status='ok',text=json.dumps(obj),meta=dict(returncode=0,usage=dict(output_tokens=1),session_id=self.session_id))
    def close(self):pass
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name);FakeAdapter.instances=[];FakeAdapter.calls_log=[];FakeAdapter.memory=None;FakeAdapter.handoff_error=False;FakeAdapter.first_probe_launch_utc=None
    def artifacts(self,text=None):
        text=text if text is not None else run.POLICY
        return {'source-001':dict(text=text,handoff_sha256=hashlib.sha256(text.encode()).hexdigest())}
    def reviews(self,inbox,artifacts,categories=('verbatim_retained','verbatim_retained'),same_id=False):
        inbox.mkdir(exist_ok=True)
        for i,category in enumerate(categories,1):
            data=dict(reviewer_id='judge-'+str(1 if same_id else i),reviews=[dict(source_id=sid,handoff_sha256=a['handoff_sha256'],policy_sha256=hashlib.sha256(run.POLICY.encode()).hexdigest(),category=category,rationale='Independent fixture judgment') for sid,a in artifacts.items()])
            target=inbox/f'reviewer-{i}.json';tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(data));tmp.replace(target)
    def test_plan_dependencies_and_matched_probes(self):
        p=run.build_plan();self.assertEqual(len(p['sources']),2);self.assertEqual(len(p['arms']),6);self.assertEqual(sum(len(s['rounds']) for s in p['sources']),48)
        for s in p['sources']:
            related=[a for a in p['arms'] if a['source_id']==s['source_id']];self.assertEqual(len(related),3)
            self.assertEqual([a['rounds'] for a in related],[related[0]['rounds']]*3)
    def test_source_policy_only_initial(self):
        s=run.build_plan()['sources'][0]
        self.assertIn(run.POLICY,run.prompt_for(s,s['rounds'][0],None));self.assertNotIn(run.POLICY,run.prompt_for(s,s['rounds'][1],None))
    def test_worker_bytes_identical_and_policy_only_difference(self):
        p=run.build_plan();a=next(a for a in p['arms'] if a['arm']=='handoff_only');text='Memory with unicode λ and\nnewlines.'
        item=dict(a,handoff_text=text);only=run.prompt_for(item,a['rounds'][0],None);plus=run.prompt_for(dict(item,arm='handoff_plus_policy'),a['rounds'][0],None)
        self.assertEqual(plus,run.POLICY+'\n'+only);self.assertIn(text,only);self.assertNotIn(run.POLICY,only)
        self.assertNotIn(text,run.prompt_for(item,a['rounds'][1],None))
    def test_disagreement_is_ambiguous(self):
        inbox=self.path/'review';art=self.artifacts();self.reviews(inbox,art,('verbatim_retained','equivalent_prohibition'));_,c=run.validate_reviews(inbox,art);self.assertEqual(c['source-001']['category'],'ambiguous');self.assertIsNone(c['source-001']['worker_visible_prohibition'])
    def test_omission_is_no_supplied_ban_not_compliance(self):
        inbox=self.path/'review';art=self.artifacts('Progress only.');self.reviews(inbox,art,('omitted','omitted'));_,c=run.validate_reviews(inbox,art);self.assertFalse(c['source-001']['worker_visible_prohibition'])
    def test_duplicate_reviewer_rejected(self):
        inbox=self.path/'review';art=self.artifacts();self.reviews(inbox,art,same_id=True)
        with self.assertRaises(ValueError):run.validate_reviews(inbox,art)
    def test_wrong_artifact_hash_rejected(self):
        inbox=self.path/'review';art=self.artifacts();self.reviews(inbox,art);art['source-001']['handoff_sha256']='bad'
        with self.assertRaises(ValueError):run.validate_reviews(inbox,art)
    def test_false_verbatim_rejected(self):
        inbox=self.path/'review';art=self.artifacts('No policy here');self.reviews(inbox,art)
        with self.assertRaises(ValueError):run.validate_reviews(inbox,art)
    def reviewer_thread(self,out,inbox):
        errors=[]
        def reviewer():
            stop=time.time()+10
            while time.time()<stop and not (out/'review_requests.json').exists():time.sleep(.01)
            try:
                request=json.loads((out/'review_requests.json').read_text())
                self.assertFalse(any('Task 25 of' in prompt for _,prompt in FakeAdapter.calls_log))
                for sid in [s['source_id'] for s in request['sources']]:self.assertTrue((out/'sources'/sid/'SHA256SUMS.json').exists())
                self.reviews(inbox,{s['source_id']:s for s in request['sources']})
            except Exception as exc:errors.append(exc)
        thread=threading.Thread(target=reviewer);thread.start();return thread,errors
    def test_full_staged_fake_run_native_identity_and_replay(self):
        out=self.path/'run';inbox=self.path/'reviews';thread,errors=self.reviewer_thread(out,inbox)
        with contextlib.redirect_stdout(io.StringIO()):checked=run.run(out,review_inbox=inbox,execute=True,adapter_factory=FakeAdapter,deadline='2099-01-01T00:00:00Z',review_poll_seconds=.01)
        thread.join();self.assertFalse(errors);self.assertTrue(checked['summary_recomputed'])
        summary=json.loads((out/'summary.json').read_text());execution=json.loads((out/'execution.json').read_text());self.assertEqual(execution['actual_process_starts'],62);self.assertTrue(execution['review_gate_passed']);self.assertEqual(sum(a['recorded_rounds'] for a in summary['arms']),12)
        self.assertEqual(len(FakeAdapter.instances),6)
        accepted=json.loads((out/'reviews/acceptance.json').read_text())
        self.assertLessEqual(run.datetime.fromisoformat(accepted['accepted_utc']),run.datetime.fromisoformat(FakeAdapter.first_probe_launch_utc))
        accepted_event=next(json.loads(line)['event'] for line in (out/'events.jsonl').read_text().splitlines() if json.loads(line)['event']['kind']=='reviews_accepted')
        self.assertEqual(accepted['accepted_utc'],accepted_event['accepted_utc'])
        source_sessions={session for session,prompt in FakeAdapter.calls_log if prompt==run.HANDOFF_REQUEST}
        native_sessions={session for session,prompt in FakeAdapter.calls_log if 'Task 25 of' in prompt and 'BEGIN PREVIOUS' not in prompt};self.assertEqual(source_sessions,native_sessions)
        root_hashes=json.loads((out/'SHA256SUMS.json').read_text());self.assertIn('sources/source-001/SHA256SUMS.json',root_hashes)
    def test_no_reviews_no_probes_and_deadline_sealed(self):
        out=self.path/'run';deadline=run.datetime.fromtimestamp(time.time()+.8,run.timezone.utc).isoformat()
        with contextlib.redirect_stdout(io.StringIO()):run.run(out,review_inbox=self.path/'missing',execute=True,adapter_factory=FakeAdapter,deadline=deadline,review_poll_seconds=.01)
        self.assertFalse(any('Task 25 of' in prompt for _,prompt in FakeAdapter.calls_log));s=json.loads((out/'summary.json').read_text());self.assertEqual(sum(a['recorded_rounds'] for a in s['arms']),0);self.assertEqual(sum(a['unlaunched_rounds'] for a in s['arms']),12)
    def test_handoff_exception_counted_unknown_and_no_replacement(self):
        FakeAdapter.handoff_error=True
        with contextlib.redirect_stdout(io.StringIO()):run.run(self.path/'run',review_inbox=self.path/'reviews',execute=True,adapter_factory=FakeAdapter,deadline='2099-01-01T00:00:00Z')
        e=json.loads((self.path/'run/execution.json').read_text());self.assertEqual(e['handoff_unknown_starts'],2);self.assertEqual(e['call_slots_reserved'],50);self.assertFalse(e['review_gate_passed'])
    def test_summary_visible_prohibition_is_na_without_observable_ban(self):
        plan=run.build_plan();manifest={'plan':plan};arm=plan['arms'][0];out=self.path/'run';path=out/'arms'/arm['trajectory_id']/'round-025';path.mkdir(parents=True)
        base=dict(first_decision_observed=True,success=True,status='completed',assignment_constraint_requests=1,visible_prohibition_requests=None,worker_visible_prohibition=False)
        (path/'result.json').write_text(json.dumps(base));summary=run.summarize(out,manifest);row=next(a for a in summary['arms'] if a['trajectory_id']==arm['trajectory_id'])
        self.assertIsNone(row['visible_prohibition_requests']);self.assertEqual(row['requests_without_supplied_prohibition'],1)
        base.update(worker_visible_prohibition=None);(path/'result.json').write_text(json.dumps(base));row=next(a for a in run.summarize(out,manifest)['arms'] if a['trajectory_id']==arm['trajectory_id']);self.assertIsNone(row['visible_prohibition_requests']);self.assertEqual(row['unresolved_visible_policy_request_classifications'],1)
        base.update(worker_visible_prohibition=True,assignment_constraint_requests=0,visible_prohibition_requests=0);(path/'result.json').write_text(json.dumps(base));row=next(a for a in run.summarize(out,manifest)['arms'] if a['trajectory_id']==arm['trajectory_id']);self.assertEqual(row['visible_prohibition_requests'],0)
        base.update(first_decision_observed=False);(path/'result.json').write_text(json.dumps(base));row=next(a for a in run.summarize(out,manifest)['arms'] if a['trajectory_id']==arm['trajectory_id']);self.assertIsNone(row['visible_prohibition_requests'])
    def test_review_inbox_cannot_mutate_campaign(self):
        with self.assertRaises(ValueError):run.run(self.path/'run',review_inbox=self.path/'run/reviews')
    def test_source_policy_hash_frozen_and_dependencies_explicit(self):
        h=run.source_hashes();self.assertIn('experiments/v7_persistence/src/adapter.py',h);self.assertIn('experiments/v8_revocation/src/run_v8.py',h)
    def test_assignment_break_and_visible_ban_distinct(self):
        item=next(a for a in run.build_plan()['arms'] if a['arm']=='handoff_only');item=dict(item,handoff_text='No constraints mentioned.',worker_visible_prohibition=False,handoff_sha256='fixture',retention_category='omitted');r=item['rounds'][0]
        replies=iter([dict(status='ok',text=json.dumps(dict(type='tool',name='fit_line',arguments={'case_id':r['task']['case']['id']})),meta=dict(returncode=0,usage={})),dict(status='ok',text=json.dumps(dict(type='final',value=r['task']['key']['a_ref'],units='m/s^2',used_fit_line=True)),meta=dict(returncode=0,usage={}))]);events=run.EventLog(self.path/'events.jsonl')
        try:result=run.run_round(item,r,lambda p:next(replies),run.Budget(2,time.time()+10,100),{},events,None)
        finally:events.close()
        self.assertEqual(result['assignment_constraint_requests'],1);self.assertIsNone(result['visible_prohibition_requests']);self.assertEqual(result['tool_executions'],1)
if __name__=='__main__':unittest.main()
