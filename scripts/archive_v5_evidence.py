#!/usr/bin/env python3
"""Preserve sealed V5/V6 evidence without inference or modifying source records.

Run from the repository root after campaigns and reports finish:
  python3 scripts/archive_v5_evidence.py --campaign experiments/v5_tool_difficulty/results/pilot-20261103 --campaign experiments/v5_tool_difficulty/results/boundary-20261103 --output /absolute/new/archive-directory

Use --check-only to verify inputs without creating an archive. The Git bundle
contains committed history; evidence-files.tar.gz also preserves selected
uncommitted results and report files. Never archives credentials or .git files.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shlex
import sys
import tarfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
V5 = ROOT / 'experiments/v5_tool_difficulty'

def version_root(campaign):
    for version, name in ((5, 'v5_tool_difficulty'), (6, 'v6_instruction_strength')):
        base = ROOT / 'experiments' / name
        if campaign.is_relative_to(base / 'results'):
            return version, base
    raise ValueError('Campaign must be inside the existing V5 or V6 results directory')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    with path.open('x') as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write('\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def collect(campaigns):
    files = set()
    checks = []
    def add(path):
        if path.is_symlink():
            raise ValueError(f'Refusing symlink: {path}')
        if path.is_file():
            files.add(path)
    for campaign in campaigns:
        version, base = version_root(campaign)
        for required in ('manifest.json', 'manifest.sha256', 'summary.json', 'execution.json', 'SHA256SUMS.json'):
            if not (campaign / required).is_file():
                raise ValueError(f'Unsealed/incomplete campaign; missing {campaign / required}')
        # A fresh process prevents V5/V6 modules named analyze from colliding.
        checked = json.loads(subprocess.check_output(
            [sys.executable, str(base / f'src/run_v{version}.py'), 'verify', str(campaign)],
            cwd=ROOT, text=True))
        manifest = json.loads((campaign / 'manifest.json').read_text())
        for name, sha in manifest['source_sha256'].items():
            source = (ROOT / name).resolve()
            if not source.is_relative_to(ROOT) or not source.is_file() or digest(source) != sha:
                raise ValueError(f'Frozen source changed or unavailable: {name}')
        checks.append({'path': str(campaign.relative_to(ROOT)), 'version': version, **checked})
        for name in manifest['source_sha256']:
            path = (ROOT / name).resolve()
            if not path.is_relative_to(ROOT):
                raise ValueError('Source path escapes repository')
            add(path)
        for path in campaign.rglob('*'):
            add(path)
    # Setup probes are distinct readiness evidence and do not have task manifests.
    for experiment in ('v5_tool_difficulty', 'v6_instruction_strength'):
        for directory in sorted((ROOT / 'experiments' / experiment / 'results').glob('setup*')):
            for path in directory.rglob('*'):
                if '__pycache__' not in path.parts:
                    add(path)
    for name in ('build_evidence_report.py', 'build_v5_report.py', 'build_v6_report.py', 'archive_v5_evidence.py'):
        add(ROOT / 'scripts' / name)
    for pattern in ('*.pdf', '*.build.json', '*.SHA256SUMS'):
        for path in (ROOT / 'reports').glob(pattern):
            add(path)
    for path in (ROOT / 'docs/evidence/2026-11-03').rglob('*'):
        if '__pycache__' not in path.parts:
            add(path)
    for path in (ROOT / 'reports').glob('*.SHA256SUMS'):
        for line in path.read_text().splitlines():
            sha, name = line.split(None, 1)
            target = path.parent / name.strip()
            if digest(target) != sha:
                raise ValueError(f'Report checksum mismatch: {target}')
    return sorted(files), checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', action='append', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    campaigns = [p.resolve() for p in args.campaign]
    if len(set(campaigns)) != len(campaigns):
        parser.error('Duplicate campaigns')
    files, checks = collect(campaigns)
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in files}
    if args.check_only:
        print(json.dumps({'verified_files': len(files), 'campaigns': checks}, indent=2))
        return
    if args.output is None:
        parser.error('--output is required unless --check-only is used')
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error('Archive must be outside the source worktree')
    output.mkdir(parents=False, exist_ok=False)
    # Exclusive directory keeps failures visible and prevents overwriting evidence.
    archive = output / 'evidence-files.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for path in files:
            tar.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    with tarfile.open(archive, 'r:gz') as tar:
        archived = {member.name: hashlib.sha256(tar.extractfile(member).read()).hexdigest()
                    for member in tar.getmembers()}
    if archived != hashes or any(digest(ROOT / p) != sha for p, sha in hashes.items()):
        raise RuntimeError('Inputs changed during archive creation or archive verification failed')
    bundle = output / 'repository.bundle'
    subprocess.run(['git', 'bundle', 'create', str(bundle), '--all'], cwd=ROOT, check=True)
    subprocess.run(['git', 'bundle', 'verify', str(bundle)], cwd=ROOT, check=True, capture_output=True)
    commands = ['# Run from a checkout of the preserved repository; overlay evidence-files.tar.gz.',
                '# Verification and report rebuilding do not perform model inference.',
                'python3 -W error::ResourceWarning -m unittest discover -s experiments/v5_tool_difficulty/tests -v']
    versions = {}
    for campaign in campaigns:
        version, base = version_root(campaign)
        versions.setdefault(version, []).append(campaign)
        commands.append('python3 ' + str((base / f'src/run_v{version}.py').relative_to(ROOT)) + ' verify ' + shlex.quote(str(campaign.relative_to(ROOT))))
    if 6 in versions:
        commands.append('python3 -W error::ResourceWarning -m unittest discover -s experiments/v6_instruction_strength/tests -v')
    for version, selected in sorted(versions.items()):
        commands.append(f'python3 scripts/build_v{version}_report.py ' + ' '.join('--campaign ' + shlex.quote(str(p.relative_to(ROOT))) for p in selected))
    (output / 'REPRODUCE.txt').write_text('\n'.join(commands) + '\n')
    write_json(output / 'manifest.json', {'created_utc': datetime.now(timezone.utc).isoformat(),
               'source_repository': str(ROOT), 'git_head': git('rev-parse', 'HEAD'),
               'git_status': git('status', '--porcelain'), 'campaigns': checks,
               'files': hashes, 'archive_round_trip_verified': True,
               'limitations': ['Git bundle contains committed history; tar archive additionally preserves selected working files.',
                              'Setup probes are readiness evidence, excluded from task denominators.',
                              'Hashes detect changes relative to retained digests; they are not signatures.']})
    entries = [p for p in sorted(output.iterdir()) if p.is_file()]
    (output / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in entries))
    print(json.dumps({'archive': str(output), 'files': len(files), 'campaigns': checks}, indent=2))


if __name__ == '__main__':
    main()
