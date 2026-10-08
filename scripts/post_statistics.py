#!/usr/bin/env python3
"""Keep timed X analytics and public counters separate; never infer follower attribution.

Ratios count events per impression, not independent-user probabilities. Engagements
are read as reported, never reconstructed by summing their possible components.
"""
import argparse
import json
import re
from pathlib import Path

try:
    from .render_public import ANALYTICS_COUNTERS, POST_COUNTERS, count, post_url, timestamp
except ImportError:  # Direct CLI execution.
    from render_public import ANALYTICS_COUNTERS, POST_COUNTERS, count, post_url, timestamp

ROOT = Path(__file__).resolve().parents[1]
RATIO_COUNTERS = {
    'engagement_events_per_impression': 'engagements',
    'detail_expands_per_impression': 'detail_expands',
    'profile_visits_per_impression': 'profile_visits',
    'link_clicks_per_impression': 'link_clicks',
}
SURFACES = (
    ('analytics_observations', 'owner_analytics', ANALYTICS_COUNTERS),
    ('post_observations', 'public_surface', POST_COUNTERS),
)


def identity(url):
    """The strict URL validator has already checked account and status syntax."""
    return url.rsplit('/', 1)[-1]


def optional_text(row, key):
    value = row.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(key + ' must be a string or null')
    return value


def event_ratios(counters):
    exposure = counters.get('impressions')
    values, reasons = {}, {}
    for name, counter in RATIO_COUNTERS.items():
        numerator = counters.get(counter)
        reason = ('unknown_impressions' if exposure is None else
                  'zero_impressions' if exposure == 0 else
                  'unknown_counter' if numerator is None else None)
        values[name] = numerator / exposure if reason is None else None
        reasons[name] = reason
    return values, reasons


def publication_for(row, catalog):
    """Only posts metadata can supply an age clock, never observation timestamps."""
    direct = row.get('published_at')
    if direct is not None:
        return direct, {'collection': 'posts', 'url': row['url'], 'field': 'published_at'}, 'publication'
    original_url = row.get('original_version_url')
    original = catalog.get(identity(original_url)) if original_url else None
    retained = row.get('original_published_at')
    looked_up = original.get('published_at') if original else None
    if retained and looked_up and timestamp(retained, 'original publication') != timestamp(looked_up, 'original publication'):
        raise ValueError('conflicting original publication timestamps')
    if looked_up:
        return looked_up, {'collection': 'posts', 'url': original['url'], 'field': 'published_at'}, 'original_publication'
    if retained:
        return retained, {'collection': 'posts', 'url': row['url'], 'field': 'original_published_at'}, 'original_publication'
    return None, None, None


def attributed_follows(row, observed, account):
    """Accept only an explicitly evidenced, same-capture owner-reported field.

    Evidence is a measurement contract, not evidence that these are unique people:
    source=owner_analytics, field=follows_attributed, same post URL and timestamp,
    official_metric_documentation on help.x.com or business.x.com, and a nonempty
    capture_evidence description. Current metrics expose no such field.
    """
    value = row.get('follows_attributed')
    count(value, 'follows_attributed', nullable=True)
    proof = row.get('follows_attributed_evidence')
    if proof is not None and not isinstance(proof, dict):
        raise ValueError('follows_attributed_evidence must be an object or null')
    if value is None or not proof:
        return None, 'not_measured' if value is None else 'attribution_evidence_missing'
    if proof.get('source') != 'owner_analytics' or proof.get('field') != 'follows_attributed':
        raise ValueError('follow attribution needs an explicit owner analytics field')
    post_url(proof.get('url'), account)
    if identity(proof['url']) != identity(row['url']):
        raise ValueError('follow attribution evidence belongs to another post')
    if timestamp(proof.get('observed_at'), 'follow attribution timestamp', nullable=False) != observed:
        raise ValueError('follow attribution evidence must use the same capture time')
    documentation = proof.get('official_metric_documentation')
    if not isinstance(documentation, str) or not re.fullmatch(r'https://(?:help|business)\.x\.com/[^\s]+', documentation):
        raise ValueError('follow attribution requires official metric documentation')
    if not isinstance(proof.get('capture_evidence'), str) or not proof['capture_evidence'].strip():
        raise ValueError('follow attribution requires actual capture evidence')
    return value, None


