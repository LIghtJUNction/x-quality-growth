import copy
import json
import unittest
from pathlib import Path
from scripts import render_public


class PublicEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((Path(__file__).resolve().parents[1] / 'public/metrics.json').read_text())

    def test_unknown_quality_stays_pending(self):
        self.data['blue_cohort'].update(observed_arrivals=2, high=1, not_high=0, unknown=1)
        self.assertIn('PENDING', render_public.metric_art(self.data))
        self.assertIn('Pending classification', render_public.block(self.data, True))
        self.assertIn('分类尚未完成', render_public.block(self.data))
        self.assertIn('50.0%–100.0%', render_public.block(self.data, True))
        self.assertEqual(render_public.quality_bounds(self.data['blue_cohort']), (0.5, 1.0))

    def test_complete_quality_appears_in_both_languages(self):
        self.data['blue_cohort'].update(observed_arrivals=2, high=1, not_high=1, unknown=0)
        self.assertIn('50.0%', render_public.block(self.data, True))
        self.assertIn('50.0%', render_public.block(self.data))

    def test_empty_cohort_does_not_claim_zero_quality(self):
        self.data['blue_cohort'].update(observed_arrivals=0, high=0, not_high=0, unknown=0)
        self.assertIn('N/A', render_public.metric_art(self.data))
        self.assertIn('N/A', render_public.block(self.data, True))

    def test_inconsistent_partition_is_rejected(self):
        self.data['blue_cohort']['high'] += 1
        with self.assertRaises(ValueError):
            render_public.metric_art(self.data)

    def test_unknown_post_counts_are_not_zero(self):
        row = copy.deepcopy(self.data['posts'][0])
        row.update(kind='launch', views=None, observed_at='2026-10-08T00:00:00Z')
        self.data['posts'] = [row]
        self.assertIn('N/A', render_public.feedback_art(self.data))

    def test_invalid_counter_is_rejected(self):
        self.data['posts'][0]['likes'] = -1
        with self.assertRaises(ValueError):
            render_public.validate(self.data)

    def test_invalid_inputs_are_rejected_before_rendering(self):
        mutations = [
            lambda d: d['blue_cohort'].update(high=True),
            lambda d: d['blue_observations'][0].update(count=-1),
            lambda d: d['blue_observations'][0].update(count='88'),
            lambda d: d['blue_cohort'].update(confirmed_new_followers=13),
            lambda d: d['posts'][0].update(url='https://x.com/someone_else/status/123'),
            lambda d: d['posts'][0].update(url='https://x.com/LIghtJUNction_x/status/123?x=1'),
            lambda d: d['posts'][0].update(observed_at='2026-10-08T00:00:00'),
            lambda d: d['progress_updates'][0].update(url='javascript:alert(1)'),
            lambda d: d['github'].update(stars=True),
            lambda d: d.update(account='not/a/handle'),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                data = copy.deepcopy(self.data)
                mutation(data)
                with self.assertRaises(ValueError):
                    render_public.validate(data)

    def test_empty_observation_lists_remain_renderable(self):
        self.data.update(follower_observations=[], blue_observations=[], posts=[])
        self.assertIn('no follower observations', render_public.metric_art(self.data))
        self.assertIn('no observed post counters', render_public.feedback_art(self.data))
        self.assertIn('N/A; no observations', render_public.block(self.data, True))

    def test_different_observation_windows_are_visible(self):
        output = render_public.block(self.data, True)
        self.assertIn(self.data['follower_observations'][-1]['observed_at'], output)
        self.assertIn(self.data['blue_observations'][-1]['observed_at'], output)
        self.assertIn('separate window', output)
        self.assertIn('self-interactions', output)

    def test_optional_histories_remain_backwards_compatible(self):
        self.data.pop('post_observations', None)
        self.data.pop('analytics_observations', None)
        self.data.pop('blue_cohort_history', None)
        render_public.validate(self.data)

    def test_prior_blue_cohort_is_validated_without_merging_into_current(self):
        prior = {
            'observed_arrivals': 12, 'confirmed_new_followers': None,
            'high': 0, 'not_high': 11, 'unknown': 1,
            'window_ended_at': '2026-10-07T21:04:50Z',
            'classified_at': '2026-10-07T23:35:15.108Z',
        }
        self.data['blue_cohort_history'] = [prior]
        self.data['blue_cohort'].update(
            id='current-independent-cohort', observed_arrivals=5,
            confirmed_new_followers=None, high=2, not_high=3, unknown=0,
            window_started_at='2026-10-07T22:58:02.912Z',
            window_ended_at='2026-10-08T00:20:00Z',
            scope='verified_followers', identity_basis='handle')
        before = copy.deepcopy(self.data)
        render_public.validate(self.data)
        self.assertEqual(self.data, before)
        self.assertIn('40.0%', render_public.block(self.data, True))
        self.assertIn('| Newly observed blue accounts | 5;', render_public.block(self.data, True))
        for en, current_label, prior_label, blue_label in (
                (True, 'Current observed-cohort window', 'Previous independent cohort',
                 'Earlier blue-count observation (separate window)'),
                (False, '当前观察队列窗口', '上一独立观察队列', '较早蓝 V 计数采集（独立窗口）')):
            with self.subTest(en=en):
                block = render_public.block(self.data, en)
                self.assertIn(current_label, block)
                self.assertIn('2026-10-07T22:58:02.912Z → 2026-10-08T00:20:00Z', block)
                self.assertIn(prior_label, block)
                self.assertIn('n=12', block)
                self.assertIn(blue_label, block)

    def test_blue_cohort_history_shapes_are_validated(self):
        for history in (None, {}, 'history', [None], [123]):
            with self.subTest(history=history):
                data = copy.deepcopy(self.data)
                data['blue_cohort_history'] = history
                with self.assertRaises(ValueError):
                    render_public.validate(data)
        self.data['blue_cohort_history'] = []
        render_public.validate(self.data)

    def test_blue_cohort_history_rejects_invalid_counts(self):
        for key in ('high', 'not_high', 'unknown', 'observed_arrivals', 'confirmed_new_followers'):
            for value in (True, False, -1, 1.5, '1'):
                with self.subTest(key=key, value=value):
                    data = copy.deepcopy(self.data)
                    prior = copy.deepcopy(data['blue_cohort'])
                    prior[key] = value
                    data['blue_cohort_history'] = [prior]
                    with self.assertRaises(ValueError):
                        render_public.validate(data)

    def test_blue_cohort_history_rejects_inconsistent_partition_and_confirmed_count(self):
        for patch in ({'high': 1, 'not_high': 11, 'unknown': 1, 'observed_arrivals': 12},
                      {'high': 0, 'not_high': 11, 'unknown': 1, 'observed_arrivals': 12,
                       'confirmed_new_followers': 13}):
            with self.subTest(patch=patch):
                data = copy.deepcopy(self.data)
                prior = copy.deepcopy(data['blue_cohort'])
                prior.update(patch)
                data['blue_cohort_history'] = [prior]
                with self.assertRaises(ValueError):
                    render_public.validate(data)

    def test_cohort_windows_reject_invalid_start_and_reversed_order(self):
        for historical in (False, True):
            for started in ('2026-10-08T01:00:00', 'not-a-date', '2026-10-08T01:00:00Z'):
                with self.subTest(historical=historical, started=started):
                    data = copy.deepcopy(self.data)
                    cohort = copy.deepcopy(data['blue_cohort'])
                    cohort.update(window_started_at=started, window_ended_at='2026-10-08T00:00:00Z')
                    if historical:
                        data['blue_cohort_history'] = [cohort]
                    else:
                        data['blue_cohort'] = cohort
                    with self.assertRaises(ValueError):
                        render_public.validate(data)

    def test_history_collections_and_rows_have_valid_shapes(self):
        for collection in ('post_observations', 'analytics_observations'):
            for rows in (None, {}, 'history', [None], [123]):
                with self.subTest(collection=collection, rows=rows):
                    data = copy.deepcopy(self.data)
                    data[collection] = rows
                    with self.assertRaises(ValueError):
                        render_public.validate(data)

    def test_histories_require_account_status_links_and_timed_snapshots(self):
        mutations = [
            {'url': 'https://x.com/someone_else/status/123'},
            {'url': 'https://x.com/LIghtJUNction_x/status/123?x=1'},
            {'url': 'https://x.com/LIghtJUNction_x/status/0'},
            {'url': 'https://x.com/LIghtJUNction_x/status/0123'},
            {'url': 'https://x.com/LIghtJUNction_x/status/１２３'},
            {'observed_at': None},
            {'observed_at': '2026-10-08T00:00:00'},
            {'observed_at': 'not-a-date'},
            {'kind': True},
        ]
        for collection in ('post_observations', 'analytics_observations'):
            for mutation in mutations:
                with self.subTest(collection=collection, mutation=mutation):
                    data = copy.deepcopy(self.data)
                    data[collection][0].update(mutation)
                    with self.assertRaises(ValueError):
                        render_public.validate(data)

    def test_all_known_history_counters_reject_invalid_values(self):
        for collection, counters in (
                ('post_observations', render_public.POST_COUNTERS),
                ('analytics_observations', render_public.ANALYTICS_COUNTERS)):
            for key in counters:
                for value in (True, False, -1, 1.5, '1'):
                    with self.subTest(collection=collection, key=key, value=value):
                        data = copy.deepcopy(self.data)
                        data[collection][0][key] = value
                        with self.assertRaises(ValueError):
                            render_public.validate(data)

    def test_history_unknown_counters_stay_unknown(self):
        for collection, counters in (
                ('post_observations', render_public.POST_COUNTERS),
                ('analytics_observations', render_public.ANALYTICS_COUNTERS)):
            for row in self.data[collection]:
                row.update({key: None for key in counters})
        before = copy.deepcopy(self.data)
        render_public.validate(self.data)
        self.assertEqual(self.data, before)

    def test_history_order_is_checked_per_post_not_globally(self):
        for collection in ('post_observations', 'analytics_observations'):
            with self.subTest(collection=collection):
                data = copy.deepcopy(self.data)
                first = copy.deepcopy(data[collection][0])
                first['observed_at'] = '2026-10-08T02:00:00Z'
                different_post = copy.deepcopy(first)
                different_post.update(url='https://x.com/LIghtJUNction_x/status/123',
                                      observed_at='2026-10-08T01:00:00Z')
                later = copy.deepcopy(first)
                later['observed_at'] = '2026-10-08T03:00:00Z'
                data[collection] = [first, different_post, later]
                render_public.validate(data)
                earlier = copy.deepcopy(first)
                earlier['observed_at'] = '2026-10-08T00:00:00Z'
                data[collection].append(earlier)
                with self.assertRaises(ValueError):
                    render_public.validate(data)

    def test_equal_time_history_captures_must_agree(self):
        for collection, counter in (('post_observations', 'views'),
                                    ('analytics_observations', 'impressions')):
            with self.subTest(collection=collection):
                data = copy.deepcopy(self.data)
                row = copy.deepcopy(data[collection][0])
                row['observed_at'] = '2026-10-08T00:00:00Z'
                repeated = copy.deepcopy(row)
                repeated['url'] = repeated['url'].replace('LIghtJUNction_x', 'lightjunction_x')
                repeated['observed_at'] = '2026-10-08T08:00:00+08:00'
                data[collection] = [row, repeated]
                render_public.validate(data)
                repeated[counter] = row[counter] + 1
                with self.assertRaises(ValueError):
                    render_public.validate(data)

    def test_histories_keep_surface_times_and_counter_corrections_separate(self):
        # Neither a later history than posts nor a different owner-analytics
        # timestamp implies a shared window or a causal conversion calculation.
        post = self.data['post_observations'][0]
        first = copy.deepcopy(post)
        first.update(observed_at='2026-10-08T02:00:00Z', views=10)
        correction = copy.deepcopy(first)
        correction.update(observed_at='2026-10-08T03:00:00Z', views=8)
        self.data['post_observations'] = [first, correction]
        self.data['analytics_observations'][0].update(
            observed_at='2026-10-08T01:00:00Z', impressions=150, profile_visits=None)
        before = copy.deepcopy(self.data)
        render_public.validate(self.data)
        self.assertEqual(self.data, before)

    def test_controlled_replacement_preserves_everything_outside_block(self):
        content = 'unrelated\n' + render_public.START + '\nold\n' + render_public.END + '\ntail'
        expected = 'unrelated\n' + render_public.START + '\nnew\n' + render_public.END + '\ntail'
        self.assertEqual(render_public.replace_block(content, 'new'), expected)
        for invalid in ('missing', content + render_public.START,
                        render_public.END + render_public.START):
            with self.assertRaises(ValueError):
                render_public.replace_block(invalid, 'new')


if __name__ == '__main__':
    unittest.main()
