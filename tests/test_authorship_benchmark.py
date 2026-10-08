"""Leakage, grouping, immutable-plan and metric checks; no model fitting."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("authorship_benchmark", Path(__file__).parents[1] / "scripts" / "authorship_benchmark.py")
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class AuthorshipBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def source(self, rows=None, name="open_qa.jsonl"):
        if rows is None:
            rows = [{"question": f"问题{i}", "human_answers": [f"人工答复编号{i}。"],
                     "chatgpt_answers": [f"模型答复编号{i}。"]} for i in range(40)]
        path = self.root / name
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        return path

    def provenance(self, source):
        revision = "a" * 40
        sha = benchmark.file_sha(source)
        size = source.stat().st_size
        timestamp = benchmark.clock()
        card = self.root / 'dataset-card.md'
        card.write_text('---\nlicense: cc-by-sa-4.0\n---\nSynthetic provenance fixture only\n')
        prefix = f"https://huggingface.co/datasets/{benchmark.DATASET}/resolve/{revision}"
        data = {"schema": "rise-hc3-acquisition-v1", "recorded_at": timestamp,
                "dataset": benchmark.DATASET, "subset": "open_qa", "revision": revision,
                "dataset_license": "CC-BY-SA-4.0", "upstream_license": "MIT",
                "source_sha256": sha, "source_bytes": size,
                "http": {"source": {"url": f"{prefix}/open_qa.jsonl", "started_at": timestamp, "completed_at": timestamp,
                                    "http_status": 200, "sha256": sha, "bytes_read": size},
                         "card": {"url": f"{prefix}/README.md", "http_status": 200,
                                  "sha256": benchmark.file_sha(card), "bytes_read": card.stat().st_size}}}
        path = self.root / "acquisition.json"
        path.write_text(json.dumps(data))
        return path

    def test_groups_stable_under_source_order_and_answers_do_not_cross_splits(self):
        rows = [{"question": f"问题{i}", "human_answers": [f"人工答复{i}"],
                 "chatgpt_answers": [f"机器答复{i}"]} for i in range(40)]
        first, coverage, manifest = benchmark.build_dataset(self.source(rows))
        _, reverse_coverage, reverse_manifest = benchmark.build_dataset(self.source(list(reversed(rows)), "reverse.jsonl"))
        self.assertEqual(manifest, reverse_manifest)
        self.assertEqual(coverage, reverse_coverage)
        for a in ("train", "validation", "test"):
            for b in ("train", "validation", "test"):
                if a == b: continue
                self.assertFalse({r['group_id'] for r in first if r['split'] == a} & {r['group_id'] for r in first if r['split'] == b})
                self.assertFalse({r['answer_sha256'] for r in first if r['split'] == a} & {r['answer_sha256'] for r in first if r['split'] == b})
        self.assertFalse(coverage['time_holdout'])
        self.assertEqual(coverage['source_creation_time'], 'unknown')

    def test_transitive_connections_survive_conflicting_answer_exclusion(self):
        rows = [{"question": f"问题{i}", "human_answers": [f"人工答复{i}"],
                 "chatgpt_answers": [f"机器答复{i}"]} for i in range(40)]
        rows[0]['human_answers'].append('共享一')
        rows[1]['human_answers'].append('共享一')
        rows[1]['chatgpt_answers'].append('共享二')
        rows[2]['human_answers'].append('共享二')
        result, coverage, _ = benchmark.build_dataset(self.source(rows))
        group_ids = {r['group_id'] for r in result if r['text'] in ['人工答复0', '人工答复1', '人工答复2']}
        self.assertEqual(len(group_ids), 1)
        self.assertFalse(any(r['text'] == '共享二' for r in result))
        self.assertEqual(coverage['counts']['conflicting_label_unique_answers_excluded'], 1)
        self.assertEqual(coverage['counts']['same_label_duplicate_occurrences_excluded'], 1)

    def test_normalization_used_for_dedupe_and_feature_hashing(self):
        self.assertEqual(benchmark.normalize('ＡＢ\n 中文\t答复'), 'ab 中文 答复')
        self.assertEqual(benchmark.feature_items('ＡＢ\n 中文\t答复'), benchmark.feature_items('ab 中文 答复'))
        features = benchmark.feature_items('中国问题答复')
        self.assertTrue(all(0 <= index < 16384 for index, _ in features))
        self.assertAlmostEqual(sum(v*v for _, v in features), 1.0)
        self.assertEqual(benchmark.feature_items('单'), [])
        with self.assertRaises(ValueError): benchmark.feature_items({'answer': '中文', 'label': 1})

    def test_schema_rejects_unexpected_metadata_inputs(self):
        source = self.source([{'question': '一', 'human_answers': ['二'], 'chatgpt_answers': ['三'], 'model': 'leaky'}])
        with self.assertRaisesRegex(ValueError, 'schema'): benchmark.build_dataset(source)

    def test_missing_answers_are_excluded_without_string_cast_or_label_fabrication(self):
        rows = [{'question': f'问题{i}', 'human_answers':[f'人工{i}'],
                 'chatgpt_answers':[f'机器{i}']} for i in range(40)]
        rows[0]['human_answers'].append(None)
        rows[1]['human_answers'].append('  ')
        retained, coverage, _ = benchmark.build_dataset(self.source(rows))
        self.assertEqual(len(retained), 80)
        self.assertEqual(coverage['counts']['missing_answer_occurrences_excluded'], 1)
        self.assertEqual(coverage['counts']['empty_answer_occurrences_excluded'], 1)
        self.assertEqual(coverage['counts']['source_answer_occurrences'], 82)
        self.assertFalse(any(r['text'] == 'none' for r in retained))

    def test_plan_never_fits_and_verifies_all_fingerprints(self):
        source = self.source()
        provenance = self.provenance(source)
        result = benchmark.plan(source, provenance, self.root/'run')
        self.assertFalse(result['training_performed'])
        self.assertFalse((self.root/'run'/'training-started.json').exists())
        frozen, _ = benchmark.verify_plan(result['plan'])
        self.assertEqual(frozen['config']['parameter_count'], 16385)
        self.assertLessEqual(frozen['config']['max_epochs'], 12)
        self.assertEqual((self.root/'run').stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.root/'run'/'plan.json').stat().st_mode & 0o777, 0o600)
        source.write_text(source.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'input changed'): benchmark.verify_plan(result['plan'])

    def test_changed_plan_manifest_provenance_and_code_are_rejected(self):
        for target in ('plan', 'manifest', 'provenance', 'code'):
            with self.subTest(target=target):
                source = self.source(name=f'{target}.jsonl')
                provenance = self.provenance(source)
                result = benchmark.plan(source, provenance, self.root/target)
                path = Path(result['plan'])
                if target == 'plan':
                    data = json.loads(path.read_text()); data['config']['max_epochs'] = 13
                    path.write_text(json.dumps(data))
                elif target == 'manifest':
                    (path.parent/'split-manifest.private.json').write_text('[]')
                elif target == 'provenance': provenance.write_text('{}')
                else:
                    data = json.loads(path.read_text()); data['code_sha256'] = '0'*64
                    path.write_text(json.dumps(data))
                    seal = json.loads((path.parent/'plan-seal.json').read_text())
                    seal['plan_sha256'] = benchmark.file_sha(path)
                    (path.parent/'plan-seal.json').write_text(json.dumps(seal))
                with self.assertRaises(ValueError): benchmark.verify_plan(path)

    def test_acquisition_provenance_requires_fixed_official_origin(self):
        source = self.source(); provenance = self.provenance(source)
        data = json.loads(provenance.read_text())
        data['http']['source']['url'] = 'https://example.org/open_qa.jsonl'
        provenance.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'official'): benchmark.validate_provenance(source, provenance)

    def test_acquisition_license_card_and_utc_timestamps_are_verified(self):
        source = self.source()
        for mutation in ('license', 'schema', 'missing_time', 'time_order', 'card'):
            provenance = self.provenance(source)
            data = json.loads(provenance.read_text())
            if mutation == 'license': data['upstream_license'] = 'CC0'
            elif mutation == 'schema': data['schema'] = 'fiction'
            elif mutation == 'missing_time': del data['http']['source']['started_at']
            elif mutation == 'time_order': data['http']['source']['started_at'] = '2100-01-01T00:00:00Z'
            else: (self.root/'dataset-card.md').write_text('license: MIT')
            provenance.write_text(json.dumps(data))
            with self.assertRaises(ValueError): benchmark.validate_provenance(source, provenance)

    def test_outputs_are_exclusive_and_existing_consumption_cannot_repeat(self):
        marker = self.root/'training-started.json'
        benchmark.write_new(marker, {'test': 'fixture only; no model fitting'})
        with self.assertRaises(FileExistsError): benchmark.write_new(marker, {'test': 'again'})
        source = self.source(); provenance = self.provenance(source)
        result = benchmark.plan(source, provenance, self.root/'run')
        benchmark.write_new(self.root/'run'/'training-started.json', {'fixture': True})
        with self.assertRaises(FileExistsError): benchmark.train(result['plan'])
        with self.assertRaises(ValueError): benchmark.plan(source, provenance, self.root/'run')

    def test_copying_plan_cannot_reconsume_or_retest(self):
        source = self.source(); provenance = self.provenance(source)
        result = benchmark.plan(source, provenance, self.root/'original')
        shutil.copytree(self.root/'original', self.root/'copied')
        with self.assertRaisesRegex(ValueError, 'moved'): benchmark.verify_plan(self.root/'copied'/'plan.json')

    def test_length_normalization_uses_only_training_stats(self):
        training = [{'text':'中'*9}, {'text':'中'*99}]
        mean, scale = benchmark.length_stats(training)
        self.assertAlmostEqual(mean, (math.log(10)+math.log(100))/2)
        self.assertAlmostEqual(benchmark.length_items(training, mean, scale)[0][0], -1)
        self.assertAlmostEqual(benchmark.length_items([{'text':'中'*999}], mean, scale)[0][0], 3)
        self.assertEqual((mean, scale), benchmark.length_stats(training))

    def test_real_sparse_runtime_without_fitting(self):
        try:
            import torch
        except ImportError:
            self.skipTest('PyTorch not installed; no model fitting test')
        torch.set_num_threads(1)
        rows = [{'text':'中文答案'}, {'text':'另一个中文回答'}, {'text':'单'}]
        features = benchmark.sparse_tensor(torch, rows)
        self.assertEqual(features.layout, torch.sparse_coo)
        self.assertEqual(tuple(features.shape), (3, 16384))
        weights = torch.arange(16384, dtype=torch.float32).reshape(-1,1)/16384
        logits = torch.sparse.mm(features, weights).squeeze(1).tolist()
        for row, actual in zip(rows, logits):
            expected = sum(column/16384*value for column,value in benchmark.feature_items(row['text']))
            self.assertAlmostEqual(actual, expected, places=5)

    def test_metrics_and_auc_ties(self):
        result = benchmark.binary_metrics([0, 0, 1, 1], [0.1, 0.4, 0.6, 0.9])
        self.assertEqual(result['accuracy'], 1)
        self.assertEqual(result['f1_ai'], 1)
        self.assertEqual(result['auroc'], 1)
        self.assertAlmostEqual(result['brier'], .085)
        self.assertAlmostEqual(result['ece'], .25)
        self.assertEqual(benchmark.binary_metrics([0, 1], [.5, .5])['auroc'], .5)
        self.assertIsNone(benchmark.binary_metrics([1], [1.0])['auroc'])
        self.assertEqual(benchmark.binary_metrics([0, 1], [0, 1])['ece'], 0)
        self.assertEqual(benchmark.binary_metrics([0, 1], [0, 1])['reliability_bins'][9]['n'], 2)
        self.assertIsNone(benchmark.binary_metrics([], [])['accuracy'])
        with self.assertRaises(ValueError): benchmark.binary_metrics([1], [float('nan')])

    def test_positive_temperature_preserves_auc(self):
        logits = [-3.0, -1.0, 0.0, 0.0, 2.0, 4.0]
        labels = [0, 1, 0, 1, 1, 1]
        raw = benchmark.binary_metrics(labels, benchmark.probabilities(logits, 1.0))
        calibrated = benchmark.binary_metrics(labels, benchmark.probabilities(logits, 4.0))
        self.assertEqual(raw['auroc'], calibrated['auroc'])
        self.assertEqual(raw['brier_definition'], 'binary_positive_class_probability_MSE_range_0_1')
        for temperature in [0, -1, float('nan')]:
            with self.assertRaises(ValueError): benchmark.probabilities(logits, temperature)

    def test_temperature_selection_ties_prefer_earlier_epoch_and_one(self):
        candidates = [(benchmark.selection_key([0, 0], [0, 1], epoch, temperature), epoch, temperature)
                      for epoch in (1, 2) for temperature in benchmark.CONFIG['temperature_candidates']]
        self.assertEqual(min(candidates)[1:], (1, 1.0))

    def test_subgroups_and_ood_refusal_never_invent_mixed_probability(self):
        state = {'schema': 'rise-hc3-binary-model-v1', 'config': copy.deepcopy(benchmark.CONFIG),
                 'feature_signature_sha256': benchmark.feature_signature(),
                 'model': {'weights': [0.0]*16384, 'bias': 0.0, 'temperature': 1.0}}
        for domain, text, task in [('x_short_post', '中文'*300, 'binary'),
                                   ('hc3_chinese_open_qa', '中文短答', 'binary'),
                                   ('hc3_chinese_open_qa', 'english answer '*40, 'binary'),
                                   ('hc3_chinese_open_qa', '中文'*300, 'three_class')]:
            result = benchmark.infer(state, text, domain, task)
            self.assertEqual(result['decision'], 'unknown')
            self.assertIsNone(result['binary_probabilities'])
            self.assertEqual(result['origin_probabilities'], {'human_written':None,'ai_generated':None,'mixed':None})
        result = benchmark.infer(state, '中文'*300, 'hc3_chinese_open_qa')
        self.assertEqual(sum(result['binary_probabilities'].values()), 1)
        self.assertIsNone(result['origin_probabilities']['mixed'])
        metrics = benchmark.subgroup_metrics([{'label':0,'text':'中文短答'},{'label':1,'text':'a'*300}], [.1,.9])
        self.assertEqual(metrics['contains_cjk']['n'], 1)
        self.assertEqual(metrics['short_le280_codepoints']['n'], 1)
        self.assertIsNone(metrics['contains_cjk']['auroc'])

    def test_inference_rejects_nonfinite_or_non_numeric_model_state(self):
        original = {'schema': 'rise-hc3-binary-model-v1', 'config': copy.deepcopy(benchmark.CONFIG),
                    'feature_signature_sha256': benchmark.feature_signature(),
                    'model': {'weights': [0.0]*16384, 'bias': 0.0, 'temperature': 1.0}}
        for key, value in [('bias', float('inf')), ('bias', float('nan')),
                           ('bias', True), ('temperature', -1), ('temperature', '1')]:
            state = copy.deepcopy(original); state['model'][key] = value
            with self.assertRaises(ValueError): benchmark.infer(state, '中文'*300, 'hc3_chinese_open_qa')
        for value in ['0', True, float('nan')]:
            state = copy.deepcopy(original); state['model']['weights'][0] = value
            with self.assertRaises(ValueError): benchmark.infer(state, '中文'*300, 'hc3_chinese_open_qa')
        state = copy.deepcopy(original); state['feature_signature_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'featurizer'): benchmark.infer(state, '中文'*300, 'hc3_chinese_open_qa')


if __name__ == '__main__':
    unittest.main()
