import contextlib
import copy
import io
import json
import math
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from scripts import predict_heat


URL = 'https://x.com/example/status/123'
PUBLICATION = '2026-10-08T00:00:00Z'


def time_at(seconds):
    return (datetime(2026, 10, 8, tzinfo=timezone.utc) + timedelta(seconds=seconds)).isoformat()


def fixture(counts=(10, 20, 25), ages=(60, 120, 180)):
    return {'posts': [{'url': URL, 'published_at': PUBLICATION,
                      'observed_at': None, 'views': None}],
            'post_observations': [{'url': URL, 'observed_at': time_at(age), 'views': count}
                                  for age, count in zip(ages, counts)]}


class HeatPredictionTests(unittest.TestCase):
    def test_rolling_origin_uses_only_past_and_latest_holdout(self):
        report = predict_heat.build_report(fixture((10, 20, 25, 40), (60, 120, 180, 240)))
        rows = report['series'][0]['predictions']
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertTrue(all(point['observed_at'] < row['target_at']
                                for point in row['training_observations']))
            self.assertNotIn(row['target_at'], [point['observed_at'] for point in row['training_observations']])
        self.assertEqual([row['prediction'] for row in rows], [20, 30, 25, 30])
        self.assertEqual([row['latest_holdout'] for row in rows], [False, False, True, True])
        self.assertEqual(rows[1]['absolute_error'], 5)
        self.assertEqual(rows[1]['squared_error'], 25)
        self.assertEqual(rows[1]['forecast_horizon_seconds'], 60)

    def test_errors_and_smape_zero_denominator_are_defined(self):
        self.assertEqual(predict_heat.errors(0, 0)['smape_percent'], 0)
        self.assertEqual(predict_heat.errors(0, 10)['smape_percent'], 200)
        self.assertAlmostEqual(predict_heat.errors(10, 20)['smape_percent'], 200 / 3)
        rows = [{'url': URL, **predict_heat.errors(10, 20)},
                {'url': URL, **predict_heat.errors(10, 5)}]
        summary = predict_heat.summarize(rows)
        self.assertEqual(summary['mae'], 7.5)
        self.assertEqual(summary['bias_predicted_minus_actual'], 2.5)
        self.assertAlmostEqual(summary['rmse'], math.sqrt(62.5))
        self.assertEqual(summary['n_posts'], 1)
        self.assertIsNone(summary['confidence_interval'])

    def test_nonzero_first_observation_is_not_synthetic_zero(self):
        report = predict_heat.build_report(fixture())
        train = report['series'][0]['predictions'][0]['training_observations']
        self.assertEqual([row['value'] for row in train], [10, 20])
        self.assertEqual([row['age_seconds'] for row in train], [60, 120])

    def test_sources_are_separate_even_at_same_timestamp(self):
        data = fixture()
        data['analytics_observations'] = [{'url': URL, 'observed_at': time_at(age), 'impressions': count}
                                          for age, count in zip((60, 120, 180), (100, 110, 115))]
        report = predict_heat.build_report(data)
        self.assertEqual(len(report['series']), 2)
        predictions = {series['source']: series['predictions'][0]['prediction'] for series in report['series']}
        self.assertEqual(predictions, {'owner_impressions': 110, 'public_views': 20})

    def test_horizons_are_not_pooled_and_text_comments_absent(self):
        report = predict_heat.build_report(fixture((10, 20, 30, 40), (1, 2, 3, 3603)))
        summaries = [row for row in report['summaries'] if row['source'] == 'public_views' and row['model'] == 'constant']
        self.assertEqual({row['horizon_bucket'] for row in summaries}, {'0_to_15_minutes', '15_to_60_minutes'})
        self.assertEqual({row['n_predictions'] for row in summaries}, {1})
        self.assertFalse(report['text_features_included'])
        self.assertFalse(report['comment_features_included'])

    def test_official_popular_score_is_not_a_prediction(self):
        expected = 10 * (1 - math.exp(-math.log(2) / 8 * 24)) / (1 - math.exp(-math.log(2) / 8 * 0.5))
        self.assertAlmostEqual(predict_heat.popular_pool_score(10, 60), expected)
        self.assertAlmostEqual(predict_heat.popular_pool_score(10, 86400), 10)
        self.assertIsNone(predict_heat.popular_pool_score(10, 86401))
        self.assertEqual(predict_heat.popular_pool_score(0, 0), 0)
        score = predict_heat.build_report(fixture())['series'][0]['official_popular_pool_score']
        self.assertEqual(score['status'], 'candidate_pool_score')
        self.assertNotIn('actual', score)
        self.assertNotIn('error', score)

    def test_no_publication_time_skips_even_if_original_version_known(self):
        data = fixture()
        data['posts'][0]['original_published_at'] = data['posts'][0].pop('published_at')
        report = predict_heat.build_report(data)
        self.assertEqual(report['series'], [])
        self.assertEqual(report['status'], 'insufficient_data')
        self.assertTrue(any(row['reason'] == 'missing_published_at' for row in report['skipped_observations']))

    def test_null_skips_deduplicates_and_sorts_actual_ages(self):
        data = fixture((10, None, 25, 30), (60, 120, 180, 240))
        data['post_observations'].append(copy.deepcopy(data['post_observations'][0]))
        data['post_observations'].reverse()
        observations = predict_heat.build_report(data)['series'][0]['observations']
        self.assertEqual([row['value'] for row in observations], [10, 25, 30])
        self.assertEqual([row['age_seconds'] for row in observations], [60, 180, 240])

    def test_counter_revision_is_not_clamped_into_growth(self):
        report = predict_heat.build_report(fixture((10, 8, 20)))
        series = report['series'][0]
        self.assertEqual(series['status'], 'counter_revision')
        self.assertEqual(series['predictions'], [])
        self.assertEqual(series['future_forecasts'], [])
        self.assertEqual(series['counter_revisions'][0]['after'], 8)

    def test_conflicting_same_time_and_publication_are_rejected(self):
        for publication_conflict in (False, True):
            data = fixture()
            row = copy.deepcopy(data['post_observations'][0])
            if publication_conflict:
                row['published_at'] = time_at(1)
            else:
                row['views'] = 99
            data['post_observations'].append(row)
            with self.assertRaises(ValueError):
                predict_heat.build_report(data)

    def test_invalid_urls_times_and_counts_are_rejected(self):
        for key, value in [('url', 'https://x.com/example'),
                           ('url', 'https://x.com/example/status/123/analytics'),
                           ('url', 'http://x.com/example/status/123'),
                           ('observed_at', '2026-10-08T00:01:00'),
                           ('observed_at', True), ('observed_at', '2026-10-07T23:59:59Z'),
                           ('views', True), ('views', float('nan')), ('views', float('inf')),
                           ('views', 1.5), ('views', -1), ('views', '10')]:
            with self.subTest(key=key, value=value):
                data = fixture()
                data['post_observations'][0][key] = value
                with self.assertRaises(ValueError):
                    predict_heat.build_report(data)

    def test_invalid_non_target_counters_are_rejected(self):
        data = fixture()
        data['post_observations'][0]['likes'] = True
        with self.assertRaises(ValueError):
            predict_heat.build_report(data)

    def test_time_offsets_preserve_elapsed_seconds(self):
        data = fixture()
        data['post_observations'][1]['observed_at'] = '2026-10-08T08:02:00+08:00'
        row = predict_heat.build_report(data)['series'][0]['predictions'][0]
        self.assertEqual(row['forecast_horizon_seconds'], 60)

    def test_small_sample_torch_does_not_train(self):
        with mock.patch.object(predict_heat, 'fit_saturation', side_effect=AssertionError('no training')):
            report = predict_heat.build_report(fixture(), model='torch')
        self.assertEqual(report['status'], 'insufficient_data')
        self.assertEqual(report['series'][0]['torch_fit']['status'], 'insufficient_data')
        self.assertEqual(report['series'][0]['latest_holdout']['torch_status'], 'insufficient_data')

    def test_torch_mock_receives_only_past_and_matched_comparison(self):
        training_calls = []
        def fake_fit(train, epochs):
            training_calls.append(copy.deepcopy(train))
            return {'status': 'experimental_fit', 'parameters': {'b': 10, 'A': 100, 'tau_seconds': 1000}}
        report = predict_heat.build_report(fixture(tuple(range(7)), tuple(range(0, 2100, 300))),
                                          model='torch', fit_fn=fake_fit)
        self.assertEqual([len(train) for train in training_calls], [6, 7])
        torch_row = next(row for row in report['series'][0]['predictions'] if row['model'] == 'torch_saturation')
        self.assertEqual(torch_row['training_points'], 6)
        self.assertEqual(torch_row['training_observations'][-1]['age_seconds'], 1500)
        self.assertEqual(torch_row['target_age_seconds'], 1800)
        comparison = next(row for row in report['matched_origin_comparison'] if row['source'] == 'public_views')
        self.assertEqual({value['n_predictions'] for value in comparison['models'].values()}, {1})
        self.assertEqual(report['status'], 'evaluated_experimental')

    def test_short_duration_torch_is_not_fit_by_mock(self):
        def no_fit(*args, **kwargs):
            raise AssertionError('short duration must not fit')
        report = predict_heat.build_report(fixture(tuple(range(7)), tuple(range(7))),
                                          model='torch', fit_fn=no_fit)
        self.assertEqual(report['series'][0]['torch_fit']['status'], 'insufficient_time_span')

    def test_future_extrapolation_has_no_fake_actual_interval_or_error(self):
        forecast = predict_heat.build_report(fixture())['series'][0]['future_forecasts'][1]
        self.assertEqual(forecast['target_age_seconds'], 86400)
        self.assertIsNone(forecast['actual'])
        self.assertIsNone(forecast['error'])
        self.assertIsNone(forecast['prediction_interval'])
        self.assertEqual(forecast['status'], 'experimental_extrapolation')
        report = predict_heat.build_report(fixture(), forecast_hours=0.04)
        self.assertEqual(report['series'][0]['future_forecasts'], [])

    def test_model_target_and_epoch_validation(self):
        for arguments in ({'model': 'wrong'}, {'forecast_hours': True}, {'forecast_hours': float('nan')},
                          {'forecast_hours': 0}, {'epochs': True}, {'epochs': 0}, {'epochs': 10001}):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    predict_heat.build_report(fixture(), **arguments)

    def test_saturation_future_increment_is_anchored_to_real_counter(self):
        train = [{'observed_at': time_at(10), 'age_seconds': 10, 'value': 1000}]
        prediction = predict_heat.anchored_saturation_prediction({'b': 0, 'A': 1, 'tau_seconds': 100}, train, 20)
        self.assertGreaterEqual(prediction, 1000)
        self.assertLess(prediction, 1001)

    def test_cli_output_is_finite_public_data_and_input_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'metrics.json'
            output = Path(directory) / 'report.json'
            original = json.dumps(fixture())
            source.write_text(original)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(predict_heat.main(['--metrics', str(source), '--outputpath', str(output)]), 0)
            self.assertEqual(source.read_text(), original)
            self.assertEqual(json.loads(output.read_text())['status'], 'evaluated_baselines')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(predict_heat.main(['--metrics', str(source), '--outputpath', str(source)]), 2)
            self.assertEqual(source.read_text(), original)


if __name__ == '__main__':
    unittest.main()
