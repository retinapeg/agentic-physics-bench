"""Prospective cumulative CLI usage accounting; unknown is never zero."""
import json,threading
from pathlib import Path
REQUIRED={'input_tokens','cached_input_tokens','output_tokens'}
ALLOWED=REQUIRED|{'reasoning_output_tokens','cache_write_input_tokens'}
class UsageLedger:
    def __init__(self):self.sessions={};self.known_totals={};self.unknown_observations=0;self.lock=threading.Lock()
    def observe(self,session_id,resumed_session_id,session_resumed,raw_usage,*,call_index):
        with self.lock:
            prior=self.sessions.get(session_id) if isinstance(session_id,str) else None
            result=dict(session_id=session_id,resumed_session_id=resumed_session_id,session_resumed=session_resumed,call_index=call_index,raw_cumulative=raw_usage,previous_cumulative=prior,status='unknown',delta=None,diagnostic=None)
            reason=None
            if not isinstance(session_id,str) or not session_id:reason='missing_session_identity'
            elif type(session_resumed) is not bool:reason='unknown_resume_flag'
            elif type(call_index) is not int or call_index<1:reason='invalid_call_index'
            elif not isinstance(raw_usage,dict) or not REQUIRED<=set(raw_usage) or not set(raw_usage)<=ALLOWED or any(type(v) is not int or v<0 for v in raw_usage.values()):reason='missing_or_incompatible_usage'
            elif session_id not in self.sessions and (session_resumed or resumed_session_id is not None or call_index!=1):reason='unverified_initial_baseline'
            elif session_id in self.sessions and (not session_resumed or resumed_session_id!=session_id):reason='session_reused_without_valid_resume'
            elif session_id in self.sessions and prior is None:reason='prior_usage_unknown'
            elif prior is not None and set(prior)!=set(raw_usage):reason='counter_schema_changed'
            elif prior is not None and any(raw_usage[k]<prior[k] for k in raw_usage):reason='counter_decreased_or_reset'
            if reason:
                result['diagnostic']=reason;self.unknown_observations+=1
                if isinstance(session_id,str) and session_id:self.sessions[session_id]=None
                return result
            baseline=prior if prior is not None else {key:0 for key in raw_usage}
            delta={key:raw_usage[key]-baseline[key] for key in raw_usage}
            self.sessions[session_id]=dict(raw_usage)
            for key,value in delta.items():self.known_totals[key]=self.known_totals.get(key,0)+value
            result.update(status='known',delta=delta,baseline='previous_recorded_total' if prior is not None else 'verified_new_session_zero')
            return result
    def observe_response(self,response):
        meta=response.get('meta') or {}
        try:
            manifest=json.loads(Path(meta['raw_manifest']).read_text())
            events=[json.loads(line) for line in Path(meta['raw_stdout']).read_text().splitlines() if line.strip()]
            if any(not isinstance(event,dict) for event in events):raise ValueError('Non-object raw trace event')
            completions=[e for e in events if e.get('type')=='turn.completed'];threads=[e for e in events if e.get('type')=='thread.started']
            if len(completions)!=1 or len(threads)!=1:raise ValueError('Expected exactly one completed turn and thread identity')
            sid=threads[0].get('thread_id')
            if sid!=meta.get('session_id'):raise ValueError('Raw/meta session identity mismatch')
            native=manifest['native_session'];resumed=native['resumed_session_id'];flag='resume' in manifest['argv']
            if resumed!=meta.get('prior_session_id') or flag!=(resumed is not None):raise ValueError('Raw/meta resume identity mismatch')
            usage=completions[0].get('usage')
            if isinstance(usage,dict) and any((meta.get('usage') or {}).get(key)!=usage.get(key) for key in REQUIRED):raise ValueError('Raw/meta usage mismatch')
            observed=self.observe(sid,resumed,flag,usage,call_index=manifest['call_index'])
            observed.update(raw_manifest=meta['raw_manifest'],raw_stdout=meta['raw_stdout'])
            return observed
        except (OSError,ValueError,TypeError,KeyError) as exc:
            with self.lock:
                self.unknown_observations+=1
                if isinstance(meta.get('session_id'),str):self.sessions[meta['session_id']]=None
            return dict(status='unknown',diagnostic='unverifiable_raw_usage: '+type(exc).__name__+': '+str(exc),session_id=meta.get('session_id'),raw_cumulative=meta.get('usage'),previous_cumulative=None,delta=None)
    def snapshot(self):
        with self.lock:return dict(known_deduplicated_usage=dict(self.known_totals),unknown_usage_observations=self.unknown_observations,session_cumulative_snapshots=dict(self.sessions),semantics='CLI cumulative counter differences; known subtotal, not independent billing evidence')
