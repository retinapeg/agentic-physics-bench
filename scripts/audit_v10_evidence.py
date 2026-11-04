#!/usr/bin/env python3
"""Independent, read-only V10 counter/context audit. Refuses unsealed campaigns.

No participant inference, campaign imports, or writes inside campaign evidence.
Only local rollout files whose names end in an observed participant UUID are read.
"""
from __future__ import annotations
import argparse
import collections
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

REQUIRED = {'input_tokens', 'cached_input_tokens', 'output_tokens'}
ALLOWED = REQUIRED | {'reasoning_output_tokens', 'cache_write_input_tokens'}
UUID = re.compile(r'^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$')
CONTEXT_TYPES = {'compacted', 'context_compacted', 'context_truncated', 'history_truncated',
                 'compaction_started', 'compaction_completed', 'context_compaction'}

class Refusal(Exception):
    pass

def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result

def loads(text):
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))

def read_json(path):
    return loads(path.read_text())

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def timestamp(value):
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamp has no timezone')
    return result

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def contained(root, value):
    path = Path(value)
    path = path if path.is_absolute() else root / path
    if path.is_symlink():
        raise ValueError('Symlink is not permitted: ' + str(path))
    path = path.resolve()
    if not path.is_relative_to(root):
        raise ValueError('Evidence path escapes campaign: ' + str(path))
    return path

def valid_usage(value):
    return (isinstance(value, dict) and REQUIRED <= set(value) <= ALLOWED
            and all(type(v) is int and v >= 0 for v in value.values()))

