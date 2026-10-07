#!/usr/bin/env python3
"""Read recorded profile observations and describe net follower rates, without attribution."""
import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def observed_time(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError('observed_at must be an ISO timestamp or null')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid observed_at timestamp') from exc
    if parsed.utcoffset() is None:
        raise ValueError('observed_at must include a timezone')
    return parsed


def diagnose(data, window_tolerance=0.2):
    """Tolerance is a duration-comparison operating budget, never a significance test."""
    if (type(window_tolerance) not in (int, float) or not math.isfinite(window_tolerance)
            or not 0 <= window_tolerance <= 1):
        raise ValueError('window tolerance must be a finite fraction between 0 and 1')
    if not isinstance(data, dict):
        raise ValueError('metrics must be an object')
    observations = data.get('follower_observations', [])
    if not isinstance(observations, list):
        raise ValueError('follower_observations must be a list')
    usable, skipped = [], []
    previous_time = None
    for index, row in enumerate(observations):
        if not isinstance(row, dict):
            raise ValueError('follower observations must be objects')
        total = row.get('total')
        if total is not None and (type(total) is not int or total < 0):
            raise ValueError('follower total must be a nonnegative integer or null')
        time = observed_time(row.get('observed_at'))
        if time is not None:
            if previous_time is not None and time <= previous_time:
                raise ValueError('profile timestamps must be strictly increasing; duplicate times need reconciliation')
            previous_time = time
        if time is None or total is None:
            skipped.append({'index': index, 'total': total, 'observed_at': row.get('observed_at'),
                            'reason': 'missing exact timestamp' if time is None else 'missing follower total'})
        else:
            usable.append((row, time))
    intervals = []
    for (before, start), (after, end) in zip(usable, usable[1:]):
        minutes = (end - start).total_seconds() / 60
        delta = after['total'] - before['total']
        intervals.append({'started_at': before['observed_at'], 'ended_at': after['observed_at'],
                          'interval_minutes': minutes, 'total_before': before['total'],
                          'total_after': after['total'], 'net_delta': delta,
                          'net_followers_per_minute': delta / minutes})
    comparison = {'status': 'insufficient_intervals', 'net_rate_direction': None,
                  'duration_relative_difference': None, 'within_duration_budget': None,
                  'duration_tolerance': window_tolerance,
                  'budget_meaning': 'Operational window-duration tolerance, not statistical proof',
                  'strategy_comparability': 'unknown'}
    if len(intervals) >= 2:
        before, after = intervals[-2:]
        difference = abs(after['interval_minutes'] - before['interval_minutes']) / before['interval_minutes']
        previous_rate, latest_rate = before['net_followers_per_minute'], after['net_followers_per_minute']
        comparison.update(status='observed_net_rates_only', duration_relative_difference=difference,
                          within_duration_budget=difference <= window_tolerance,
                          net_rate_direction=('increased' if latest_rate > previous_rate else
                                              'decreased' if latest_rate < previous_rate else 'unchanged'))
    posts = data.get('posts', [])
    if not isinstance(posts, list):
        raise ValueError('posts must be a list')
    post_times = []
    for post in posts:
        if not isinstance(post, dict):
            raise ValueError('post records must be objects')
        time = observed_time(post.get('observed_at'))
        if time is not None:
            post_times.append(time)
    for interval in intervals[-2:]:
        start, end = observed_time(interval['started_at']), observed_time(interval['ended_at'])
        interval['post_counter_observations_in_window'] = sum(start < time <= end for time in post_times)
        interval['matched_post_feedback_delta'] = None
    return {'account': data.get('account'),
            'status': 'observed_intervals' if intervals else 'insufficient_timed_observations',
            'latest_intervals': intervals[-2:], 'skipped_observations': skipped,
            'fixed_window_comparison': comparison, 'causal_explanation': 'unknown',
            'gross_new_followers': None, 'confirmed_new_blue_followers': None,
            'confirmed_new_high_quality_blue_followers': None,
            'profile_visit_to_follow_conversion': None,
            'confirmed_action_mix': None,
            'confounders': data.get('confounders', []),
            'limitations': [
                'Profile total changes are net changes, not gross arrivals, new blue followers or quality gains.',
                'Untimed observations never receive invented timestamps; null counts are not zero.',
                'Duration similarity alone does not establish matched actions, audience, posting age or concurrent activity.',
                'A post counter sample inside a profile window is not a matched feedback delta or conversion measurement.',
                'Action pauses and confirmed action proportions require actual action logs; they cannot be inferred here.',
                'Small samples and net-rate declines do not prove recommendation throttling or causality.'
            ]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('metrics', nargs='?', type=Path, default=ROOT / 'public/metrics.json')
    parser.add_argument('--window-tolerance', type=float, default=0.2,
                        help='Allowed relative duration difference, default 0.2; an operating budget, not proof')
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.metrics.read_text())
        result = diagnose(data, args.window_tolerance)
    except (OSError, ValueError) as exc:
        print(f'Invalid recorded metrics: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
