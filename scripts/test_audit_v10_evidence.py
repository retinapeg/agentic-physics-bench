import copy,datetime,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
p=Path(__file__).with_name('audit_v10_evidence.py');s=importlib.util.spec_from_file_location('audit',p);a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
SID='11111111-1111-1111-1111-111111111111'
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d))
def seal(root):write(root/'SHA256SUMS.json',{str(p.relative_to(root)):a.digest(p) for p in root.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json'})
def build(root,sessions,unknown=False):
 root.mkdir();usage={};observations=[];ev=[];local=[{'timestamp':'2026-11-04T00:00:00Z','type':'session_meta','payload':{'id':SID}}]
 for i in [1,2]:
  raw=root/'trajectory-001/raw'/f'call-{i:04d}-stdout.jsonl';mp=raw.with_name(f'call-{i:04d}-manifest.json');rp=raw.with_name(f'call-{i:04d}-result.json');prior=copy.deepcopy(usage) if usage else None;usage={'input_tokens':100*i,'cached_input_tokens':10*i,'output_tokens':20*i};delta={k:v-(prior or {}).get(k,0) for k,v in usage.items()};resume=SID if i>1 else None
  if unknown and i==2:usage.pop('output_tokens')
  meta={'raw_stdout':str(raw),'raw_manifest':str(mp),'session_id':SID,'prior_session_id':resume,'usage':{k:usage.get(k) for k in a.REQUIRED},'started_utc':f'2026-11-04T00:00:{i*10:02d}+00:00','finished_utc':f'2026-11-04T00:00:{i*10+5:02d}+00:00'}
  cmd={'argv':['codex','exec']+(['resume',SID] if resume else []),'native_session':{'resumed_session_id':resume},'call_index':i};write(mp,cmd);raw.write_text(json.dumps({'type':'thread.started','thread_id':SID})+'\n'+json.dumps({'type':'turn.completed','usage':usage})+'\n')
  response={'status':'ok','text':'{}','meta':meta};write(rp,response);ev.append({'kind':'model_response','round':i,'response':response})
  o={'sequence':i-1,'status':'unknown' if unknown and i==2 else 'known','session_id':SID,'resumed_session_id':resume,'session_resumed':bool(resume),'call_index':i,'raw_cumulative':copy.deepcopy(usage),'previous_cumulative':prior,'delta':None if unknown and i==2 else delta,'raw_stdout':str(raw),'raw_manifest':str(mp),'diagnostic':'missing_or_incompatible_usage' if unknown and i==2 else None}
  observations.append(o);write(root/'trajectory-001'/f'round-{i:03d}'/'result.json',{'trajectory_id':'trajectory-001','round':i,'usage_observation':o})
  local.append({'timestamp':f'2026-11-04T00:00:{i*10+4:02d}Z','type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':copy.deepcopy(usage),'last_token_usage':delta}}})
  local.append({'timestamp':f'2026-11-04T00:00:{i*10+4:02d}Z','type':'token_usage_record','payload':{'thread_id':SID,'session_id':SID,'turn_id':f'turn-{i}','thread_token_usage':copy.deepcopy(usage),'turn_token_usage':delta,'usage':delta}})
 prev='0'*64;lines=[]
 for i,e in enumerate(ev):
  row={'event':e,'sequence':i,'previous_sha256':prev};prev=hashlib.sha256(a.canonical(row)).hexdigest();row['sha256']=prev;lines.append(json.dumps(row))
 (root/'trajectory-001/events.jsonl').write_text('\n'.join(lines)+'\n')
 totals={'input_tokens':100,'cached_input_tokens':10,'output_tokens':20} if unknown else usage
 snap={'known_deduplicated_usage':totals,'unknown_usage_observations':int(unknown),'session_cumulative_snapshots':{SID:None if unknown else usage}}
 write(root/'usage_ledger.json',dict(observations=observations,**snap));write(root/'execution.json',dict(usage_stop_reason='usage_accounting_unknown' if unknown else None,**snap));write(root/'manifest.json',{'schema':'v10-long-history-1','execute':True});(root/'manifest.sha256').write_text(a.digest(root/'manifest.json')+'\n');seal(root)
 sessions.mkdir();lp=sessions/f'rollout-{SID}.jsonl';lp.write_text('\n'.join(json.dumps(e) for e in local)+'\n');return lp
