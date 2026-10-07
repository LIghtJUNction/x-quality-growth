"""Test upstream drift reporting with local synthetic Git histories."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import review_upstream as review


class UpstreamReviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic source')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('remote', 'add', 'origin', review.REPOSITORY + '.git')
        for name in ('changed.rs', 'deleted.rs', 'unchanged.rs'):
            (self.root / name).write_text('old source\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Reviewed synthetic source')
        self.manifest = {'repository': review.REPOSITORY, 'commit': self.git('rev-parse', 'HEAD'),
                         'files': [{'path': name, 'sha256': hashlib.sha256(b'old source\n').hexdigest()}
                                   for name in ('changed.rs', 'deleted.rs', 'unchanged.rs')]}

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def advance(self):
        (self.root / 'changed.rs').write_text('new semantics require review\n')
        (self.root / 'deleted.rs').unlink()
        self.git('add', '.')
        self.git('commit', '-qm', 'New synthetic revision')

    def test_reviewed_revision_creates_no_report(self):
        result, report = review.review(self.root, self.manifest)
        self.assertFalse(result['upstream_changed'])
        self.assertIsNone(report)

    def test_reports_changed_deleted_and_unchanged_with_pinned_links(self):
        original = json.dumps(self.manifest, sort_keys=True)
        self.advance()
        result, report = review.review(self.root, self.manifest)
        self.assertEqual(result['changed_files'], 1)
        self.assertEqual(result['deleted_files'], 1)
        self.assertEqual(result['compared_files'], 3)
        self.assertIn('Semantic review is pending', report)
        self.assertIn('UNCHANGED', report)
        self.assertIn(f"/compare/{self.manifest['commit']}...{self.git('rev-parse', 'HEAD')}", report)
        self.assertEqual(json.dumps(self.manifest, sort_keys=True), original)

    def test_change_outside_bound_files_still_requires_review(self):
        (self.root / 'dependency.rs').write_text('new code')
        self.git('add', '.')
        self.git('commit', '-qm', 'Dependency change')
        result, report = review.review(self.root, self.manifest)
        self.assertTrue(result['upstream_changed'])
        self.assertEqual(result['changed_files'], 0)
        self.assertIn('dependencies and configuration outside this set', report)

    def test_hidden_worktree_modification_cannot_enter_report(self):
        self.advance()
        expected = review.review(self.root, self.manifest)
        self.git('update-index', '--assume-unchanged', 'changed.rs')
        (self.root / 'changed.rs').write_text('hidden local edit')
        self.assertEqual(review.review(self.root, self.manifest), expected)

    def test_unofficial_origin_and_dirty_source_rejected(self):
        self.advance()
        (self.root / 'untracked').write_text('private data')
        with self.assertRaisesRegex(ValueError, 'clean'):
            review.review(self.root, self.manifest)
        (self.root / 'untracked').unlink()
        self.git('remote', 'set-url', 'origin', 'https://github.com/other/fork.git')
        with self.assertRaisesRegex(ValueError, 'official'):
            review.review(self.root, self.manifest)

    def test_duplicate_and_traversal_paths_rejected(self):
        self.advance()
        self.manifest['files'].append(self.manifest['files'][0].copy())
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            review.review(self.root, self.manifest)
        self.manifest['files'].pop()
        self.manifest['files'][0]['path'] = '../secret'
        with self.assertRaisesRegex(ValueError, 'invalid'):
            review.review(self.root, self.manifest)

    def run_cli(self, manifest, output):
        result = subprocess.run([sys.executable, review.__file__, '--source', str(self.root),
                                 '--manifest', str(manifest), '--output', str(output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_cli_has_no_empty_report_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as external:
            manifest = Path(external) / 'manifest.json'
            output = Path(external) / 'pending.md'
            manifest.write_text(json.dumps(self.manifest))
            self.assertFalse(self.run_cli(manifest, output)['report_changed'])
            self.assertFalse(output.exists())
            self.advance()
            self.assertTrue(self.run_cli(manifest, output)['report_changed'])
            first_mtime = output.stat().st_mtime_ns
            self.assertFalse(self.run_cli(manifest, output)['report_changed'])
            self.assertEqual(output.stat().st_mtime_ns, first_mtime)
            self.assertEqual(json.loads(manifest.read_text()), self.manifest)


if __name__ == '__main__':
    unittest.main()
