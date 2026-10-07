import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import update_github_stats


class GitHubStatsTests(unittest.TestCase):
    def setUp(self):
        self.repository = 'LIghtJUNction/x-quality-growth'
        self.response = {'full_name': self.repository,
                         'html_url': 'https://github.com/' + self.repository,
                         'stargazers_count': 3, 'forks_count': 2}

    def test_invalid_counters_and_wrong_repository_are_rejected(self):
        for key, value in [('stargazers_count', -1), ('forks_count', True),
                           ('forks_count', '2'), ('full_name', 'other/repo'),
                           ('html_url', 'https://evil.example/')]:
            with self.subTest(key=key, value=value):
                response = copy.deepcopy(self.response)
                response[key] = value
                with self.assertRaises(ValueError):
                    update_github_stats.github_observation(response, self.repository, 'now')

    def test_refresh_preserves_all_x_fields_and_timestamps(self):
        recorded = {'account': 'LIghtJUNction_x', 'github': {},
                    'follower_observations': [{'total': 221, 'observed_at': 'original'}],
                    'blue_observations': [{'count': 100, 'observed_at': 'blue-original'}],
                    'posts': [{'url': 'x-proof', 'observed_at': 'post-original'}],
                    'progress_updates': [{'reported_profile_observation': 'progress-original'}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'public').mkdir()
            path = root / 'public/metrics.json'
            path.write_text(json.dumps(recorded))
            with patch.object(update_github_stats, 'ROOT', root), \
                 patch.dict('os.environ', {'GITHUB_REPOSITORY': self.repository, 'GITHUB_TOKEN': ''}), \
                 patch.object(update_github_stats, 'urlopen', return_value=io.StringIO(json.dumps(self.response))):
                update_github_stats.main()
            result = json.loads(path.read_text())
            self.assertEqual(result['github']['stars'], 3)
            result.pop('github')
            recorded.pop('github')
            self.assertEqual(result, recorded)

    def test_bad_api_response_does_not_mutate_recorded_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'public').mkdir()
            path = root / 'public/metrics.json'
            original = '{"github": {"stars": 1}}'
            path.write_text(original)
            response = dict(self.response, forks_count=-1)
            with patch.object(update_github_stats, 'ROOT', root), \
                 patch.dict('os.environ', {'GITHUB_REPOSITORY': self.repository, 'GITHUB_TOKEN': ''}), \
                 patch.object(update_github_stats, 'urlopen', return_value=io.StringIO(json.dumps(response))):
                with self.assertRaises(ValueError):
                    update_github_stats.main()
            self.assertEqual(path.read_text(), original)


if __name__ == '__main__':
    unittest.main()
