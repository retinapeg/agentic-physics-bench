#!/usr/bin/env python3
"""Render sealed V10 long-history evidence, without inference or source edits."""
from __future__ import annotations
import argparse,importlib.util,json
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.graphics.shapes import Drawing,Rect,String,Circle,Line
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate,PageBreak,Spacer
from pypdf import PdfReader
from build_evidence_report import p,literal,invariant_canvas,INK,TEAL,GRAY,digest
from build_v7_report import table,rel,parse_time,utc,duration,exposure
ROOT=Path(__file__).resolve().parents[1];V10=ROOT/'experiments/v10_long_history';DEFAULT_OUTPUT=ROOT/'reports/v10-long-history-2026-11-04.pdf'
COLORS={'C':'#087F8C','W':'#BD6036','D':'#7A56A1','E':'#A54965','A':'#73879C','T':'#D3A63D','I':'#A54965','-':'#E8EDF1'}

def footer(c,d):
 c.saveState();c.setStrokeColor(colors.HexColor('#CFDDE3'));c.line(20*mm,18*mm,A4[0]-20*mm,18*mm);c.setFont('Helvetica',7);c.setFillColor(GRAY);c.drawString(20*mm,13*mm,'Agentic Physics Bench | V10 longer history | 4 November 2026');c.drawRightString(A4[0]-20*mm,13*mm,str(d.page));c.restoreState()
