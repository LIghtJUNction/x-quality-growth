import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import contribute as c


def repository(owner='alice', parent=c.UPSTREAM):
    result = {'full_name': f'{owner}/x-quality-growth', 'owner': {'login': owner},
              'private': False, 'visibility': 'public', 'default_branch': 'main',
              'fork': owner.lower() != 'lightjunction'}
    if result['fork']:
        result['parent'] = {'full_name': parent}
    return result


class ContributionTests(unittest.TestCase):
    def api(self, owner='alice', fork=True):
        values = {'user': {'login': owner}, f'repos/{c.UPSTREAM}': repository('LIghtJUNction'),
                  f'repos/{owner}/x-quality-growth': repository(owner) if fork else None}
        return lambda path, optional=False: copy.deepcopy(values[path])

    def state(self, dirty=False, branch='main', remote=False):
        return {'dirty': dirty, 'branch': branch, 'has_contributor': remote}

    def test_default_is_plan_and_never_creates_fork(self):
        with patch.object(c, 'api', side_effect=self.api(fork=False)), patch.object(c, 'command') as run:
            result = c.contribute()
        self.assertEqual(result['fork'], 'create_planned')
        run.assert_not_called()

    def test_sync_without_apply_is_still_read_only(self):
        with patch.object(c, 'api', side_effect=self.api()), patch.object(c, 'local_state', return_value=self.state()), patch.object(c, 'git') as git, patch.object(c, 'command') as run:
            result = c.contribute(sync=True)
        self.assertIn('fetch_planned', result['sync'])
        git.assert_not_called()
        run.assert_not_called()

    def test_missing_authenticated_identity_is_rejected(self):
        with patch.object(c, 'api', return_value={}), patch.object(c, 'command') as run:
            with self.assertRaisesRegex(ValueError, 'authenticated GitHub user'):
                c.contribute(apply=True)
        run.assert_not_called()

    def test_maintainer_does_not_fork_self(self):
        with patch.object(c, 'api', side_effect=self.api('LIghtJUNction')), patch.object(c, 'command') as run:
            result = c.contribute(apply=True)
        self.assertEqual(result['fork'], 'maintainer_self')
        run.assert_not_called()

    def test_maintainer_sync_fetches_without_duplicate_contributor_remote(self):
        calls = []
        def run(args, directory, check=True):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, 'abcdef\n' if args[0] == 'rev-parse' else '', '')
        with patch.object(c, 'api', side_effect=self.api('LIghtJUNction')), patch.object(c, 'local_state', return_value=self.state(dirty=True)), patch.object(c, 'git', side_effect=run):
            result = c.contribute(apply=True, sync=True)
        self.assertEqual(result['fork'], 'maintainer_self')
        self.assertEqual(result['sync'], 'fetched_only')
        self.assertIn(['fetch', '--no-tags', c.SOURCE_URL, 'refs/heads/main'], calls)
        self.assertFalse(any(args[:2] == ['remote', 'add'] for args in calls))

    def test_same_name_nonfork_wrong_parent_or_private_is_rejected(self):
        for changes in ({'fork': False}, {'parent': {'full_name': 'evil/x-quality-growth'}},
                        {'visibility': 'private', 'private': True}, {'owner': {'login': 'other'}}):
            bad = repository()
            bad.update(changes)
            lookup = self.api()
            def read(path, optional=False):
                return bad if path == 'repos/alice/x-quality-growth' else lookup(path, optional)
            with self.subTest(changes=changes), patch.object(c, 'api', side_effect=read), patch.object(c, 'command') as run:
                with self.assertRaises(ValueError):
                    c.contribute(apply=True)
                run.assert_not_called()

    def test_apply_fork_is_verified_after_creation(self):
        calls = 0
        lookup = self.api()
        def read(path, optional=False):
            nonlocal calls
            if path == 'repos/alice/x-quality-growth':
                calls += 1
                return None if calls == 1 else repository()
            return lookup(path, optional)
        with patch.object(c, 'api', side_effect=read), patch.object(c, 'command') as run:
            result = c.contribute(apply=True)
        self.assertEqual(result['fork'], 'created_and_verified')
        run.assert_called_once_with(['gh', 'repo', 'fork', c.UPSTREAM, '--clone=false', '--remote=false'])

    def test_unexpected_created_fork_is_rejected(self):
        lookup = self.api()
        calls = 0
        def read(path, optional=False):
            nonlocal calls
            if path == 'repos/alice/x-quality-growth':
                calls += 1
                return None if calls == 1 else repository(parent='wrong/repository')
            return lookup(path, optional)
        with patch.object(c, 'api', side_effect=read), patch.object(c, 'command'):
            with self.assertRaisesRegex(ValueError, 'exact upstream'):
                c.contribute(apply=True)

    def test_dirty_or_feature_branch_fetches_without_merge(self):
        for state in (self.state(dirty=True), self.state(branch='improve/topic')):
            calls = []
            def run(args, directory, check=True):
                calls.append(args)
                return subprocess.CompletedProcess(args, 0, 'abcdef\n' if args[0] == 'rev-parse' else '', '')
            with self.subTest(state=state), patch.object(c, 'api', side_effect=self.api()), patch.object(c, 'local_state', return_value=state), patch.object(c, 'git', side_effect=run):
                result = c.contribute(apply=True, sync=True)
            self.assertEqual(result['sync'], 'fetched_only')
            self.assertTrue(any(args[0] == 'fetch' for args in calls))
            self.assertFalse(any(args[0] == 'merge' for args in calls))
            self.assertFalse(any('reset' in args or '--force' in args for args in calls))

    def test_clean_main_merges_only_fetched_commit_and_never_pushes(self):
        calls = []
        def run(args, directory, check=True):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, 'abcdef\n' if args[0] == 'rev-parse' else '', '')
        with patch.object(c, 'api', side_effect=self.api()), patch.object(c, 'local_state', return_value=self.state(remote=True)), patch.object(c, 'git', side_effect=run):
            result = c.contribute(apply=True, sync=True)
        self.assertEqual(result['sync'], 'fast_forward_checked')
        self.assertIn(['merge', '--ff-only', 'abcdef'], calls)
        self.assertFalse(any(args[0] in ('push', 'reset', 'checkout') for args in calls))
        self.assertFalse(any(args[:2] == ['remote', 'add'] for args in calls))

    def test_diverged_branch_and_new_dirty_work_are_preserved(self):
        calls = []
        def run(args, directory, check=True):
            calls.append(args)
            code = 1 if args[0] == 'merge-base' else 0
            return subprocess.CompletedProcess(args, code, 'abcdef\n' if args[0] == 'rev-parse' else '', '')
        with patch.object(c, 'api', side_effect=self.api()), patch.object(c, 'local_state', return_value=self.state()), patch.object(c, 'git', side_effect=run):
            result = c.contribute(apply=True, sync=True)
        self.assertEqual(result['sync'], 'fetched_only')
        self.assertFalse(any(args[0] == 'merge' for args in calls))
        calls.clear()
        with patch.object(c, 'api', side_effect=self.api()), patch.object(c, 'local_state', side_effect=[self.state(), self.state(dirty=True)]), patch.object(c, 'git', side_effect=run):
            c.contribute(apply=True, sync=True)
        self.assertFalse(any(args[0] == 'merge' for args in calls))

    def test_local_collision_blocks_fork_creation_before_mutation(self):
        with patch.object(c, 'api', side_effect=self.api(fork=False)), patch.object(c, 'local_state', side_effect=ValueError('remote collision')), patch.object(c, 'command') as run:
            with self.assertRaisesRegex(ValueError, 'collision'):
                c.contribute(apply=True, sync=True)
        run.assert_not_called()

    def test_local_state_checks_both_fetch_and_push_urls(self):
        def run(args, directory, check=True):
            values = {('rev-parse', '--show-toplevel'): '/tmp/project', ('remote',): 'origin\ncontributor',
                      ('remote', 'get-url', '--all', 'origin'): c.SOURCE_URL,
                      ('remote', 'get-url', '--push', '--all', 'origin'): c.SOURCE_URL,
                      ('remote', 'get-url', '--all', 'contributor'): 'git@github.com:alice/x-quality-growth.git',
                      ('remote', 'get-url', '--push', '--all', 'contributor'): 'https://github.com/other/x-quality-growth.git'}
            return subprocess.CompletedProcess(args, 0, values[tuple(args)], '')
        with patch.object(c, 'git', side_effect=run):
            with self.assertRaisesRegex(ValueError, 'contributor remote'):
                c.local_state(Path('/tmp/project'), 'alice/x-quality-growth')

    def test_api_only_404_is_treated_as_absent_and_errors_hide_stderr(self):
        missing = subprocess.CompletedProcess([], 1, '', 'gh: Not Found (HTTP 404)')
        denied = subprocess.CompletedProcess([], 1, '', 'gh: denied token=SECRET (HTTP 403)')
        for response in (missing, denied):
            with self.subTest(response=response), patch.object(c.subprocess, 'run', return_value=response):
                if response is missing:
                    self.assertIsNone(c.api('repos/alice/x-quality-growth', optional=True))
                else:
                    with self.assertRaises(c.CommandError) as caught:
                        c.api('repos/alice/x-quality-growth', optional=True)
                    self.assertNotIn('SECRET', str(caught.exception))

    def test_github_urls_are_normalized_without_rewriting(self):
        for url in ('https://github.com/alice/x-quality-growth.git',
                    'git@github.com:alice/x-quality-growth.git',
                    'ssh://git@github.com/alice/x-quality-growth'):
            self.assertEqual(c.github_repo(url), 'alice/x-quality-growth')
        self.assertIsNone(c.github_repo('https://github.com.evil.test/alice/x-quality-growth'))


if __name__ == '__main__':
    unittest.main()
