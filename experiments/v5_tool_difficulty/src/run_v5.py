"""Prospective, exclusive-directory V5 development campaigns; no historical runner invoked."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import random
import platform
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())

def source_hashes():
    files = list(HERE.glob('*.py')) + list((HERE.parent/'tests').glob('*.py'))
    files += [ROOT/'src/tools.py', ROOT/'src/tasks.py']
    files += list(HERE.parent.glob('*.md'))
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(files)}

def verify_sources(hashes):
    changed = [p for p,h in hashes.items() if not (ROOT/p).is_file() or digest(ROOT/p) != h]
    if changed:
        raise RuntimeError('Frozen source changed: '+', '.join(changed))

def build_plan(seeds, models):
    from tasks import make_task, make_necessary_task
    plan=[]
    for model, effort in models:
        block=[]
        for seed in seeds:
            for level in range(1,5):
                task=make_task(level, seed)
                for condition in ('forbidden','allowed','no_tool'):
                    block.append(dict(task=task,condition=condition,model=model,effort=effort))
            block.append(dict(task=make_necessary_task(seed),condition='necessary_tool',model=model,effort=effort))
        random.Random(20261103).shuffle(block)
        plan.extend(block)
    for i,item in enumerate(plan):
        item['episode_id']=f'episode-{i+1:03d}'
    return plan

class Budget:
    def __init__(self, calls, tokens, seconds):
        self.max_calls=calls
        self.max_tokens=tokens
        self.deadline=time.monotonic()+seconds
        self.calls=0
        self.tokens=0
        self.unknown_usage_calls=0
        self.lock=threading.Lock()

    def reserve(self):
        with self.lock:
            if self.calls >= self.max_calls: return 'call_budget'
            if self.tokens >= self.max_tokens: return 'observed_token_budget'
            if time.monotonic() >= self.deadline: return 'campaign_deadline'
            self.calls+=1
            return None

    def record(self, result):
        # Adapter reports provider usage when available; missing usage is not zero-cost evidence.
        usage=result.get('usage', result.get('meta',{}).get('usage',{})) or {}
        with self.lock:
            self.tokens+=int(usage.get('output_tokens',0) or 0)
            self.unknown_usage_calls+=int(usage.get('output_tokens') is None)

class EventLog:
    def __init__(self,path):
        self.path=path
        self.previous='0'*64
        self.sequence=0
        self.file=path.open('x')

    def __call__(self,event):
        row={'sequence':self.sequence,'previous_sha256':self.previous,'event':event}
        self.previous=hashlib.sha256(canonical(row)).hexdigest()
        row['sha256']=self.previous
        self.file.write(canonical(row).decode()+'\n')
        self.file.flush()
        os.fsync(self.file.fileno())
        self.sequence+=1

    def close(self): self.file.close()

def seal(directory):
    files={str(p.relative_to(directory)):digest(p) for p in sorted(directory.rglob('*'))
           if p.is_file() and p.name != 'SHA256SUMS.json'}
    save(directory/'SHA256SUMS.json',files)

def verify_campaign(directory):
    directory=Path(directory)
    hashes=json.loads((directory/'SHA256SUMS.json').read_text())
    bad=[p for p,h in hashes.items() if not (directory/p).is_file() or digest(directory/p)!=h]
    actual={str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json'}
    bad.extend(sorted(actual-set(hashes)))
    for p in directory.glob('episode-*/events.jsonl'):
        previous='0'*64
        for i,line in enumerate(p.read_text().splitlines()):
            row=json.loads(line)
            h=row.pop('sha256')
            if row['sequence'] != i or row['previous_sha256'] != previous or hashlib.sha256(canonical(row)).hexdigest()!=h:
                bad.append(str(p))
            previous=h
    if bad: raise RuntimeError('Evidence verification failed: '+repr(bad))
    manifest_path=directory/'manifest.json'
    if manifest_path.exists():
        if (directory/'manifest.sha256').read_text().strip()!=digest(manifest_path):
            raise RuntimeError('Pre-call manifest digest mismatch')
        manifest=json.loads(manifest_path.read_text())
        if manifest['execute']:
            from analyze import summarize
            results=[json.loads((directory/p['episode_id']/'result.json').read_text()) for p in manifest['plan']]
            if summarize(results)!=json.loads((directory/'summary.json').read_text()):
                raise RuntimeError('Recomputed summary differs from sealed summary')
    return {'verified_files':len(hashes),'event_logs':len(list(directory.glob('episode-*/events.jsonl'))),
            'summary_recomputed':manifest_path.exists() and manifest['execute']}

def run(directory, *, execute=False, max_calls=104, seconds=1200, timeout=60, token_budget=120000, mode='pilot'):
    from engine import run_episode
    from analyze import summarize
    if min(max_calls, seconds, timeout, token_budget) <= 0 or timeout > 900:
        raise ValueError('Budgets must be positive and timeout at most 900 seconds')
    if mode=='pilot':
        plan=build_plan([2026110301,2026110302],[('gpt-6.1-sol','high'),('gpt-6-astra','ultra')])
    else:
        from tasks import make_task
        # Independent assessment seeds, chosen before reading the pilot outcomes.
        plan=[dict(task=make_task(4,seed),condition='no_tool',model='gpt-6.1-sol',effort='high',
                   episode_id=f'episode-{i+1:03d}') for i,seed in enumerate(range(2026110401,2026110431))]
    directory=Path(directory).resolve()
    directory.mkdir(parents=True,exist_ok=False)
    hashes=source_hashes()
    frozen_identities={}
    if execute:
        from adapter import preflight
        for model,effort in sorted({(p['model'],p['effort']) for p in plan}):
            try: frozen_identities[model]=preflight(model,effort)
            except Exception as exc: frozen_identities[model]={'error':type(exc).__name__+': '+str(exc)}
    manifest={'schema':'v5-development-1','created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
              'python_version':sys.version,'platform':platform.platform(),
              'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'git_status':subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True),
              'source_sha256':hashes,'plan':plan,'execute':execute,'mode':mode,'frozen_cli_identities':frozen_identities,
              'budgets':{'max_calls':max_calls,'wall_seconds':seconds,'call_timeout_seconds':timeout,
                         'observed_output_tokens_stop':token_budget,'concurrency':2,'decisions_per_episode':3,'tool_calls_per_episode':2},
              'sampling':'Task seeds fixed in plan, fresh contexts; provider sampling seed unsupported. Development only.',
              'token_budget_limitation':'Observed usage stop; concurrent in-flight calls and unreported usage can overshoot. Not a billing cap.'}
    save(directory/'manifest.json',manifest)
    (directory/'manifest.sha256').write_text(digest(directory/'manifest.json')+'\n')
    if not execute:
        seal(directory)
        return {'planned':len(plan),'executed':False,'directory':str(directory)}
    from adapter import CodexAdapter
    budget=Budget(max_calls,token_budget,seconds)
    def episode(item):
        out=directory/item['episode_id']; out.mkdir()
        save(out/'attempt.json',item)
        events=EventLog(out/'events.jsonl')
        adapter=None
        preflight_error=None
        try:
            frozen=frozen_identities[item['model']]
            if 'error' in frozen: raise RuntimeError(frozen['error'])
            adapter=CodexAdapter(item['model'],item['effort'],out/'raw',timeout_s=timeout)
            if adapter.identity != frozen: raise RuntimeError('CLI identity differs from campaign freeze')
        except Exception as exc:
            preflight_error=type(exc).__name__+': '+str(exc)
        def call(prompt):
            if preflight_error:
                return {'status':'preflight_error','text':'','error':preflight_error,'model_call_started':False}
            try: verify_sources(hashes)
            except RuntimeError as e: return {'status':'source_changed','text':'','error':str(e),'model_call_started':False}
            stop=budget.reserve()
            if stop: return {'status':stop,'text':'','model_call_started':False}
            result=adapter(prompt)
            result['model_call_started']=result.get('meta',{}).get('returncode') is not None
            budget.record(result)
            return result
        try:
            result=run_episode(item['task'],item['condition'],call,model=item['model'],effort=item['effort'],emit=events)
            result['episode_id']=item['episode_id']
            save(out/'result.json',result)
        finally: events.close()
        print(json.dumps({'episode':item['episode_id'],'model':item['model'],'condition':item['condition'],
                          'level':item['task']['level'],'status':result.get('status'),
                          'success':result.get('success'),'calls_started':budget.calls}),flush=True)
        return result
    results=[]
    # Codex/Sol block is attempted before Astra, with at most two concurrent episodes.
    for model in ('gpt-6.1-sol','gpt-6-astra'):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results.extend(pool.map(episode,[p for p in plan if p['model']==model]))
    save(directory/'summary.json',summarize(results))
    save(directory/'execution.json',{'call_slots_reserved':budget.calls,
         'calls_started':sum(r['model_calls'] for r in results),
         'observed_output_tokens':budget.tokens,'unknown_usage_calls':budget.unknown_usage_calls,'episodes':len(results)})
    seal(directory)
    return verify_campaign(directory)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['plan','run','verify'])
    parser.add_argument('directory')
    parser.add_argument('--max-calls',type=int,default=104)
    parser.add_argument('--seconds',type=int,default=1200)
    parser.add_argument('--timeout',type=int,default=60)
    parser.add_argument('--mode',choices=['pilot','boundary'],default='pilot')
    args=parser.parse_args()
    if args.command=='verify': result=verify_campaign(args.directory)
    else: result=run(args.directory,execute=args.command=='run',max_calls=args.max_calls,seconds=args.seconds,timeout=args.timeout,mode=args.mode)
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
