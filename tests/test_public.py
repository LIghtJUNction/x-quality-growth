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


if __name__ == '__main__':
    unittest.main()
