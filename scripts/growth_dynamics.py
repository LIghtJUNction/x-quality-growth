#!/usr/bin/env python3
"""Describe recorded count dynamics; no X access, acquisition or causal inference."""
import argparse
import json
import math
import re
import sys
from datetime import timezone
from pathlib import Path
from urllib.parse import urlsplit

try:
    from .diagnose_growth import observed_time
except ImportError:  # Direct CLI invocation from scripts/.
    from diagnose_growth import observed_time

ROOT = Path(__file__).resolve().parents[1]
POST_COUNTERS = ('views', 'replies', 'likes', 'reposts', 'bookmarks')


def count(value, label, nullable=True):
    if value is None and nullable:
        return
    if type(value) is not int or value < 0:
        raise ValueError(label + ' must be a nonnegative integer' + (' or null' if nullable else ''))


def finite(value, label):
    if not math.isfinite(value):
        raise ValueError(label + ' is outside the finite numeric range')
    return value


def divide(numerator, denominator, label):
    if denominator <= 0:
        raise ValueError(label + ' requires a positive elapsed time or denominator')
    try:
        return finite(numerator / denominator, label)
    except OverflowError as exc:
        raise ValueError(label + ' is outside the finite numeric range') from exc


def utc(time):
    return time.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def rows(data, collection):
    value = data.get(collection, [])
    if not isinstance(value, list):
        raise ValueError(collection + ' must be a list')
    if not all(isinstance(row, dict) for row in value):
        raise ValueError(collection + ' rows must be objects')
    return value


def count_dynamics(observations, field, kind):
    usable, skipped, previous_time = [], [], None
    for index, row in enumerate(observations):
        value = row.get(field)
        count(value, kind + ' count')
        time = observed_time(row.get('observed_at'))
        if time is not None:
            if previous_time is not None and time <= previous_time:
                raise ValueError(kind + ' timestamps must increase strictly; reconcile duplicates or reversed times')
            previous_time = time
        if time is None or value is None:
            skipped.append({'index': index, 'observed_at': row.get('observed_at'), 'count': value,
                            'reason': 'missing_exact_timestamp' if time is None else 'missing_count'})
        else:
            usable.append((index, row, time))
    intervals = []
    for (_, before, start), (_, after, end) in zip(usable, usable[1:]):
        seconds = (end - start).total_seconds()
        delta = after[field] - before[field]
        speed = divide(delta, seconds, kind + ' rate')
        midpoint = start + (end - start) / 2
        intervals.append({'started_at': before['observed_at'], 'ended_at': after['observed_at'],
                          'interval_seconds': seconds, 'midpoint_at': utc(midpoint),
                          'count_before': before[field], 'count_after': after[field], 'net_delta': delta,
                          'net_rate_per_second': speed,
                          'net_rate_per_hour': finite(speed * 3600, kind + ' hourly rate')})
    accelerations = []
    for before, after in zip(intervals, intervals[1:]):
        # Adjacent intervals share an endpoint. Their midpoint separation is
        # half the sum of durations, avoiding datetime's half-microsecond rounding.
        seconds = (before['interval_seconds'] + after['interval_seconds']) / 2
        acceleration = divide(after['net_rate_per_second'] - before['net_rate_per_second'],
                              seconds, kind + ' acceleration')
        accelerations.append({'from_interval_midpoint_at': before['midpoint_at'],
                              'to_interval_midpoint_at': after['midpoint_at'],
                              'midpoint_interval_seconds': seconds,
                              'acceleration_per_second_squared': acceleration,
                              'acceleration_per_hour_squared': finite(acceleration * 3600**2,
                                                                      kind + ' hourly acceleration')})
    average = None
    if intervals:
        _, before, start = usable[0]
        _, after, end = usable[-1]
        seconds, delta = (end - start).total_seconds(), after[field] - before[field]
        speed = divide(delta, seconds, kind + ' weighted rate')
        average = {'started_at': before['observed_at'], 'ended_at': after['observed_at'],
                   'interval_seconds': seconds, 'net_delta': delta,
                   'net_rate_per_second': speed,
                   'net_rate_per_hour': finite(speed * 3600, kind + ' weighted hourly rate'),
                   'method': 'duration_weighted; first-to-last timed count difference / elapsed seconds'}
    return {'kind': kind, 'status': 'observed_intervals' if intervals else 'insufficient_timed_observations',
            'intervals': intervals, 'accelerations': accelerations,
            'duration_weighted_average': average, 'skipped_observations': skipped,
            'confirmed_acquisition': False}