def validated_inputs(data):
    if not isinstance(data, dict):
        raise ValueError('metrics must be an object')
    account = data.get('account')
    if not isinstance(account, str) or not re.fullmatch(r'[A-Za-z0-9_]{1,15}', account):
        raise ValueError('invalid measured X account')
    posts = data.get('posts')
    if not isinstance(posts, list):
        raise ValueError('posts must be a list')
    catalog = {}
    for row in posts:
        if not isinstance(row, dict):
            raise ValueError('posts rows must be objects')
        post_url(row.get('url'), account)
        key = identity(row['url'])
        if key in catalog:
            raise ValueError('duplicate post catalog identity')
        optional_text(row, 'kind')
        optional_text(row, 'published_at_source')
        observed = timestamp(row.get('observed_at'), 'post observation')
        published = timestamp(row.get('published_at'), 'post publication')
        original = timestamp(row.get('original_published_at'), 'original publication')
        if row.get('original_version_url') is not None:
            post_url(row['original_version_url'], account)
            if identity(row['original_version_url']) == key:
                raise ValueError('original_version_url must identify another version')
        if published and observed and published > observed:
            raise ValueError('publication must not follow observation')
        if original and observed and original > observed:
            raise ValueError('original publication must not follow observation')
        for counter in POST_COUNTERS:
            count(row.get(counter), 'post ' + counter, nullable=True)
        catalog[key] = row

    histories = {}
    for collection, surface, counters in SURFACES:
        rows = data.get(collection, [])
        if not isinstance(rows, list):
            raise ValueError(collection + ' must be a list')
        history, previous = {}, {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(collection + ' rows must be objects')
            post_url(row.get('url'), account)
            key = identity(row['url'])
            for field in ('kind', 'source', 'note'):
                optional_text(row, field)
            observed = timestamp(row.get('observed_at'), collection + ' timestamp', nullable=False)
            for counter in counters:
                count(row.get(counter), collection + ' ' + counter, nullable=True)
            follow, follow_reason = attributed_follows(row, observed, account) if surface == 'owner_analytics' else (None, 'not_measured')
            signature = tuple(row.get(counter) for counter in counters) + (row.get('follows_attributed'), row.get('source'))
            if key in previous:
                previous_time, previous_signature = previous[key]
                if observed < previous_time:
                    raise ValueError(collection + ' timestamps must be chronological per post')
                if observed == previous_time:
                    if signature != previous_signature:
                        raise ValueError(collection + ' conflicting counters at the same post timestamp')
                    continue  # Identical repeated capture, not a zero-duration interval.
            previous[key] = (observed, signature)
            history.setdefault(key, []).append((row, observed, follow, follow_reason))
        histories[surface] = history
    return account, catalog, histories


def snapshot(row, observed, surface, collection, counters, age_at, age_source, age_basis, follow, follow_reason):
    values = {key: row.get(key) for key in counters}
    if age_at:
        age_seconds = (observed - timestamp(age_at, 'publication')).total_seconds()
        if age_seconds < 0:
            raise ValueError('publication must not follow observation')
    else:
        age_seconds = None
    result = {
        'source': surface, 'source_collection': collection,
        'source_detail': row.get('source'), 'observed_at': row['observed_at'],
        'counts': values, 'age_seconds': age_seconds,
        'age_basis': age_basis, 'age_publication_at': age_at,
        'age_publication_source': age_source,
        'follows_attributed': follow, 'follows_attributed_reason': follow_reason,
    }
    if surface == 'owner_analytics':
        result['event_ratios'], result['event_ratio_reasons'] = event_ratios(values)
    return result


def interval(url, before, after, surface, collection, counters):
    start = timestamp(before['observed_at'], 'interval start', nullable=False)
    end = timestamp(after['observed_at'], 'interval end', nullable=False)
    elapsed = (end - start).total_seconds()
    if elapsed <= 0:
        raise ValueError('paired interval needs increasing timestamps')
    old, new = before['counts'], after['counts']
    revised = [key for key in counters if old[key] is not None and new[key] is not None and new[key] < old[key]]
    # A revised cumulative snapshot is not a clean observation interval. Retain
    # the endpoints, but suppress all interval estimates rather than cherry-pick.
    reason = 'counter_revision' if revised else None
    deltas, reasons = {}, {}
    for key in counters:
        field_reason = reason or ('unknown_counter' if old[key] is None or new[key] is None else None)
        deltas[key] = new[key] - old[key] if field_reason is None else None
        reasons[key] = field_reason
    result = {
        'url': url, 'source': surface, 'source_collection': collection,
        'started_at': before['observed_at'], 'ended_at': after['observed_at'],
        'elapsed_seconds': elapsed, 'status': reason or 'paired',
        'revised_counters': revised, 'delta_counts': deltas, 'delta_reasons': reasons,
        'counts_per_second': {key: value / elapsed if value is not None else None for key, value in deltas.items()},
        'count_rate_unit': 'counted events/second; not independent users/second',
        'follows_attributed': None,
    }
    if surface == 'owner_analytics':
        ratios, ratio_reasons = event_ratios(deltas)
        if reason:
            ratio_reasons = {key: reason for key in ratios}
        result['event_ratios'] = ratios
        result['event_ratio_reasons'] = ratio_reasons
        result['events_per_1000_impressions'] = {key: value * 1000 if value is not None else None for key, value in ratios.items()}
        result['impression_rate_unit'] = 'counted events/1000 impressions; not unique-user conversion'
    return result


def build_statistics(data):
    account, catalog, histories = validated_inputs(data)
    ordered_keys = list(catalog)
    for history in histories.values():
        ordered_keys.extend(key for key in history if key not in ordered_keys)
    posts, intervals = [], []
    for key in ordered_keys:
        metadata = catalog.get(key)
        history_row = next((rows[key][0][0] for rows in histories.values() if key in rows), None)
        url = metadata['url'] if metadata else history_row['url']
        age_at, age_source, age_basis = publication_for(metadata, catalog) if metadata else (None, None, None)
        result = {
            'url': url, 'kind': metadata.get('kind') if metadata else history_row.get('kind'),
            'published_at': metadata.get('published_at') if metadata else None,
            'published_at_source': {'collection': 'posts', 'url': url, 'field': 'published_at'} if metadata and metadata.get('published_at') else None,
            'publication_evidence': metadata.get('published_at_source') if metadata else None,
            'age_publication_at': age_at, 'age_publication_source': age_source, 'age_basis': age_basis,
            'follows_attributed': None,
        }
        for collection, surface, counters in SURFACES:
            observations = [snapshot(row, observed, surface, collection, counters, age_at, age_source, age_basis, follow, follow_reason)
                            for row, observed, follow, follow_reason in histories[surface].get(key, [])]
            result[surface] = observations
            result['latest_' + surface] = observations[-1] if observations else None
            intervals.extend(interval(url, before, after, surface, collection, counters)
                             for before, after in zip(observations, observations[1:])
                             if before['source_detail'] == after['source_detail'])
        latest_analytics = result['latest_owner_analytics']
        if latest_analytics and latest_analytics['follows_attributed'] is not None:
            result['follows_attributed'] = latest_analytics['follows_attributed']
            result['follows_attributed_source'] = {
                'source': 'owner_analytics', 'observed_at': latest_analytics['observed_at'],
                'field': 'follows_attributed',
            }
        posts.append(result)
    return {
        'account': account, 'per_post': posts, 'paired_intervals': intervals,
        'interpretation': {
            'event_ratios': 'Counted events per impression, not independent-user probabilities; values may exceed 1.',
            'components': 'Reported engagements are never summed with detail expands, profile visits, link clicks, or public counters.',
            'surfaces': 'Public views are not analytics impressions. Sources and clocks remain separate.',
            'followers': 'No net-follower/views conversion or inferred attribution. No unique-user exposure is available.',
            'definitions': ['https://business.x.com/help/tweet-activity-dashboard', 'https://help.x.com/en/using-x/view-counts'],
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('metrics', nargs='?', type=Path, default=ROOT / 'public/metrics.json')
    parser.add_argument('--output', type=Path, help='Write JSON here instead of stdout')
    args = parser.parse_args(argv)
    try:
        result = build_statistics(json.loads(args.metrics.read_text()))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
