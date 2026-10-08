import contextlib
import copy
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import growth_dynamics


def at(seconds):
    return (datetime(2026, 10, 8, tzinfo=timezone.utc) + timedelta(seconds=seconds)).isoformat()


def observation(seconds, total, **extra):
    return {'observed_at': at(seconds), 'total': total, **extra}


class GrowthDynamicsTests(unittest.TestCase):
    def test_unequal_quadratic_intervals_have_correct_midpoint_acceleration_and_weighted_average(self):
        times = [0, 10, 30, 60]
        data = {'follower_observations': [observation(t, t*t + 3*t + 100) for t in times]}
        result = growth_dynamics.analyze(data)['follower_dynamics']
        self.assertEqual([x['interval_seconds'] for x in result['intervals']], [10, 20, 30])
        self.assertEqual([x['net_rate_per_second'] for x in result['intervals']], [13, 43, 93])
        self.assertEqual([x['midpoint_interval_seconds'] for x in result['accelerations']], [15, 25])
        for acceleration in result['accelerations']:
            self.assertAlmostEqual(acceleration['acceleration_per_second_squared'], 2)
            self.assertAlmostEqual(acceleration['acceleration_per_hour_squared'], 2 * 3600**2)
        average = result['duration_weighted_average']
        self.assertEqual(average['net_rate_per_second'], 63)
        self.assertEqual(average['net_rate_per_hour'], 63 * 3600)
        self.assertNotEqual(average['net_rate_per_second'], (13 + 43 + 93) / 3)

    def test_untimed_and_unknown_counts_are_skipped_without_invented_baseline(self):
        data = {'follower_observations': [
            {'total': 175, 'observed_at': None}, observation(0, 200),
            observation(10, None), observation(20, 220)]}
        result = growth_dynamics.analyze(data)['follower_dynamics']
        self.assertEqual(len(result['skipped_observations']), 2)
        self.assertEqual(result['intervals'][0]['net_delta'], 20)
        self.assertEqual(result['intervals'][0]['interval_seconds'], 20)
        self.assertEqual(result['duration_weighted_average']['net_rate_per_second'], 1)

    def test_midpoint_acceleration_avoids_half_microsecond_datetime_rounding(self):
        data = {'follower_observations': [observation(t/1_000_000, t*t) for t in (0, 1, 3, 6)]}
        result = growth_dynamics.analyze(data)['follower_dynamics']
        self.assertAlmostEqual(result['accelerations'][0]['midpoint_interval_seconds'], .0000015)
        for interval in result['accelerations']:
            self.assertAlmostEqual(interval['acceleration_per_second_squared'] / 2_000_000_000_000, 1)

    def test_losses_and_zero_net_changes_are_allowed(self):
        result = growth_dynamics.analyze({'follower_observations': [
            observation(0, 5), observation(10, 5), observation(30, 1)]})['follower_dynamics']
        self.assertEqual([x['net_delta'] for x in result['intervals']], [0, -4])
        self.assertEqual(result['intervals'][1]['net_rate_per_second'], -.2)
        self.assertAlmostEqual(result['accelerations'][0]['acceleration_per_second_squared'], -.2 / 15)

    def test_blue_membership_is_not_confirmed_acquisition(self):
        data = {'blue_observations': [
            {'observed_at': at(0), 'count': 88}, {'observed_at': at(60), 'count': 100}]}
        result = growth_dynamics.analyze(data)
        blue = result['blue_membership_dynamics']
        self.assertEqual(blue['kind'], 'observed_blue_membership')
        self.assertEqual(blue['intervals'][0]['net_rate_per_second'], .2)
        self.assertFalse(blue['confirmed_acquisition'])
        self.assertIsNone(result['confirmed_acquisition_rates']['gross_blue_followers_per_second'])
        self.assertIsNone(result['conversion'])

    def test_missing_series_have_unknown_average_instead_of_zero(self):
        result = growth_dynamics.analyze({})
        for name in ('follower_dynamics', 'blue_membership_dynamics'):
            self.assertEqual(result[name]['intervals'], [])
            self.assertIsNone(result[name]['duration_weighted_average'])
        self.assertIsNone(result['observed_cohort_quality']['lower_bound'])

    def test_following_ratio_uses_only_the_same_snapshot_and_handles_zero_denominator(self):
        data = {'follower_observations': [observation(0, 10), observation(10, None, following=5),
                                          observation(20, 0, following=2), observation(30, 4, following=6)]}
        ratios = growth_dynamics.analyze(data)['following_ratios']
        self.assertEqual([x['following_to_total_ratio'] for x in ratios], [None, None, None, 1.5])
        self.assertEqual(ratios[2]['reason'], 'zero_denominator')
        self.assertIn('not a quality score', ratios[-1]['meaning'])

    def test_timezone_offsets_use_elapsed_time_and_utc_midpoints(self):
        data = {'follower_observations': [observation(0, 1),
                {'observed_at': '2026-10-08T08:01:00+08:00', 'total': 61}]}
        interval = growth_dynamics.analyze(data)['follower_dynamics']['intervals'][0]
        self.assertEqual(interval['interval_seconds'], 60)
        self.assertEqual(interval['midpoint_at'], '2026-10-08T00:00:30Z')

    def test_invalid_counts_nan_boolean_and_unknown_strings_are_rejected(self):
        for field in ('total', 'following'):
            for invalid in (True, False, -1, 1.0, float('nan'), float('inf'), 'unknown'):
                with self.subTest(field=field, invalid=invalid):
                    row = observation(0, 1)
                    row[field] = invalid
                    with self.assertRaises(ValueError):
                        growth_dynamics.analyze({'follower_observations': [row]})
        for invalid in (True, float('nan'), 'unknown'):
            with self.assertRaises(ValueError):
                growth_dynamics.analyze({'blue_observations': [{'observed_at': at(0), 'count': invalid}]})

    def test_duplicate_reversed_missing_timezone_and_invalid_time_are_rejected(self):
        for value in (at(0), at(-1), '2026-10-08T00:00:01', 'unknown', True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    growth_dynamics.analyze({'follower_observations': [observation(0, 1),
                                             {'observed_at': value, 'total': 2}]})
        with self.assertRaises(ValueError):
            growth_dynamics.analyze({'blue_observations': [
                {'observed_at': at(0), 'count': 1}, {'observed_at': at(0), 'count': 2}]})

    def test_malformed_collections_and_cohort_partitions_are_rejected(self):
        for invalid in (None, [], 'unknown'):
            with self.assertRaises(ValueError):
                growth_dynamics.analyze(invalid)
        for collection in ('follower_observations', 'blue_observations', 'post_observations'):
            for invalid in (None, {}, 'unknown', [None]):
                with self.subTest(collection=collection, invalid=invalid):
                    with self.assertRaises(ValueError):
                        growth_dynamics.analyze({collection: invalid})
        for patch in ({'high': True}, {'unknown': 'unknown'}, {'not_high': 3},
                      {'confirmed_new_followers': 4}):
            cohort = {'observed_arrivals': 3, 'high': 1, 'not_high': 1, 'unknown': 1, **patch}
            with self.assertRaises(ValueError):
                growth_dynamics.analyze({'blue_cohort': cohort})

    def test_cohort_bounds_describe_observed_sample_without_population_confidence(self):
        cohort = {'observed_arrivals': 3, 'high': 1, 'not_high': 1, 'unknown': 1}
        result = growth_dynamics.analyze({'blue_cohort': cohort})['observed_cohort_quality']
        self.assertAlmostEqual(result['lower_bound'], 1/3)
        self.assertAlmostEqual(result['upper_bound'], 2/3)
        self.assertIsNone(result['general_population_confidence_interval'])
        cohort.update(observed_arrivals=0, high=0, not_high=0, unknown=0)
        self.assertIsNone(growth_dynamics.analyze({'blue_cohort': cohort})['observed_cohort_quality']['lower_bound'])

    def test_post_windows_are_separate_and_negative_counter_changes_are_revisions(self):
        one, two = 'https://x.com/example/status/1', 'https://x.com/example/status/2'
        data = {'post_observations': [
            {'url': one, 'observed_at': at(0), 'views': 10},
            {'url': two, 'observed_at': at(5), 'views': 100},
            {'url': one, 'observed_at': at(10), 'views': 30},
            {'url': two, 'observed_at': at(25), 'views': 90}]}
        result = growth_dynamics.analyze(data)
        posts = {x['status_id']: x for x in result['post_view_dynamics']['posts']}
        self.assertEqual(posts['1']['intervals'][0]['counter_rate_per_second'], 2)
        corrected = posts['2']['intervals'][0]
        self.assertEqual(corrected['counter_delta'], -10)
        self.assertEqual(corrected['counter_rate_per_second'], -.5)
        self.assertEqual(corrected['status'], 'counter_revision')
        self.assertIsNone(corrected['observed_view_rate_per_second'])
        self.assertIsNone(result['conversion'])
        self.assertEqual(result['conversion_status'], 'insufficient_matched_window')

    def test_post_alias_duplicates_are_reported_without_zero_time_rates_and_conflicts_fail(self):
        row = {'url': 'https://x.com/example/status/1', 'observed_at': at(0), 'views': 10}
        alias = {**row, 'url': 'https://twitter.com/renamed/status/1?s=20'}
        result = growth_dynamics.analyze({'post_observations': [row, alias]})['post_view_dynamics']['posts'][0]
        self.assertEqual(result['intervals'], [])
        self.assertEqual(result['skipped_observations'][0]['reason'], 'duplicate_identical_counter_snapshot')
        alias['views'] = 11
        with self.assertRaises(ValueError):
            growth_dynamics.analyze({'post_observations': [row, alias]})
        alias['observed_at'] = at(-1)
        with self.assertRaises(ValueError):
            growth_dynamics.analyze({'post_observations': [row, alias]})

    def test_missing_post_view_baselines_are_not_zero_and_bad_counters_urls_fail(self):
        one = 'https://x.com/example/status/1'
        data = {'post_observations': [{'url': one, 'observed_at': at(0), 'views': None},
                                       {'url': one, 'observed_at': at(10), 'views': 8}]}
        self.assertEqual(growth_dynamics.analyze(data)['post_view_dynamics']['posts'][0]['intervals'], [])
        for invalid in (True, float('nan'), -1, 'unknown'):
            bad = copy.deepcopy(data)
            bad['post_observations'][1]['views'] = invalid
            with self.assertRaises(ValueError):
                growth_dynamics.analyze(bad)
        data['post_observations'][0]['url'] = 'https://x.com/example'
        with self.assertRaises(ValueError):
            growth_dynamics.analyze(data)

    def test_cli_preserves_input_writes_only_requested_aggregate_and_rejects_bad_json(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/'metrics.json', Path(directory)/'report.json'
            original = json.dumps({'follower_observations': [observation(0, 1), observation(10, 2)]})
            source.write_text(original)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(growth_dynamics.main([str(source), '--output', str(output)]), 0)
            self.assertEqual(source.read_text(), original)
            self.assertEqual(json.loads(output.read_text())['follower_dynamics']['intervals'][0]['net_delta'], 1)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(growth_dynamics.main([str(source), '--output', str(source)]), 2)
                for invalid in ('{"follower_observations":[],"follower_observations":[]}',
                                '{"follower_observations":[],"unknown":NaN}'):
                    source.write_text(invalid)
                    before = output.read_text()
                    self.assertEqual(growth_dynamics.main([str(source), '--output', str(output)]), 2)
                    self.assertEqual(output.read_text(), before)


if __name__ == '__main__':
    unittest.main()
