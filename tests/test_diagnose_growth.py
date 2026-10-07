import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import diagnose_growth


class GrowthDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.data = {'account': 'example', 'posts': [], 'follower_observations': [
            {'total': 175, 'observed_at': None},
            {'total': 200, 'observed_at': '2026-10-08T00:00:00Z'},
            {'total': 210, 'observed_at': '2026-10-08T00:10:00Z'},
            {'total': 212, 'observed_at': '2026-10-08T00:20:00Z'}]}

    def test_latest_two_rates_do_not_invent_baseline_time(self):
        result = diagnose_growth.diagnose(self.data)
        self.assertEqual([r['net_delta'] for r in result['latest_intervals']], [10, 2])
        self.assertEqual([r['net_followers_per_minute'] for r in result['latest_intervals']], [1, 0.2])
        self.assertEqual(result['skipped_observations'][0]['total'], 175)
        self.assertEqual(result['fixed_window_comparison']['net_rate_direction'], 'decreased')
        self.assertEqual(result['causal_explanation'], 'unknown')
        self.assertIsNone(result['confirmed_new_blue_followers'])

    def test_shorter_window_is_not_comparable_despite_normalized_rate(self):
        self.data['follower_observations'][-1]['observed_at'] = '2026-10-08T00:11:00Z'
        result = diagnose_growth.diagnose(self.data)
        self.assertFalse(result['fixed_window_comparison']['within_duration_budget'])
        self.assertEqual(result['fixed_window_comparison']['strategy_comparability'], 'unknown')

    def test_zero_and_negative_net_changes_are_valid(self):
        self.data['follower_observations'] = [
            {'total': 1, 'observed_at': '2026-10-08T00:00:00Z'},
            {'total': 1, 'observed_at': '2026-10-08T00:10:00Z'},
            {'total': 0, 'observed_at': '2026-10-08T00:20:00Z'}]
        result = diagnose_growth.diagnose(self.data)
        self.assertEqual([r['net_delta'] for r in result['latest_intervals']], [0, -1])

    def test_null_counts_are_skipped_not_converted_to_zero(self):
        self.data['follower_observations'][2]['total'] = None
        result = diagnose_growth.diagnose(self.data)
        self.assertEqual(result['latest_intervals'][0]['net_delta'], 12)
        self.assertEqual(result['latest_intervals'][0]['interval_minutes'], 20)
        self.assertEqual(result['fixed_window_comparison']['status'], 'insufficient_intervals')

    def test_duplicate_reversed_and_timezone_missing_times_are_rejected(self):
        for value in ('2026-10-08T00:10:00Z', '2026-10-08T00:09:00Z',
                      '2026-10-08T00:20:00', 123):
            with self.subTest(value=value):
                data = copy.deepcopy(self.data)
                data['follower_observations'][-1]['observed_at'] = value
                with self.assertRaises(ValueError):
                    diagnose_growth.diagnose(data)

    def test_timezone_offsets_use_actual_elapsed_time(self):
        self.data['follower_observations'][2]['observed_at'] = '2026-10-08T08:10:00+08:00'
        self.assertEqual(diagnose_growth.diagnose(self.data)['latest_intervals'][0]['interval_minutes'], 10)

    def test_empty_data_and_one_timed_interval_do_not_claim_slowdown(self):
        for rows in ([], self.data['follower_observations'][:3]):
            result = diagnose_growth.diagnose({'follower_observations': rows})
            self.assertIsNone(result['fixed_window_comparison']['net_rate_direction'])

    def test_invalid_count_and_tolerance_are_rejected(self):
        for total in (True, -1, '200'):
            data = copy.deepcopy(self.data)
            data['follower_observations'][1]['total'] = total
            with self.assertRaises(ValueError):
                diagnose_growth.diagnose(data)
        for value in (-0.1, 1.1, True, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                diagnose_growth.diagnose(self.data, value)

    def test_post_samples_do_not_invent_feedback_deltas_or_conversion(self):
        self.data['posts'] = [{'observed_at': '2026-10-08T00:09:00Z', 'views': 100}]
        result = diagnose_growth.diagnose(self.data)
        self.assertEqual(result['latest_intervals'][0]['post_counter_observations_in_window'], 1)
        self.assertIsNone(result['latest_intervals'][0]['matched_post_feedback_delta'])
        self.assertIsNone(result['profile_visit_to_follow_conversion'])
        self.assertIsNone(result['confirmed_action_mix'])

    def test_cli_never_changes_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'metrics.json'
            original = json.dumps(self.data)
            path.write_text(original)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(diagnose_growth.main([str(path)]), 0)
            self.assertEqual(path.read_text(), original)


if __name__ == '__main__':
    unittest.main()
