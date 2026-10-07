"""Synthetic source fixtures verify auditing, not actual recommendation outcomes."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_source as source


class ExtractionTests(unittest.TestCase):
    def fixture(self, path):
        return '\n'.join(f'param!({name}, f64, "switch_{name}", 1.0);'
                         for name in sorted(source.REQUIRED[path]))

    def test_commented_macros_cannot_supply_missing_evidence(self):
        path = 'vm-ranker/params.rs'
        content = self.fixture(path)
        self.assertEqual(len(source.extract_parameters(content, path)), len(source.REQUIRED[path]))
        content = content.replace('param!(ReplyWeight', '// param!(ReplyWeight')
        with self.assertRaisesRegex(ValueError, 'ReplyWeight'):
            source.extract_parameters(content, path)

    def test_duplicate_selected_parameter_fails(self):
        path = 'vm-ranker/params.rs'
        with self.assertRaisesRegex(ValueError, 'duplicate parameter ReplyWeight'):
            source.extract_parameters(self.fixture(path) + '\nparam!(ReplyWeight, f64, "other", 2.0);', path)

    def test_unsupported_upstream_syntax_requires_review(self):
        path = 'vm-ranker/params.rs'
        content = self.fixture(path).replace('"switch_ReplyWeight", 1.0', '"switch_ReplyWeight", 1e1')
        with self.assertRaisesRegex(ValueError, 'extraction incomplete'):
            source.extract_parameters(content, path)

    def test_comments_preserve_line_numbers_and_strings(self):
        path = 'vm-ranker/params.rs'
        content = '/* first\nsecond */\n' + self.fixture(path)
        result = source.extract_parameters(content, path)
        self.assertEqual(min(v['line'] for v in result.values()), 3)
        self.assertEqual(source.strip_comments('"https://a/*b*/" // comment'), '"https://a/*b*/"           ')

    def test_nested_rust_comments_cannot_supply_evidence(self):
        path = 'vm-ranker/params.rs'
        content = self.fixture(path).replace('param!(ReplyWeight, f64, "switch_ReplyWeight", 1.0);', '')
        content += '\n/* outer /* inner */ param!(ReplyWeight, f64, "fake", 5.0); */'
        with self.assertRaisesRegex(ValueError, 'ReplyWeight'):
            source.extract_parameters(content, path)

    def test_max_age_extracts_seconds_without_evaluating_code(self):
        result = source.extract_max_post_age('\npub const MAX_POST_AGE: u64 = 48 * 60 * 60;')
        self.assertEqual(result['value'], 172800)
        self.assertEqual(result['line'], 2)
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            source.extract_max_post_age('pub const MAX_POST_AGE: u64 = dangerous();')
        with self.assertRaisesRegex(ValueError, 'missing'):
            source.extract_max_post_age('// pub const MAX_POST_AGE: u64 = 123;')


class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Source audit test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('remote', 'add', 'origin', source.OFFICIAL_URL)
        for name in source.FILES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('synthetic audit fixture\n')
        helper = ExtractionTests()
        for name in source.REQUIRED:
            (self.root / name).write_text(helper.fixture(name))
        (self.root / 'home-mixer/params/config.rs').write_text('pub const MAX_POST_AGE: u64 = 48 * 60 * 60;\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Synthetic fixture')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def test_records_committed_hashes_and_configuration(self):
        result = source.audit(self.root)
        self.assertEqual(result['commit'], self.git('rev-parse', 'HEAD'))
        self.assertEqual(result['files'][0]['sha256'], hashlib.sha256(b'synthetic audit fixture\n').hexdigest())
        self.assertEqual(result['constants']['home-mixer/params/config.rs']['MAX_POST_AGE']['value'], 172800)

    def test_dirty_and_unofficial_checkout_fail(self):
        (self.root / 'README.md').write_text('modified')
        with self.assertRaisesRegex(ValueError, 'clean'):
            source.audit(self.root)
        self.git('checkout', '--', 'README.md')
        self.git('remote', 'set-url', 'origin', 'https://github.com/other/fork.git')
        with self.assertRaisesRegex(ValueError, 'official'):
            source.audit(self.root)

    def test_assume_unchanged_cannot_replace_committed_evidence(self):
        expected = source.audit(self.root)
        self.git('update-index', '--assume-unchanged', 'README.md')
        (self.root / 'README.md').write_text('uncommitted bytes hidden from status')
        self.assertEqual(source.audit(self.root), expected)

    def test_current_upstream_check_detects_unreviewed_revision(self):
        run = subprocess.check_output
        def different_remote(args, **kwargs):
            if args[:2] == ['git', 'ls-remote']:
                return '0' * 40 + '\tHEAD\n'
            return run(args, **kwargs)
        with patch.object(source.subprocess, 'check_output', side_effect=different_remote):
            with self.assertRaisesRegex(ValueError, 'HEAD differs'):
                source.audit(self.root, check_latest=True)

    def test_manifest_check_rejects_drift_without_overwriting_it(self):
        with tempfile.TemporaryDirectory() as external:
            manifest = Path(external) / 'manifest.json'
            data = source.audit(self.root)
            data['parameters']['vm-ranker/params.rs']['ReplyWeight']['default'] = 99
            manifest.write_text(json.dumps(data))
            previous = manifest.read_bytes()
            result = subprocess.run([sys.executable, source.__file__, '--source', str(self.root),
                                     '--check', str(manifest)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('manifest differs', result.stderr)
            self.assertEqual(manifest.read_bytes(), previous)


if __name__ == '__main__':
    unittest.main()
