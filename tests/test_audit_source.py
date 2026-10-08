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
        dpp_defaults = {'DppEnabled': ('bool', 'true'), 'DppTheta': ('f64', '0.65'),
                        'DppMaxSelectedRank': ('u32', '150')}
        records = []
        for name in sorted(source.REQUIRED[path]):
            kind, literal = dpp_defaults.get(name, ('f64', '1.0'))
            records.append(f'param!({name}, {kind}, "switch_{name}", {literal});')
        return '\n'.join(records)

    def test_dpp_parameters_are_required_only_in_vm_and_parse_their_source_types(self):
        names = {'DppEnabled', 'DppTheta', 'DppMaxSelectedRank'}
        self.assertTrue(names <= source.REQUIRED['vm-ranker/params.rs'])
        self.assertTrue(names.isdisjoint(source.REQUIRED['home-mixer/params/param.rs']))
        values = source.extract_parameters(self.fixture('vm-ranker/params.rs'), 'vm-ranker/params.rs')
        self.assertIs(values['DppEnabled']['default'], True)
        self.assertEqual(values['DppTheta']['default'], .65)
        self.assertEqual(values['DppMaxSelectedRank']['default'], 150)

    def test_each_dpp_parameter_must_be_present_exactly_once(self):
        path = 'vm-ranker/params.rs'
        content = self.fixture(path)
        for name in ('DppEnabled', 'DppTheta', 'DppMaxSelectedRank'):
            declaration = next(line for line in content.splitlines() if line.startswith(f'param!({name},'))
            with self.subTest(name=name, invalid='missing'):
                with self.assertRaisesRegex(ValueError, name):
                    source.extract_parameters(content.replace(declaration, ''), path)
            with self.subTest(name=name, invalid='duplicate'):
                with self.assertRaisesRegex(ValueError, 'duplicate parameter ' + name):
                    source.extract_parameters(content + '\n' + declaration, path)

    def test_dpp_max_selected_rank_rejects_invalid_unsigned_defaults(self):
        path = 'vm-ranker/params.rs'
        for literal in ('-1', '4294967296'):
            with self.subTest(literal=literal):
                content = self.fixture(path).replace('"switch_DppMaxSelectedRank", 150',
                                                    f'"switch_DppMaxSelectedRank", {literal}')
                with self.assertRaisesRegex(ValueError, 'u32 default'):
                    source.extract_parameters(content, path)

    def test_startup_dpp_gate_is_extracted_separately_with_source_line(self):
        content = '/* header\ncomment */\n#[arg(long, default_value_t = false)]\npub dpp_enabled: bool,\n'
        record = source.extract_dpp_startup_default(content)
        self.assertIs(record['default'], False)
        self.assertEqual(record['argument'], '--dpp-enabled')
        self.assertEqual(record['line'], 3)

    def test_startup_dpp_gate_requires_one_uncommented_literal_default(self):
        declaration = '#[arg(long, default_value_t = false)]\npub dpp_enabled: bool,\n'
        for invalid in ('// ' + declaration.replace('\n', '\n// '),
                        declaration.replace('false', 'runtime_default()'),
                        declaration.replace('default_value_t', 'default_value')):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, 'missing or unsupported'):
                    source.extract_dpp_startup_default(invalid)
        with self.assertRaisesRegex(ValueError, 'duplicate startup argument'):
            source.extract_dpp_startup_default(declaration + declaration)

    def test_startup_dpp_gate_ignores_string_examples_and_keeps_real_field_position(self):
        declaration = '#[arg(long, default_value_t = false)]\npub dpp_enabled: bool,\n'
        examples = [
            'const EXAMPLE: &str = "' + declaration + '";\n',
            'const EXAMPLE: &str = r#"\n' + declaration + '"#;\n',
            'const EXAMPLE: &str = r##"an inner " quote and /* marker\n' + declaration + '"##;\n',
            'const EXAMPLE: &[u8] = br#"\n' + declaration + '"#;\n',
        ]
        real = declaration.replace('false', 'true')
        for example in examples:
            with self.subTest(example=example):
                with self.assertRaisesRegex(ValueError, 'missing or unsupported'):
                    source.extract_dpp_startup_default(example)
                record = source.extract_dpp_startup_default(example + real)
                self.assertIs(record['default'], True)
                self.assertEqual(record['line'], example.count('\n') + 1)
                with self.assertRaisesRegex(ValueError, 'duplicate startup argument'):
                    source.extract_dpp_startup_default(example + real + real)

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
        (self.root / 'vm-ranker/args.rs').write_text(
            '#[arg(long, default_value_t = false)]\npub dpp_enabled: bool,\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Synthetic fixture')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def test_records_committed_hashes_and_configuration(self):
        result = source.audit(self.root)
        self.assertEqual(result['commit'], self.git('rev-parse', 'HEAD'))
        self.assertEqual(result['files'][0]['sha256'], hashlib.sha256(b'synthetic audit fixture\n').hexdigest())
        self.assertEqual(result['constants']['home-mixer/params/config.rs']['MAX_POST_AGE']['value'], 172800)
        self.assertIs(result['parameters']['vm-ranker/params.rs']['DppEnabled']['default'], True)
        self.assertIs(result['startup_arguments']['vm-ranker/args.rs']['dpp_enabled']['default'], False)
        self.assertIn('effective production settings are unknown', result['interpretation'])
        bound_paths = {record['path'] for record in result['files']}
        self.assertEqual(bound_paths, set(source.FILES))
        self.assertIn('home-mixer/sources/thunder_source.rs', bound_paths)
        self.assertIn('home-mixer/selectors/top_k_score_selector.rs', bound_paths)
        self.assertIn('vm-ranker/scoring/dpp_model.rs', bound_paths)

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
