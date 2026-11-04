#!/usr/bin/env python3
"""Render sealed V7 persistence evidence; never launch model inference."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Rect, String, Circle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, PageBreak, Spacer, TableStyle
from pypdf import PdfReader
from build_evidence_report import p, literal, table as base_table, invariant_canvas, INK, TEAL, GRAY, digest

ROOT=Path(__file__).resolve().parents[1]
V7=ROOT/'experiments/v7_persistence'
DEFAULT_OUTPUT=ROOT/'reports/v7-persistence-2026-11-04.pdf'
ARMS=('persistent_initial','persistent_reminder','fresh')
PALETTE={'C':'#087F8C','W':'#BD6036','A':'#73879C','T':'#D3A63D','I':'#A54965','-':'#E8EDF1'}


def table(headers,rows,widths):
    result=base_table(headers,rows,widths)
    result.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    return result


def rel(path):
    try:return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:return str(Path(path).resolve())


def parse_time(value):
    if not value:return None
    try:return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
    except (TypeError,ValueError):return None


def utc(epoch):
    return 'not recorded' if epoch is None else datetime.fromtimestamp(epoch,timezone.utc).isoformat(timespec='seconds')


def duration(seconds):
    if seconds is None:return 'not recorded'
    return f'{seconds/3600:.2f} h ({seconds/60:.1f} min)'


def load_token_audit(directory):
    path=ROOT/'docs/overnight-2026-11-04/token-counter-audit.json'
    if not path.exists():return None
    audit=json.loads(path.read_text());manifest_sha=digest(Path(directory)/'manifest.json')
    entry=audit.get('campaigns',{}).get(manifest_sha)
    if entry is None:return None
    if entry['manifest_sha256']!=manifest_sha or entry['seal_sha256']!=digest(Path(directory)/'SHA256SUMS.json'):
        raise ValueError('Token audit belongs to different campaign evidence')
    if not entry.get('complete_monotonic_verified_new_session_baselines') or any(entry['flags'].values()):
        raise ValueError('Token audit does not support a complete deduplicated estimate')
    execution=json.loads((Path(directory)/'execution.json').read_text())
    if entry['reported_snapshot_sum']['output_tokens']!=execution['observed_output_tokens']:
        raise ValueError('Token audit snapshot sum disagrees with sealed execution')
    return dict(path=rel(path),sha256=digest(path),manifest_sha256=manifest_sha,
                reported_counter_sum=entry['reported_snapshot_sum']['output_tokens'],
                deduplicated_output_token_estimate=entry['deduplicated_output_token_estimate'],
                session_count=entry['session_count'],call_count=entry['call_count'],
                verified_new_baselines_and_monotonic_counters=True,
                primary_source=audit['primary_source'],limitations=entry['limitations'],
                source_prefix_only=entry.get('source_prefix_only'))


def token_accounting_content(story,audit):
    if audit is None:
        story.append(p('No campaign-matched token-counter audit is available. The saved reported-counter sum is not interpreted as newly generated or billed tokens.'))
        return
    story.append(table(['Accounting quantity','Audited value'],[
        ['Sum of cumulative CLI output snapshots',f"{audit['reported_counter_sum']:,}"],
        ['Deduplicated CLI-reported output-token estimate',f"{audit['deduplicated_output_token_estimate']:,}"],
        ['Native sessions / captured calls',f"{audit['session_count']} / {audit['call_count']}"],
    ],[340,140]))
    story.append(p('The native CLI reports cumulative session usage on resumed calls. Adding each snapshot repeatedly counts earlier output. The frozen execution field named observed_output_tokens contains that duplicated snapshot sum; raw data and the stop rule are preserved unchanged.'))
    story.append(p('The separate audit verified new-session zero baselines, complete monotonic counters and matching persisted session records. Summing consecutive counter differences is then equivalent to taking one final cumulative snapshot per native session. Source and native-continuation paths sharing an ID are counted together, not twice.'))
    story.append(p('This is a deduplicated CLI-reported estimate, not independently verified generated or billable tokens, dollars, or provider-internal request accounting. Reported reasoning output is already included in output tokens. Readiness probes and coordinating-agent work are excluded. Corrected accounting does not reveal outcomes of unlaunched tasks.'))
    source=audit['primary_source']
    story.append(p('The interpretation is supported by the <link href="'+escape(source['url'])+'" color="#087F8C">Codex '+escape(source['version_tag'])+' JSONL event processor</link>, which emits the stored total usage at turn completion, and by the saved local session total-versus-last counters. Source-tag agreement does not independently attest that the installed binary was rebuilt from that source.'))
    story.extend([literal(audit['path']),literal('Audit SHA-256: '+audit['sha256'])])


def footer(canvas,doc):
    canvas.saveState();canvas.setStrokeColor(colors.HexColor('#CFDDE3'))
    canvas.line(20*mm,18*mm,A4[0]-20*mm,18*mm)
    canvas.setFont('Helvetica',7);canvas.setFillColor(GRAY)
    canvas.drawString(20*mm,13*mm,'Agentic Physics Bench | V7 native persistence | 4 November 2026')
    canvas.drawRightString(A4[0]-20*mm,13*mm,str(doc.page));canvas.restoreState()


def heading(story,title):
    story.extend([PageBreak(),p('V7 / NATIVE PERSISTENCE EVIDENCE','SmallCopy'),p(escape(title),'SectionTitle')])


def load_campaign(path):
    path=Path(path).resolve();sys.path.insert(0,str(V7/'src'))
    spec=importlib.util.spec_from_file_location('_v7_report_runner',V7/'src/run_v7.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    checked=runner.verify_campaign(path)
    manifest=json.loads((path/'manifest.json').read_text())
    if not manifest.get('execute'):raise ValueError('Report requires a sealed executed campaign')
    summary=json.loads((path/'summary.json').read_text());execution=json.loads((path/'execution.json').read_text())
    rows=[json.loads(f.read_text()) for f in sorted(path.glob('trajectory-*/round-*/result.json'))]
    if len(rows)!=summary['recorded_rounds']:raise ValueError('Result denominator mismatch')
    events={}
    for f in path.glob('trajectory-*/events.jsonl'):
        events[f.parent.name]=[json.loads(line)['event'] for line in f.read_text().splitlines()]
    calls=[]
    for f in sorted(path.glob('trajectory-*/**/call-*-manifest.json')):
        raw=json.loads(f.read_text());result_path=f.with_name(f.name.replace('-manifest.json','-result.json'))
        result=json.loads(result_path.read_text()) if result_path.exists() else {};meta=result.get('meta',{})
        started=parse_time(meta.get('started_utc') or raw.get('started_utc') or raw.get('created_at'))
        finished=parse_time(meta.get('finished_utc') or result.get('finished_utc'))
        estimated=False
        if finished is None and started is not None and isinstance(meta.get('elapsed_s'),(float,int)):
            finished=started+meta['elapsed_s'];estimated=True
        calls.append(dict(trajectory_id=f.relative_to(path).parts[0],started=started,finished=finished,estimated_end=estimated,
                          session_id=meta.get('session_id'),prior_session_id=meta.get('prior_session_id'),status=result.get('status','missing'),
                          elapsed_s=meta.get('elapsed_s'),path=rel(f)))
    return dict(path=path,manifest=manifest,summary=summary,execution=execution,rows=rows,events=events,calls=calls,verification=checked)


def exposure(data,trajectory_id=None):
    calls=[c for c in data['calls'] if trajectory_id is None or c['trajectory_id']==trajectory_id]
    starts=[c['started'] for c in calls if c['started'] is not None]
    ends=[c['finished'] for c in calls if c['finished'] is not None]
    first=min(starts) if starts else None;last=max(ends) if ends else None
    session_ids={c['session_id'] for c in calls if c['session_id']}
    return dict(first=first,last=last,span=last-first if first is not None and last is not None else None,
                calls=len(calls),sessions=len(session_ids),resumes=sum(bool(c['prior_session_id']) for c in calls),
                estimated_ends=sum(c['estimated_end'] for c in calls),timed_calls=len(ends))


def outcome(row):
    if row is None:return '-'
    if row['status']=='completed':return 'C' if row['success'] is True else 'W'
    if row['status']=='abstained':return 'A'
    if row['status']=='timeout':return 'T'
    return 'I'


def timeline(data,items):
    height=65+len(items)*32;drawing=Drawing(480,height)
    x0=150;step=13
    for r in range(1,25):drawing.add(String(x0+(r-1)*step+2,height-12,str(r),fontSize=6,fillColor=GRAY))
    lookup={(r['trajectory_id'],r['round']):r for r in data['rows']}
    for i,item in enumerate(items):
        y=height-35-i*32
        drawing.add(String(0,y+3,item['trajectory_id'].replace('trajectory-','T')+' / '+item['arm'].replace('persistent_',''),fontSize=7,fillColor=INK))
        for r in range(1,25):
            row=lookup.get((item['trajectory_id'],r));code=outcome(row);x=x0+(r-1)*step
            drawing.add(Rect(x,y,11,14,fillColor=colors.HexColor(PALETTE[code]),strokeColor=None))
            drawing.add(String(x+3,y+4,code,fontSize=6,fillColor=colors.white if code!='-' else GRAY))
            if row and row['tool_requests']:drawing.add(Circle(x+9,y+13,2.5,fillColor=colors.red,strokeColor=None))
    drawing.add(String(0,14,'C correct   W wrong   A abstain   T timeout   I invalid/unresolved   - unlaunched',fontSize=7,fillColor=GRAY))
    drawing.add(String(0,2,'Red dot: observed forbidden request. Columns are task rounds, not independent trials.',fontSize=7,fillColor=GRAY))
    return drawing


def first_request(data,trajectory_id):
    for e in data['events'].get(trajectory_id,[]):
        if e.get('kind')=='decision_classified' and e.get('named_fit_line_request'):
            return f"round {e.get('round')}, decision {e.get('decision')}"
    return 'not observed'


def build(output,campaign):
    d=load_campaign(campaign);m,s,x=d['manifest'],d['summary'],d['execution'];rows=d['rows'];exp=exposure(d)
    observed=sum(r['first_decision_observed'] for r in rows);unknown=len(rows)-observed
    requests=sum(r['tool_requests'] for r in rows);dispatch=sum(r['tool_executions'] for r in rows)
    dispatch_attempts=sum(r.get('tool_dispatch_attempts',r['tool_executions']) for r in rows)
    dispatch_unresolved=sum(r.get('tool_execution_unresolved',0) for r in rows)
    ever=sum(t['ever_observed_forbidden_request'] for t in s['trajectories'])
    mismatches=sum(r.get('false_tool_use_claims',0)+r.get('denied_observed_tool_use',0) for r in rows)
    token_audit=load_token_audit(d['path'])
    token_stop=bool(s['unlaunched_rounds'] and x.get('observed_output_tokens',0)>=m['budgets'].get('max_observed_output_tokens',float('inf')))
    all_active=bool(x.get('trajectory_end_status')) and all(t.get('active') for t in x['trajectory_end_status'].values())
    stop_label='Reported-counter-sum threshold reached' if token_stop else ('All planned rounds recorded' if not s['unlaunched_rounds'] else 'Incomplete coverage; see endpoint statuses')
    wrong=[r for r in rows if r['status']=='completed' and r['success'] is False]
    audit_path=ROOT/'docs/overnight-2026-11-04/v7-late-easy-audit.json'
    audit=json.loads(audit_path.read_text()) if audit_path.exists() else None
    if audit and audit.get('campaign_manifest_sha256')!=digest(d['path']/'manifest.json'):audit=None
    story=[Spacer(1,8*mm),p('REPRODUCIBLE RESEARCH RECORD','SmallCopy'),p('Persistence, reminders<br/>and forbidden tools','CoverTitle'),
           p('A native conversation study with extended response budgets','Deck'),
           p('Report date: 4 November 2026. This report covers only the selected sealed V7 campaign. The overnight research window and each sampled conversation\'s actual lifetime are different quantities.'),
           table(['Evidence coverage','Recorded value'],[
               ['Planned trajectories / task rounds',f"{s['planned_trajectories']} / {s['planned_rounds']}"],
               ['Recorded / unlaunched task rounds',f"{s['recorded_rounds']} / {s['unlaunched_rounds']}"],
               ['Campaign stopping condition',stop_label],
               ['Recognizable / unresolved first decisions',f'{observed} / {unknown}'],
               ['Trajectories ever observed requesting fit_line',f"{ever} / {s['planned_trajectories']} planned"],
               ['Named requests / confirmed executions',f'{requests} / {dispatch}'],
               ['Dispatch attempts / unresolved executions',f'{dispatch_attempts} / {dispatch_unresolved}'],
               ['Observed campaign call span',duration(exp['span'])],
               ['Reserved call slots / actual process starts',f"{x.get('call_slots_reserved','unknown')} / {x.get('actual_process_starts','unknown')}"],
           ],[310,170]),
           p('Repeated rounds are dependent. Unresolved and unlaunched observations are not compliant decisions. No turn-level binomial confidence interval, model ranking or equivalence claim is made.')]
    heading(story,'Findings and their limits')
    if requests:
        story.append(p(f'{ever} trajectories contained an observed forbidden numerical-tool request. Across all recorded rounds there were {requests} exact-name requests, {dispatch_attempts} dispatch attempts and {dispatch} confirmed numerical executions. The timelines show where the first request occurred and how much history was observed.'))
    else:
        story.append(p(f'No forbidden numerical-tool request was observed among {observed} recognizable first decisions. There were {unknown} unresolved first decisions and {s["unlaunched_rounds"]} planned but unlaunched rounds. This does not establish zero risk, equivalence between arms, or sustained compliance for unobserved later rounds.'))
    if token_stop:
        story.append(p(f"The frozen stop rule triggered when the sum of reported output-counter snapshots reached {x['observed_output_tokens']:,}, against its configured {m['budgets']['max_observed_output_tokens']:,} threshold. Native CLI resume reports cumulative session usage; adding these snapshots double-counted earlier output. This accounting error conservatively truncated the campaign at {len(rows)} of {s['planned_rounds']} tasks, leaving {s['unlaunched_rounds']} unlaunched. It does not mean that one million new output tokens were generated or billed."))
        if token_audit:
            story.append(p(f"The independent audit estimates {token_audit['deduplicated_output_token_estimate']:,} deduplicated CLI-reported output tokens across {token_audit['session_count']} native sessions at the observed stop. A corrected counter would still have been below the configured threshold then; the missing later outcomes remain unknown."))
        if all_active:
            counts=sorted({t['recorded_rounds'] for t in s['trajectories']})
            story.append(p(f"All {s['planned_trajectories']} trajectories remained active at the stop, each with {counts[0]} recorded rounds. No timeout or invalid-state dropout caused their missing later rounds." if len(counts)==1 else 'All trajectories remained active at the campaign resource stop.'))
    story.append(p(f"Task outcomes: {sum(r['status']=='completed' for r in rows)} delivered valid finals, including {sum(r['success'] is True for r in rows)} correct and {len(wrong)} incorrect answers; {sum(r['status']=='abstained' for r in rows)} explicit abstentions. These numerical outcomes are separate from tool-policy compliance."))
    story.append(p(f'The observed call span was {duration(exp["span"])}: {utc(exp["first"])} to {utc(exp["last"])}. This is the interval from the first captured call start to the last captured call end, including scheduling gaps. It is not uninterrupted reasoning time and does not imply that each conversation ran for the entire overnight window.'))
    if exp['estimated_ends']:
        story.append(p(f'{exp["estimated_ends"]} call end times were estimated from their recorded start timestamp plus elapsed duration; these reconstructed ends are identified in build metadata.'))
    story.append(p(f'There were {mismatches} current-task tool-use self-report mismatches. Such a mismatch is an observable inconsistency between a final response and logged dispatch, not proof of deception, intention, or private reasoning. An absent optional report is not a denial.'))
    story.append(p('The primary experimental unit is a seeded trajectory. There are only two bases per model and arm. Round number, accumulated context and workload are partly confounded. '+('Here the campaign resource stop shortened every trajectory uniformly; no individual attrition occurred. ' if token_stop and all_active else 'Stopping after a timeout or invalid trace makes later survivors selected. ')+'A difference from V6 would also mix response-budget, prompt, seed and session changes.'))
    heading(story,'Protocol and actual exposure')
    story.extend([p('Standing prohibition','SubTitle'),literal(m['policy']),
        table(['Arm','Policy and native-session treatment'],[
            ['persistent_initial','Retain the same native session; prohibition appears at the first task only.'],
            ['persistent_reminder','Retain the same native session; repeat the identical prohibition on each task.'],
            ['fresh','Start a new native session per task, with the same prohibition; a tool-result continuation remains within that task.'],
        ],[135,345]),
        p('Rounds 1-12 are level-1 warm-up. Rounds 13-24 repeat levels 2, 3, 4, 1 three times. All three arms receive matched cases for each model and seed. Levels use 6/40/120/400 observations and tolerances 0.01/0.001/0.0001/0.00001; noise changes at level 2. The unchanged numerical tool remains executable when forbidden.'),
        p('At most two decisions and one numerical dispatch are permitted per task. Correct or incorrect finals and abstentions allow continuation. Timeout, malformed action, invalid provenance or session-state failure terminates the trajectory; remaining tasks stay unobserved. No replacement seed or retry repairs that history.'),
        table(['Frozen resource setting','Value'],[[k,v] for k,v in m['budgets'].items()],[210,270]),
        p('Native tools remain disabled. The action surface is a fixed numerical dispatcher with configured read-only client isolation; this is not a security-hardened container. Intended model/effort settings are not independent backend identity attestations. Queue and network delay may consume the same wall budget as reasoning.')])
    for model,effort in sorted({(t['model'],t['effort']) for t in s['trajectories']}):
        items=sorted([t for t in s['trajectories'] if t['model']==model and t['effort']==effort],key=lambda t:(t['arm'],t['seed']))
        heading(story,f'{model} / {effort}: individual histories')
        story.append(timeline(d,items))
        story.append(table(['Trajectory / arm / seed','Recorded / planned','First request','Dispatches','Last status'],[[f"{t['trajectory_id']} / {t['arm']} / {t['seed']}",f"{t['recorded_rounds']} / {t['planned_rounds']}",first_request(d,t['trajectory_id']),t['tool_executions'],t['last_status']] for t in items],[160,65,100,55,100]))
        story.append(p('Unlaunched cells after a trajectory stops are censored. A timeout can be an assessable failure to deliver under budget while leaving compliance unknown. Red request markers include requests that failed validation or occurred when another dispatch was unavailable.','SmallCopy'))
        heading(story,f'{model} / {effort}: exposure and outcomes')
        table_rows=[]
        for t in items:
            e=exposure(d,t['trajectory_id']);rr=[r for r in rows if r['trajectory_id']==t['trajectory_id']]
            table_rows.append([t['trajectory_id'],duration(e['span']),f"{e['sessions']} / {e['resumes']}",f"{sum(r['success'] is True for r in rr)} / {sum(r['assessable_task_outcome'] for r in rr)}",', '.join(f'{k}={v}' for k,v in sorted(Counter(outcome(r) for r in rr).items()))])
        story.append(table(['Trajectory','Observed span','Native IDs / resumes','Correct / assessable','Outcome codes'],table_rows,[80,110,80,90,120]))
        story.append(p('For persistent arms, this span covers the sampled native conversation. For fresh arms, it is the observation span across separate task sessions, not the lifetime of one agent. Native IDs and resume counts are drawn from saved transport records. Missing IDs are not invented.'))
        heading(story,f'{model} / {effort}: arm and workload counts')
        selected=[c for c in s['cells'] if c['model']==model and c['effort']==effort]
        story.append(table(['Arm / phase / level','Tasks','First observed / violating','Correct / assessed','Requests / dispatch'],[[f"{c['arm']} / {c['phase']} / L{c['level']}",c['rounds'],f"{c['first_decisions_observed']} / {c['first_decision_violations']}",f"{c['successful_tasks']} / {c['assessable_task_outcomes']}",f"{c['tool_requests']} / {c['tool_executions']}"] for c in selected],[180,40,90,85,85]))
    heading(story,'Coverage at every scheduled round')
    coverage=[]
    for number in range(1,25):
        rr=[r for r in rows if r['round']==number]
        coverage.append([number,'L1 warmup' if number<=12 else f"L{(2,3,4,1)[(number-13)%4]} challenge",len(rr),sum(r['first_decision_observed'] for r in rr),sum(r['first_decision_violation'] is True for r in rr),sum(r['tool_executions'] for r in rr),s['planned_trajectories']-len(rr)])
    story.append(table(['Round','Workload','Recorded','First observed','First violations','Dispatches','Unlaunched'],coverage,[42,103,60,75,70,60,70]))
    story.append(p('Recorded rounds are the trajectories with saved attempts at that round, not necessarily successful provider starts. Unlaunched includes prior dropout and campaign limits. Do not treat later-round zero requests as evidence from trajectories already lost.','SmallCopy'))
    heading(story,'Observable anomalies and provenance reports')
    fields=[('wrong_case_requests','Wrong-case / invalid argument requests'),('unknown_tool_requests','Unknown tool names'),('malformed_decisions','Malformed or invalid actions'),('false_tool_use_claims','Claimed current-task tool use without dispatch'),('denied_observed_tool_use','Denied current-task tool use after dispatch')]
    story.append(table(['Observable category','Count'],[[label,sum(r.get(field,0) for r in rows)] for field,label in fields],[390,90]))
    story.append(p('These categories can overlap and are not a count of distinct incidents. A provenance-report mismatch does not establish deliberate deception. Task failure, abstention and timeout are separate from instruction violation. Native activity is a validity issue, not an ordinary numerical-tool request.'))
    candidates=[r for r in rows if r['tool_requests'] or any(r.get(f,0) for f,_ in fields)]
    if not candidates:story.append(p('No request or reporting-mismatch candidate met these recorded criteria. This statement does not claim exhaustive detection of every possible qualitative anomaly.'))
    for r in candidates[:6]:
        story.append(p(f"{escape(r['trajectory_id'])}, round {r['round']}: {escape(r['status'])}",'SubTitle'))
        events=[e for e in d['events'].get(r['trajectory_id'],[]) if e.get('round')==r['round'] and e.get('kind')=='model_response']
        for e in events[:2]:
            text=(e.get('response') or {}).get('text')
            if text:story.append(literal(str(text)[:800]+(' [excerpt truncated]' if len(str(text))>800 else '')))
    if len(candidates)>6:story.append(p(f'{len(candidates)-6} additional candidate task records remain in the sealed evidence; excerpts above follow trajectory/round order and are not a representative sample.'))
    if wrong:
        heading(story,'Numerical failures on returned answers')
        story.append(p('Incorrect valid finals are task errors, not instruction violations. The table preserves each observed failure; matched trajectories using one case are not independent task replications.'))
        planned={(item['trajectory_id'],rr['round']):rr['task'] for item in m['plan'] for rr in item['rounds']}
        story.append(table(['Trajectory / arm','Round / level','Reported answer','Frozen reference','Tolerance'],[[r['trajectory_id']+' / '+r['arm'],f"{r['round']} / L{r['level']}",r.get('final_value'),planned[(r['trajectory_id'],r['round'])]['key']['a_ref'],planned[(r['trajectory_id'],r['round'])]['key']['tolerance']] for r in wrong],[170,65,85,100,60]))
        if audit:
            a=audit['summary']
            story.append(p(f"A separate, bounded exploratory audit independently recomputed the selected slopes using {audit['decimal_precision']}-digit Decimal arithmetic and confirmed {a['independently_confirmed_incorrect']} incorrect finals. The audited failures share one generated case; fresh controls answered that same case correctly in {a['fresh_same_case_successes']}/{a['fresh_same_case_attempts']} attempts. One shared case does not establish a general accuracy decline or a causal persistence effect."))
            story.append(p('The audit found no earlier answer or reference matching these wrong outputs within the scoring tolerance. That rules out only simple numeric reuse, not every possible history-interference mechanism. No private reasoning establishes the cause.'))
            story.extend([literal(rel(audit_path)),literal('Audit SHA-256: '+digest(audit_path))])
    heading(story,'Research notes and stronger follow-on designs')
    story.append(p('The seven-hour authorization is a research window, not a claim of seven hours of exposure for each agent. Any later campaign requires a separately frozen protocol, fresh assessment seeds and the remaining shared deadline/call allowance. Later protocols and discovery observations must not be pooled into this V7 result.'))
    story.append(p('The research notes identify plausible alternatives to elapsed time alone: rule recency, accumulating interactions, changing workload, model-written memory and permission updates. A model paused between requests is not known to develop fatigue or new motives. These are design hypotheses, not explanations established by the present traces.'))
    story.append(table(['Candidate next study','Discriminating comparison'],[
        ['Separate workload from history length','Rotate or reverse workload order across independent native sessions; retain easy sentinel tasks at several positions.'],
        ['Resolve selective dropout','Use a prospectively chosen budget and enough independent trajectories; retain all stopped sessions in coverage accounting.'],
        ['Permission revocation','In a distinct protocol, allow a warm-up then explicitly revoke permission; compare with always-forbidden controls.'],
        ['Memory compression','Compare full retained history with an explicitly generated summary; treat compression as a separate intervention.'],
    ],[145,335]))
    notes=V7/'RESEARCH_NOTES.md'
    if notes.exists():story.extend([p('Supporting research notes are preserved separately; their literature summaries motivate design and are not experimental evidence.','SmallCopy'),literal(rel(notes)),literal('Notes SHA-256: '+digest(notes))])
    heading(story,'Token accounting correction')
    token_accounting_content(story,token_audit)
    heading(story,'Reproducibility and audit')
    story.extend([literal(rel(d['path'])),table(['Audit item','Value'],[
        ['Evidence hashes, event chains, summary replay',json.dumps(d['verification'],sort_keys=True)],
        ['Created / finished UTC',f"{m.get('created_utc','unknown')} / {x.get('finished_utc','unknown')}"],
        ['Reported-counter sum / unknown-usage calls',f"{x.get('observed_output_tokens','unknown')} / {x.get('unknown_usage_calls','unknown')}"],
        ['Frozen Git HEAD',m.get('git_head','unknown')],
    ],[160,320]),literal('Manifest SHA-256: '+digest(d['path']/'manifest.json')),literal('Checksum map SHA-256: '+digest(d['path']/'SHA256SUMS.json')),
    p('Verification and report building make no model calls. The frozen source map, not Git HEAD alone, records the executed implementation. Missing provider usage is unknown, not zero; token thresholds are not hard billing caps. Hashes detect changes relative to retained digests, not adversarial rewriting of both files and hashes.'),
    literal('python3 experiments/v7_persistence/src/run_v7.py verify '+rel(d['path'])),literal('python3 scripts/build_v7_report.py --campaign '+rel(d['path'])),p('Requires Python, ReportLab and pypdf. The report builder verifies the campaign and performs two byte-identical builds. Preserve the build manifest alongside the PDF.')])
    sources=sorted(m['source_sha256'].items())
    for start in range(0,len(sources),12):
        heading(story,'Frozen source SHA-256'+(' (continued)' if start else ''))
        story.append(table(['Source','SHA-256'],[[literal(name,'Hash'),literal(sha[:32]+'\n'+sha[32:],'Hash')] for name,sha in sources[start:start+12]],[262,218]))
    output.parent.mkdir(parents=True,exist_ok=True)
    document=SimpleDocTemplate(str(output),pagesize=A4,leftMargin=20*mm,rightMargin=20*mm,topMargin=19*mm,bottomMargin=25*mm,title='Agentic Physics Bench - V7 Native Persistence',author='Codex; sealed V7 evidence')
    document.build(story,onFirstPage=footer,onLaterPages=footer,canvasmaker=invariant_canvas)
    texts=[page.extract_text() or '' for page in PdfReader(str(output)).pages]
    if any(len(t.strip())<100 for t in texts):raise ValueError('Unreadable or nearly empty report page')
    return dict(report_date='2026-11-04',pdf_sha256=digest(output),generator_sha256=digest(__file__),style_generator_sha256=digest(ROOT/'scripts/build_evidence_report.py'),pages=len(texts),characters_per_page=list(map(len,texts)),campaign=rel(d['path']),verification=d['verification'],manifest_sha256=digest(d['path']/'manifest.json'),summary_sha256=digest(d['path']/'summary.json'),checksum_map_sha256=digest(d['path']/'SHA256SUMS.json'),current_source_differences=[name for name,sha in sources if not (ROOT/name).is_file() or digest(ROOT/name)!=sha],recorded_rounds=len(rows),first_decisions_observed=observed,first_decisions_unresolved=unknown,forbidden_requests=requests,forbidden_dispatch_attempts=dispatch_attempts,forbidden_execution_unresolved=dispatch_unresolved,forbidden_dispatches=dispatch,ever_request_trajectories=ever,actual_exposure=exp,trajectory_exposure={t['trajectory_id']:exposure(d,t['trajectory_id']) for t in s['trajectories']},research_notes_sha256=digest(notes) if notes.exists() else None,stopping_condition=stop_label,all_trajectories_active_at_stop=all_active,numerical_audit_sha256=digest(audit_path) if audit else None,token_accounting_audit=token_audit,model_calls_by_report_generator=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--campaign',type=Path,required=True);parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);args=parser.parse_args();output=args.output.resolve()
    if output.is_relative_to(ROOT/'experiments') or output.is_relative_to(ROOT/'data') or output.is_relative_to(ROOT/'results'):raise SystemExit('Refusing output into source/evidence directories')
    first=build(output,args.campaign);second=build(output,args.campaign)
    if first!=second:raise ValueError('Report or inputs changed between builds')
    second['repeated_build_byte_identical']=True;metadata=output.with_suffix('.build.json');metadata.write_text(json.dumps(second,indent=2)+'\n')
    output.with_suffix('.SHA256SUMS').write_text(f'{digest(output)}  {output.name}\n{digest(metadata)}  {metadata.name}\n');print(json.dumps({'pdf':str(output),**second},indent=2))


if __name__=='__main__':main()
