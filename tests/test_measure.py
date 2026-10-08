import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from measure import compare


def row(uid, handle, badge='blue', quality='unknown'):
    q = {'status': quality}
    if quality == 'high':
        q.update(relevant=True, original=True, substantive=True,
                 evidence=[f'https://x.com/{handle}/status/123'])
    return {'id': uid, 'handle': handle, 'badge': badge, 'quality': q}


def snap(rows, hour=0, **kwargs):
    return dict(account='owner', observed_at=f'2026-10-08T{hour:02}:00:00+08:00',
                scope='all_followers', complete=True, evidence='synthetic fixture',
                total_followers=len(rows), followers=rows, posts={}, **kwargs)


class MeasurementTests(unittest.TestCase):
    def test_growth_upgrade_churn_and_unknown_denominator(self):
        before = snap([row('1', 'old'), row('2', 'upgrade', 'none')])
        after = snap([row('2', 'upgrade'), row('3', 'high', quality='high'),
                      row('4', 'unknown'), row('5', 'gold', 'gold')], 1)
        r = compare(before, after)
        self.assertEqual(r['confirmed_new_blue'], 2)
        self.assertEqual(r['quality_share'], .5)
        self.assertEqual(r['quality_possible_range'], [.5, 1])
        self.assertEqual(r['existing_became_blue'], 1)
        self.assertEqual(r['confirmed_blue_follower_departures'], 1)
        self.assertIsNone(r['quality_share_wilson95'])

    def test_zero_growth_not_zero_quality(self):
        a, b = snap([]), snap([], 1)
        a['collection_started_at'] = a['observed_at']
        b['collection_started_at'] = b['observed_at']
        r = compare(a, b)
        self.assertEqual(r['confirmed_new_blue'], 0)
        self.assertIsNone(r['quality_share'])
        self.assertIsNone(r['full_window_quality_share'])
        self.assertEqual(r['quality_share_denominator_count'], 0)

    def test_partial_list_never_claims_exact_growth(self):
        a, b = snap([]), snap([row('1', 'new')], 1)
        a['complete'] = False
        r = compare(a, b)
        self.assertIsNone(r['confirmed_new_blue'])
        self.assertEqual(r['observed_blue_arrivals'], 1)

    def test_two_captured_high_events_in_partial_lists_are_not_full_window_100_percent(self):
        for partial_side in ('before', 'after'):
            with self.subTest(partial_side=partial_side):
                a, b = snap([]), snap([row('1', 'one', quality='high'),
                                      row('2', 'two', quality='high')], 1)
                a['collection_started_at'] = a['observed_at']
                b['collection_started_at'] = b['observed_at']
                partial = a if partial_side == 'before' else b
                partial.update(complete=False, total_followers=len(partial['followers']) + 2)
                r = compare(a, b)
                self.assertEqual(r['quality_share'], 1)
                self.assertEqual(r['quality_share_scope'], 'captured_blue_arrival_events')
                self.assertEqual(r['quality_share_denominator_count'], 2)
                self.assertEqual(r['quality_share_status'], 'complete')
                self.assertTrue(r['quality_classification_complete'])
                self.assertFalse(r['coverage_complete'])
                self.assertIsNone(r['confirmed_new_blue'])
                self.assertIsNone(r['full_window_quality_share'])
                self.assertIsNone(r['full_window_quality_share_kind'])
                self.assertTrue(any('captured blue arrival events only' in w for w in r['warnings']))

    def test_complete_all_followers_with_known_ids_times_and_quality_has_full_window_share(self):
        a = snap([row('1', 'existing', badge='none')])
        b = snap([row('1', 'existing'), row('2', 'new_high', quality='high'),
                  row('3', 'new_unmatched', quality='not_high')], 1)
        a['collection_started_at'] = a['observed_at']
        b['collection_started_at'] = b['observed_at']
        r = compare(a, b)
        self.assertTrue(r['coverage_complete'])
        self.assertEqual(r['existing_became_blue'], 1)
        self.assertEqual(r['confirmed_new_blue'], 2)
        self.assertEqual(r['quality_share_denominator_count'], 2)
        self.assertEqual(r['quality_share'], .5)
        self.assertEqual(r['full_window_quality_share'], .5)
        self.assertEqual(r['full_window_quality_share_kind'], 'confirmed_new_blue')

    def test_complete_selected_lists_with_handle_or_verified_scope_have_no_full_window_share(self):
        for mode in ('handle', 'verified'):
            with self.subTest(mode=mode):
                a, b = snap([]), snap([row('1', 'new', quality='high')], 1)
                a['collection_started_at'] = a['observed_at']
                b['collection_started_at'] = b['observed_at']
                if mode == 'handle':
                    del b['followers'][0]['id']
                else:
                    a['scope'] = b['scope'] = 'verified_followers'
                r = compare(a, b)
                self.assertTrue(r['coverage_complete'])
                self.assertEqual(r['quality_share'], 1)
                self.assertEqual(r['quality_share_kind'], 'observed_arrivals_only')
                self.assertIsNone(r['confirmed_new_blue'])
                self.assertIsNone(r['full_window_quality_share'])

    def test_full_window_share_requires_complete_badge_quality_and_collection_times(self):
        for missing_evidence in ('badge', 'quality', 'before_start', 'after_start'):
            with self.subTest(missing_evidence=missing_evidence):
                a, b = snap([]), snap([row('1', 'high', quality='high'),
                                      row('2', 'other', quality='high')], 1)
                a['collection_started_at'] = a['observed_at']
                b['collection_started_at'] = b['observed_at']
                if missing_evidence == 'badge':
                    b['followers'][1]['badge'] = 'unknown'
                elif missing_evidence == 'quality':
                    b['followers'][1]['quality'] = {'status': 'unknown'}
                elif missing_evidence == 'before_start':
                    del a['collection_started_at']
                else:
                    del b['collection_started_at']
                r = compare(a, b)
                self.assertTrue(r['coverage_complete'])
                self.assertTrue(r['exact_follower_comparison'])
                self.assertIsNone(r['full_window_quality_share'])
                self.assertIsNone(r['full_window_quality_share_kind'])

    def test_verified_only_upgrade_ambiguity(self):
        a, b = snap([]), snap([row('1', 'new')], 1)
        a['scope'] = b['scope'] = 'verified_followers'
        self.assertIsNone(compare(a, b)['confirmed_new_blue'])

    def test_stable_id_rename_is_not_growth(self):
        self.assertEqual(compare(snap([row('1', 'before')]),
                                 snap([row('1', 'after')], 1))['confirmed_new_blue'], 0)

    def test_handle_only_is_unconfirmed(self):
        r1, r2 = row('1', 'before'), row('2', 'after')
        del r1['id'], r2['id']
        self.assertIsNone(compare(snap([r1]), snap([r2], 1))['confirmed_new_blue'])

    def test_mixed_identity_rejected(self):
        r = row('2', 'new')
        del r['id']
        with self.assertRaisesRegex(ValueError, 'mixed identity'):
            compare(snap([row('1', 'old')]), snap([r], 1))

    def test_wrong_account_time_scope_and_total_rejected(self):
        a, b = snap([]), snap([], 1)
        for field, value in [('account', 'other'), ('observed_at', a['observed_at']),
                             ('scope', 'verified_followers'), ('total_followers', 1)]:
            bad = copy.deepcopy(b)
            bad[field] = value
            with self.assertRaises(ValueError):
                compare(a, bad)

    def test_quality_requires_evidence(self):
        r = row('1', 'high', quality='high')
        r['quality']['evidence'] = []
        with self.assertRaisesRegex(ValueError, 'evidence'):
            compare(snap([]), snap([r], 1))

    def test_duplicates_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            compare(snap([]), snap([row('1', 'one'), row('1', 'two')], 1))

    def test_feedback_unavailable_and_decreased(self):
        a, b = snap([]), snap([], 1)
        url = 'https://x.com/owner/status/123'
        a['posts'][url] = dict(likes=2, replies=0, views=10, bookmarks=None)
        b['posts'][url] = dict(likes=4, replies=1, views=9, bookmarks=2)
        p = compare(a, b)['post_feedback'][url]
        self.assertEqual(p['likes']['delta'], 2)
        self.assertIsNone(p['views']['delta'])
        self.assertIsNone(p['bookmarks']['delta'])

    def test_complete_quality_has_uncertainty_interval(self):
        r = compare(snap([]), snap([row('1', 'high', quality='high')], 1))
        self.assertEqual(r['quality_share'], 1)
        self.assertLess(r['quality_share_wilson95'][0], .5)

    def test_no_quality_defaults_to_unknown(self):
        r = row('1', 'new')
        del r['quality']
        self.assertEqual(compare(snap([]), snap([r], 1))['unknown_quality_arrivals'], 1)

    def test_unknown_quality_is_labelled_as_lower_bound(self):
        r = compare(snap([]), snap([row('1', 'new')], 1))
        self.assertEqual(r['quality_share'], 0)
        self.assertEqual(r['quality_share_status'], 'lower_bound')
        self.assertFalse(r['quality_classification_complete'])
        self.assertEqual(r['quality_possible_range'], [0, 1])

    def test_unknown_badge_is_not_upgrade_or_downgrade(self):
        a = snap([row('1', 'one', 'unknown'), row('2', 'two')])
        b = snap([row('1', 'one'), row('2', 'two', 'unknown')], 1)
        r = compare(a, b)
        self.assertEqual(r['existing_became_blue'], 0)
        self.assertEqual(r['existing_no_longer_blue'], 0)
        self.assertEqual(r['unresolved_existing_badge_transitions'], 2)
        self.assertIsNone(r['blue_membership_net'])

    def test_permalink_aliases_measure_same_post(self):
        a, b = snap([]), snap([], 1)
        a['posts']['https://twitter.com/owner/status/123?s=20'] = {'likes': 2}
        url = 'https://x.com/i/web/status/123'
        b['posts'][url] = {'likes': 5}
        r = compare(a, b)['post_feedback']
        self.assertEqual(len(r), 1)
        self.assertEqual(r[url]['likes']['delta'], 3)

    def test_duplicate_aliases_and_nonpost_urls_are_rejected(self):
        for url in ('https://x.com/owner', 'https://x.com/owner/status/abc',
                    'https://x.com.evil.test/owner/status/123'):
            b = snap([], 1)
            b['posts'][url] = {'likes': 2}
            with self.assertRaisesRegex(ValueError, 'status URL'):
                compare(snap([]), b)
        b = snap([], 1)
        b['posts'] = {'https://x.com/owner/status/123': {'likes': 2},
                      'https://twitter.com/renamed/status/123': {'likes': 3}}
        with self.assertRaisesRegex(ValueError, 'duplicate post'):
            compare(snap([]), b)

    def test_stale_post_observation_does_not_invent_feedback(self):
        a, b = snap([]), snap([], 1)
        url = 'https://x.com/owner/status/123'
        a['posts'][url] = {'likes': 1}
        b['posts'][url] = {'likes': 3, 'observed_at': a['observed_at']}
        r = compare(a, b)['post_feedback'][url]
        self.assertIsNone(r['likes']['delta'])
        self.assertIn('time did not advance', r['likes']['reason'])
        self.assertEqual(r['observation_window']['to'], a['observed_at'])

    def test_post_time_window_is_preserved_and_future_time_rejected(self):
        a, b = snap([]), snap([], 2)
        url = 'https://x.com/owner/status/123'
        a['posts'][url] = {'likes': 1}
        b['posts'][url] = {'likes': 3, 'observed_at': '2026-10-08T01:00:00+08:00'}
        p = compare(a, b)['post_feedback'][url]
        self.assertEqual(p['likes']['delta'], 2)
        self.assertEqual(p['observation_window']['to'], b['posts'][url]['observed_at'])
        b['posts'][url]['observed_at'] = '2026-10-08T03:00:00+08:00'
        with self.assertRaisesRegex(ValueError, 'later than snapshot'):
            compare(a, b)

    def test_overlapping_collection_windows_are_unconfirmed(self):
        a, b = snap([]), snap([row('1', 'new', quality='high')], 2)
        a['observed_at'] = '2026-10-08T01:00:00+08:00'
        a['collection_started_at'] = a['observed_at']
        b['collection_started_at'] = '2026-10-08T00:30:00+08:00'
        r = compare(a, b)
        self.assertIsNone(r['confirmed_new_blue'])
        self.assertEqual(r['observed_blue_arrivals'], 1)
        self.assertFalse(r['coverage_complete'])
        self.assertIsNone(r['full_window_quality_share'])
        self.assertTrue(any('windows overlap' in warning for warning in r['warnings']))
        b['collection_started_at'] = '2026-10-08T03:00:00+08:00'
        with self.assertRaisesRegex(ValueError, 'collection_started_at'):
            compare(a, b)

    def test_noncanonical_ids_are_rejected(self):
        for uid in ('0', '01', '١٢٣'):
            with self.assertRaisesRegex(ValueError, 'canonical positive'):
                compare(snap([]), snap([row(uid, 'new')], 1))

    def test_rubric_changes_are_not_comparable(self):
        a, b = snap([]), snap([], 1)
        b['quality_rubric'] = 'changed-after-results'
        with self.assertRaisesRegex(ValueError, 'rubrics'):
            compare(a, b)

    def test_malformed_objects_rejected_cleanly(self):
        for invalid in ([], None, 'bad'):
            with self.assertRaises(ValueError):
                compare(invalid, snap([], 1))
        r = row('1', 'new')
        r['quality'] = 'high'
        with self.assertRaises(ValueError):
            compare(snap([]), snap([r], 1))


if __name__ == '__main__':
    unittest.main()
