import contextlib
import copy
import io
import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts import authorship


def example():
    """Entire fixture is synthetic, not a model execution or real-post evidence."""
    return {'contract_version': authorship.CONTRACT,
            'post': {'platform': 'x', 'post_id': '123', 'version': 'v1',
                     'post_url': 'https://x.com/example/status/123',
                     'published_at': '2026-10-08T00:00:00Z', 'captured_at': '2026-10-08T00:01:00Z'},
            'prediction_at': '2026-10-08T00:03:00Z',
            'external_prediction': {
                'model_id': 'synthetic-model', 'model_version': 'synthetic-v1',
                'generated_at': '2026-10-08T00:02:00Z', 'available_at': '2026-10-08T00:02:01Z',
                'probabilities': {'human_written': 0.6, 'ai_generated': 0.2, 'mixed': 0.2},
                'input_features': [{'name': 'body', 'kind': 'text', 'version': 'v1',
                                    'captured_at': '2026-10-08T00:01:00Z', 'available_at': '2026-10-08T00:01:01Z'}],
                'provenance': {
                    'strategy': 'chronological', 'training_cutoff': '2026-10-07T20:00:00Z',
                    'trained_at': '2026-10-07T21:00:00Z',
                    'training_groups': [{'platform': 'x', 'post_id': '122',
                                         'published_at': '2026-10-07T10:00:00Z',
                                         'latest_input_available_at': '2026-10-07T11:00:00Z',
                                         'label_available_at': '2026-10-07T12:00:00Z'}]}}}


def label_example():
    return {'contract_version': authorship.LABEL_CONTRACT,
            'scope': 'text.body', 'label_policy': 'synthetic-body-origin-v1',
            'post': copy.deepcopy(example()['post']), 'content_origin': 'human_written',
            'label_available_at': '2026-10-08T01:00:00Z',
            'evidence': [{'method': 'documented_creation', 'reference': 'synthetic/private-writing-record',
                          'available_at': '2026-10-08T00:59:00Z'}]}


