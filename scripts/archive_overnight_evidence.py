#!/usr/bin/env python3
"""Archive sealed overnight V7/V8/V9 evidence; never perform model inference.

Use --campaign once per sealed campaign and --output for a new external
archive directory. --check-only validates selected inputs without an archive.
The final archive should be made only after all reports and commits are ready.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = 'docs/overnight-2026-11-04'
STATE = 'experiments/v7_persistence/overnight_state.json'
READINESS = ('readiness-20261104', 'readiness-frozen-20261104')
SOURCE_PATTERN = re.compile(r'experiments/v[5-9]_[a-z0-9_]+/(?:src/[a-zA-Z0-9_]+\.py|tests/[a-zA-Z0-9_]+\.py|PROTOCOL\.md|README\.md)\Z')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_path(name):
    """Reject escaping paths, hidden files and symlinks before any file read."""
    rel = PurePosixPath(name)
    if rel.is_absolute() or not rel.parts or any(p in ('.', '..') or p.startswith('.') for p in rel.parts):
        raise ValueError(f'Unsafe repository path: {name}')
    path = ROOT
    for part in rel.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f'Refusing symlink: {path}')
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError(f'Path escapes repository: {name}')
    if path.name.lower() in {'auth.json', 'credentials.json', 'credentials', 'id_rsa', 'id_ed25519'}:
        raise ValueError(f'Credential-like file is outside the archive contract: {name}')
    return path


def source_path(name):
    if name not in ('src/tasks.py', 'src/tools.py') and not SOURCE_PATTERN.fullmatch(name):
        raise ValueError(f'Source is outside the explicit archive allowlist: {name}')
    return safe_path(name)


def campaign_identity(path):
    path = Path(path).absolute()
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        raise ValueError('Campaign must be within this existing repository') from None
    checked = safe_path(rel.as_posix())
    if len(rel.parts) != 4 or rel.parts[0] != 'experiments' or rel.parts[2] != 'results':
        raise ValueError('Campaign must be a direct child of an experiment results directory')
    match = re.fullmatch(r'v([789])_[a-z0-9_]+', rel.parts[1])
    if not match:
        raise ValueError('Only overnight V7/V8/V9 campaign roots are accepted')
    version = int(match.group(1))
    if version == 7 and rel.parts[1] != 'v7_persistence' or version == 8 and rel.parts[1] != 'v8_revocation':
        raise ValueError('Unrecognized V7/V8 experiment root')
    base = ROOT / 'experiments' / rel.parts[1]
    return checked, version, base


def verify_sealed(path, version, base, *, probe=False):
    required = ['manifest.json', 'manifest.sha256', 'SHA256SUMS.json']
    required += ['probe_results.json'] if probe else ['summary.json', 'execution.json']
    for name in required:
        if not (path / name).is_file():
            raise ValueError(f'Unsealed/incomplete evidence: {path / name}')
    # Pre-validate checksum paths before invoking a version-specific verifier.
    hashes = json.loads((path / 'SHA256SUMS.json').read_text())
    for name in hashes:
        member = PurePosixPath(name)
        if member.is_absolute() or '..' in member.parts:
            raise ValueError('Escaping evidence checksum member')
        safe_path((path.relative_to(ROOT) / name).as_posix())
    runner = safe_path((base / f'src/run_v{version}.py').relative_to(ROOT).as_posix())
    checked = json.loads(subprocess.check_output([sys.executable, str(runner), 'verify', str(path)], cwd=ROOT, text=True))
    manifest = json.loads((path / 'manifest.json').read_text())
    if probe:
        if manifest.get('schema') != 'v7-readiness-only' or manifest.get('execute') is not False:
            raise ValueError('Readiness record has an unexpected schema')
    elif manifest.get('execute') is not True:
        raise ValueError('Selected campaign is a plan or readiness probe, not executed evidence')
    differences = []
    for name, sha in manifest['source_sha256'].items():
        source = source_path(name)
        if not source.is_file() or digest(source) != sha:
            differences.append(name)
    if differences and not probe:
        raise ValueError(f'Campaign frozen sources changed: {differences}')
    return manifest, dict(path=str(path.relative_to(ROOT)), version=version, verification=checked,
                          current_source_differences=differences, task_evidence=not probe)


def collect(campaigns):
    files, checks, probes = set(), [], []
    def add(path):
        path = safe_path(path.relative_to(ROOT).as_posix())
        if path.is_file():
            files.add(path)
    def tree(directory):
        for path in sorted(directory.rglob('*')):
            if '__pycache__' in path.parts:
                continue
            add(path)
    for selected in campaigns:
        path, version, base = campaign_identity(selected)
        tree(path)  # Reject symlinks/hidden or credential-like files before verification.
        manifest, checked = verify_sealed(path, version, base)
        for name in manifest['source_sha256']:
            add(source_path(name))
        checks.append(checked)
    for name in READINESS:
        path = safe_path(f'experiments/v7_persistence/results/{name}')
        if not path.exists():
            continue
        tree(path)
        manifest, checked = verify_sealed(path, 7, ROOT / 'experiments/v7_persistence', probe=True)
        checked['limitation'] = ('Readiness-only development probe, excluded from task counts. '
            'Archived current source may differ from its recorded source hashes; an exact old working-source snapshot is not asserted.')
        for source in manifest['source_sha256']:
            add(source_path(source))
        probes.append(checked)
    for name in ('build_evidence_report.py', 'build_v7_report.py', 'build_v8_report.py',
                 'build_v9_report.py', 'archive_overnight_evidence.py'):
        add(ROOT / 'scripts' / name)
    for version in (7, 8, 9):
        for pattern in (f'v{version}-*.pdf', f'v{version}-*.build.json', f'v{version}-*.SHA256SUMS'):
            for path in (ROOT / 'reports').glob(pattern):
                add(path)
        for sums in (ROOT / 'reports').glob(f'v{version}-*.SHA256SUMS'):
            for line in sums.read_text().splitlines():
                sha, name = line.split(None, 1)
                if Path(name.strip()).name != name.strip() or not name.startswith(f'v{version}-'):
                    raise ValueError('Report checksum points outside the versioned report set')
                report = safe_path('reports/' + name.strip())
                if report not in files or digest(report) != sha:
                    raise ValueError(f'Report checksum mismatch: {report}')
    docs = safe_path(DOCS)
    if docs.exists():
        tree(docs)
    state = safe_path(STATE)
    if state.exists():
        add(state)
    return sorted(files), checks, probes


def reproduction(campaigns):
    lines = ['# Clone repository.bundle; check out the manifest git_head; overlay evidence-files.tar.gz.',
             '# These commands verify or render saved evidence. They do not call a model.',
             '# PDF builds require reportlab and pypdf (versions recorded in the report build environment).']
    tested = set()
    for selected in campaigns:
        path, version, base = campaign_identity(selected)
        base_name = str(base.relative_to(ROOT))
        if version not in tested:
            lines.append(f'python3 -W error::ResourceWarning -m unittest discover -s {shlex.quote(base_name + "/tests")} -v')
            tested.add(version)
        lines.append(f'python3 {shlex.quote(base_name + f"/src/run_v{version}.py")} verify {shlex.quote(str(path.relative_to(ROOT)))}')
        if (ROOT / f'scripts/build_v{version}_report.py').is_file():
            lines.append(f'python3 scripts/build_v{version}_report.py --campaign {shlex.quote(str(path.relative_to(ROOT)))}')
    return '\n'.join(lines) + '\n'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', action='append', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    campaigns = [Path(p).absolute() for p in args.campaign]
    if len(set(campaigns)) != len(campaigns):
        parser.error('Duplicate campaigns')
    files, checks, probes = collect(campaigns)
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in files}
    if args.check_only:
        print(json.dumps(dict(files=len(files), campaigns=checks, readiness_probes=probes), indent=2))
        return
    if args.output is None:
        parser.error('--output is required except with --check-only')
    output = args.output.resolve()
    if output.is_relative_to(ROOT.resolve()):
        parser.error('Archive must be external to the source worktree')
    output.mkdir(parents=False, exist_ok=False)
    head_before, refs_before = git('rev-parse', 'HEAD'), git('show-ref')
    archive = output / 'evidence-files.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for path in files:
            tar.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    with tarfile.open(archive, 'r:gz') as tar:
        restored = {member.name: hashlib.sha256(tar.extractfile(member).read()).hexdigest()
                    for member in tar.getmembers()}
    if restored != hashes or any(digest(ROOT / name) != sha for name, sha in hashes.items()):
        raise RuntimeError('Inputs changed during archiving or tar round-trip failed')
    bundle = output / 'repository.bundle'
    subprocess.run(['git', 'bundle', 'create', str(bundle), '--all'], cwd=ROOT, check=True)
    subprocess.run(['git', 'bundle', 'verify', str(bundle)], cwd=ROOT, check=True, capture_output=True)
    if git('rev-parse', 'HEAD') != head_before or git('show-ref') != refs_before:
        raise RuntimeError('Git refs changed during archive creation')
    # Audit the selected evidence again after archive writing; no provider calls.
    final_files, final_checks, final_probes = collect(campaigns)
    if files != final_files or checks != final_checks or probes != final_probes or any(digest(ROOT / name) != sha for name, sha in hashes.items()):
        raise RuntimeError('Evidence or supporting files changed during archiving')
    (output / 'REPRODUCE.txt').write_text(reproduction(campaigns))
    manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), repository=str(ROOT),
                    git_head=head_before, git_refs=refs_before, git_status=git('status', '--porcelain'),
                    campaigns=checks, readiness_probes=probes, files=hashes,
                    archive_round_trip_verified=True, git_bundle_verified=True,
                    limitations=['Git bundle preserves committed history; tar also preserves selected working evidence.',
                                 'Older readiness probes retain their original hashes but may lack an exact archived working-source snapshot.',
                                 'Readiness probes are separate development evidence and never task observations.',
                                 'Checksums are integrity checks against retained digests, not signatures.'])
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    entries = [p for p in sorted(output.iterdir()) if p.is_file()]
    (output / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in entries))
    print(json.dumps(dict(archive=str(output), files=len(files), campaigns=checks), indent=2))


if __name__ == '__main__':
    main()
