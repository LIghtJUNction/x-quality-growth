#!/usr/bin/env python3
"""Inspect a personal RISE fork; --apply permits creation, --sync local fetching.

Uses authenticated gh without reading or printing credentials. Never pushes,
resets, switches branches, or creates PRs. JSON stdout is safe to review.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

UPSTREAM = 'LIghtJUNction/x-quality-growth'
SOURCE_URL = f'https://github.com/{UPSTREAM}.git'
ROOT = Path(__file__).resolve().parents[1]


class CommandError(ValueError):
    def __init__(self, args, result):
        self.returncode = result.returncode
        self.not_found = 'HTTP 404' in result.stderr or '(404)' in result.stderr
        # Do not expose command stderr: gh/git errors can include credentials.
        super().__init__(f'{args[0]} command failed (exit {result.returncode})')


def command(args, cwd=None, check=True):
    try:
        result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    except OSError:
        raise ValueError(f'{args[0]} unavailable') from None
    if check and result.returncode:
        raise CommandError(args, result)
    return result


def api(path, optional=False):
    try:
        return json.loads(command(['gh', 'api', path]).stdout)
    except CommandError as error:
        if optional and error.not_found:
            return None
        raise
    except json.JSONDecodeError:
        raise ValueError('gh returned invalid JSON') from None


def validate_repository(repo, owner, fork):
    expected = f'{owner}/x-quality-growth'
    if not isinstance(repo, dict) or repo.get('full_name', '').lower() != expected.lower():
        raise ValueError('repository identity does not match requested owner/name')
    if repo.get('owner', {}).get('login', '').lower() != owner.lower():
        raise ValueError('repository owner does not match authenticated account')
    if repo.get('private') is not False or repo.get('visibility') != 'public':
        raise ValueError('repository must be public; visibility mismatch')
    if fork and (repo.get('fork') is not True or
                 repo.get('parent', {}).get('full_name', '').lower() != UPSTREAM.lower()):
        raise ValueError('same-name repository is not a fork of the exact upstream')
    return repo


def github_repo(url):
    """Only recognized GitHub URLs match; never rewrite arbitrary remotes."""
    match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?', url)
    return match.group(1).lower() if match else None


def git(args, directory, check=True):
    return command(['git', *args], cwd=directory, check=check)


def local_state(directory, personal):
    git(['rev-parse', '--show-toplevel'], directory)
    remotes = {}
    for name in git(['remote'], directory).stdout.splitlines():
        # All fetch/push URLs must agree; preserve extra URLs and fail closed.
        urls = git(['remote', 'get-url', '--all', name], directory).stdout.splitlines()
        pushes = git(['remote', 'get-url', '--push', '--all', name], directory).stdout.splitlines()
        remotes[name] = urls + pushes
    allowed = {UPSTREAM.lower(), personal.lower()}
    if not any(github_repo(url) in allowed for urls in remotes.values() for url in urls):
        raise ValueError('local repository has no remote for this upstream or validated personal fork')
    if 'contributor' in remotes and any(github_repo(url) != personal.lower() for url in remotes['contributor']):
        raise ValueError('existing contributor remote points elsewhere; refusing to replace it')
    return {
        'dirty': bool(git(['status', '--porcelain'], directory).stdout),
        'branch': git(['branch', '--show-current'], directory).stdout.strip(),
        'has_contributor': 'contributor' in remotes,
    }


def contribute(apply=False, sync=False, repo_path=ROOT):
    user = api('user')
    owner = user.get('login') if isinstance(user, dict) else None
    if not isinstance(owner, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', owner):
        raise ValueError('cannot establish authenticated GitHub user')
    upstream = validate_repository(api(f'repos/{UPSTREAM}'), UPSTREAM.split('/')[0], False)
    branch = upstream.get('default_branch')
    if not isinstance(branch, str) or not branch or branch.startswith('-'):
        raise ValueError('upstream default branch is invalid')
    personal = f'{owner}/x-quality-growth'
    maintainer = owner.lower() == UPSTREAM.split('/')[0].lower()
    fork = upstream if maintainer else api(f'repos/{personal}', optional=True)
    if fork is not None:
        validate_repository(fork, owner, not maintainer)
    # Inspect local collisions before creating a remote public repository.
    state = local_state(repo_path, personal) if sync else None
    result = {'account': owner, 'upstream': UPSTREAM, 'repository': personal,
              'mode': 'apply' if apply else 'plan',
              'fork': 'maintainer_self' if maintainer else 'reuse' if fork else 'create_planned',
              'sync': 'not_requested', 'pr': 'not_automated'}
    if fork is None and apply:
        command(['gh', 'repo', 'fork', UPSTREAM, '--clone=false', '--remote=false'])
        fork = validate_repository(api(f'repos/{personal}'), owner, True)
        result['fork'] = 'created_and_verified'
    if sync:
        result['local'] = state
        result['sync'] = 'fetch_planned; merge only on clean upstream default branch'
        if apply:
            if not maintainer and not state['has_contributor']:
                git(['remote', 'add', 'contributor', f'https://github.com/{personal}.git'], repo_path)
            git(['fetch', '--no-tags', SOURCE_URL, f'refs/heads/{branch}'], repo_path)
            fetched = git(['rev-parse', 'FETCH_HEAD'], repo_path).stdout.strip()
            current = local_state(repo_path, personal)
            result['local'] = current
            result['sync'] = 'fetched_only'
            if current['dirty']:
                result['reason'] = 'working tree is dirty; no merge'
            elif current['branch'] != branch:
                result['reason'] = 'not on upstream default branch; no merge'
            else:
                ancestry = git(['merge-base', '--is-ancestor', 'HEAD', fetched], repo_path, check=False)
                if ancestry.returncode == 1:
                    result['reason'] = 'local HEAD is not an ancestor of upstream; no merge'
                elif ancestry.returncode:
                    raise CommandError(['git'], ancestry)
                else:
                    # ff-only rechecks ancestry and refuses diverged concurrent work.
                    git(['merge', '--ff-only', fetched], repo_path)
                    result['sync'] = 'fast_forward_checked'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='permit fork creation and requested local synchronization')
    parser.add_argument('--sync', action='store_true', help='inspect local remotes; with --apply fetch upstream and conditionally fast-forward')
    parser.add_argument('--repo-path', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = contribute(args.apply, args.sync, args.repo_path)
    except (ValueError, OSError, TypeError, KeyError) as error:
        parser.exit(2, f'Contribution check failed: {error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
