#!/usr/bin/env python3
"""Report upstream revision drift without approving new algorithm semantics."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

REPOSITORY = 'https://github.com/xai-org/x-algorithm'


def git(source, *args, binary=False):
    return subprocess.check_output(['git', '-C', str(source), *args],
                                   text=not binary, timeout=30)


def review(source, manifest):
    if manifest.get('repository') != REPOSITORY or not re.fullmatch(r'[0-9a-f]{40}', manifest.get('commit', '')):
        raise ValueError('expected a pinned official algorithm manifest')
    origin = git(source, 'remote', 'get-url', 'origin').strip()
    if origin not in (REPOSITORY, REPOSITORY + '.git', 'git@github.com:xai-org/x-algorithm.git'):
        raise ValueError('source must use the official algorithm origin')
    if git(source, 'status', '--porcelain', '--untracked-files=all').strip():
        raise ValueError('source checkout must be clean')
    current = git(source, 'rev-parse', 'HEAD').strip()
    if not re.fullmatch(r'[0-9a-f]{40}', current):
        raise ValueError('invalid source commit')
    old = manifest['commit']
    if current == old:
        return {'upstream_changed': False, 'reviewed_commit': old, 'upstream_commit': current}, None
    paths = set(git(source, 'ls-tree', '-r', '--name-only', '-z', current).split('\0'))
    rows = []
    seen = set()
    for record in manifest['files']:
        name = record['path']
        parsed = PurePosixPath(name)
        if parsed.is_absolute() or '..' in parsed.parts or name in seen or not re.fullmatch(r'[a-zA-Z0-9_./-]+', name):
            raise ValueError('invalid or duplicate evidence path')
        if not re.fullmatch(r'[0-9a-f]{64}', record['sha256']):
            raise ValueError('invalid evidence hash')
        seen.add(name)
        if name not in paths:
            status, new_hash = 'DELETED', '—'
        else:
            new_hash = hashlib.sha256(git(source, 'show', f'{current}:{name}', binary=True)).hexdigest()
            status = 'UNCHANGED' if new_hash == record['sha256'] else 'CHANGED'
        rows.append((name, status, record['sha256'], new_hash))
    if not rows:
        raise ValueError('manifest must contain evidence files')
    report = '\n'.join([
        '# Pending upstream algorithm review', '',
        '**未完成语义复核 / Semantic review is pending.**', '',
        'This report detects a new official source revision. It does not approve changed defaults, execution paths, or growth strategies.',
        'The reviewed manifest and strategy remain unchanged. No production behavior or follower-growth result is inferred.', '',
        f'- Reviewed: [`{old}`]({REPOSITORY}/commit/{old})',
        f'- New source: [`{current}`]({REPOSITORY}/commit/{current})',
        f'- Full upstream diff: [compare revisions]({REPOSITORY}/compare/{old}...{current})',
        f'- Bound files compared: {len(rows)}. Files outside this evidence set also require review when relevant.', '',
        '| Bound source file | Status | Reviewed SHA-256 | New SHA-256 |',
        '| --- | --- | --- | --- |',
        *[f'| [{name}]({REPOSITORY}/blob/{old if status == "DELETED" else current}/{name}) | {status} | `{old_hash}` | `{new_hash}` |'
          for name, status, old_hash, new_hash in rows], '',
        'Before accepting the source revision, inspect changed/deleted files and their callers, recompute pinned evidence, update algorithm conclusions, and run validation.',
        'An unchanged hash set does not prove unchanged behavior: dependencies and configuration outside this set may have changed.', '',
    ])
    return {'upstream_changed': True, 'reviewed_commit': old, 'upstream_commit': current,
            'changed_files': sum(r[1] == 'CHANGED' for r in rows),
            'deleted_files': sum(r[1] == 'DELETED' for r in rows),
            'compared_files': len(rows)}, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--manifest', type=Path, default=Path('references/upstream.json'))
    parser.add_argument('--output', type=Path, default=Path('references/pending-upstream-review.md'))
    args = parser.parse_args()
    try:
        result, report = review(args.source, json.loads(args.manifest.read_text()))
        changed = report is not None and (not args.output.exists() or args.output.read_text() != report)
        if changed:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report)
        result['report_changed'] = changed
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, f'Cannot review upstream: {error}\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