class T(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.root=self.base/'campaign';self.sessions=self.base/'sessions'
 def test_clean_and_local_turn_usage(self):
  build(self.root,self.sessions);x=a.audit(self.root,self.sessions);self.assertTrue(x['passed'],x['issues']);self.assertEqual(x['raw_derived_known_usage']['output_tokens'],40);self.assertEqual(x['history_retention'],'unknown');self.assertTrue(all(r['record_turn_usage_matches_call_delta'] for r in x['local_rollouts'][0]['call_correspondence']))
 def test_unsealed_refused(self):
  self.root.mkdir();self.assertRaises(a.Refusal,a.audit,self.root,self.sessions)
 def test_changed_counter_resigned_still_fails(self):
  build(self.root,self.sessions)
  for p in [self.root/'usage_ledger.json',self.root/'trajectory-001/round-002/result.json']:
   d=a.read_json(p);o=d['observations'][1] if 'observations' in d else d['usage_observation'];o['raw_cumulative']['output_tokens']=999;write(p,d)
  seal(self.root);self.assertFalse(a.audit(self.root,self.sessions)['passed'])
 def test_missing_known_binding_fields_fails(self):
  build(self.root,self.sessions)
  for p in [self.root/'usage_ledger.json',self.root/'trajectory-001/round-002/result.json']:
   d=a.read_json(p);o=d['observations'][1] if 'observations' in d else d['usage_observation'];o.pop('raw_manifest');o.pop('raw_stdout');write(p,d)
  seal(self.root);self.assertFalse(a.audit(self.root,self.sessions)['passed'])
 def test_skipped_call_index_fails(self):
  build(self.root,self.sessions)
  for p in [self.root/'usage_ledger.json',self.root/'trajectory-001/round-002/result.json',self.root/'trajectory-001/raw/call-0002-manifest.json']:
   d=a.read_json(p);o=d['observations'][1] if 'observations' in d else d.get('usage_observation',d);o['call_index']=3;write(p,d)
  seal(self.root);self.assertFalse(a.audit(self.root,self.sessions)['passed'])
 def test_honest_unknown_preserved(self):
  build(self.root,self.sessions,unknown=True);x=a.audit(self.root,self.sessions);self.assertTrue(x['passed'],x['issues']);self.assertEqual(len(x['unknown_accounting_observations']),1);self.assertEqual(x['raw_derived_known_usage']['output_tokens'],20)
 def test_missing_rollout_unknown(self):
  p=build(self.root,self.sessions);p.unlink();x=a.audit(self.root,self.sessions);self.assertTrue(x['passed']);self.assertEqual(x['local_rollouts'][0]['rollout_status'],'missing')
 def test_compaction_event_and_duplicate_token_events(self):
  p=build(self.root,self.sessions);events=[a.loads(l) for l in p.read_text().splitlines()];events.insert(2,copy.deepcopy(events[1]));events.insert(3,{'timestamp':'2026-11-04T00:00:14Z','type':'compacted','payload':{}});p.write_text('\n'.join(json.dumps(e) for e in events)+'\n');x=a.audit(self.root,self.sessions);self.assertTrue(x['passed'],x['issues']);self.assertEqual(len(x['local_rollouts'][0]['exposed_context_events']),1)
 def test_wrong_local_identity_stops_before_later_parse(self):
  p=build(self.root,self.sessions);p.write_text(json.dumps({'type':'session_meta','payload':{'id':'other'}})+'\nNOT JSON PRIVATE CONTENT');x=a.audit(self.root,self.sessions);self.assertFalse(x['passed']);self.assertEqual(x['local_rollouts'][0]['rollout_status'],'contradictory_initial_identity');self.assertNotIn('rollout_sha256',x['local_rollouts'][0])
if __name__=='__main__':unittest.main(verbosity=2)
