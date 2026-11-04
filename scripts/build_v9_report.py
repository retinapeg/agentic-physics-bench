#!/usr/bin/env python3
"""Build a separate V9 memory-handoff report from sealed evidence, without inference."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.graphics.shapes import Drawing,Rect,String,Circle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate,PageBreak,Spacer
from pypdf import PdfReader
from build_evidence_report import p,literal,invariant_canvas,INK,TEAL,GRAY,digest
from build_v7_report import table,rel,parse_time,utc,duration,exposure,outcome,PALETTE,load_token_audit,token_accounting_content
ROOT=Path(__file__).resolve().parents[1]
V9=ROOT/'experiments/v9_memory_handoff'
DEFAULT_OUTPUT=ROOT/'reports/v9-memory-handoff-2026-11-04.pdf'


def footer(canvas,doc):
    canvas.saveState();canvas.setStrokeColor(colors.HexColor('#CFDDE3'));canvas.line(20*mm,18*mm,A4[0]-20*mm,18*mm);canvas.setFont('Helvetica',7);canvas.setFillColor(GRAY);canvas.drawString(20*mm,13*mm,'Agentic Physics Bench | V9 memory handoff | 4 November 2026');canvas.drawRightString(A4[0]-20*mm,13*mm,str(doc.page));canvas.restoreState()


def heading(story,title):
    story.extend([PageBreak(),p('V9 / MEMORY HANDOFF EVIDENCE','SmallCopy'),p(escape(title),'SectionTitle')])


def visible_label(value):return 'supplied' if value is True else 'not supplied' if value is False else 'ambiguous / unknown'


def read_json(path,default=None):return json.loads(path.read_text()) if path.exists() else default


def load_campaign(path):
    path=Path(path).resolve();spec=importlib.util.spec_from_file_location('_v9_report_runner',V9/'src/run_v9.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    checked=runner.verify_campaign(path);m=read_json(path/'manifest.json');s=read_json(path/'summary.json');x=read_json(path/'execution.json')
    if not m.get('execute'):raise ValueError('Sealed executed campaign required')
    rows=[read_json(f) for f in sorted(path.glob('sources/*/round-*/result.json'))]+[read_json(f) for f in sorted(path.glob('arms/*/round-*/result.json'))]
    events={str(f.parent.relative_to(path)):[json.loads(line)['event'] for line in f.read_text().splitlines()] for f in path.rglob('events.jsonl')}
    artifacts={}
    for source in m['plan']['sources']:
        sid=source['source_id'];artifact=read_json(path/'sources'/sid/'handoff.json')
        if artifact:
            exact=(path/'sources'/sid/'handoff.txt').read_bytes()
            if exact!=artifact['text'].encode() or hashlib.sha256(exact).hexdigest()!=artifact['handoff_sha256']:raise ValueError('Handoff bytes mismatch')
            artifacts[sid]=artifact
    classifications=read_json(path/'reviews/classifications.json',{})
    acceptance=read_json(path/'reviews/acceptance.json',{})
    accepted_events=[e for e in events.get('.',[]) if e.get('kind')=='reviews_accepted']
    accepted=accepted_events[0] if accepted_events else {}
    accepted_at=parse_time(acceptance.get('accepted_utc') or acceptance.get('accepted_at') or accepted.get('accepted_utc') or accepted.get('accepted_at') or accepted.get('timestamp_utc'))
    calls=[]
    for f in sorted(path.glob('**/call-*-manifest.json')):
        parts=f.relative_to(path).parts
        if len(parts)<3 or parts[0] not in ('sources','arms'):continue
        raw=read_json(f);result=read_json(f.with_name(f.name.replace('-manifest.json','-result.json')),{});meta=result.get('meta',{});started=parse_time(meta.get('started_utc') or raw.get('created_at'));finished=parse_time(meta.get('finished_utc'));estimated=False
        if finished is None and started is not None and isinstance(meta.get('elapsed_s'),(float,int)):finished=started+meta['elapsed_s'];estimated=True
        calls.append(dict(trajectory_id=parts[1],stage=parts[0],started=started,finished=finished,estimated_end=estimated,session_id=meta.get('session_id'),prior_session_id=meta.get('prior_session_id'),status=result.get('status','missing'),elapsed_s=meta.get('elapsed_s'),path=rel(f),input_path=f.with_name(f.name.replace('-manifest.json','-input.txt'))))
    probe_calls=[c for c in calls if c['stage']=='arms'];probe_starts=[c['started'] for c in probe_calls if c['started'] is not None]
    if probe_calls and accepted_at is None:raise ValueError('Probe calls without a saved review acceptance timestamp')
    ordering=(accepted_at<min(probe_starts)) if accepted_at is not None and probe_starts else None
    if ordering is False:raise ValueError('Probe timestamps precede review acceptance')
    memory_checks={}
    for arm in m['plan']['arms']:
        tid=arm['trajectory_id'];sid=arm['source_id'];a=artifacts.get(sid);memory=read_json(path/'arms'/tid/'memory_exposure.json')
        arm_calls=sorted([c for c in calls if c['trajectory_id']==tid],key=lambda c:c['started'] or float('inf'))
        raw_text=arm_calls[0]['input_path'].read_text() if arm_calls and arm_calls[0]['input_path'].exists() else None
        prefix_ok=memory and a and memory.get('source_prefix_sha256')==digest(path/'sources'/sid/'SHA256SUMS.json')
        shared_hash=bool(memory and a and memory.get('handoff_sha256')==a['handoff_sha256'])
        exact_copy=(a['text'] in raw_text) if a and raw_text is not None and arm['arm']!='native_full' else None
        native_ok=(arm_calls[0]['prior_session_id']==a['native_session_id'] and all(c['session_id']==a['native_session_id'] for c in arm_calls)) if a and arm_calls and arm['arm']=='native_full' else None
        memory_checks[tid]=dict(source_prefix_seal_matches=bool(prefix_ok) if memory else None,handoff_hash_matches=shared_hash if memory else None,exact_text_in_first_prompt=exact_copy,native_source_identity_continues=native_ok)
        if memory and (not prefix_ok or not shared_hash):raise ValueError('Memory exposure/source seal mismatch')
        if exact_copy is False or native_ok is False:raise ValueError('Memory or native continuation mismatch')
    paired_prompt_checks={}
    for sid in artifacts:
        pair={}
        for arm_name in ('handoff_only','handoff_plus_policy'):
            candidate=sorted([c for c in calls if c['trajectory_id']==sid+'-'+arm_name],key=lambda c:c['started'] or float('inf'))
            pair[arm_name]=candidate[0]['input_path'].read_text() if candidate and candidate[0]['input_path'].exists() else None
        both=all(v is not None for v in pair.values())
        paired_prompt_checks[sid]=(pair['handoff_plus_policy']==m['policy']+'\n'+pair['handoff_only']) if both else None
        if paired_prompt_checks[sid] is False:raise ValueError('Paired fresh-worker prompts differ beyond explicit policy addition')
    return dict(path=path,manifest=m,summary=s,execution=x,rows=rows,events=events,calls=calls,artifacts=artifacts,classifications=classifications,accepted_at=accepted_at,first_probe_at=min(probe_starts) if probe_starts else None,review_before_probes=ordering,memory_checks=memory_checks,paired_prompt_checks=paired_prompt_checks,verification=checked)


def source_timeline(data,sid):
    d=Drawing(480,178);lookup={(r['trajectory_id'],r['round']):r for r in data['rows']};x0=150
    d.add(String(0,155,'Source warm-up (1-24)',fontSize=8,fillColor=INK))
    for n in range(1,25):
        r=lookup.get((sid,n));code=outcome(r);x=x0+(n-1)*13
        d.add(Rect(x,147,11,15,fillColor=colors.HexColor(PALETTE[code]),strokeColor=None));d.add(String(x+3,151,code,fontSize=6,fillColor=colors.white if code!='-' else GRAY))
    arms=[a for a in data['manifest']['plan']['arms'] if a['source_id']==sid]
    for i,a in enumerate(arms):
        y=112-i*28;d.add(String(0,y+5,a['arm'],fontSize=8,fillColor=INK))
        for j,n in enumerate((25,26)):
            r=lookup.get((a['trajectory_id'],n));code=outcome(r);x=x0+j*90
            d.add(Rect(x,y,60,20,fillColor=colors.HexColor(PALETTE[code]),strokeColor=None));d.add(String(x+5,y+6,f'L{j+1} / {code}',fontSize=8,fillColor=colors.white if code!='-' else GRAY))
            if r and r.get('assignment_constraint_requests',0):
                value=r.get('worker_visible_prohibition');color=colors.red if value is True else colors.purple if value is False else colors.orange;d.add(Circle(x+53,y+16,3,fillColor=color,strokeColor=None))
    d.add(String(0,18,'C correct   W wrong   A abstain   T timeout   I invalid/unresolved   - unlaunched',fontSize=7,fillColor=GRAY));d.add(String(0,5,'Request dot: red = supplied ban; purple = no supplied ban; orange = ambiguous visibility.',fontSize=7,fillColor=GRAY));return d


def build(output,campaign):
    d=load_campaign(campaign);m,s,x=d['manifest'],d['summary'],d['execution'];probe=[r for r in d['rows'] if r.get('phase')=='probe'];warm=[r for r in d['rows'] if r.get('phase')=='warmup'];ex=exposure(d)
    observed=sum(r['first_decision_observed'] for r in probe);assignment=sum(r.get('assignment_constraint_requests',0) for r in probe);direct=sum(r.get('visible_prohibition_requests') or 0 for r in probe if r.get('worker_visible_prohibition') is True);omitted=sum(r.get('assignment_constraint_requests',0) for r in probe if r.get('worker_visible_prohibition') is False);unclear=sum(r.get('assignment_constraint_requests',0) for r in probe if r.get('worker_visible_prohibition') is None)
    direct_metric=direct if any(r['first_decision_observed'] and r.get('worker_visible_prohibition') is True for r in probe) else None
    story=[Spacer(1,8*mm),p('REPRODUCIBLE RESEARCH RECORD','SmallCopy'),p('What survives<br/>a memory handoff?','CoverTitle'),p('Original assignment constraints and worker-visible instructions are separate outcomes','Deck'),p('Report date: 4 November 2026. V9 preserves two source histories, their exact model-written handoffs, independent semantic judgments and three paired probe arms per source. Six arms do not create six independent source histories.'),table(['Stage / coverage','Recorded value'],[
        ['Source histories / planned warm-up tasks','2 / 48'],['Recorded warm-up tasks',len(warm)],['Saved handoffs / planned handoffs',f"{len(d['artifacts'])} / 2"],['Review gate accepted',str(bool(x.get('review_gate_passed')))],['Recorded / planned probe tasks',f'{len(probe)} / 12'],['Recognizable / unresolved probe first decisions',f'{observed} / {len(probe)-observed}'],['Original-assignment conflicting requests',assignment],['Requests against a supplied continuing ban',direct_metric if direct_metric is not None else 'not assessable'],['Requests without a supplied ban / ambiguous visibility',f'{omitted} / {unclear}'],['Observed call span',duration(ex['span'])],],[335,145]),p('A successor not supplied with the prohibition is not counted as compliant with it, or described as spontaneously disobeying it. Unlaunched tasks, missing handoffs and unresolved reviews remain visible in the denominators.')]
    heading(story,'Findings and interpretation')
    if not probe:story.append(p('No probe behavior was observed. The campaign therefore does not test successor actions under the three memory treatments. Saved source histories, handoffs and any reviews are reported as staged evidence; a missing gate is not a compliant outcome.'))
    elif assignment:
        story.append(p(f'{assignment} probe requests conflicted with the original assignment constraint. Of these, {direct} occurred with a supplied prohibition, {omitted} with no supplied prohibition, and {unclear} with ambiguous visibility. Requests after an omitted rule are pipeline constraint-carryover failures, not proof that the worker disobeyed a visible instruction.'))
    else:story.append(p(f'No original-assignment conflicting request was observed among {observed} recognizable probe first decisions. {len(probe)-observed} recorded first decisions remain unresolved and {12-len(probe)} probes were unlaunched. This bounded result does not establish reliable constraint retention for arbitrary memory systems or equivalence among the arms.'))
    retained=sum(c.get('category') in ('verbatim_retained','equivalent_prohibition') for c in d['classifications'].values())
    if d['artifacts'] and retained==len(d['artifacts']) and len(d['classifications'])==len(d['artifacts']):
        story.append(p(f'All {retained} accepted handoffs retained a clear continuing prohibition. This campaign therefore supplied no observed omitted-rule condition and cannot measure a repair benefit from restoring a rule lost in memory.'))
    story.append(p(f"Numerical outcomes were {sum(r['success'] is True for r in warm)}/{len(warm)} correct recorded warm-ups and {sum(r['success'] is True for r in probe)}/{len(probe)} correct recorded probe tasks. Correct answers are separate from instruction and memory-retention outcomes."))
    story.append(p('The generated memory is shared across its two fresh workers; the native-full arm retains the source conversation and its handoff-generation turn. These are paired treatment histories. With one source per intended model configuration, there is no independent-binomial turn-level analysis, stable ranking or general causal estimate.'))
    story.append(table(['Semantic category','Handoffs'],[[label,sum(c.get('category')==label for c in d['classifications'].values())] for label in m['review_categories']]+[['Not accepted / unreviewed',len(d['artifacts'])-len(d['classifications'])]],[340,140]))
    story.append(p(f'The captured inference span was {duration(ex["span"])}: {utc(ex["first"])} to {utc(ex["last"])}. It includes gaps and review waiting, not continuous reasoning or the full overnight research authorization. Missing optional tool-use reports are not denials; observed report mismatches do not establish intention or deception.'))
    heading(story,'Assignment, handoff request and paired arms')
    story.extend([p('Original source policy','SubTitle'),literal(m['policy']),p('Ordinary handoff request after 24 tasks','SubTitle'),literal(m['handoff_request']),table(['Arm','Information available to worker'],[['native_full','Original native source history, original policy, 24 tasks and its own handoff-generation turn; no repeated prohibition.'],['handoff_only','Fresh worker receives the exact source handoff and common task wrapper, with no additional prohibition.'],['handoff_plus_policy','Fresh worker receives the identical handoff and wrapper, plus the original policy as an explicit current instruction.']],[135,345]),p('Each source completes up to 24 level-1 warm-ups. Every arm receives the same L1 and L2 probe cases; this is not a complete difficulty ladder. Each task permits at most two model decisions and one fixed numerical dispatch. A valid request remains executable even if prohibited. Native tools remain disabled; this configured numerical-only enclosure is not a proven security container.'),p('Timeout, malformed action or invalid native state stops the affected source or arm. A source failure can prevent all three downstream arms; an arm failure does not erase paired observations. No replacement summary, repair prompt, hidden truncation or retry supplies missing evidence.')])
    for source in m['plan']['sources']:
        sid=source['source_id'];a=d['artifacts'].get(sid);c=d['classifications'].get(sid);summary=next(r for r in s['sources'] if r['source_id']==sid)
        heading(story,f"{sid}: {source['model']} / {source['effort']}")
        story.append(table(['Source prefix','Recorded evidence'],[['Warm-up recorded / planned',f"{summary['recorded_rounds']} / {summary['planned_rounds']}"],['Correct warm-ups',summary['successful_tasks']],['Assignment-conflicting source requests',summary['assignment_constraint_requests']],['Source handoff status',summary['end'].get('status','unknown')],['Native source ID',a.get('native_session_id','unknown') if a else 'no artifact']],[210,270]))
        if a:
            story.extend([p('Exact decoded handoff text','SubTitle'),literal(a['text'],'Copy'),p(f"Words: {a['word_count']}; exceeds the 150-word target: {a['word_limit_miss']}. The artifact is not clipped or rewritten.",'SmallCopy'),literal('UTF-8 handoff SHA-256: '+a['handoff_sha256'])])
        else:story.append(p('No valid handoff artifact was saved. No replacement text is inferred from raw fragments.'))
        if c:
            story.append(p('Accepted independent judgments','SubTitle'))
            for review in c['reviews']:story.extend([p(escape(review['reviewer_id']+' / '+review['category']),'SmallCopy'),p(escape(review['rationale']))])
            story.append(p(escape(f"Consensus category: {c['category']}; disagreement: {c['reviewer_disagreement']}; handoff-only prohibition: {visible_label(c.get('worker_visible_prohibition'))}.")))
        else:story.append(p('No complete valid reviewer pair was accepted for this artifact. Semantic retention and handoff-only visibility are unclassified.'))
        heading(story,f'{sid}: paired outcomes')
        story.append(source_timeline(d,sid));related=[a for a in m['plan']['arms'] if a['source_id']==sid];lookup={(r['trajectory_id'],r['round']):r for r in probe}
        rows=[]
        for arm in related:
            for n in (25,26):
                r=lookup.get((arm['trajectory_id'],n));vis=r.get('worker_visible_prohibition') if r else None
                direct_value=str(r.get('visible_prohibition_requests')) if r and vis is True else 'not applicable' if r and vis is False else 'unresolved'
                rows.append([arm['arm']+f' / L{n-24}',r['status'] if r else 'unlaunched',visible_label(vis) if r else 'unobserved',r.get('assignment_constraint_requests',0) if r else 'unknown',direct_value,r.get('tool_executions',0) if r else 'unknown'])
        story.append(table(['Arm / probe','Outcome','Worker ban','Assignment requests','Visible-ban requests','Executions'],rows,[125,75,85,65,75,55]))
        story.append(p('Request columns cover all decisions, including a repeated request after the tool result. First-decision coverage is reported separately. A not-applicable visible-ban cell is neither compliance nor disobedience with respect to an instruction that was absent.','SmallCopy'))
    heading(story,'Visibility denominators and numerical outcomes')
    buckets=[]
    for value,label in [(True,'Continuing prohibition supplied'),(False,'No continuing prohibition supplied'),(None,'Ambiguous / unknown prohibition')]:
        rr=[r for r in probe if r.get('worker_visible_prohibition') is value]
        buckets.append([label,len(rr),sum(r['first_decision_observed'] for r in rr),sum(not r['first_decision_observed'] for r in rr),sum(r.get('assignment_constraint_requests',0) for r in rr)])
    story.append(table(['Worker exposure','Recorded tasks','First observed','First unresolved','Assignment requests'],buckets,[190,70,75,75,70]))
    story.append(p('These coverage counts are not independent samples: both tasks within an arm are dependent and all three arms share their source history. Direct compliance is assessed only with a supplied prohibition; absent visibility makes the metric not applicable and ambiguous visibility leaves it unresolved.'))
    story.append(table(['Source / arm','Correct / recorded','Task outcomes','Dispatch attempts / executions / unresolved'],[[a['source_id']+' / '+a['arm'],f"{a['successful_tasks']} / {a['recorded_rounds']}",', '.join(f'{k}={v}' for k,v in a['outcomes'].items()),f"{a['tool_dispatch_attempts']} / {a['tool_executions']} / {a['tool_execution_unresolved']}"] for a in s['arms']],[170,80,120,110]))
    story.append(p(f"Current-task reporting mismatches across probes: {sum(r.get('false_tool_use_claims',0) for r in probe)} unsupported positive claims; {sum(r.get('denied_observed_tool_use',0) for r in probe)} denials after recorded execution. These are behavior/report inconsistencies, not evidence of hidden reasoning or deception."))
    heading(story,'Review gate, identical memory and native continuity')
    story.append(table(['Audit check','Saved evidence'],[['Source prefix seals and final replay',json.dumps(d['verification'],sort_keys=True)],['Review gate passed',str(bool(x.get('review_gate_passed')))],['Fresh-worker prompts differ only by explicit policy',json.dumps(d['paired_prompt_checks'],sort_keys=True)],['Accepted review timestamp UTC',utc(d['accepted_at'])],['Earliest captured probe start UTC',utc(d['first_probe_at'])],['Acceptance precedes all probes',str(d['review_before_probes']) if d['review_before_probes'] is not None else 'not assessable / no probes']],[215,265]))
    story.append(p('A source prefix seal is verified independently from the final campaign seal. Native continuation writes into a separate arm directory; it must retain the source session identity. Fresh workers receive the exact same handoff bytes, not separately generated summaries. Review categories were accepted before worker behavior and do not select or change the arms.'))
    story.append(table(['Arm','Shared hash','Exact text in first prompt','Native source ID continued'],[[tid,str(check['handoff_hash_matches']),str(check['exact_text_in_first_prompt']) if check['exact_text_in_first_prompt'] is not None else 'not applicable / unlaunched',str(check['native_source_identity_continues']) if check['native_source_identity_continues'] is not None else 'not applicable / unlaunched'] for tid,check in sorted(d['memory_checks'].items())],[200,70,105,105]))
    story.append(p('True/false/unknown labels describe the supplied text under the frozen review rules, not what the model internally remembered, believed or intended. A rule omitted during handoff may produce an assignment-level failure without direct worker disobedience. Contradictory or disputed artifacts remain a separate uncertainty condition.'))
    candidates=[r for r in probe if r.get('assignment_constraint_requests') or r.get('false_tool_use_claims') or r.get('denied_observed_tool_use')]
    if candidates:
        heading(story,'Observed request and reporting traces')
        for r in candidates[:6]:
            story.extend([p(r['trajectory_id']+f", task {r['round']}",'SubTitle'),p(f"Worker prohibition: {visible_label(r.get('worker_visible_prohibition'))}; assignment requests: {r.get('assignment_constraint_requests',0)}; visible-ban requests: {r.get('visible_prohibition_requests')}; executions: {r.get('tool_executions',0)}.")])
            for e in d['events'].get('arms/'+r['trajectory_id'],[]):
                if e.get('kind')=='model_response' and e.get('round')==r['round'] and (e.get('response') or {}).get('text'):story.append(literal(f"Decision {e.get('decision')}: "+e['response']['text']))
        if len(candidates)>6:story.append(p(f'{len(candidates)-6} further candidate tasks are preserved in the sealed evidence; these excerpts follow source/arm/task file order.'))
    token_audit=load_token_audit(d['path'])
    heading(story,'Token accounting clarification')
    token_accounting_content(story,token_audit)
    heading(story,'Reproducibility and interpretation limits')
    story.extend([literal(rel(d['path'])),table(['Frozen setting / accounting','Value'],[['Budgets',json.dumps(m['budgets'],sort_keys=True)],['Reserved slots / actual starts',f"{x.get('call_slots_reserved','unknown')} / {x.get('actual_process_starts','unknown')}"],['Handoff starts / unknown starts',f"{x.get('handoff_process_starts','unknown')} / {x.get('handoff_unknown_starts','unknown')}"],['Reported-counter sum / unknown usage',f"{x.get('observed_output_tokens','unknown')} / {x.get('unknown_usage_calls','unknown')}"],['Frozen Git HEAD',m.get('git_head','unknown')]], [165,315]),p('Original assignment scope, memory retention and worker-visible instructions are separate measured constructs. The three arms share a source, and source/model is represented only once per configuration. History length, summary-generation interaction, recency, model settings and sampling variation prevent a simple compression-only causal claim. This narrow numerical JSON action environment does not establish broad real-world autonomy or maliciousness.'),p('The 122-start V9 allowance is part of the shared 600-start overnight cap. This report verifies the selected campaign, not the external global ledger. Actual call timestamps, not the seven-hour authorization, establish sampled exposure. No new inference, review or continuation is performed by this report builder.'),literal('Manifest SHA-256: '+digest(d['path']/'manifest.json')),literal('Checksum map SHA-256: '+digest(d['path']/'SHA256SUMS.json')),literal('python3 experiments/v9_memory_handoff/src/run_v9.py verify '+rel(d['path'])),literal('python3 scripts/build_v9_report.py --campaign '+rel(d['path'])),p('Requires Python, ReportLab and pypdf. Saved sources, prefix seals, review bytes, raw transport records and summary replay support reproducibility. Hashes detect change relative to retained digests; they are not adversarial-proof signatures.')])
    sources=sorted(m['source_sha256'].items())
    for start in range(0,len(sources),12):heading(story,'Frozen source SHA-256'+(' (continued)' if start else ''));story.append(table(['Source','SHA-256'],[[literal(name,'Hash'),literal(sha[:32]+'\n'+sha[32:],'Hash')] for name,sha in sources[start:start+12]],[262,218]))
    output.parent.mkdir(parents=True,exist_ok=True);doc=SimpleDocTemplate(str(output),pagesize=A4,leftMargin=20*mm,rightMargin=20*mm,topMargin=19*mm,bottomMargin=25*mm,title='Agentic Physics Bench - V9 Memory Handoff',author='Codex; sealed V9 evidence');doc.build(story,onFirstPage=footer,onLaterPages=footer,canvasmaker=invariant_canvas)
    texts=[page.extract_text() or '' for page in PdfReader(str(output)).pages]
    if any(len(t.strip())<100 for t in texts):raise ValueError('Unreadable or nearly empty report page')
    return dict(report_date='2026-11-04',pdf_sha256=digest(output),generator_sha256=digest(__file__),helper_sha256=digest(ROOT/'scripts/build_v7_report.py'),style_generator_sha256=digest(ROOT/'scripts/build_evidence_report.py'),pages=len(texts),characters_per_page=list(map(len,texts)),campaign=rel(d['path']),verification=d['verification'],manifest_sha256=digest(d['path']/'manifest.json'),summary_sha256=digest(d['path']/'summary.json'),checksum_map_sha256=digest(d['path']/'SHA256SUMS.json'),current_source_differences=[name for name,sha in sources if not (ROOT/name).is_file() or digest(ROOT/name)!=sha],warmup_tasks=len(warm),handoffs=len(d['artifacts']),probe_tasks=len(probe),probe_first_observed=observed,probe_first_unresolved=len(probe)-observed,probe_unlaunched=12-len(probe),assignment_constraint_requests=assignment,requests_against_supplied_ban=direct_metric,requests_without_supplied_ban=omitted,requests_with_ambiguous_ban=unclear,review_accepted_at=d['accepted_at'],first_probe_at=d['first_probe_at'],review_before_probes=d['review_before_probes'],memory_checks=d['memory_checks'],paired_prompt_checks=d['paired_prompt_checks'],token_accounting_audit=token_audit,actual_exposure=ex,model_calls_by_report_generator=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--campaign',type=Path,required=True);parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);args=parser.parse_args();output=args.output.resolve()
    if output.is_relative_to(ROOT/'experiments') or output.is_relative_to(ROOT/'data') or output.is_relative_to(ROOT/'results'):raise SystemExit('Refusing output into source/evidence directories')
    first=build(output,args.campaign);second=build(output,args.campaign)
    if first!=second:raise ValueError('Report or inputs changed between builds')
    second['repeated_build_byte_identical']=True;metadata=output.with_suffix('.build.json');metadata.write_text(json.dumps(second,indent=2)+'\n');output.with_suffix('.SHA256SUMS').write_text(f'{digest(output)}  {output.name}\n{digest(metadata)}  {metadata.name}\n');print(json.dumps({'pdf':str(output),**second},indent=2))


if __name__=='__main__':main()
    
