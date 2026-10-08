import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts import post_statistics


class PostStatisticsTests(unittest.TestCase):
    def setUp(self):
        self.url = 'https://x.com/example_owner/status/123'
        self.data = {
            'account': 'example_owner',
            'posts': [{'url': self.url, 'kind': 'original', 'published_at': '2026-10-08T00:00:00Z'}],
            'analytics_observations': [], 'post_observations': [],
        }

    def analytics(self, at='2026-10-08T00:01:00Z', **counts):
        values = dict(impressions=100, engagements=20, detail_expands=10, profile_visits=4, link_clicks=2)
        values.update(counts)
        return dict(url=self.url, observed_at=at, **values)

    def public(self, at='2026-10-08T00:01:30Z', **counts):
        values = dict(views=200, replies=1, likes=4, reposts=2, bookmarks=None)
        values.update(counts)
        return dict(url=self.url, observed_at=at, **values)

    def output(self):
        return post_statistics.build_statistics(self.data)

    def test_exact_same_capture_ratios_and_age(self):
        self.data['analytics_observations'] = [self.analytics()]
        row = self.output()['per_post'][0]['latest_owner_analytics']
        self.assertEqual(row['event_ratios'], {
            'engagement_events_per_impression': .2, 'detail_expands_per_impression': .1,
            'profile_visits_per_impression': .04, 'link_clicks_per_impression': .02})
        self.assertEqual(row['age_seconds'], 60)
        self.assertEqual(row['age_publication_source']['field'], 'published_at')
        self.assertIsNone(row['follows_attributed'])

    def test_zero_and_unknown_impressions_are_not_zero_ratios(self):
        for impressions, reason in ((0, 'zero_impressions'), (None, 'unknown_impressions')):
            with self.subTest(impressions=impressions):
                self.data['analytics_observations'] = [self.analytics(impressions=impressions)]
                row = self.output()['per_post'][0]['latest_owner_analytics']
                self.assertTrue(all(value is None for value in row['event_ratios'].values()))
                self.assertEqual(set(row['event_ratio_reasons'].values()), {reason})

    def test_unknown_event_is_not_silently_zero(self):
        self.data['analytics_observations'] = [self.analytics(link_clicks=None)]
        row = self.output()['per_post'][0]['latest_owner_analytics']
        self.assertIsNone(row['event_ratios']['link_clicks_per_impression'])
        self.assertEqual(row['event_ratio_reasons']['link_clicks_per_impression'], 'unknown_counter')
        self.assertEqual(row['event_ratios']['engagement_events_per_impression'], .2)

    def test_more_than_one_event_per_impression_is_not_clipped(self):
        self.data['analytics_observations'] = [self.analytics(impressions=2, engagements=5, detail_expands=4)]
        ratios = self.output()['per_post'][0]['latest_owner_analytics']['event_ratios']
        self.assertEqual(ratios['engagement_events_per_impression'], 2.5)
        self.assertEqual(ratios['detail_expands_per_impression'], 2)

    def test_paired_interval_uses_deltas_and_exact_units(self):
        self.data['analytics_observations'] = [
            self.analytics(), self.analytics('2026-10-08T00:03:00Z', impressions=140,
                                            engagements=28, detail_expands=14, profile_visits=6, link_clicks=3)]
        interval = self.output()['paired_intervals'][0]
        self.assertEqual(interval['elapsed_seconds'], 120)
        self.assertEqual(interval['delta_counts']['impressions'], 40)
        self.assertEqual(interval['counts_per_second']['engagements'], 8 / 120)
        self.assertEqual(interval['event_ratios']['engagement_events_per_impression'], .2)
        self.assertEqual(interval['events_per_1000_impressions']['engagement_events_per_impression'], 200)
        self.assertEqual(interval['events_per_1000_impressions']['profile_visits_per_impression'], 50)

    def test_counter_revision_suppresses_interval_estimates(self):
        self.data['analytics_observations'] = [self.analytics(), self.analytics('2026-10-08T00:02:00Z',
                                                                             impressions=120, engagements=19)]
        interval = self.output()['paired_intervals'][0]
        self.assertEqual(interval['status'], 'counter_revision')
        self.assertEqual(interval['revised_counters'], ['engagements'])
        for field in ('delta_counts', 'counts_per_second', 'event_ratios', 'events_per_1000_impressions'):
            self.assertTrue(all(value is None for value in interval[field].values()))
        self.assertEqual(set(interval['event_ratio_reasons'].values()), {'counter_revision'})

    def test_unknown_delta_stays_unknown_but_other_fields_remain_measured(self):
        self.data['analytics_observations'] = [self.analytics(link_clicks=None),
            self.analytics('2026-10-08T00:02:00Z', impressions=120, engagements=24, link_clicks=3)]
        interval = self.output()['paired_intervals'][0]
        self.assertEqual(interval['delta_counts']['engagements'], 4)
        self.assertIsNone(interval['delta_counts']['link_clicks'])
        self.assertIsNone(interval['event_ratios']['link_clicks_per_impression'])

    def test_zero_interval_exposure_has_no_event_ratio(self):
        self.data['analytics_observations'] = [self.analytics(),
            self.analytics('2026-10-08T00:02:00Z', engagements=24)]
        interval = self.output()['paired_intervals'][0]
        self.assertEqual(interval['delta_counts']['impressions'], 0)
        self.assertEqual(interval['counts_per_second']['engagements'], 4 / 60)
        self.assertTrue(all(value is None for value in interval['event_ratios'].values()))
        self.assertEqual(set(interval['event_ratio_reasons'].values()), {'zero_impressions'})

    def test_public_counter_revision_is_also_not_an_event_rate(self):
        self.data['post_observations'] = [self.public(),
            self.public('2026-10-08T00:02:30Z', views=190, likes=5)]
        interval = self.output()['paired_intervals'][0]
        self.assertEqual(interval['status'], 'counter_revision')
        self.assertEqual(interval['revised_counters'], ['views'])
        self.assertTrue(all(value is None for value in interval['counts_per_second'].values()))

    def test_different_declared_analytics_sources_are_not_paired(self):
        self.data['analytics_observations'] = [self.analytics(source='post_details_analytics'),
            self.analytics('2026-10-08T00:02:00Z', source='date_filtered_export', impressions=150)]
        output = self.output()
        self.assertEqual(len(output['per_post'][0]['owner_analytics']), 2)
        self.assertEqual(output['paired_intervals'], [])

    def test_public_and_analytics_clocks_never_mix(self):
        self.data['analytics_observations'] = [self.analytics(),
            self.analytics('2026-10-08T00:02:00Z', impressions=110, engagements=24)]
        self.data['post_observations'] = [self.public(),
            self.public('2026-10-08T00:04:30Z', views=240, likes=5)]
        self.data['follower_observations'] = [{'total': 100}, {'total': 999}]
        output = self.output()
        owner, public = output['paired_intervals']
        self.assertEqual(owner['elapsed_seconds'], 60)
        self.assertEqual(public['elapsed_seconds'], 180)
        self.assertEqual(owner['event_ratios']['engagement_events_per_impression'], .4)
        self.assertNotIn('event_ratios', public)
        self.assertNotIn('impressions', public['delta_counts'])
        self.assertEqual(output['per_post'][0]['latest_public_surface']['counts']['views'], 240)
        self.assertIsNone(output['per_post'][0]['follows_attributed'])

    def test_observation_never_substitutes_for_unknown_publication(self):
        self.data['posts'][0].pop('published_at')
        self.data['posts'][0]['observed_at'] = '2026-10-08T00:00:30Z'
        self.data['analytics_observations'] = [self.analytics()]
        row = self.output()['per_post'][0]
        self.assertIsNone(row['published_at'])
        self.assertIsNone(row['latest_owner_analytics']['age_seconds'])
        self.assertIsNone(row['published_at_source'])

    def test_edited_version_preserves_original_clock_without_fabricating_edit_time(self):
        edited = 'https://x.com/example_owner/status/456'
        self.data['posts'].append({'url': edited, 'kind': 'edited', 'original_version_url': self.url,
                                  'original_published_at': '2026-10-08T00:00:00Z'})
        self.data['analytics_observations'] = [dict(self.analytics(), url=edited)]
        row = self.output()['per_post'][1]
        self.assertIsNone(row['published_at'])
        self.assertEqual(row['age_basis'], 'original_publication')
        self.assertEqual(row['age_publication_source']['url'], self.url)
        self.assertEqual(row['latest_owner_analytics']['age_seconds'], 60)

    def test_history_only_post_has_unknown_publication(self):
        self.data['posts'] = []
        self.data['analytics_observations'] = [self.analytics()]
        self.assertIsNone(self.output()['per_post'][0]['latest_owner_analytics']['age_seconds'])

    def test_identical_capture_is_deduplicated_without_zero_time_pair(self):
        self.data['analytics_observations'] = [self.analytics(), self.analytics(),
                                            self.analytics('2026-10-08T00:02:00Z', impressions=120)]
        output = self.output()
        self.assertEqual(len(output['per_post'][0]['owner_analytics']), 2)
        self.assertEqual(len(output['paired_intervals']), 1)

    def test_conflicting_same_time_and_reverse_time_are_rejected(self):
        for second in (self.analytics(engagements=99), self.analytics('2026-10-08T00:00:30Z')):
            with self.subTest(second=second):
                self.data['analytics_observations'] = [self.analytics(), second]
                with self.assertRaises(ValueError):
                    self.output()

    def test_equivalent_timezone_timestamps_conflict_at_same_instant(self):
        self.data['analytics_observations'] = [self.analytics(),
            self.analytics('2026-10-08T08:01:00+08:00', engagements=21)]
        with self.assertRaisesRegex(ValueError, 'same post timestamp'):
            self.output()

    def test_invalid_types_counters_urls_and_times_are_rejected(self):
        mutations = [
            lambda d: d.update(account='bad/name'),
            lambda d: d.update(posts={}),
            lambda d: d.update(analytics_observations={}),
            lambda d: d['analytics_observations'].append('bad'),
            lambda d: d['analytics_observations'][0].update(impressions=-1),
            lambda d: d['analytics_observations'][0].update(impressions=True),
            lambda d: d['analytics_observations'][0].update(engagements=2.5),
            lambda d: d['analytics_observations'][0].update(observed_at='2026-10-08T00:01:00'),
            lambda d: d['analytics_observations'][0].update(observed_at=None),
            lambda d: d['analytics_observations'][0].update(url=self.url + '?q=1'),
            lambda d: d['analytics_observations'][0].update(source=False),
            lambda d: d['posts'][0].update(published_at='2026-10-08T00:00:00'),
            lambda d: d['posts'][0].update(published_at='2026-10-08T00:02:00Z'),
            lambda d: d['posts'].append(copy.deepcopy(d['posts'][0])),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                data = copy.deepcopy(self.data)
                data['analytics_observations'] = [self.analytics()]
                mutate(data)
                with self.assertRaises(ValueError):
                    post_statistics.build_statistics(data)

    def test_no_components_are_added_to_engagements(self):
        self.data['analytics_observations'] = [self.analytics(engagements=1, detail_expands=50, profile_visits=50, link_clicks=50)]
        row = self.output()['per_post'][0]['latest_owner_analytics']
        self.assertEqual(row['counts']['engagements'], 1)
        self.assertEqual(row['event_ratios']['engagement_events_per_impression'], .01)

    def test_unproved_follow_count_remains_unknown(self):
        self.data['analytics_observations'] = [self.analytics(follows_attributed=2)]
        row = self.output()['per_post'][0]['latest_owner_analytics']
        self.assertIsNone(row['follows_attributed'])
        self.assertEqual(row['follows_attributed_reason'], 'attribution_evidence_missing')

    def test_explicit_follow_field_requires_same_capture_official_and_actual_evidence(self):
        proof = {'source': 'owner_analytics', 'field': 'follows_attributed', 'url': self.url,
                 'observed_at': '2026-10-08T00:01:00Z',
                 'official_metric_documentation': 'https://help.x.com/example-metric-definition',
                 'capture_evidence': 'Synthetic test fixture: explicit metric visible in this same capture.'}
        self.data['analytics_observations'] = [self.analytics(follows_attributed=2, follows_attributed_evidence=proof)]
        self.assertEqual(self.output()['per_post'][0]['latest_owner_analytics']['follows_attributed'], 2)
        for field, value in (('observed_at', '2026-10-08T00:02:00Z'), ('url', 'https://x.com/example_owner/status/789'),
                             ('official_metric_documentation', 'https://unofficial.example/metric'), ('capture_evidence', '')):
            with self.subTest(field=field):
                bad = copy.deepcopy(self.data)
                bad['analytics_observations'][0]['follows_attributed_evidence'][field] = value
                with self.assertRaises(ValueError):
                    post_statistics.build_statistics(bad)

    def test_cli_writes_requested_output(self):
        with tempfile.TemporaryDirectory(prefix='rise-post-stats-test-') as folder:
            source, output = Path(folder, 'metrics.json'), Path(folder, 'statistics.json')
            source.write_text(json.dumps(self.data))
            self.assertEqual(post_statistics.main([str(source), '--output', str(output)]), 0)
            self.assertEqual(json.loads(output.read_text())['account'], 'example_owner')


if __name__ == '__main__':
    unittest.main()