class AuthorshipTests(unittest.TestCase):
    def test_missing_model_returns_unknown_not_fake_probability(self):
        record = example()
        record.pop('external_prediction')
        prediction = authorship.predict(record)
        self.assertEqual(prediction['estimated_content_origin'], 'unknown')
        self.assertIsNone(prediction['probabilities'])
        self.assertIsNone(prediction['verified_content_origin'])
        features = authorship.auxiliary_features(record)['features']
        self.assertTrue(features['authorship_missing'])
        self.assertIsNone(features['authorship_p_human_written'])

    def test_supplied_probability_remains_uncalibrated_estimate(self):
        prediction = authorship.predict(example())
        self.assertEqual(prediction['estimated_content_origin'], 'human_written')
        self.assertEqual(prediction['status'], 'unverified_external_model_estimate')
        self.assertEqual(prediction['uncertainty']['calibration'], 'not_verified')
        self.assertIsNone(prediction['uncertainty']['probability_interval'])
        self.assertIsNone(prediction['verified_content_origin'])
        self.assertAlmostEqual(prediction['uncertainty']['normalized_entropy'],
                               -sum(p * math.log(p) for p in (0.6, 0.2, 0.2)) / math.log(3))

    def test_soft_features_have_no_true_or_hard_label(self):
        output = authorship.auxiliary_features(example())
        self.assertEqual(output['features']['authorship_p_human_written'], 0.6)
        self.assertNotIn('estimated_content_origin', output['features'])
        self.assertNotIn('label', output['features'])
        self.assertFalse(output['verified_label_included'])
        self.assertEqual(output['provenance']['training_group_count'], 1)
        self.assertNotIn('training_groups', output['provenance'])
        self.assertNotIn('authorship_p_unknown', output['features'])
        self.assertFalse(output['provenance']['canonical_lineage_verified'])
        self.assertFalse(output['provenance']['comment_lineage_verified'])
        self.assertFalse(output['provenance']['duplicate_text_grouping_verified'])

    def test_label_scope_and_policy_are_required_and_text_specific(self):
        for key, value in [('scope', None), ('scope', 'account'), ('label_policy', None),
                           ('label_policy', ''), ('label_policy', '  ')]:
            label = label_example()
            if value is None:
                label.pop(key)
            else:
                label[key] = value
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError):
                    authorship.validate_label(label)

    def test_unknown_is_abstention_not_a_fourth_probability_class(self):
        record = example()
        record['external_prediction']['probabilities'] = dict(human_written=1 / 3, ai_generated=1 / 3, mixed=1 / 3)
        prediction = authorship.predict(record)
        self.assertEqual(prediction['estimated_content_origin'], 'unknown')
        self.assertAlmostEqual(prediction['uncertainty']['normalized_entropy'], 1)
        record['external_prediction']['probabilities']['unknown'] = 0
        with self.assertRaises(ValueError):
            authorship.predict(record)

    def test_invalid_probabilities_are_rejected_without_normalizing(self):
        for value in (True, float('nan'), float('inf'), -0.1, 1.1, '0.6', 0.5):
            with self.subTest(value=value):
                record = example()
                record['external_prediction']['probabilities']['human_written'] = value
                with self.assertRaises(ValueError):
                    authorship.predict(record)
        record = example()
        record['external_prediction']['probabilities'].pop('mixed')
        with self.assertRaises(ValueError):
            authorship.predict(record)

    def test_no_publishing_control_or_truth_label_in_input_contract(self):
        for name in ('publishing_control', 'truth_label', 'target'):
            record = example()
            record[name] = 'manual'
            with self.assertRaises(ValueError):
                authorship.predict(record)

    def test_future_prediction_and_backfilled_inputs_rejected(self):
        changes = [('generated_at', '2026-10-08T00:04:00Z'),
                   ('available_at', '2026-10-08T00:04:00Z')]
        for key, value in changes:
            record = example()
            record['external_prediction'][key] = value
            with self.assertRaises(ValueError):
                authorship.predict(record)
        for key in ('captured_at', 'available_at'):
            record = example()
            record['external_prediction']['input_features'][0][key] = '2026-10-08T00:04:00Z'
            with self.assertRaises(ValueError):
                authorship.predict(record)

    def test_late_capture_cannot_claim_earlier_availability(self):
        record = example()
        feature = record['external_prediction']['input_features'][0]
        feature['captured_at'] = '2026-10-08T00:01:30Z'
        with self.assertRaises(ValueError):
            authorship.predict(record)

    def test_comment_latest_time_checked_not_only_capture_metadata(self):
        record = example()
        feature = record['external_prediction']['input_features'][0]
        feature.update(kind='comments', name='comment_context')
        with self.assertRaises(ValueError):
            authorship.predict(record)
        feature['latest_event_at'] = '2026-10-08T00:04:00Z'
        with self.assertRaises(ValueError):
            authorship.predict(record)
        feature['latest_event_at'] = '2026-10-08T00:00:30Z'
        self.assertEqual(authorship.auxiliary_features(record)['features']['authorship_p_human_written'], 0.6)

    def test_labels_cannot_enter_model_feature_descriptors(self):
        for change in ({'name': 'ground_truth'}, {'kind': 'label'}, {'label': 'human_written'}):
            record = example()
            record['external_prediction']['input_features'][0].update(change)
            with self.assertRaises(ValueError):
                authorship.auxiliary_features(record)

    def test_same_target_native_post_is_excluded_across_versions(self):
        record = example()
        record['post']['version'] = 'edited-v2'
        record['external_prediction']['input_features'][0]['version'] = 'edited-v2'
        record['external_prediction']['provenance']['training_groups'][0]['post_id'] = '123'
        with self.assertRaises(ValueError):
            authorship.auxiliary_features(record)

    def test_in_sample_probabilities_cannot_be_auxiliary_features(self):
        record = example()
        record['external_prediction']['provenance']['strategy'] = 'in_sample'
        self.assertEqual(authorship.predict(record)['status'], 'unverified_external_model_estimate')
        with self.assertRaises(ValueError):
            authorship.auxiliary_features(record)

    def test_unknown_provenance_can_be_displayed_but_not_fused(self):
        record = example()
        record['external_prediction'].pop('provenance')
        self.assertIsNone(authorship.predict(record)['provenance'])
        with self.assertRaises(ValueError):
            authorship.auxiliary_features(record)

    def test_oof_requires_fold_and_does_not_override_chronology(self):
        record = example()
        provenance = record['external_prediction']['provenance']
        provenance['strategy'] = 'out_of_fold'
        with self.assertRaises(ValueError):
            authorship.auxiliary_features(record)
        provenance['fold_id'] = 'synthetic-fold-1'
        self.assertTrue(authorship.auxiliary_features(record)['provenance']['auxiliary_eligible'])
        provenance['training_cutoff'] = '2026-10-08T00:01:00Z'
        provenance['trained_at'] = '2026-10-08T00:01:30Z'
        group = provenance['training_groups'][0]
        group.update(published_at='2026-10-08T00:00:30Z',
                     latest_input_available_at='2026-10-08T00:00:40Z',
                     label_available_at='2026-10-08T00:00:50Z')
        with self.assertRaises(ValueError):
            authorship.auxiliary_features(record)

    def test_future_training_labels_and_inputs_rejected(self):
        for key in ('latest_input_available_at', 'label_available_at'):
            record = example()
            record['external_prediction']['provenance']['training_groups'][0][key] = '2026-10-08T00:00:00Z'
            with self.assertRaises(ValueError):
                authorship.auxiliary_features(record)

    def test_auxiliary_available_after_downstream_time_is_rejected(self):
        with self.assertRaises(ValueError):
            authorship.auxiliary_features(example(), '2026-10-08T00:01:00Z')

    def test_submillisecond_authorship_availability_cannot_leak(self):
        record = example()
        record['prediction_at'] = '2026-10-08T00:03:00.000900Z'
        record['external_prediction']['available_at'] = record['prediction_at']
        with self.assertRaises(ValueError):
            authorship.auxiliary_features(record, '2026-10-08T00:03:00.000100Z')
        output = authorship.auxiliary_features(record, record['prediction_at'])
        self.assertEqual(output['prediction_at'], record['prediction_at'])

    def test_submillisecond_label_availability_cannot_leak(self):
        label = label_example()
        label['label_available_at'] = '2026-10-08T01:00:00.000900Z'
        with self.assertRaises(ValueError):
            authorship.evaluate(example(), label, '2026-10-08T01:00:00.000100Z')
        result = authorship.evaluate(example(), label, label['label_available_at'])
        self.assertEqual(result['label']['label_available_at'], label['label_available_at'])

    def test_invalid_offsets_and_unrepresentable_precision_rejected(self):
        for value in ('2026-10-08T00:00:00+00:99', '2026-10-08T00:00:00-01:60',
                      '2026-10-08T00:00:00+24:00', '2026-10-08T00:00:00.000000001Z'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    authorship.time(value, 'synthetic timestamp')

    def test_external_label_evidence_not_linguistic_guess(self):
        for method in ('style_guess', 'blue_badge', 'external_detector'):
            label = label_example()
            label['evidence'][0]['method'] = method
            with self.assertRaises(ValueError):
                authorship.validate_label(label)
        label = label_example()
        label['evidence'] = []
        with self.assertRaises(ValueError):
            authorship.validate_label(label)

    def test_evaluation_waits_for_truth_and_uses_brier_logloss(self):
        with self.assertRaises(ValueError):
            authorship.evaluate(example(), label_example(), '2026-10-08T00:30:00Z')
        result = authorship.evaluate(example(), label_example(), '2026-10-08T01:01:00Z')
        self.assertAlmostEqual(result['brier'], 0.24)
        self.assertAlmostEqual(result['log_loss'], -math.log(0.6))
        self.assertFalse(result['label_used_as_feature'])
        self.assertNotIn('synthetic/private-writing-record', json.dumps(result))

    def test_unknown_truth_not_turned_into_classifier_training_label(self):
        label = label_example()
        label.update(content_origin='unknown', evidence=[])
        result = authorship.evaluate(example(), label, '2026-10-08T01:01:00Z')
        self.assertEqual(result['status'], 'unknown_label')
        self.assertIsNone(result['brier'])

    def test_zero_target_probability_does_not_export_infinity(self):
        record = example()
        record['external_prediction']['probabilities'] = dict(human_written=0, ai_generated=1, mixed=0)
        result = authorship.evaluate(record, label_example(), '2026-10-08T01:01:00Z')
        self.assertIsNone(result['log_loss'])
        self.assertIn('infinite', result['log_loss_reason'])
        json.dumps(result, allow_nan=False)

    def test_version_url_and_exact_times_are_checked(self):
        for change in ({'post_url': 'https://x.com/example/status/124'},
                       {'published_at': '2026-10-08T00:00:00'},
                       {'captured_at': '2026-10-08T00:04:00Z'}):
            record = example()
            record['post'].update(change)
            with self.assertRaises(ValueError):
                authorship.predict(record)
        record = example()
        record['external_prediction']['input_features'][0]['version'] = 'future-final-v2'
        with self.assertRaises(ValueError):
            authorship.predict(record)

    def test_label_version_mismatch_is_rejected(self):
        label = label_example()
        label['post']['version'] = 'another-version'
        with self.assertRaises(ValueError):
            authorship.evaluate(example(), label, '2026-10-08T01:01:00Z')

    def test_label_optional_permalink_is_not_part_of_native_identity(self):
        label = label_example()
        label['post'].pop('post_url')
        self.assertEqual(authorship.evaluate(example(), label, '2026-10-08T01:01:00Z')['status'],
                         'descriptive_evaluation')

    def test_cli_does_not_overwrite_input_or_publish_raw_training_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input.json'
            output = Path(directory) / 'estimate.json'
            original = json.dumps(example())
            source.write_text(original)
            self.assertEqual(authorship.main([str(source), '--output', str(output), '--auxiliary']), 0)
            self.assertEqual(source.read_text(), original)
            self.assertNotIn('training_groups', output.read_text())
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(authorship.main([str(source), '--output', str(source)]), 2)
            self.assertEqual(source.read_text(), original)


if __name__ == '__main__':
    unittest.main()
