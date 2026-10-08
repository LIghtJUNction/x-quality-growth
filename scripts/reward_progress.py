#!/usr/bin/env python3
"""Measure recorded rewards eligibility counters; do not train or forecast growth."""
import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRIC = 'verified_home_timeline_impressions_excluding_replies'
SOURCE = 'X Creator Studio / Original Content Rewards'
EXACT_TIME = re.compile(
    r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z')


def exact_time(value, field='observed_at'):
    if not isinstance(value, str) or EXACT_TIME.fullmatch(value) is None:
        raise ValueError(f'{field} must be an exact ISO timestamp with seconds and timezone')
    if not value.endswith('Z') and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise ValueError(f'invalid {field} timezone offset')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f'invalid {field} timestamp') from exc


def integer(value, field, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        adjective = 'positive' if positive else 'nonnegative'
        raise ValueError(f'{field} must be a {adjective} integer')
    return value


def optional_text(value, field):
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f'{field} must be a nonempty string or null')
    return value


def finite_ratio(numerator, denominator, field):
    try:
        result = numerator / denominator
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError(f'{field} cannot be represented as a finite ratio') from exc
    if not math.isfinite(result):
        raise ValueError(f'{field} cannot be represented as a finite ratio')
    return result


def analyze(data):
    """Progress refers to the supplied targets, not admission or payout qualification."""
    if not isinstance(data, dict):
        raise ValueError('reward observations must be an object')
    if data.get('metric') != METRIC:
        raise ValueError('unsupported metric; payout-qualified impressions are a separate metric')
    window_days = integer(data.get('window_days'), 'window_days', positive=True)
    if window_days != 90:
        raise ValueError('verified_home_impressions_90d requires window_days=90')
    impression_target = integer(data.get('impression_target'), 'impression_target', positive=True)
    follower_target = integer(data.get('verified_follower_target'), 'verified_follower_target', positive=True)
    if data.get('source') != SOURCE:
        raise ValueError('unsupported source; eligibility and payout sources cannot be merged')
    policy_url = optional_text(data.get('policy_url'), 'policy_url')
    policy_checked_at = data.get('policy_checked_at')
    if policy_checked_at is not None:
        exact_time(policy_checked_at, 'policy_checked_at')
    observations = data.get('observations')
    if not isinstance(observations, list):
        raise ValueError('observations must be a list')

    validated = []
    for index, row in enumerate(observations):
        if not isinstance(row, dict):
            raise ValueError(f'observations[{index}] must be an object')
        when = exact_time(row.get('observed_at'))
        if validated and when <= validated[-1][1]:
            raise ValueError('observation times must be strictly increasing; duplicate or conflicting snapshots need reconciliation')
        if row.get('source') != SOURCE:
            raise ValueError('each observation must use the same eligibility source; payout sources cannot be merged')
        if row.get('replies_excluded') is not True:
            raise ValueError('replies_excluded must be true for this metric')
        home = integer(row.get('verified_home_impressions_90d'), 'verified_home_impressions_90d')
        followers = integer(row.get('verified_followers'), 'verified_followers')
        payout = row.get('payout_qualified_impressions')
        if payout is not None:
            integer(payout, 'payout_qualified_impressions')
        source_url = optional_text(row.get('source_url'), 'source_url')
        validated.append(({'observed_at': row['observed_at'], 'source': SOURCE,
                          'source_url': source_url, 'verified_home_impressions_90d': home,
                          'verified_followers': followers, 'replies_excluded': True}, when))

    intervals = []
    for (before, start), (after, end) in zip(validated, validated[1:]):
        seconds = (end - start).total_seconds()
        home_delta = after['verified_home_impressions_90d'] - before['verified_home_impressions_90d']
        follower_delta = after['verified_followers'] - before['verified_followers']
        intervals.append({
            'started_at': before['observed_at'], 'ended_at': after['observed_at'],
            'interval_seconds': seconds, 'source': SOURCE,
            'rolling_net_impression_delta': home_delta,
            'rolling_net_impressions_per_second': finite_ratio(home_delta, seconds, 'rolling impression rate'),
            'rolling_net_impressions_per_hour': finite_ratio(home_delta * 3600, seconds, 'hourly rolling impression rate'),
            'impression_change_status': ('rolling_net_decline_possible_expiry' if home_delta < 0 else
                                         'rolling_net_increase' if home_delta > 0 else 'rolling_net_unchanged'),
            'verified_follower_net_delta': follower_delta,
            'verified_followers_net_per_second': finite_ratio(follower_delta, seconds, 'verified follower net rate'),
            'verified_followers_net_per_hour': finite_ratio(follower_delta * 3600, seconds, 'hourly verified follower net rate'),
            'gross_new_verified_home_impressions': None,
            'expired_verified_home_impressions': None,
            'meaning': 'Same-source observed net changes; the rolling difference is not gross newly eligible exposure.'
        })

    latest = None
    if validated:
        row = validated[-1][0]
        home, followers = row['verified_home_impressions_90d'], row['verified_followers']
        latest = {**row,
                  'impression_deficit': max(0, impression_target - home),
                  'verified_follower_deficit': max(0, follower_target - followers),
                  'impression_progress_fraction': finite_ratio(home, impression_target, 'impression progress'),
                  'verified_follower_progress_fraction': finite_ratio(followers, follower_target, 'verified follower progress'),
                  'observed_impression_threshold_met': home >= impression_target,
                  'observed_verified_follower_threshold_met': followers >= follower_target,
                  'both_observed_thresholds_met': home >= impression_target and followers >= follower_target}
    return {
        'metric': METRIC, 'window_days': window_days, 'source': SOURCE,
        'policy_url': policy_url, 'policy_checked_at': policy_checked_at,
        'targets': {'impressions': impression_target, 'verified_followers': follower_target},
        'observation_count': len(validated),
        'status': ('measured_rolling_net_changes' if intervals else
                   'measured_baseline_only' if latest is not None else 'no_observations'),
        'latest': latest, 'intervals': intervals,
        'latest_net_rates': intervals[-1] if intervals else None,
        'forecast': {'status': 'untrained_model', 'method': None,
                     'future_eligible_impressions_1h': None, 'future_eligible_impressions_24h': None,
                     'impression_target_eta': None, 'verified_follower_target_eta': None,
                     'both_thresholds_eta': None, 'threshold_probability': None},
        'program_admission': None, 'payout_qualification': None,
        'gross_new_verified_home_impressions': None, 'daily_expiry': None,
        'limitations': [
            'Progress measures the supplied observed thresholds only; it does not establish program admission or payout qualification.',
            'Verified followers are the backend category, not a blue-only count or a high-quality follower score.',
            'A 90-day counter can decline as exposure expires or measurements change; no daily expiry history is inferred.',
            'Rolling net change is not gross new eligible impressions and is never extrapolated here.',
            'Total post views and blue-follower ratios are not substitutes for verified home-timeline impressions.',
            'Payout-qualified impressions are a separate metric and are not merged into eligibility progress.',
            'No trained model or matched predictive validation exists; future quantities, ETA and threshold probability remain unknown.'
        ]
    }


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError(f'nonfinite JSON value: {value}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputpath', type=Path, default=ROOT / 'public/reward-observations.json')
    parser.add_argument('--outputpath', type=Path, help='Optional path for aggregate JSON; otherwise print to stdout')
    args = parser.parse_args(argv)
    try:
        if args.outputpath is not None and args.outputpath.resolve() == args.inputpath.resolve():
            raise ValueError('outputpath must not overwrite the input observations')
        data = json.loads(args.inputpath.read_text(), object_pairs_hook=strict_object,
                          parse_constant=invalid_constant)
        result = analyze(data)
        rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.outputpath is not None:
            args.outputpath.write_text(rendered)
        else:
            print(rendered, end='')
    except (OSError, ValueError) as exc:
        print(f'Invalid reward observations: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
