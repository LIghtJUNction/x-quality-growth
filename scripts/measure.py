#!/usr/bin/env python3
"""Compare authorized, locally collected follower snapshots. No X/network access."""
import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

BADGES = {'blue', 'gold', 'gray', 'none', 'unknown'}
COUNTERS = ('replies', 'likes', 'reposts', 'bookmarks', 'views')


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('observed_at must be an ISO timestamp string')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('observed_at requires a timezone')
    return dt


def identity(row):
    return 'id:' + row['id'] if row.get('id') else 'handle:' + row['handle'].lower()


def post_identity(url):
    """A permalink alias is not a different post; never match by display text."""
    if not isinstance(url, str):
        raise ValueError('post key must be an X status URL')
    parsed = urlsplit(url)
    match = re.fullmatch(r'/(?:[A-Za-z0-9_]{1,15}|i/web)/status/([1-9][0-9]*)/?', parsed.path)
    if parsed.scheme != 'https' or parsed.netloc not in ('x.com', 'twitter.com') or not match:
        raise ValueError('post key must be an X status URL')
    return match.group(1)


def post_observations(snapshot):
    return {post_identity(url): (url, metrics) for url, metrics in snapshot.get('posts', {}).items()}


def validate(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError('snapshot must be an object')
    if not isinstance(snapshot.get('account'), str) or not snapshot['account']:
        raise ValueError('account required')
    timestamp(snapshot['observed_at'])
    if 'collection_started_at' in snapshot and timestamp(snapshot['collection_started_at']) > timestamp(snapshot['observed_at']):
        raise ValueError('collection_started_at cannot be later than observed_at')
    if snapshot.get('scope') not in ('all_followers', 'verified_followers'):
        raise ValueError('invalid scope')
    if type(snapshot.get('complete')) is not bool:
        raise ValueError('complete must be boolean')
    if snapshot['complete'] and not snapshot.get('evidence'):
        raise ValueError('complete snapshots require collection evidence')
    rows = snapshot['followers']
    if not isinstance(rows, list):
        raise ValueError('followers must be a list')
    handles, ids = set(), set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('follower must be an object')
        handle = row.get('handle', '')
        if not isinstance(handle, str) or not re.fullmatch(r'[A-Za-z0-9_]{1,15}', handle):
            raise ValueError('invalid handle')
        handle = handle.lower()
        if handle in handles:
            raise ValueError('duplicate handle')
        handles.add(handle)
        if row.get('id') is not None:
            if not isinstance(row['id'], str) or not re.fullmatch(r'[1-9][0-9]*', row['id']):
                raise ValueError('id must be a canonical positive numeric string')
            if row['id'] in ids:
                raise ValueError('duplicate id')
            ids.add(row['id'])
        if row.get('badge') not in BADGES:
            raise ValueError('invalid badge')
        q = row.get('quality', {'status': 'unknown'})
        if not isinstance(q, dict):
            raise ValueError('quality must be an object')
        if q.get('status') not in ('high', 'not_high', 'unknown'):
            raise ValueError('invalid quality status')
        if q['status'] == 'high':
            if not all(q.get(k) is True for k in ('relevant', 'original', 'substantive')):
                raise ValueError('high requires all three rubric criteria')
            evidence = q.get('evidence')
            if not isinstance(evidence, list) or not evidence or not all(
                isinstance(u, str) and u.startswith(('https://x.com/', 'https://twitter.com/'))
                for u in evidence
            ):
                raise ValueError('high requires public X evidence URLs')
    total = snapshot.get('total_followers')
    if total is not None and (type(total) is not int or total < 0):
        raise ValueError('invalid total_followers')
    if snapshot['complete'] and snapshot['scope'] == 'all_followers' and total != len(rows):
        raise ValueError('complete all_followers must match total_followers')
    if not isinstance(snapshot.get('posts', {}), dict):
        raise ValueError('posts must be an object')
    post_ids = set()
    for url, metrics in snapshot.get('posts', {}).items():
        post_id = post_identity(url)
        if post_id in post_ids:
            raise ValueError('duplicate post identity through permalink aliases')
        post_ids.add(post_id)
        if not isinstance(metrics, dict):
            raise ValueError('post metrics must be an object')
        if 'observed_at' in metrics and timestamp(metrics['observed_at']) > timestamp(snapshot['observed_at']):
            raise ValueError('post observed_at cannot be later than snapshot observed_at')
        for key in COUNTERS:
            v = metrics.get(key)
            if v is not None and (type(v) is not int or v < 0):
                raise ValueError('counters must be nonnegative integers or null')


def wilson(high, count):
    if not count:
        return None
    z = 1.959963984540054
    p, den = high / count, 1 + z * z / count
    center = (p + z * z / (2 * count)) / den
    radius = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / den
    return [max(0, center - radius), min(1, center + radius)]


def compare(before, after):
    validate(before)
    validate(after)
    if before['account'].lower() != after['account'].lower():
        raise ValueError('cannot compare different accounts')
    if before['scope'] != after['scope']:
        raise ValueError('cannot compare different list scopes')
    if before.get('quality_rubric', 'public-v1') != after.get('quality_rubric', 'public-v1'):
        raise ValueError('cannot compare different quality rubrics')
    if timestamp(after['observed_at']) <= timestamp(before['observed_at']):
        raise ValueError('after must be later than before')
    old = {identity(r): r for r in before['followers']}
    new = {identity(r): r for r in after['followers']}
    # Do not mix ID and handle matching silently. It would invent arrivals.
    modes = {k.split(':', 1)[0] for k in old | new}
    if len(modes) > 1:
        raise ValueError('mixed identity modes; reconcile stable IDs before comparison')
    old_blue = {k for k, r in old.items() if r['badge'] == 'blue'}
    new_blue = {k for k, r in new.items() if r['badge'] == 'blue'}
    arrivals = sorted(new_blue - old.keys())
    departures = sorted(old_blue - new.keys())
    upgrades = sorted(k for k in new_blue & old.keys() if old[k]['badge'] not in ('blue', 'unknown'))
    downgraded = sorted(k for k in old_blue & new.keys() if new[k]['badge'] not in ('blue', 'unknown'))
    unresolved_badges = sorted(k for k in old.keys() & new.keys()
                              if (old[k]['badge'] == 'unknown' and new[k]['badge'] == 'blue')
                              or (old[k]['badge'] == 'blue' and new[k]['badge'] == 'unknown'))
    n = len(arrivals)
    high = sum(new[k].get('quality', {}).get('status', 'unknown') == 'high' for k in arrivals)
    unknown = sum(new[k].get('quality', {}).get('status', 'unknown') == 'unknown' for k in arrivals)
    overlapping = timestamp(after.get('collection_started_at', after['observed_at'])) < timestamp(before['observed_at'])
    exact = (before['complete'] and after['complete'] and not overlapping
             and before['scope'] == 'all_followers' and modes <= {'id'})
    known_badges = all(r['badge'] != 'unknown' for r in before['followers'] + after['followers'])
    warnings = []
    if not before['complete'] or not after['complete']:
        warnings.append('partial lists: absence does not establish a new follower or churn')
    if overlapping:
        warnings.append('collection windows overlap: snapshot changes cannot establish distinct follower arrivals')
    if before['scope'] == 'verified_followers':
        warnings.append('verified-only lists: old followers gaining a badge may look new')
    if 'handle' in modes:
        warnings.append('handle-only identity: renames cannot be ruled out')
    if unknown:
        warnings.append('quality classification incomplete: quality_share is a lower bound, not a final ratio')
    if unresolved_badges:
        warnings.append('unknown badges: some existing follower badge transitions cannot be established')
    posts = {}
    old_posts, new_posts = post_observations(before), post_observations(after)
    for post_id in sorted(old_posts.keys() | new_posts.keys()):
        old_url, old_metrics = old_posts.get(post_id, (None, {}))
        new_url, new_metrics = new_posts.get(post_id, (None, {}))
        url = new_url or old_url
        start = old_metrics.get('observed_at', before['observed_at']) if old_url else None
        end = new_metrics.get('observed_at', after['observed_at']) if new_url else None
        post = {'observation_window': {'from': start, 'to': end}}
        for key in COUNTERS:
            b = old_metrics.get(key)
            a = new_metrics.get(key)
            if a is None or b is None:
                post[key] = {'delta': None, 'reason': 'unavailable or missing baseline'}
            elif timestamp(end) <= timestamp(start):
                post[key] = {'delta': None, 'reason': 'post observation time did not advance'}
            elif a < b:
                post[key] = {'delta': None, 'reason': 'counter decreased; reconcile observations'}
            else:
                post[key] = {'delta': a - b}
        posts[url] = post
    return {
        'account': after['account'], 'from': before['observed_at'], 'to': after['observed_at'],
        'scope': after['scope'], 'exact_follower_comparison': exact,
        'confirmed_new_blue': n if exact else None,
        'observed_blue_arrivals': n, 'arrival_identities': arrivals,
        'confirmed_blue_follower_departures': len(departures) if exact else None,
        'observed_blue_departures': len(departures), 'departure_identities': departures,
        'existing_became_blue': len(upgrades), 'existing_no_longer_blue': len(downgraded),
        'unresolved_existing_badge_transitions': len(unresolved_badges),
        'blue_membership_net': len(new_blue) - len(old_blue) if exact and known_badges else None,
        'confirmed_high_quality_new_blue': high if exact else None,
        'observed_high_quality_arrivals': high, 'unknown_quality_arrivals': unknown,
        'quality_classification_complete': unknown == 0,
        'quality_share_status': 'undefined' if not n else 'lower_bound' if unknown else 'complete',
        'quality_share': high / n if n else None,
        'quality_share_kind': 'confirmed_new_blue' if exact else 'observed_arrivals_only',
        'quality_possible_range': [high / n, (high + unknown) / n] if n else None,
        'quality_share_wilson95': wilson(high, n) if exact and unknown == 0 else None,
        'post_feedback': posts, 'causal_attribution': 'not established', 'warnings': warnings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    args = parser.parse_args()
    try:
        result = compare(json.loads(args.before.read_text()), json.loads(args.after.read_text()))
    except (ValueError, KeyError, TypeError, OSError) as e:
        parser.exit(2, f'Invalid observation: {e}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