def following_ratios(observations):
    result = []
    for index, row in enumerate(observations):
        total, following = row.get('total'), row.get('following')
        count(total, 'follower total')
        count(following, 'following count')
        ratio, reason = None, None
        if total is None or following is None:
            reason = 'missing_same_snapshot_counts'
        elif total == 0:
            reason = 'zero_denominator'
        else:
            ratio = divide(following, total, 'following / total ratio')
        result.append({'index': index, 'observed_at': row.get('observed_at'),
                       'following': following, 'total_followers': total,
                       'following_to_total_ratio': ratio, 'reason': reason,
                       'meaning': 'same-snapshot following / total followers; not a quality score'})
    return result


def cohort_quality(cohort):
    if cohort is None:
        return {'status': 'unavailable', 'lower_bound': None, 'upper_bound': None,
                'general_population_confidence_interval': None}
    if not isinstance(cohort, dict):
        raise ValueError('blue_cohort must be an object or null')
    for name in ('observed_arrivals', 'high', 'not_high', 'unknown'):
        count(cohort.get(name), 'blue_cohort ' + name, nullable=False)
    n, high, unknown = cohort['observed_arrivals'], cohort['high'], cohort['unknown']
    if high + cohort['not_high'] + unknown != n:
        raise ValueError('blue_cohort quality partition must equal observed_arrivals')
    confirmed = cohort.get('confirmed_new_followers')
    count(confirmed, 'confirmed_new_followers')
    if confirmed is not None and confirmed > n:
        raise ValueError('confirmed_new_followers exceeds observed_arrivals')
    start = observed_time(cohort.get('window_started_at'))
    end = observed_time(cohort.get('window_ended_at'))
    observed_time(cohort.get('classified_at'))
    if start is not None and end is not None and start > end:
        raise ValueError('blue_cohort window start follows its end')
    return {'status': 'undefined' if not n else 'classification_incomplete' if unknown else 'classified',
            'observed_arrivals': n, 'high': high, 'not_high': cohort['not_high'], 'unknown': unknown,
            'lower_bound': divide(high, n, 'cohort lower bound') if n else None,
            'upper_bound': divide(high + unknown, n, 'cohort upper bound') if n else None,
            'window_started_at': cohort.get('window_started_at'),
            'window_ended_at': cohort.get('window_ended_at'),
            'scope': 'the declared observed cohort only; not all followers or a representative sample',
            'general_population_confidence_interval': None}


def status_id(url):
    if not isinstance(url, str):
        raise ValueError('post observation needs a permanent X status URL')
    parsed = urlsplit(url)
    match = re.fullmatch(r'/(?:[A-Za-z0-9_]{1,15}|i/web)/status/([1-9][0-9]*)/?', parsed.path)
    if parsed.scheme != 'https' or parsed.netloc not in ('x.com', 'twitter.com') or not match:
        raise ValueError('post observation needs a permanent X status URL')
    return match[1]


