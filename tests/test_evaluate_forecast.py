import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import evaluate_forecast as evaluator


def at(seconds):
    return (datetime(2026, 10, 8, tzinfo=timezone.utc) + timedelta(seconds=seconds)).isoformat()


def frozen_fixture():
    snapshot = {'post_url': 'https://x.com/example/status/123',
                'published_at': at(0), 'source': 'public_views', 'metric': 'views',
                'numeric_observations': [{'observed_at': at(60), 'source': 'public_views', 'views': 6},
                                         {'observed_at': at(120), 'source': 'public_views', 'views': 14}],
                'initial_observation': {'observed_at': at(30), 'views': None}}
    result = {'contract_version': 'rise-prospective-exposure-1', 'forecast_id': 'synthetic-123-60m',
              'status': 'frozen_before_target', 'post_url': snapshot['post_url'], 'post_id': '123',
              'version': 'synthetic-v1', 'source': 'public_views', 'metric': 'views',
              'published_at': at(0), 'origin_at': at(120), 'input_cutoff_at': at(120),
              'generated_at': at(180), 'frozen_at': at(181), 'target_at': at(3600),
              'n_numeric_points': 2, 'input_snapshot': snapshot,
              'predictions': {'constant': {'point_prediction': 14.0},
                              'recent_rate': {'point_prediction': 27.5},
                              'untrained': {'point_prediction': None}},
              'observation_policy': {'early_tolerance_seconds': 0, 'late_tolerance_seconds': 300,
                                     'accepted_observed_at_start': at(3600),
                                     'accepted_observed_at_end': at(3900)},
              'outcome': {'actual': None, 'observed_at': None, 'errors': None}}
    rehash_snapshot(result)
    return result


def rehash_snapshot(frozen):
    raw = json.dumps(frozen['input_snapshot'], sort_keys=True, separators=(',', ':'),
                     ensure_ascii=False, allow_nan=False).encode()
    frozen['input_snapshot_sha256'] = hashlib.sha256(raw).hexdigest()


def sealed(frozen):
    raw = json.dumps(frozen, ensure_ascii=False).encode()
    return raw, hashlib.sha256(raw).hexdigest()


def row(value=20, when=3600, start=None):
    return {'actual': value, 'observed_at': at(when),
            'observation_started_at': at(when if start is None else start),
            'observation_completed_at': at(when)}


def actual_fixture(rows=None):
    f = frozen_fixture()
    return {'contract_version': 'rise-prospective-actual-1',
            **{key: f[key] for key in evaluator.IDENTITY},
            'first_successful_numeric_read_at_or_after_target': True,
            'observations': [row()] if rows is None else rows}


def evaluate(frozen=None, actual=None):
    raw, digest = sealed(frozen or frozen_fixture())
    return evaluator.evaluate_forecast(raw, actual or actual_fixture(), digest)