def local_audit(session_id, calls, sessions_root, issues):
    """Expose metadata/numerical counters only; never retain message contents."""
    result = {'session_id': session_id, 'history_retention': 'unknown',
              'history_retention_reason': 'Absence of exposed events cannot establish complete backend history retention.',
              'rollout_status': 'unavailable', 'exposed_context_events': [], 'call_correspondence': []}
    if not isinstance(session_id, str) or not UUID.fullmatch(session_id):
        result['rollout_status'] = 'invalid_participant_uuid'
        issues.append('Invalid participant UUID: ' + repr(session_id))
        return result
    # Inventory only filenames. Open only an exact participant-ID suffix match.
    matches = sorted(p for p in sessions_root.rglob('*' + session_id + '.jsonl')
                     if p.is_file() and not p.is_symlink()) if sessions_root.is_dir() else []
    if len(matches) != 1:
        result.update(rollout_status='missing' if not matches else 'ambiguous',
                      matching_file_count=len(matches))
        return result
    path = matches[0]
    result['rollout_path'] = str(path)
    # Validate the first metadata record before hashing/reading the complete file.
    try:
        with path.open() as stream:
            first = next((loads(line) for line in stream if line.strip()), None)
        if not isinstance(first, dict) or first.get('type') != 'session_meta':
            result['rollout_status'] = 'unknown_initial_metadata'; return result
        first_payload = first.get('payload')
        if not isinstance(first_payload, dict) or first_payload.get('id') != session_id:
            result['rollout_status'] = 'contradictory_initial_identity'
            issues.append('Selected rollout has contradictory initial identity: ' + session_id)
            return result
    except (OSError, ValueError, TypeError) as exc:
        result.update(rollout_status='unreadable_initial_metadata', diagnostic=str(exc)); return result
    result.update(rollout_sha256=digest(path), rollout_status='read')
    counts = collections.Counter(); tokens = []; records = []; identities = []
    starts = [timestamp(c['started_utc']) for c in calls if c.get('started_utc')]
    ends = [timestamp(c['finished_utc']) for c in calls if c.get('finished_utc')]
    lower = min(starts) if starts else None
    upper = max(ends) if ends else None
    try:
        with path.open() as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                event = loads(line)
                if not isinstance(event, dict):
                    raise ValueError('Non-object rollout event')
                kind = event.get('type'); payload = event.get('payload') or {}
                if not isinstance(payload, dict):
                    continue
                if kind == 'session_meta':
                    identities.append(payload.get('id'))
                when = timestamp(event['timestamp']) if event.get('timestamp') else None
                in_window = when is not None and lower is not None and lower <= when <= upper
                if not in_window and kind != 'session_meta':
                    continue
                counts[str(kind)] += 1
                subkind = payload.get('type') if kind == 'event_msg' else None
                # Do not search generated prose, summaries, or the comp_hash configuration field.
                if kind in CONTEXT_TYPES or subkind in CONTEXT_TYPES:
                    result['exposed_context_events'].append({'line': line_number, 'timestamp': event.get('timestamp'),
                                                             'type': kind, 'event_type': subkind})
                if kind == 'event_msg' and subkind == 'token_count' and isinstance(payload.get('info'), dict):
                    info = payload['info']
                    tokens.append({'line': line_number, 'timestamp': event.get('timestamp'),
                                   'total': info.get('total_token_usage'), 'last': info.get('last_token_usage')})
                if kind == 'token_usage_record':
                    records.append({'line': line_number, 'timestamp': event.get('timestamp'),
                                    **{k: payload.get(k) for k in ('thread_id', 'turn_id', 'session_id',
                                                                  'usage', 'turn_token_usage', 'thread_token_usage')}})
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result.update(rollout_status='unreadable_or_incompatible', diagnostic=str(exc))
        return result
    final_hash = digest(path)
    if final_hash != result['rollout_sha256']:
        result.update(rollout_status='changed_during_scan', rollout_sha256_after_scan=final_hash)
        return result
    result['metadata_event_counts'] = dict(counts)
    result['selected_record_counts'] = {'token_count': len(tokens), 'token_usage_record': len(records)}
    result['session_meta_identity_matches'] = bool(identities) and all(s == session_id for s in identities)
    if identities and not result['session_meta_identity_matches']:
        issues.append('Selected rollout has contradictory session_meta identity: ' + session_id)
    if result['exposed_context_events']:
        result['history_retention_reason'] = 'Exposed compaction/truncation events observed; complete original history is not established.'
    for call in calls:
        usage = call.get('raw_usage')
        if not valid_usage(usage) or not call.get('started_utc') or not call.get('finished_utc'):
            result['call_correspondence'].append({'sequence': call['sequence'], 'status': 'unknown'})
            continue
        start, end = timestamp(call['started_utc']), timestamp(call['finished_utc'])
        within = [row for row in tokens if row['timestamp'] and start <= timestamp(row['timestamp']) <= end]
        matching = [row for row in within if isinstance(row['total'], dict)
                    and all(row['total'].get(k) == v for k, v in usage.items())]
        row = {'sequence': call['sequence'], 'call_index': call.get('call_index'),
               'token_count_events_in_call_window': len(within),
               'matching_cumulative_total_events': len(matching),
               'status': 'matched' if matching else 'unknown_no_matching_exposed_total'}
        if matching:
            last = matching[-1]['last']
            row.update(matched_line=matching[-1]['line'], matched_timestamp=matching[-1]['timestamp'],
                       last_usage_matches_whole_call_delta=(isinstance(last, dict) and call.get('delta') is not None
                           and all(last.get(k) == v for k, v in call['delta'].items())))
        # An exposed final cumulative total different from CLI evidence is contradictory.
        if within and isinstance(within[-1]['total'], dict):
            final = within[-1]['total']
            if any(final.get(k) != v for k, v in usage.items()):
                issues.append('Local final cumulative total contradicts raw CLI call: ' + str(call['sequence']))
                row['status'] = 'mismatch'
        record_window = [r for r in records if r['timestamp'] and start <= timestamp(r['timestamp']) <= end]
        row['token_usage_record_events_in_call_window'] = len(record_window)
        row['record_turn_ids'] = sorted({r['turn_id'] for r in record_window if isinstance(r.get('turn_id'), str)})
        if any(r.get('thread_id') not in (None, session_id) for r in record_window):
            issues.append('Local token_usage_record thread identity contradicts participant: ' + session_id)
        if record_window:
            final_record = record_window[-1]
            thread_usage = final_record.get('thread_token_usage')
            turn_usage = final_record.get('turn_token_usage')
            row['record_thread_usage_matches_raw'] = (isinstance(thread_usage, dict)
                and all(thread_usage.get(k) == v for k, v in usage.items()))
            if isinstance(thread_usage, dict) and not row['record_thread_usage_matches_raw']:
                issues.append('Local record thread total contradicts raw CLI call: ' + str(call['sequence']))
            row['record_turn_usage_matches_call_delta'] = (isinstance(turn_usage, dict)
                and call.get('delta') is not None and len(row['record_turn_ids']) == 1
                and all(turn_usage.get(k) == v for k, v in call['delta'].items()))
        result['call_correspondence'].append(row)
    result['last_usage_limit'] = 'last_token_usage may describe only the last provider request, not the whole CLI call; inequality alone is diagnostic, not a failure.'
    return result

