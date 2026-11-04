"""Narrow offline regressions for overnight archive coverage; no inference."""
import json
import shlex
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import archive_overnight_evidence as archive


class ArchiveCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.root_patch = patch.object(archive, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def write(self, name, content='fixture'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_exact_frozen_docs_dependency_is_hash_checked(self):
        dependency = self.write(archive.FROZEN_TOKEN_AUDIT, '{}')
        self.assertEqual(archive.source_path(archive.FROZEN_TOKEN_AUDIT), dependency)
        with self.assertRaises(ValueError):
            archive.source_path(archive.DOCS + '/unlisted-audit.json')
        base = self.root / 'experiments/v10_long_history'
        campaign = base / 'results/fixture'
        manifest = {'execute': True, 'source_sha256': {archive.FROZEN_TOKEN_AUDIT: archive.digest(dependency)}}
        for name, content in [('manifest.json', json.dumps(manifest)), ('manifest.sha256', 'fixture'),
                              ('SHA256SUMS.json', '{}'), ('summary.json', '{}'), ('execution.json', '{}')]:
            self.write(str((campaign / name).relative_to(self.root)), content)
        with patch.object(archive.subprocess, 'check_output', return_value='{}'):
            _, checked = archive.verify_sealed(campaign, 10, base)
            self.assertEqual(checked['current_source_differences'], [])
            dependency.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError, 'Campaign frozen sources changed'):
                archive.verify_sealed(campaign, 10, base)

    def test_synthesis_audit_scripts_and_json_are_archived_and_checked(self):
        names = ['build_overnight_report.py', 'audit_v10_evidence.py', 'test_audit_v10_evidence.py']
        expected = {self.write('scripts/' + name) for name in names}
        expected.add(self.write(archive.DOCS + '/v10-independent-audit.json', '{}'))
        pdf = self.write('reports/overnight-synthesis-2026-11-04.pdf')
        metadata = self.write('reports/overnight-synthesis-2026-11-04.build.json', '{}')
        checksum = self.write('reports/overnight-synthesis-2026-11-04.SHA256SUMS', ''.join(
            f'{archive.digest(path)}  {path.name}\n' for path in (pdf, metadata)))
        expected.update((pdf, metadata, checksum))
        files, _, _ = archive.collect([])
        self.assertTrue(expected.issubset(files))
        pdf.write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'Report checksum mismatch'):
            archive.collect([])

    def test_reproduction_uses_new_audit_output_and_synthesis_arguments(self):
        for name in ('audit_v10_evidence.py', 'build_overnight_report.py'):
            self.write('scripts/' + name)
        campaigns = [self.root / f'experiments/{name}/results/fixture' for name in
                     ('v7_persistence', 'v8_revocation', 'v9_memory_handoff', 'v10_long_history')]
        commands = archive.reproduction(campaigns)
        self.assertIn('mktemp -d', commands)
        self.assertIn('--output "$overnight_replay_dir/v10-audit-1.json"', commands)
        self.assertIn('--original-campaign ' + shlex.quote(str(campaigns[-1])), commands)
        spaced = campaigns[-1].with_name('fixture with spaces')
        self.assertIn('--original-campaign ' + shlex.quote(str(spaced)), archive.reproduction([spaced]))
        self.assertIn('python3 scripts/build_overnight_report.py --v7 ', commands)
        self.assertIn('--v10 experiments/v10_long_history/results/fixture', commands)
        self.assertIn('does not copy those sessions', commands)
        with self.assertRaises(ValueError):
            archive.safe_path('.codex/sessions/example.jsonl')


if __name__ == '__main__':
    unittest.main()