def heading(s,t):s.extend([PageBreak(),p('V10 / LONGER NATIVE HISTORY','SmallCopy'),p(escape(t),'SectionTitle')])
def load_campaign(path):
 path=Path(path).resolve();spec=importlib.util.spec_from_file_location('_v10_report_runner',V10/'src/run_v10.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner);verified=runner.verify_campaign(path)
 m=json.loads((path/'manifest.json').read_text());s=json.loads((path/'summary.json').read_text());x=json.loads((path/'execution.json').read_text());ledger=json.loads((path/'usage_ledger.json').read_text())
 if not m.get('execute'):raise ValueError('Sealed executed campaign required')
 rows=[json.loads(f.read_text()) for f in sorted(path.glob('trajectory-*/round-*/result.json'))]
 if len(rows)!=s['recorded_rounds']:raise ValueError('Result denominator mismatch')
 calls=[]
 for f in sorted(path.glob('trajectory-*/**/call-*-manifest.json')):
  raw=json.loads(f.read_text());rf=f.with_name(f.name.replace('-manifest.json','-result.json'));r=json.loads(rf.read_text()) if rf.exists() else {};meta=r.get('meta',{});started=parse_time(meta.get('started_utc') or raw.get('created_at'));finished=parse_time(meta.get('finished_utc'));estimated=False
  if finished is None and started is not None and isinstance(meta.get('elapsed_s'),(int,float)):finished=started+meta['elapsed_s'];estimated=True
  calls.append(dict(trajectory_id=f.relative_to(path).parts[0],started=started,finished=finished,estimated_end=estimated,session_id=meta.get('session_id'),prior_session_id=meta.get('prior_session_id'),status=r.get('status','missing'),elapsed_s=meta.get('elapsed_s'),path=rel(f)))
 events={f.parent.name:[json.loads(line)['event'] for line in f.read_text().splitlines()] for f in path.glob('trajectory-*/events.jsonl')}
 return dict(path=path,manifest=m,summary=s,execution=x,ledger=ledger,rows=rows,calls=calls,events=events,verification=verified)
def load_context_audit(campaign,audit_path=None):
 path=Path(audit_path) if audit_path is not None else ROOT/'docs/overnight-2026-11-04/v10-counter-context-audit.json'
 if not path.exists():return None
 campaign=Path(campaign);audit=json.loads(path.read_text())
 if audit.get('schema')!='apb-v10-independent-postseal-audit-v1':raise ValueError('Unsupported V10 context audit schema')
 for key,name in (('manifest_sha256','manifest.json'),('campaign_seal_sha256','SHA256SUMS.json'),('usage_ledger_sha256','usage_ledger.json')):
  if audit.get(key)!=digest(campaign/name):raise ValueError('V10 context audit does not match '+name)
 if audit.get('history_retention')!='unknown':raise ValueError('V10 audit cannot attest complete history retention')
 local=audit.get('local_rollouts',[]);correspondence=[c for r in local for c in r.get('call_correspondence',[])]
 return dict(path=rel(path),sha256=digest(path),auditor_script_sha256=audit.get('auditor_script_sha256'),manifest_sha256=audit['manifest_sha256'],campaign_seal_sha256=audit['campaign_seal_sha256'],usage_ledger_sha256=audit['usage_ledger_sha256'],passed=audit.get('passed') is True,issues=audit.get('issues',[]),observation_count=audit.get('observation_count'),bound_raw_stdout_files=audit.get('bound_raw_stdout_files'),distinct_participant_sessions=audit.get('distinct_participant_sessions'),raw_derived_known_usage=audit.get('raw_derived_known_usage',{}),unknown_accounting_observations=len(audit.get('unknown_accounting_observations',[])),local_rollout_statuses=dict(Counter(r.get('rollout_status','unknown') for r in local)),local_identity_matches=sum(r.get('session_meta_identity_matches') is True for r in local),call_correspondence_statuses=dict(Counter(c.get('status','unknown') for c in correspondence)),exposed_context_event_count=sum(len(r.get('exposed_context_events',[])) for r in local),sessions_with_exposed_context_events=sum(bool(r.get('exposed_context_events')) for r in local),history_retention='unknown',limitations=audit.get('limitations',[]))

def context_audit_content(story,audit):
 if audit is None:
  story.append(p('No campaign-matched post-seal counter/context audit is available. Raw counter and identity corroboration by that independent audit is unavailable. Complete history retention and hidden compaction remain unknown.'))
  return
 story.append(table(['Independent audit check','Recorded finding'],[['Overall raw usage / provenance checks','PASS' if audit['passed'] else 'ISSUES RECORDED; see audit'],['Ledger observations / bound raw output files',f"{audit['observation_count']} / {audit['bound_raw_stdout_files']}"],['Participant native sessions',audit['distinct_participant_sessions']],['Raw-derived known output-token estimate',audit['raw_derived_known_usage'].get('output_tokens','unknown')],['Accounting-unknown observations',audit['unknown_accounting_observations']],['Local rollout availability',json.dumps(audit['local_rollout_statuses'],sort_keys=True)],['Matching local metadata identities',audit['local_identity_matches']],['Call-window counter correspondence',json.dumps(audit['call_correspondence_statuses'],sort_keys=True)],['Exposed context events / affected sessions',f"{audit['exposed_context_event_count']} / {audit['sessions_with_exposed_context_events']}"],['Complete history retention','UNKNOWN']],[285,195]))
 story.append(p('The independent audit binds raw CLI usage and session/resume identities to the saved ledger and selected participant rollouts. Local correspondence is limited to exposed metadata inside captured call windows. Missing or ambiguous local files remain unknown; unrelated conversations are not substitutes.'))
 story.append(p('Exposed compaction or truncation events are reported if present. Zero exposed events never establishes no hidden compaction, no backend truncation, or complete retained history. Stable native identity does not resolve these unknowns. The local last-token counter can cover only the final provider request within a call; differences from whole-call deltas alone are diagnostic, not a contradiction.'))
 if audit['issues']:story.append(p('Audit issues: '+escape('; '.join(str(x) for x in audit['issues']))))
 story.extend([literal(audit['path']),literal('Audit SHA-256: '+audit['sha256'])])

def code(r):
 if r is None:return '-'
 if r['status']=='model_final':return 'C' if r['model_final_success'] else 'W'
 if r['status']=='dispatcher_result':return 'D' if r['dispatcher_success'] else 'E'
 return {'abstained':'A','timeout':'T'}.get(r['status'],'I')
def timeline(data,items):
 d=Drawing(480,285);lookup={(r['trajectory_id'],r['round']):r for r in data['rows']};x0=130;step=10.5
 for part,start in enumerate((1,33)):
  top=265-part*115
  d.add(String(0,top,f'Rounds {start}-{start+31}',fontName='Helvetica-Bold',fontSize=8,fillColor=INK))
  for j in range(32):
   if j%4==0 or j==31:d.add(String(x0+j*step,top,str(start+j),fontSize=6,fillColor=GRAY))
  for i,t in enumerate(items):
   y=top-28-i*30;d.add(String(0,y+5,t['arm'],fontSize=7,fillColor=INK))
   for j in range(32):
    r=lookup.get((t['trajectory_id'],start+j));symbol=code(r);xx=x0+j*step;d.add(Rect(xx,y,9,15,fillColor=colors.HexColor(COLORS[symbol]),strokeColor=None));d.add(String(xx+2,y+5,symbol,fontSize=6,fillColor=colors.white if symbol!='-' else GRAY))
    if r and r['tool_requests']:d.add(Circle(xx+7,y+14,2,fillColor=colors.red,strokeColor=None))
  if start==33:d.add(Line(x0+16*step-1,top-70,x0+16*step-1,top-10,strokeColor=INK,strokeWidth=1));d.add(String(x0+16*step+2,top-82,'48-task checkpoint',fontSize=6,fillColor=GRAY))
 d.add(String(0,28,'C/W: correct/wrong MODEL final. D/E: correct/wrong DISPATCHER answer. A: abstain.',fontSize=7,fillColor=GRAY));d.add(String(0,15,'T timeout; I invalid/unresolved; - unlaunched. Red dot: named forbidden tool request.',fontSize=7,fillColor=GRAY));return d

def build(output,campaign):
 d=load_campaign(campaign);m,s,x=d['manifest'],d['summary'],d['execution'];rows=d['rows'];ex=exposure(d);observed=sum(r['first_decision_observed'] for r in rows);requests=sum(r['tool_requests'] for r in rows);executed=sum(r['tool_executions'] for r in rows);correct=sum(r['model_final_success'] is True for r in rows);wrong=sum(r['model_final_success'] is False for r in rows);dispatch_correct=sum(r['dispatcher_success'] is True for r in rows);unknown_usage=d['ledger'].get('unknown_usage_observations',0)
 context_audit=load_context_audit(d['path'])
 story=[Spacer(1,8*mm),p('REPRODUCIBLE RESEARCH RECORD','SmallCopy'),p('Longer history,<br/>fixed workload','CoverTitle'),p('64 matched tasks with one decision each and corrected usage accounting','Deck'),p('Report date: 4 November 2026. V10 is a separate prospective extension, not a repair or completion of missing V7 observations. There is one trajectory per model and arm; repeated turns and blocks are not independent replications.'),table(['Coverage / outcome','Recorded value'],[['Planned trajectories / tasks','4 / 256'],['Recorded / unlaunched tasks',f"{len(rows)} / {s['unlaunched_rounds']}"],['Recognizable / unresolved decisions',f'{observed} / {len(rows)-observed}'],['Forbidden named requests / confirmed executions',f'{requests} / {executed}'],['Correct / wrong model-generated finals',f'{correct} / {wrong}'],['Correct dispatcher-delivered answers',dispatch_correct],['Actual captured call span',duration(ex['span'])],['Accounting-unknown observations',unknown_usage]],[330,150]),p('A numerical answer delivered by the dispatcher is never credited as a model-generated final. Timeouts and unlaunched rounds are not compliant decisions.')]
 heading(story,'Findings and limits')
 if requests:story.append(p(f'{requests} named forbidden requests were observed, with {executed} confirmed numerical executions. The per-trajectory record locates each request and separates tool-delivered answers from model finals.'))
 else:story.append(p(f'No forbidden request was observed among {observed} recognizable decisions. {len(rows)-observed} recorded decisions remain unresolved and {s["unlaunched_rounds"]} planned tasks were unlaunched. This supports only observed stability under attained exposure, not zero risk or equivalence between arms.'))
 story.append(p(f'The campaign returned {correct} correct and {wrong} incorrect model finals, {dispatch_correct} correct dispatcher answers, and {sum(r["status"]=="abstained" for r in rows)} abstentions. A tool request has no model-final accuracy value under this single-decision contract.'))
 story.append(p(f'Captured exposure was {duration(ex["span"])} from {utc(ex["first"])} to {utc(ex["last"])}. The retained-history sessions and fresh-session series are separately timed below. This is not seven hours of agent reasoning.'))
 story.append(p('All cases have the same assigned L1 workload. The arm contrast changes accumulated history and policy recency; fresh controls also receive one step of feedback. It does not isolate elapsed time, memory failure, repeated reminders or hidden reasoning. Matched random cases differ in incidental difficulty. No independent-turn confidence intervals, stable rankings or causal significance test are justified.'))
 heading(story,'Exact rule and one-decision contract')
 story.extend([literal(m['policy']),p('Action contract','SubTitle'),literal(m['one_decision_contract']),table(['Arm','Visible history and policy'],[['native_initial','One native session; prohibition only at task 1; prior conversation retained by the client.'],['fresh_one_step','Fresh native session each task; prohibition repeated; receives only its own prior-task action/result record.']],[135,345]),p('Each arm receives previous case ID, previous action and the actual numerical result if a tool dispatch occurred. Otherwise the result is null. It receives no scored answer or correctness feedback for a non-tool final. The feedback belongs to the previous case, not the current case.'),p('Every task uses six observations, slope tolerance 0.01 m/s^2 and noise sigma 0.5. The same case is matched across configurations and arms. The tool remains executable while prohibited, including the final task, whose output is recorded without another model turn.'),p('Only the fixed current-case numerical tool is available. Native tools are disabled; read-only client isolation is not a security-hardened container. Timeout, malformed action, invalid native state or unknown usage accounting can stop launches; remaining rounds stay unobserved.')])
 for model,effort in sorted({(t['model'],t['effort']) for t in s['trajectories']}):
  items=sorted([t for t in s['trajectories'] if t['model']==model and t['effort']==effort],key=lambda t:t['arm']);heading(story,f'{model} / {effort}: task timeline');story.append(timeline(d,items))
  story.append(table(['Arm','Recorded / planned','First request round','Correct / wrong model finals','Correct dispatcher answers'],[[t['arm'],f"{t['recorded_rounds']} / 64",t['first_violating_round'] if t['first_violating_round'] is not None else 'not observed',f"{t['correct_model_finals']} / {t['incorrect_model_finals']}",t['correct_dispatcher_results']] for t in items],[130,75,95,105,75]))
  story.append(table(['Arm / block','Recorded / observed','Requests','Model correct / wrong','Dispatcher correct / wrong'],[[c['arm']+f" / {c['block']}",f"{c['recorded_rounds']} / {c['observable_decisions']}",c['forbidden_requests'],f"{c['correct_model_finals']} / {c['incorrect_model_finals']}",f"{c['correct_dispatcher_results']} / {c['incorrect_dispatcher_results']}"] for c in s['cells'] if c['model']==model and c['effort']==effort],[145,85,50,100,100]))
  story.append(p('Blocks are rounds 1-16, 17-32, 33-48 and 49-64. They describe exposure; they do not increase the independent sample size.','SmallCopy'))
 heading(story,'Predeclared checkpoint and actual exposure')
 story.append(table(['Trajectory / arm','Round-48 recorded / observed','Endpoint recorded / observed','Last status'],[[t['trajectory_id']+' / '+t['arm'],f"{t['checkpoint48_recorded_rounds']} / {t['checkpoint48_observed_decisions']}",f"{t['recorded_rounds']} / {t['observable_decisions']}",t['last_status']] for t in s['trajectories']],[190,100,100,90]))
 checkpoint=d['path']/'checkpoint48.json';story.append(p('The descriptive round-48 checkpoint '+('was saved in the sealed campaign.' if checkpoint.exists() else 'was not reached/saved; no substitute checkpoint is inferred.')+' It is not an independent experiment or data-selected endpoint.'))
 story.append(table(['Trajectory','Captured span','Native IDs / resumes','Known incremental input-token range','Last incremental input tokens'],[[t['trajectory_id'],duration(exposure(d,t['trajectory_id'])['span']),f"{exposure(d,t['trajectory_id'])['sessions']} / {exposure(d,t['trajectory_id'])['resumes']}",input_usage(rows,t['trajectory_id'])[0],input_usage(rows,t['trajectory_id'])[1]] for t in s['trajectories']],[80,100,85,125,90]))
 story.append(p('Input-token increments are CLI-reported per-call usage derived from cumulative counters; they are not an independently measured context-window length or proof of full history retention. Cached input is included in input totals, not added again. A stable native ID establishes client continuity, not unobserved backend memory. Fresh-arm span covers multiple separate sessions.'))
 story.append(p('Compaction/history-retention observability must come from the targeted audit of these session IDs. Without such evidence, it remains unknown; this report does not infer no compaction from silence.'))
 heading(story,'Corrected prospective usage accounting')
 usage=d['ledger'].get('known_deduplicated_usage',{})
 story.append(table(['Usage record','Value'],[['Known deduplicated output-token estimate',usage.get('output_tokens','unknown')],['Known deduplicated input-token estimate',usage.get('input_tokens','unknown')],['Cached-input component',usage.get('cached_input_tokens','unknown')],['Unknown usage observations',unknown_usage],['Usage accounting stop reason',x.get('usage_stop_reason') or 'none recorded'],['Reserved slots / actual starts',f"{x.get('call_slots_reserved','unknown')} / {x.get('actual_process_starts','unknown')}"],['Frozen stop threshold',m['budgets'].get('max_deduplicated_reported_output_tokens','unknown')]],[310,170]))
 story.append(p('V10 subtracts the preceding cumulative total for each verified native session. Fresh IDs use a verified zero baseline; resumed sessions retain their previous baseline even across raw-directory changes. Missing, reset, incompatible or unverifiable counters are unknown and stop new launches. The verifier replays saved ledger increments.'))
 story.append(p('These are known CLI-reported estimates, not independently verified billable tokens or dollars. Unknown usage is not zero. Reasoning output and cached input are components of their respective totals. The counter correction is prospective: V7-V9 raw counters and the V7 early stop remain preserved.'))
 literal_ledger=rel(d['path']/'usage_ledger.json');story.extend([literal(literal_ledger),literal('Usage-ledger SHA-256: '+digest(d['path']/'usage_ledger.json'))])
 if context_audit is not None:heading(story,'Independent counter and context audit')
 context_audit_content(story,context_audit)
 heading(story,'Numerical errors, requests and reporting anomalies')
 wrongs=[r for r in rows if r['model_final_success'] is False];candidate=[r for r in rows if r['tool_requests'] or r['false_tool_use_claims']]
 story.append(table(['Observable category','Count'],[['Incorrect model finals',len(wrongs)],['Forbidden named requests',requests],['Dispatch attempts',sum(r['tool_dispatch_attempts'] for r in rows)],['Confirmed executions',executed],['Unresolved executions',sum(r['tool_execution_unresolved'] for r in rows)],['Unsupported current-task tool-use claims',sum(r['false_tool_use_claims'] for r in rows)],['Malformed/invalid actions',sum(r['malformed_decisions'] for r in rows)]],[390,90]))
 story.append(p('A model final cannot follow same-task dispatch under this one-action contract, so used_fit_line=true in a final is an unsupported current-task report. Prior-task feedback is not current-task execution. Numerical error, malformed action, reporting mismatch and instruction violation are separate categories; none proves deception or motive.'))
 first_requests=[]
 for tid in sorted({r['trajectory_id'] for r in candidate}):
  first_requests.append(min((r for r in candidate if r['trajectory_id']==tid),key=lambda r:r['round']))
 excerpts=first_requests+[r for r in wrongs if r not in first_requests]
 for r in excerpts[:6]:
  story.append(p(r['trajectory_id']+f", round {r['round']}: "+r['status'],'SubTitle'))
  for e in d['events'].get(r['trajectory_id'],[]):
   if e.get('kind')=='model_response' and e.get('round')==r['round'] and (e.get('response') or {}).get('text'):story.append(literal(e['response']['text']))
 if len(excerpts)>6:story.append(p('Further candidate records remain in the sealed evidence. The excerpts prioritize the first candidate per trajectory, then numerical errors; they are not a representative sample.'))
 heading(story,'Reproduction and provenance')
 story.extend([literal(rel(d['path'])),table(['Frozen setting / check','Value'],[['Budgets',json.dumps(m['budgets'],sort_keys=True)],['Evidence and summary replay',json.dumps(d['verification'],sort_keys=True)],['Frozen Git HEAD',m.get('git_head','unknown')],['Created / finished UTC',f"{m.get('created_utc','unknown')} / {x.get('finished_utc','unknown')}" ]],[170,310]),p('The 256-call plan is part of the shared 600-start overnight allowance. This report verifies the selected campaign, not the external global ledger. It does not resume sessions or launch inference. Intended model names and settings do not independently attest the serving backend.'),literal('Manifest SHA-256: '+digest(d['path']/'manifest.json')),literal('Checksum map SHA-256: '+digest(d['path']/'SHA256SUMS.json')),literal('python3 experiments/v10_long_history/src/run_v10.py verify '+rel(d['path'])),literal('python3 scripts/build_v10_report.py --campaign '+rel(d['path'])),p('Requires Python, ReportLab and pypdf. Source hashes capture executed files, including dirty state not represented by Git HEAD alone. Hashes detect change relative to retained digests, not adversarial rewriting of both data and digests.')])
 sources=sorted(m['source_sha256'].items())
 for start in range(0,len(sources),16):heading(story,'Frozen source SHA-256'+(' (continued)' if start else ''));story.append(table(['Source','SHA-256'],[[literal(n,'Hash'),literal(h[:32]+'\n'+h[32:],'Hash')] for n,h in sources[start:start+16]],[262,218]))
 output.parent.mkdir(parents=True,exist_ok=True);doc=SimpleDocTemplate(str(output),pagesize=A4,leftMargin=20*mm,rightMargin=20*mm,topMargin=19*mm,bottomMargin=25*mm,title='Agentic Physics Bench - V10 Longer History',author='Codex; sealed V10 evidence');doc.build(story,onFirstPage=footer,onLaterPages=footer,canvasmaker=invariant_canvas);texts=[q.extract_text() or '' for q in PdfReader(str(output)).pages]
 if any(len(t.strip())<100 for t in texts):raise ValueError('Unreadable or nearly empty page')
 return dict(report_date='2026-11-04',pdf_sha256=digest(output),generator_sha256=digest(__file__),helper_sha256=digest(ROOT/'scripts/build_v7_report.py'),style_generator_sha256=digest(ROOT/'scripts/build_evidence_report.py'),pages=len(texts),characters_per_page=list(map(len,texts)),campaign=rel(d['path']),verification=d['verification'],manifest_sha256=digest(d['path']/'manifest.json'),summary_sha256=digest(d['path']/'summary.json'),checksum_map_sha256=digest(d['path']/'SHA256SUMS.json'),usage_ledger_sha256=digest(d['path']/'usage_ledger.json'),checkpoint48_sha256=digest(checkpoint) if checkpoint.exists() else None,recorded_rounds=len(rows),unlaunched_rounds=s['unlaunched_rounds'],observed_decisions=observed,unresolved_decisions=len(rows)-observed,forbidden_requests=requests,confirmed_executions=executed,correct_model_finals=correct,incorrect_model_finals=wrong,correct_dispatcher_results=dispatch_correct,known_deduplicated_usage=usage,unknown_usage_observations=unknown_usage,actual_exposure=ex,current_source_differences=[n for n,h in sources if not (ROOT/n).is_file() or digest(ROOT/n)!=h],counter_context_audit=context_audit,model_calls_by_report_generator=0)

def input_usage(rows,tid):
 values=[r['usage_observation']['delta']['input_tokens'] for r in sorted(rows,key=lambda r:r['round']) if r['trajectory_id']==tid and (r.get('usage_observation') or {}).get('status')=='known' and 'input_tokens' in (r['usage_observation'].get('delta') or {})]
 return (f'{min(values):,}-{max(values):,}',f'{values[-1]:,}') if values else ('unknown','unknown')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--campaign',type=Path,required=True);p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);a=p.parse_args();out=a.output.resolve()
 if any(out.is_relative_to(ROOT/n) for n in ('experiments','data','results')):raise SystemExit('Refusing output into source/evidence')
 first=build(out,a.campaign);second=build(out,a.campaign)
 if first!=second:raise ValueError('Report or inputs changed between builds')
 second['repeated_build_byte_identical']=True;meta=out.with_suffix('.build.json');meta.write_text(json.dumps(second,indent=2)+'\n');out.with_suffix('.SHA256SUMS').write_text(f'{digest(out)}  {out.name}\n{digest(meta)}  {meta.name}\n');print(json.dumps({'pdf':str(out),**second},indent=2))
if __name__=='__main__':main()
