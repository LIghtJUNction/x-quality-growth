import contextlib
import copy
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import reward_progress


def at(seconds):
    return (datetime(2026, 10, 8, 4, 2, 12, 455000, tzinfo=timezone.utc)
            + timedelta(seconds=seconds)).isoformat()


def observation(seconds=0, home=534, followers=167, **extra):
    return {'observed_at': at(seconds), 'verified_home_impressions_90d': home,
            'verified_followers': followers, 'replies_excluded': True,
            'source': reward_progress.SOURCE, 'payout_qualified_impressions': None, **extra}


def baseline(*rows):
    return {'metric': reward_progress.METRIC, 'window_days': 90,
            'impression_target': 500000, 'verified_follower_target': 500,
            'source': reward_progress.SOURCE, 'observations': list(rows)}


class RewardProgressTests(unittest.TestCase):
    def test_single_real_baseline_has_exact_deficits_and_no_growth_or_forecast(self):
        result = reward_progress.analyze(baseline(observation()))
        self.assertEqual(result['status'], 'measured_baseline_only')
        self.assertEqual(result['latest']['impression_deficit'], 499466)
        self.assertEqual(result['latest']['verified_follower_deficit'], 333)
        self.assertEqual(result['latest']['impression_progress_fraction'], .001068)
        self.assertEqual(result['latest']['verified_follower_progress_fraction'], .334)
        self.assertFalse(result['latest']['both_observed_thresholds_met'])
        self.assertEqual(result['intervals'], [])
        self.assertIsNone(result['latest_net_rates'])
        self.assertEqual(result['forecast']['status'], 'untrained_model')
        for field, value in result['forecast'].items():
            if field != 'status':
                self.assertIsNone(value, field)
        for field in ('program_admission', 'payout_qualification',
                      'gross_new_verified_home_impressions', 'daily_expiry'):
            self.assertIsNone(result[field])

    def test_same_source_unequal_windows_measure_only_net_changes(self):
        result = reward_progress.analyze(baseline(
            observation(0), observation(1800, home=1434, followers=170),
            observation(9000, home=5034, followers=178)))
        intervals = result['intervals']
        self.assertEqual([x['interval_seconds'] for x in intervals], [1800, 7200])
        self.assertEqual([x['rolling_net_impression_delta'] for x in intervals], [900, 3600])
        self.assertEqual([x['rolling_net_impressions_per_second'] for x in intervals], [.5, .5])
        self.assertEqual([x['rolling_net_impressions_per_hour'] for x in intervals], [1800, 1800])
        self.assertEqual(intervals[1]['verified_followers_net_per_hour'], 4)
        self.assertIsNone(result['latest_net_rates']['gross_new_verified_home_impressions'])
        self.assertIsNone(result['forecast']['impression_target_eta'])

    def test_rolling_decline_is_allowed_without_counter_revision_or_invented_expiry(self):
        result = reward_progress.analyze(baseline(observation(0), observation(60, home=474, followers=166)))
        interval = result['intervals'][0]
        self.assertEqual(interval['rolling_net_impression_delta'], -60)
        self.assertEqual(interval['rolling_net_impressions_per_second'], -1)
        self.assertEqual(interval['impression_change_status'], 'rolling_net_decline_possible_expiry')
        self.assertNotIn('counter_revision', json.dumps(result))
        self.assertAlmostEqual(interval['verified_followers_net_per_second'], -1/60)
        self.assertIsNone(interval['expired_verified_home_impressions'])
        self.assertIsNone(result['daily_expiry'])

    def test_zero_counts_empty_history_and_above_target_do_not_imply_program_admission(self):
        empty = reward_progress.analyze(baseline())
        self.assertIsNone(empty['latest'])
        self.assertIsNone(empty['latest_net_rates'])
        self.assertEqual(empty['status'], 'no_observations')
        zero = reward_progress.analyze(baseline(observation(home=0, followers=0)))['latest']
        self.assertEqual(zero['impression_progress_fraction'], 0)
        self.assertEqual(zero['verified_follower_deficit'], 500)
        above = reward_progress.analyze(baseline(observation(home=600000, followers=501)))
        self.assertEqual(above['latest']['impression_progress_fraction'], 1.2)
        self.assertEqual(above['latest']['impression_deficit'], 0)
        self.assertEqual(above['latest']['verified_follower_deficit'], 0)
        self.assertTrue(above['latest']['both_observed_thresholds_met'])
        self.assertIsNone(above['program_admission'])
        self.assertIsNone(above['forecast']['threshold_probability'])

    def test_types_nan_unknown_and_zero_targets_are_strictly_rejected(self):
        invalid_counts = (True, False, -1, 1.0, float('nan'), float('inf'), 'unknown', None)
        for field in ('verified_home_impressions_90d', 'verified_followers', 'payout_qualified_impressions'):
            for invalid in invalid_counts:
                if field == 'payout_qualified_impressions' and invalid is None:
                    continue
                with self.subTest(field=field, invalid=invalid):
                    with self.assertRaises(ValueError):
                        reward_progress.analyze(baseline(observation(**{field: invalid})))
        for field in ('window_days', 'impression_target', 'verified_follower_target'):
            for invalid in (True, 0, -1, 1.0, float('nan'), float('inf'), 'unknown', None):
                with self.subTest(field=field, invalid=invalid):
                    data = baseline(observation())
                    data[field] = invalid
                    with self.assertRaises(ValueError):
                        reward_progress.analyze(data)
        for invalid in (None, [], 'unknown'):
            with self.assertRaises(ValueError):
                reward_progress.analyze(invalid)
        for invalid in (None, {}, 'unknown', [None]):
            data = baseline()
            data['observations'] = invalid
            with self.assertRaises(ValueError):
                reward_progress.analyze(data)

    def test_timestamp_precision_timezone_duplicates_conflicts_and_order(self):
        for invalid in (None, True, 'unknown', '2026-10-08', '2026-10-08T04:02:12',
                        '2026-10-08T04:02Z', '2026-10-08T04:02:12.1234567Z',
                        '2026-13-08T04:02:12Z'):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    reward_progress.analyze(baseline(observation(observed_at=invalid)))
        for second in (observation(), observation(home=535), observation(-1)):
            with self.assertRaisesRegex(ValueError, 'strictly increasing'):
                reward_progress.analyze(baseline(observation(), second))
        # The same instant in another timezone remains a duplicate.
        with self.assertRaises(ValueError):
            reward_progress.analyze(baseline(observation(), observation(
                observed_at='2026-10-08T12:02:12.455+08:00')))
        result = reward_progress.analyze(baseline(observation(), observation(
            home=535, observed_at='2026-10-08T12:02:13.455+08:00')))
        self.assertEqual(result['intervals'][0]['interval_seconds'], 1)
        precise = reward_progress.analyze(baseline(observation(), observation(.000001, home=535)))
        self.assertEqual(precise['intervals'][0]['rolling_net_impressions_per_second'], 1000000)

    def test_wrong_metric_source_window_or_reply_semantics_are_not_merged(self):
        for field, wrong in (('metric', 'qualifiedpayout'), ('source', 'qualifiedpayout'), ('window_days', 30)):
            data = baseline(observation())
            data[field] = wrong
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    reward_progress.analyze(data)
        for wrong in ('qualifiedpayout', 'other source', None):
            with self.assertRaises(ValueError):
                reward_progress.analyze(baseline(observation(), observation(60, source=wrong)))
        for wrong in (False, 1, 'true', None):
            with self.assertRaises(ValueError):
                reward_progress.analyze(baseline(observation(replies_excluded=wrong)))

    def test_timezone_offset_components_cannot_be_normalized_into_valid_times(self):
        for offset in ('+00:99', '-01:60', '+24:00'):
            with self.subTest(offset=offset):
                with self.assertRaisesRegex(ValueError, 'timezone offset'):
                    reward_progress.analyze(baseline(observation(
                        observed_at='2026-10-08T04:02:12.455' + offset)))

    def test_payout_counter_total_views_and_blue_ratios_cannot_replace_eligibility_counter(self):
        data = baseline(observation(payout_qualified_impressions=999999,
                                    total_views=9999999, blue_ratio=.99))
        result = reward_progress.analyze(data)
        self.assertEqual(result['latest']['verified_home_impressions_90d'], 534)
        self.assertEqual(result['latest']['impression_deficit'], 499466)
        self.assertIsNone(result['payout_qualification'])
        self.assertNotIn('payout_qualified_impressions', result['latest'])
        del data['observations'][0]['verified_home_impressions_90d']
        with self.assertRaises(ValueError):
            reward_progress.analyze(data)

    def test_public_metadata_is_kept_without_snapshot_or_private_note(self):
        data = baseline(observation(source_url='https://x.com/i/jf/creators/original_content_rewards',
                                    note='private raw note', snapshot='raw private snapshot'))
        data.update(policy_url='https://help.x.com/en/using-x/original-content-rewards',
                    policy_checked_at='2026-10-08T04:00:26Z')
        result = reward_progress.analyze(data)
        self.assertEqual(result['policy_url'], data['policy_url'])
        self.assertEqual(result['policy_checked_at'], data['policy_checked_at'])
        self.assertEqual(result['latest']['source_url'], data['observations'][0]['source_url'])
        self.assertNotIn('private', json.dumps(result))
        for field in ('policy_url', 'policy_checked_at'):
            invalid = copy.deepcopy(data)
            invalid[field] = True
            with self.assertRaises(ValueError):
                reward_progress.analyze(invalid)

    def test_overflow_cannot_silently_emit_infinite_progress_or_rates(self):
        with self.assertRaises(ValueError):
            reward_progress.analyze(baseline(observation(home=10**400)))
        with self.assertRaises(ValueError):
            reward_progress.analyze(baseline(observation(), observation(1, home=10**400)))

    def test_cli_default_input_optional_output_and_invalid_input_do_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / 'public'
            public.mkdir()
            input_path, output_path = public / 'reward-observations.json', root / 'aggregate.json'
            input_path.write_text(json.dumps(baseline(observation())))
            original_root = reward_progress.ROOT
            reward_progress.ROOT = root
            try:
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    self.assertEqual(reward_progress.main([]), 0)
                self.assertEqual(json.loads(stdout.getvalue())['latest']['impression_deficit'], 499466)
                self.assertEqual(reward_progress.main(['--inputpath', str(input_path),
                                                      '--outputpath', str(output_path)]), 0)
                self.assertEqual(json.loads(output_path.read_text())['observation_count'], 1)
                unchanged = output_path.read_text()
                for malformed in ('{"metric": "a", "metric": "b"}', '{"value": NaN}', '{'):
                    input_path.write_text(malformed)
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(reward_progress.main(['--inputpath', str(input_path),
                                                              '--outputpath', str(output_path)]), 2)
                    self.assertEqual(output_path.read_text(), unchanged)
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(reward_progress.main(['--inputpath', str(input_path),
                                                          '--outputpath', str(input_path)]), 2)
                self.assertEqual(input_path.read_text(), '{')
            finally:
                reward_progress.ROOT = original_root


if __name__ == '__main__':
    unittest.main()