class ProspectiveEvaluationTests(unittest.TestCase):
    def test_exact_target_errors_and_single_target_scope(self):
        result = evaluate()
        self.assertEqual(result['status'], 'exact_target_observation')
        self.assertTrue(result['eligible_primary_comparison'])
        self.assertEqual(result['exact_target_actual'], 20)
        self.assertEqual(result['actual_age_seconds'], 3600)
        self.assertEqual(result['models']['constant']['errors'],
                         {'signed_error': -6.0, 'absolute_error': 6.0,
                          'squared_error': 36.0, 'smape_percent': 1200 / 34})
        self.assertEqual(result['models']['recent_rate']['errors']['signed_error'], 7.5)
        self.assertIsNone(result['models']['untrained']['errors'])
        self.assertEqual(result['n_primary_observations'], 1)
        self.assertIsNone(result['statistical_superiority'])
        self.assertIsNone(result['future_verification'])
        self.assertFalse(result['training_performed'])

    def test_first_numeric_target_read_sorted_without_cherry_picking(self):
        actual = actual_fixture([row(14, 3500), row(None, 3600), row(28, 3620), row(20, 3610)])
        result = evaluate(actual=actual)
        self.assertEqual(result['selected_observation']['actual'], 20)
        self.assertEqual(result['selected_observation']['observed_at'], at(3610))
        self.assertEqual(len(result['observations']), 4)
        self.assertIsNone(result['observations'][1]['actual'])
        self.assertIn('not independently verified', result['selection_evidence'])

    def test_declaration_required_only_for_target_window_scoring(self):
        actual = actual_fixture()
        actual.pop('first_successful_numeric_read_at_or_after_target')
        with self.assertRaisesRegex(ValueError, 'declaration'):
            evaluate(actual=actual)
        actual['observation_history_complete_since_target'] = True
        self.assertTrue(evaluate(actual=actual)['target_window_eligible'])
        actual['observation_history_complete_since_target'] = 1
        with self.assertRaisesRegex(ValueError, 'boolean'):
            evaluate(actual=actual)

    def test_late_proxy_at_budget_keeps_real_age_and_frozen_prediction(self):
        result = evaluate(actual=actual_fixture([row(20, 3900, 3899)]))
        self.assertEqual(result['status'], 'delayed_proxy')
        self.assertEqual(result['actual_age_seconds'], 3900)
        self.assertEqual(result['lateness_seconds'], 300)
        self.assertIsNone(result['exact_target_actual'])
        self.assertEqual(result['models']['recent_rate']['point_prediction'], 27.5)
        self.assertTrue(result['eligible_primary_comparison'])

    def test_early_missing_outside_and_straddling_never_primary(self):
        for rows, status in [([row(20, 3599)], 'early'), ([row(None)], 'pending'),
                             ([], 'pending'), ([row(20, 3900.001)], 'outside_window'),
                             ([row(20, 3601, 3599)], 'early_or_straddling_capture')]:
            with self.subTest(status=status):
                result = evaluate(actual=actual_fixture(rows))
                self.assertEqual(result['status'], status)
                self.assertFalse(result['eligible_primary_comparison'])
                self.assertEqual(result['n_primary_observations'], 0)
                self.assertIsNone(result['exact_target_actual'])
                if rows and rows[0]['actual'] is not None:
                    self.assertIsNotNone(result['models']['constant']['errors'])

    def test_revision_retains_zero_and_all_diagnostic_errors(self):
        result = evaluate(actual=actual_fixture([row(0, 3601)]))
        self.assertEqual(result['selected_observation']['actual'], 0)
        self.assertTrue(result['apparent_revision'])
        self.assertTrue(result['target_window_eligible'])
        self.assertFalse(result['eligible_primary_comparison'])
        self.assertEqual(result['models']['constant']['errors']['signed_error'], 14)
        self.assertEqual(result['models']['recent_rate']['errors']['signed_error'], 27.5)
        self.assertEqual(result['models']['constant']['errors']['smape_percent'], 200)
        self.assertEqual(evaluator.errors(0, 0)['smape_percent'], 0)

    def test_invalid_actuals_and_predictions_are_not_unknown_zero(self):
        for value in (-1, True, False, 1.5, 2.0, float('nan'), float('inf'), '20'):
            with self.subTest(actual=value):
                with self.assertRaises(ValueError):
                    evaluate(actual=actual_fixture([row(value)]))
        for value in (-1, True, float('nan'), float('inf')):
            with self.subTest(prediction=value):
                f = frozen_fixture()
                f['predictions']['constant']['point_prediction'] = value
                with self.assertRaises(ValueError):
                    evaluate(frozen=f)
        self.assertEqual(evaluate()['models']['recent_rate']['point_prediction'], 27.5)

    def test_identity_mismatch_and_conflicting_duplicate_reads_rejected(self):
        for key, value in [('post_url', 'https://x.com/example/status/456'), ('version', 'edited-v2'),
                           ('source', 'owner_impressions'), ('metric', 'impressions'), ('forecast_id', 'other')]:
            with self.subTest(key=key):
                actual = actual_fixture()
                actual[key] = value
                with self.assertRaises(ValueError):
                    evaluate(actual=actual)
        actual = actual_fixture([row(20), row(21)])
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            evaluate(actual=actual)
        actual = actual_fixture()
        actual['observations'][0]['source'] = 'owner_impressions'
        with self.assertRaises(ValueError):
            evaluate(actual=actual)

    def test_frozen_input_availability_and_time_order_guards(self):
        for key, value in [('frozen_at', at(3600)), ('generated_at', at(182)),
                           ('input_cutoff_at', at(119)), ('target_at', '2026-10-08T01:00:00')]:
            with self.subTest(key=key):
                f = frozen_fixture()
                f[key] = value
                with self.assertRaises(ValueError):
                    evaluate(frozen=f)
        f = frozen_fixture()
        f['input_snapshot']['numeric_observations'][-1]['available_at'] = at(120.001)
        rehash_snapshot(f)
        with self.assertRaisesRegex(ValueError, 'cutoff'):
            evaluate(frozen=f)
        f['input_snapshot']['numeric_observations'][-1]['available_at'] = at(120)
        rehash_snapshot(f)
        self.assertTrue(evaluate(frozen=f)['target_window_eligible'])

    def test_predeclared_late_budget_integer_boundaries(self):
        for budget in (None, -1, 301, True, 1.5):
            with self.subTest(budget=budget):
                f = frozen_fixture()
                f['observation_policy']['late_tolerance_seconds'] = budget
                with self.assertRaisesRegex(ValueError, 'budget'):
                    evaluate(frozen=f)
        f = frozen_fixture()
        f['observation_policy']['late_tolerance_seconds'] = 0
        f['observation_policy']['accepted_observed_at_end'] = at(3600)
        self.assertTrue(evaluate(frozen=f)['eligible_primary_comparison'])
        self.assertFalse(evaluate(frozen=f, actual=actual_fixture([row(20, 3600.001)]))['eligible_primary_comparison'])

    def test_file_and_input_hashes_detect_tampering(self):
        frozen = frozen_fixture()
        original_raw, original_digest = sealed(frozen)
        for change in ('prediction', 'budget', 'input'):
            with self.subTest(change=change):
                changed = copy.deepcopy(frozen)
                if change == 'prediction': changed['predictions']['constant']['point_prediction'] = 20
                elif change == 'budget': changed['observation_policy']['late_tolerance_seconds'] = 299
                else: changed['input_snapshot']['numeric_observations'][0]['views'] = 7
                raw, _ = sealed(changed)
                with self.assertRaisesRegex(ValueError, 'forecast SHA256'):
                    evaluator.evaluate_forecast(raw, actual_fixture(), original_digest)
        frozen['input_snapshot']['numeric_observations'][0]['views'] = 7
        with self.assertRaisesRegex(ValueError, 'snapshot SHA256'):
            evaluate(frozen=frozen)
        self.assertEqual(hashlib.sha256(original_raw).hexdigest(), original_digest)

    def test_late_actual_generation_does_not_fake_late_capture(self):
        actual = actual_fixture([row(20, 3601)])
        actual['generated_at'] = at(9000)
        actual['observations'][0]['available_at'] = at(9000)
        self.assertEqual(evaluate(actual=actual)['status'], 'delayed_proxy')
        actual['observations'][0]['available_at'] = at(3600)
        with self.assertRaisesRegex(ValueError, 'completion'):
            evaluate(actual=actual)

    def test_cli_never_overwrites_inputs_or_an_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            forecast, actual, output = (directory / name for name in ('forecast.json', 'actual.json', 'evaluation.json'))
            raw, digest = sealed(frozen_fixture())
            forecast.write_bytes(raw)
            actual.write_text(json.dumps(actual_fixture()))
            arguments = [str(forecast), str(actual), '--forecast-sha256', digest]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(evaluator.main(arguments + ['--output', str(forecast)]), 2)
                self.assertEqual(evaluator.main(arguments + ['--output', str(actual)]), 2)
                self.assertEqual(evaluator.main(arguments + ['--output', str(output)]), 0)
                self.assertEqual(evaluator.main(arguments + ['--output', str(output)]), 2)
            self.assertEqual(forecast.read_bytes(), raw)
            self.assertEqual(json.loads(output.read_text())['n_primary_observations'], 1)

    def test_duplicate_json_keys_and_nonfinite_constants_rejected(self):
        for raw in (b'{"actual": 1, "actual": 2}', b'{"actual": NaN}', b'{"actual": Infinity}'):
            with self.assertRaises(ValueError):
                evaluator.read_json(raw)

    def test_timestamp_precision_and_offset_validation(self):
        for timestamp in ('2026-10-08T01:00:00+00:99', '2026-10-08T01:00:00+24:00',
                          '2026-10-08T01:00:00.1234567Z', '2026-10-08T01:00Z'):
            with self.subTest(timestamp=timestamp):
                with self.assertRaises(ValueError):
                    evaluator.time(timestamp, 'synthetic timestamp')
        self.assertEqual(evaluator.time('2026-10-08T09:00:00+08:00', 'offset'),
                         evaluator.time('2026-10-08T01:00:00Z', 'UTC'))

    def test_conflicting_capture_metadata_cannot_change_result_by_input_order(self):
        after = row(20, 3601, 3600)
        straddling = row(20, 3601, 3599)
        for records in ([after, straddling], [straddling, after]):
            with self.assertRaisesRegex(ValueError, 'capture metadata'):
                evaluate(actual=actual_fixture(records))
        result = evaluate(actual=actual_fixture([after, copy.deepcopy(after)]))
        self.assertEqual(len(result['observations']), 1)
        self.assertTrue(result['eligible_primary_comparison'])


if __name__ == '__main__':
    unittest.main()