def post_views(observations):
    groups = {}
    for index, row in enumerate(observations):
        key = status_id(row.get('url'))
        group = groups.setdefault(key, {'status_id': key, 'url': row['url'], 'usable': [],
                                        'last_time': None, 'last_signature': None,
                                        'skipped_observations': []})
        for counter in POST_COUNTERS:
            count(row.get(counter), 'post ' + counter)
        time = observed_time(row.get('observed_at'))
        signature = tuple(row.get(counter) for counter in POST_COUNTERS)
        reason = None
        if time is not None:
            if group['last_time'] is not None:
                if time < group['last_time']:
                    raise ValueError('post timestamps must increase per status ID')
                if time == group['last_time']:
                    if signature != group['last_signature']:
                        raise ValueError('conflicting post counters at a duplicate timestamp')
                    reason = 'duplicate_identical_counter_snapshot'
            group['last_time'], group['last_signature'] = time, signature
        if reason is None and (time is None or row.get('views') is None):
            reason = 'missing_exact_timestamp' if time is None else 'missing_view_count'
        if reason is not None:
            group['skipped_observations'].append({'index': index, 'observed_at': row.get('observed_at'),
                                                  'reason': reason})
        else:
            group['usable'].append((row, time))
    result = []
    for group in groups.values():
        intervals = []
        for (before, start), (after, end) in zip(group['usable'], group['usable'][1:]):
            seconds, delta = (end - start).total_seconds(), after['views'] - before['views']
            rate = divide(delta, seconds, 'post view counter rate')
            correction = delta < 0
            intervals.append({'started_at': before['observed_at'], 'ended_at': after['observed_at'],
                              'interval_seconds': seconds, 'views_before': before['views'],
                              'views_after': after['views'], 'counter_delta': delta,
                              'counter_rate_per_second': rate,
                              'counter_rate_per_hour': finite(rate * 3600, 'post hourly counter rate'),
                              'status': 'counter_revision' if correction else 'observed_counter_change',
                              'observed_view_rate_per_second': None if correction else rate,
                              'meaning': 'counter change, not negative exposure' if correction else
                                         'public counter change; operator views and repeated views may contribute'})
        result.append({'status_id': group['status_id'], 'url': group['url'], 'intervals': intervals,
                       'skipped_observations': group['skipped_observations']})
    return {'kind': 'per_post_cumulative_view_counter', 'posts': result,
            'independent_audience_exposure': None, 'versions_merged': False}


def analyze(data):
    if not isinstance(data, dict):
        raise ValueError('metrics must be an object')
    account = data.get('account')
    if account is not None and (not isinstance(account, str) or not re.fullmatch(r'[A-Za-z0-9_]{1,15}', account)):
        raise ValueError('invalid measured account')
    followers = rows(data, 'follower_observations')
    blues = rows(data, 'blue_observations')
    return {'account': account,
            'follower_dynamics': count_dynamics(followers, 'total', 'observed_total_follower_net_change'),
            'blue_membership_dynamics': count_dynamics(blues, 'count', 'observed_blue_membership'),
            'following_ratios': following_ratios(followers),
            'observed_cohort_quality': cohort_quality(data.get('blue_cohort')),
            'post_view_dynamics': post_views(rows(data, 'post_observations')),
            'confirmed_acquisition_rates': {'gross_followers_per_second': None, 'gross_followers_per_hour': None,
                                            'gross_blue_followers_per_second': None, 'gross_blue_followers_per_hour': None,
                                            'status': 'no_confirmed_gross_acquisition_event_log'},
            'conversion': None, 'conversion_status': 'insufficient_matched_window',
            'causal_attribution': 'not established',
            'concepts': {
                'net_velocity': 'endpoint count difference / actual elapsed seconds; units accounts/s or accounts/h',
                'net_acceleration': 'adjacent interval velocity difference / elapsed interval-midpoint seconds; accounts/s^2 or accounts/h^2',
                'weighted_average': 'first-to-last timed net change / total elapsed seconds, not the unweighted mean of speeds',
                'blue_membership': 'observed list membership may include badge upgrades, renames and collection changes; not new-blue acquisition',
                'quality_bounds': 'high/N to (high+unknown)/N for the observed cohort; no population confidence claim',
                'conversion': 'follower net change divided by post views is not a matched conversion rate'},
            'limitations': ['Count slopes are observations, not strategy effects or forecasts.',
                            'Missing timestamps or counts are skipped, never assigned invented times or zeros.',
                            'Each post and each edited status ID retains its own counter window.',
                            'Acceleration describes a finite-difference estimate; it does not prove exponential growth.']}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('non-finite JSON constant: ' + value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('metrics', nargs='?', type=Path, default=ROOT / 'public/metrics.json')
    parser.add_argument('--output', type=Path, help='optional aggregate JSON destination; source metrics are preserved')
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.resolve() == args.metrics.resolve():
            raise ValueError('output must not overwrite source metrics')
        data = json.loads(args.metrics.read_text(), object_pairs_hook=unique_object, parse_constant=reject_constant)
        payload = json.dumps(analyze(data), ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload)
    except (OSError, ValueError) as exc:
        print(f'Invalid recorded dynamics: {exc}', file=sys.stderr)
        return 2
    print(payload, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