def audit(campaign, sessions_root):
    root = campaign.resolve(); seal_path = root / 'SHA256SUMS.json'
    if not seal_path.is_file():
        raise Refusal('Campaign is not sealed; no evidence or participant rollout contents were read.')
    hashes = read_json(seal_path)
    if not isinstance(hashes, dict):
        raise Refusal('Invalid seal')
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p != seal_path}
    if set(hashes) != actual:
        raise Refusal('Seal membership mismatch')
    for name, expected in hashes.items():
        path = contained(root, name)
        if digest(path) != expected:
            raise Refusal('Seal hash mismatch: ' + name)
    manifest = read_json(root / 'manifest.json')
    if manifest.get('schema') != 'v10-long-history-1' or manifest.get('execute') is not True:
        raise Refusal('Expected a sealed executed V10 campaign')
    if digest(root / 'manifest.json') != (root / 'manifest.sha256').read_text().strip():
        raise Refusal('Manifest companion hash mismatch')
    issues = []; unknowns = []; saved = read_json(root / 'usage_ledger.json')
    observations = saved['observations']; row_observations = {}; responses = {}; chain_count = 0
    for path in sorted(root.glob('trajectory-*/events.jsonl')):
        previous = '0' * 64; chain_count += 1
        for n, line in enumerate(path.read_text().splitlines()):
            entry = loads(line); expected = entry.pop('sha256')
            if entry['sequence'] != n or entry['previous_sha256'] != previous or hashlib.sha256(canonical(entry)).hexdigest() != expected:
                issues.append('Event chain mismatch: ' + str(path.relative_to(root)))
            previous = expected; event = entry['event']
            if event.get('kind') == 'model_response':
                key = (path.parent.name, event['round'])
                if key in responses:
                    issues.append('Multiple model responses for one-decision task: ' + repr(key))
                responses[key] = event['response']
    for path in sorted(root.glob('trajectory-*/round-*/result.json')):
        row = read_json(path); observation = row.get('usage_observation')
        if observation is None:
            continue
        n = observation.get('sequence')
        if type(n) is not int or n in row_observations:
            issues.append('Duplicate/invalid round usage sequence: ' + str(path.relative_to(root)))
            continue
        row_observations[n] = (observation, row, str(path.relative_to(root)))
    if set(row_observations) != set(range(len(observations))):
        issues.append('Round results and ledger observations are not one-to-one')
    prior = {}; indices = {}; totals = {}; calls = []; unknown_count = 0; raw_paths = set()
    for n, observation in enumerate(observations):
        call = {'sequence': n, 'status': observation.get('status')}
        calls.append(call)
        known_fields = {'raw_manifest', 'raw_stdout', 'session_id', 'resumed_session_id',
                        'session_resumed', 'call_index', 'raw_cumulative', 'previous_cumulative', 'delta'}
        if observation.get('status') == 'known' and not known_fields <= set(observation):
            issues.append('Known observation missing raw binding fields at sequence ' + str(n))
        if observation.get('sequence') != n:
            issues.append('Noncontiguous atomic ledger sequence at ' + str(n))
        bound = row_observations.get(n)
        if not bound:
            continue
        row_observation, row, row_path = bound
        call['round_result'] = row_path
        if row_observation != observation:
            issues.append('Ledger/round observation mismatch at ' + str(n))
        response = responses.get((row['trajectory_id'], row['round']))
        if response is not None and not isinstance(response, dict):
            issues.append('Non-object response at sequence ' + str(n)); response = None
        meta = (response or {}).get('meta') or {}
        if not isinstance(meta, dict):
            issues.append('Non-object response metadata at sequence ' + str(n)); meta = {}
        sid = meta.get('session_id', observation.get('session_id'))
        call['session_id'] = sid
        parsed = False; usage = None; index = None; resume = None; resumed = None
        try:
            raw = contained(root, meta['raw_stdout']); manpath = contained(root, meta['raw_manifest'])
            if str(raw.relative_to(root)) not in hashes or str(manpath.relative_to(root)) not in hashes:
                raise ValueError('Raw binding not covered by seal')
            raw_paths.add(str(raw.relative_to(root)))
            cmd = read_json(manpath); events = [loads(line) for line in raw.read_text().splitlines() if line.strip()]
            if any(not isinstance(e, dict) for e in events):
                raise ValueError('Non-object raw trace event')
            completed = [e for e in events if e.get('type') == 'turn.completed']
            threads = [e for e in events if e.get('type') == 'thread.started']
            if len(completed) != 1 or len(threads) != 1:
                raise ValueError('Raw trace lacks exactly one completed turn/thread')
            if threads[0].get('thread_id') != sid:
                raise ValueError('Raw/meta native identity mismatch')
            usage = completed[0].get('usage'); index = cmd['call_index']
            resume = cmd['native_session']['resumed_session_id']; resumed = 'resume' in cmd['argv']
            if resume != meta.get('prior_session_id') or resumed != (resume is not None):
                raise ValueError('Raw/meta resume identity mismatch')
            meta_usage = meta.get('usage') or {}
            if not isinstance(meta_usage, dict):
                raise ValueError('Incompatible raw/meta usage schema')
            if isinstance(usage, dict) and any(meta_usage.get(k) != usage.get(k) for k in REQUIRED):
                raise ValueError('Raw/meta usage mismatch')
            for key, value in [('raw_manifest', str(manpath)), ('raw_stdout', str(raw))]:
                if observation.get(key) is not None and contained(root, observation[key]) != Path(value):
                    raise ValueError('Observation/raw path mismatch: ' + key)
            if (observation.get('status') == 'known' or observation.get('raw_manifest')) and any(observation.get(k) != v for k, v in [
                    ('session_id', sid), ('resumed_session_id', resume), ('session_resumed', resumed),
                    ('call_index', index), ('raw_cumulative', usage)]):
                raise ValueError('Saved observation contradicts raw identity/usage')
            result_path = raw.with_name(raw.name.replace('-stdout.jsonl', '-result.json'))
            if result_path.is_file() and read_json(result_path) != response:
                raise ValueError('Event response differs from raw saved result')
            parsed = True
            call.update(raw_stdout=str(raw.relative_to(root)), raw_manifest=str(manpath.relative_to(root)),
                        raw_usage=usage, call_index=index, resumed_session_id=resume,
                        started_utc=meta.get('started_utc'), finished_utc=meta.get('finished_utc'),
                        local_rollout_identity_bound=isinstance(sid, str) and bool(UUID.fullmatch(sid)))
        except (OSError, KeyError, TypeError, ValueError) as exc:
            call['raw_binding_diagnostic'] = str(exc)
            # Known accounting must always bind. Honest missing/incomplete timeout evidence is unknown.
            if observation.get('status') == 'known' or 'mismatch' in str(exc).lower() or 'contradict' in str(exc).lower() or 'escapes' in str(exc).lower():
                issues.append('Raw binding failed at sequence ' + str(n) + ': ' + str(exc))
        if parsed and isinstance(sid, str):
            expected_index = indices.get(sid, 0) + 1
            if type(index) is not int or index != expected_index:
                issues.append('Nonconsecutive native call index at sequence ' + str(n))
            indices[sid] = index if type(index) is int else expected_index
        previous = prior.get(sid) if isinstance(sid, str) else None
        reason = None
        if not parsed: reason = 'unverifiable_raw_usage'
        elif not isinstance(sid, str) or not UUID.fullmatch(sid): reason = 'missing_or_invalid_session_identity'
        elif not valid_usage(usage): reason = 'missing_or_incompatible_usage'
        elif sid not in prior and (resumed or resume is not None or index != 1): reason = 'unverified_initial_baseline'
        elif sid in prior and (not resumed or resume != sid): reason = 'session_reused_without_valid_resume'
        elif sid in prior and previous is None: reason = 'prior_usage_unknown'
        elif previous is not None and set(previous) != set(usage): reason = 'counter_schema_changed'
        elif previous is not None and any(usage[k] < previous[k] for k in usage): reason = 'counter_decreased_or_reset'
        if reason:
            unknown_count += 1; unknowns.append({'sequence': n, 'reason': reason})
            if observation.get('status') != 'unknown' or observation.get('delta') is not None:
                issues.append('Unknown raw accounting presented as known at sequence ' + str(n))
            if isinstance(sid, str): prior[sid] = None
            continue
        baseline = previous if previous is not None else {k: 0 for k in usage}
        delta = {k: usage[k] - baseline[k] for k in usage}
        if observation.get('status') != 'known' or observation.get('delta') != delta or observation.get('previous_cumulative') != previous:
            issues.append('Raw-derived delta/previous/status differs at sequence ' + str(n))
        call['delta'] = delta; prior[sid] = dict(usage)
        for key, value in delta.items(): totals[key] = totals.get(key, 0) + value
    if totals != saved['known_deduplicated_usage'] or unknown_count != saved['unknown_usage_observations'] or prior != saved['session_cumulative_snapshots']:
        issues.append('Raw-derived ledger totals/unknown count/session snapshots differ')
    execution = read_json(root / 'execution.json')
    if any(execution.get(k) != saved.get(k) for k in ('known_deduplicated_usage', 'unknown_usage_observations', 'session_cumulative_snapshots')):
        issues.append('Execution/ledger summary mismatch')
    if unknown_count and execution.get('usage_stop_reason') != 'usage_accounting_unknown':
        issues.append('Unknown usage lacks campaign accounting-stop reason')
    grouped = collections.defaultdict(list)
    for call in calls:
        if call.get('local_rollout_identity_bound') is True:
            grouped[call['session_id']].append(call)
    local = [local_audit(sid, group, sessions_root, issues) for sid, group in sorted(grouped.items())]
    return {'schema': 'apb-v10-independent-postseal-audit-v1',
            'audited_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'campaign': str(root), 'auditor_script_sha256': digest(Path(__file__)),
            'campaign_seal_sha256': digest(seal_path), 'manifest_sha256': digest(root / 'manifest.json'),
            'usage_ledger_sha256': digest(root / 'usage_ledger.json'), 'verified_files': len(hashes),
            'event_chains_checked': chain_count, 'observation_count': len(observations),
            'distinct_participant_sessions': len(grouped), 'bound_raw_stdout_files': len(raw_paths),
            'raw_derived_known_usage': totals, 'unknown_accounting_observations': unknowns,
            'issues': issues, 'passed': not issues, 'calls': calls, 'local_rollouts': local,
            'history_retention': 'unknown',
            'limitations': ['Only raw usage/provenance and exposed local context metadata are audited; this script does not grade behavioral outcomes.',
                            'Absence of compaction events does not establish complete retained history or absence of hidden server truncation.',
                            'last_token_usage can cover only the final provider request within a CLI call; whole-call deltas use cumulative differences.',
                            'Missing/ambiguous local rollouts leave corroboration unknown; they are never replaced by unrelated conversations.',
                            'CLI counters do not independently establish billing or hidden provider requests.',
                            'Evidence hashes establish internal consistency, not an external trusted timestamp or adversarial tamper-proof custody.'],
            'no_experimental_inference': True, 'source_or_evidence_modified': False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sessions-root', type=Path, default=Path.home()/'.codex/sessions')
    args = parser.parse_args(); root = args.campaign.resolve(); output = args.output.resolve()
    if output.is_relative_to(root) or output.exists():
        parser.error('Output must be a new file outside the sealed campaign')
    try:
        result = audit(root, args.sessions_root.resolve())
    except (Refusal, OSError, ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
        print('AUDIT REFUSED: ' + str(exc), file=sys.stderr); return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')
    print(json.dumps({'output': str(output), 'sha256': digest(output), 'passed': result['passed'],
                      'issues': result['issues'], 'observations': result['observation_count'],
                      'history_retention': result['history_retention']}, sort_keys=True))
    return 0 if result['passed'] else 1

if __name__ == '__main__':
    sys.exit(main())
