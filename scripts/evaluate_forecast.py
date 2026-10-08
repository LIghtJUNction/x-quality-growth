#!/usr/bin/env python3
"""Evaluate a sealed prospective forecast without training or rewriting it.

Actual JSON uses contract_version=rise-prospective-actual-1 and the forecast's
forecast_id, post_url, version, source and metric. Its observations contain
actual (integer/null), observed_at, observation_started_at and
observation_completed_at. observed_at is the conservative capture-end anchor.
For scoring, declare first_successful_numeric_read_at_or_after_target=true or
observation_history_complete_since_target=true. These are operator assertions,
not independent proof that omitted reads do not exist.
"""
import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCES = {'public_views': 'views', 'owner_impressions': 'impressions'}
IDENTITY = ('forecast_id', 'post_url', 'version', 'source', 'metric')
SHA256 = re.compile(r'[0-9a-fA-F]{64}\Z')
ISO_TIME = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|([+-])(\d{2}):(\d{2}))\Z')


def read_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError(f'nonfinite JSON constant: {value}')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)


def time(value, name):
    if not isinstance(value, str):
        raise ValueError(f'{name} requires a timestamp with timezone')
    match = ISO_TIME.fullmatch(value)
    if match is None or (match.group(1) and (int(match.group(2)) > 23 or int(match.group(3)) > 59)):
        raise ValueError(f'{name} requires ISO seconds, <=6 fractional digits and valid timezone')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'invalid {name}') from exc
    if result.utcoffset() is None:
        raise ValueError(f'{name} requires timezone')
    return result.astimezone(timezone.utc)


def count(value, name):
    if value is not None and (type(value) is not int or value < 0):
        raise ValueError(f'{name} must be a nonnegative integer or null')
    return value


def prediction(value):
    if value is not None:
        try:
            valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError('prediction must be finite, nonnegative or null')
    return value


def capture(row, required=True):
    observed = time(row.get('observed_at'), 'observed_at')
    start, end = row.get('observation_started_at'), row.get('observation_completed_at')
    if start is None and end is None and not required:
        return observed, observed, observed
    start = time(start, 'observation_started_at')
    end = time(end, 'observation_completed_at')
    if start > end or observed != end:
        raise ValueError('capture must start <= end; observed_at must equal capture end')
    return start, end, observed


def validate_frozen(raw, expected_sha256):
    if not isinstance(expected_sha256, str) or not SHA256.fullmatch(expected_sha256):
        raise ValueError('an independently retained forecast SHA256 is required')
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError('forecast SHA256 mismatch')
    frozen = read_json(raw)
    if not isinstance(frozen, dict) or frozen.get('contract_version') != 'rise-prospective-exposure-1':
        raise ValueError('unsupported frozen contract')
    if frozen.get('status') != 'frozen_before_target':
        raise ValueError('forecast must have been frozen before target')
    if frozen.get('source') not in SOURCES or SOURCES[frozen['source']] != frozen.get('metric'):
        raise ValueError('source/metric mismatch')
    for key in IDENTITY:
        if not isinstance(frozen.get(key), str) or not frozen[key]:
            raise ValueError(f'missing forecast {key}')
    if not frozen['post_url'].endswith('/status/' + str(frozen.get('post_id'))):
        raise ValueError('forecast post_id/url mismatch')
    clocks = {key: time(frozen.get(key), key) for key in
              ('published_at', 'origin_at', 'input_cutoff_at', 'generated_at', 'frozen_at', 'target_at')}
    if not (clocks['published_at'] <= clocks['origin_at'] <= clocks['input_cutoff_at']
            <= clocks['generated_at'] <= clocks['frozen_at'] < clocks['target_at']):
        raise ValueError('invalid publication/input/generation/freeze/target order')
    policy = frozen.get('observation_policy', {})
    budget = policy.get('late_tolerance_seconds')
    if type(budget) is not int or not 0 <= budget <= 300:
        raise ValueError('late budget must be an integer from 0 to 300 seconds')
    if type(policy.get('early_tolerance_seconds')) is not int or policy['early_tolerance_seconds'] != 0:
        raise ValueError('early tolerance must be zero')
    window_start = time(policy.get('accepted_observed_at_start'), 'window start')
    window_end = time(policy.get('accepted_observed_at_end'), 'window end')
    if window_start != clocks['target_at'] or (window_end - window_start).total_seconds() != budget:
        raise ValueError('accepted window does not match target and frozen budget')
    if not isinstance(frozen.get('outcome'), dict) or any(v is not None for v in frozen['outcome'].values()):
        raise ValueError('frozen outcome must remain null')
    if frozen.get('future_verification') is not None:
        raise ValueError('frozen future verification must remain null')
    snapshot = frozen.get('input_snapshot')
    if not isinstance(snapshot, dict):
        raise ValueError('input snapshot is required')
    canonical = json.dumps(snapshot, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False, allow_nan=False).encode()
    if hashlib.sha256(canonical).hexdigest() != frozen.get('input_snapshot_sha256'):
        raise ValueError('input snapshot SHA256 mismatch')
    for key in ('post_url', 'source', 'metric', 'published_at'):
        if snapshot.get(key) != frozen.get(key):
            raise ValueError(f'input snapshot {key} mismatch')
    observations = snapshot.get('numeric_observations')
    if not isinstance(observations, list) or not observations:
        raise ValueError('numeric input observations are required')
    prior, last_count = None, None
    for row in observations + ([snapshot['initial_observation']] if snapshot.get('initial_observation') else []):
        if not isinstance(row, dict):
            raise ValueError('input observation must be an object')
        if row.get('source', frozen['source']) != frozen['source']:
            raise ValueError('input observation source mismatch')
        start, end, observed = capture(row, required=False)
        available = time(row.get('available_at', row['observed_at']), 'input available_at')
        if start < clocks['published_at'] or available < end or available > clocks['input_cutoff_at']:
            raise ValueError('input not available by cutoff or before publication')
        value = count(row.get(frozen['metric']), 'input count')
        if row is not snapshot.get('initial_observation'):
            if value is None or (prior is not None and observed <= prior):
                raise ValueError('numeric inputs must be nonmissing and strictly chronological')
            prior, last_count = observed, value
    if prior != clocks['origin_at']:
        raise ValueError('origin must match the latest numeric input')
    if frozen.get('n_numeric_points') != len(observations):
        raise ValueError('numeric input count mismatch')
    models = frozen.get('predictions')
    if not isinstance(models, dict) or not models:
        raise ValueError('predictions are required')
    for model in models.values():
        if not isinstance(model, dict):
            raise ValueError('prediction entry must be an object')
        prediction(model.get('point_prediction'))
    return frozen, clocks, window_end, digest, last_count


def errors(p, y):
    try:
        signed = p - y
        result = {'signed_error': signed, 'absolute_error': abs(signed),
                  'squared_error': signed ** 2,
                  'smape_percent': 200 * abs(signed) / (abs(p) + abs(y)) if p or y else 0.0}
        if not all(math.isfinite(v) for v in result.values()):
            raise ValueError('error computation overflow')
        return result
    except OverflowError as exc:
        raise ValueError('error computation overflow') from exc


def evaluate_forecast(forecast_bytes, actual, expected_forecast_sha256):
    frozen, clocks, window_end, digest, origin_count = validate_frozen(forecast_bytes, expected_forecast_sha256)
    if not isinstance(actual, dict) or actual.get('contract_version') != 'rise-prospective-actual-1':
        raise ValueError('unsupported actual contract')
    for key in IDENTITY:
        if actual.get(key) != frozen[key]:
            raise ValueError(f'actual {key} mismatch')
    if 'post_id' in actual and actual['post_id'] != frozen['post_id']:
        raise ValueError('actual post_id mismatch')
    supplied = actual.get('observations')
    if not isinstance(supplied, list):
        raise ValueError('actual observations must be a list')
    rows, seen = [], {}
    for row in supplied:
        if not isinstance(row, dict):
            raise ValueError('actual observation must be an object')
        for key in IDENTITY:
            if key in row and row[key] != frozen[key]:
                raise ValueError(f'actual observation {key} mismatch')
        start, end, observed = capture(row)
        if start < clocks['published_at']:
            raise ValueError('actual capture precedes publication')
        available = row.get('available_at')
        if available is not None and time(available, 'actual available_at') < end:
            raise ValueError('actual available_at cannot precede capture completion')
        value = count(row.get('actual'), 'actual')
        evidence = (start, end, value, time(available, 'actual available_at') if available is not None else None)
        if observed in seen:
            if seen[observed] != evidence:
                raise ValueError('conflicting counts or capture metadata at the same time')
            continue
        seen[observed] = evidence
        rows.append({'actual': value, 'observed_at': row['observed_at'],
                     'observation_started_at': row['observation_started_at'],
                     'observation_completed_at': row['observation_completed_at'],
                     'available_at': available,
                     '_start': start, '_end': end})
    rows.sort(key=lambda row: row['_end'])
    if actual.get('generated_at') is not None and rows:
        if time(actual['generated_at'], 'actual generated_at') < rows[-1]['_end']:
            raise ValueError('actual generation precedes capture completion')
    numeric = [row for row in rows if row['actual'] is not None]
    candidates = [row for row in numeric if row['_end'] >= clocks['target_at']]
    selected = candidates[0] if candidates else (numeric[0] if numeric else None)
    status = 'pending'
    if selected:
        status = ('early' if selected['_end'] < clocks['target_at'] else
                  'early_or_straddling_capture' if selected['_start'] < clocks['target_at'] else
                  'outside_window' if selected['_end'] > window_end else
                  'exact_target_observation' if selected['_end'] == clocks['target_at'] else 'delayed_proxy')
    window_eligible = status in ('exact_target_observation', 'delayed_proxy')
    revision = selected['actual'] < origin_count if selected else None
    eligible = window_eligible and not revision
    declarations = ('first_successful_numeric_read_at_or_after_target', 'observation_history_complete_since_target')
    for key in declarations:
        if key in actual and type(actual[key]) is not bool:
            raise ValueError(f'{key} must be boolean')
    if window_eligible and not any(actual.get(key) is True for key in declarations):
        raise ValueError('scoring requires a first-read or complete-history operator declaration')
    clean = lambda row: {key: value for key, value in row.items() if not key.startswith('_')}
    models = {}
    for name, model in frozen['predictions'].items():
        p = model.get('point_prediction')
        models[name] = {'point_prediction': p, 'errors': errors(p, selected['actual']) if selected and p is not None else None}
    return {'contract_version': 'rise-prospective-evaluation-1',
            **{key: frozen[key] for key in IDENTITY}, 'forecast_sha256': digest,
            'input_snapshot_sha256_verified': True, 'status': status,
            'target_at': frozen['target_at'], 'selected_observation': clean(selected) if selected else None,
            'observations': [clean(row) for row in rows],
            'actual_age_seconds': (selected['_end'] - clocks['published_at']).total_seconds() if selected else None,
            'lateness_seconds': (selected['_end'] - clocks['target_at']).total_seconds() if selected else None,
            'exact_target_actual': selected['actual'] if status == 'exact_target_observation' else None,
            'target_window_eligible': window_eligible, 'n_observed_targets': int(window_eligible),
            'eligible_primary_comparison': eligible, 'n_primary_observations': int(eligible),
            'apparent_revision': revision,
            'error_scope': ('target_window_descriptive' if window_eligible else 'outside_primary_window_diagnostic'),
            'models': models, 'future_verification': None, 'training_performed': False,
            'statistical_superiority': None, 'confidence_interval': None,
            'selection_evidence': 'First numeric target read among supplied records; completeness is an operator declaration, not independently verified.',
            'interpretation': 'All numeric selected reads retain descriptive errors, including revisions and missed windows. Revisions require reconciliation before clean comparison; no failed prediction is deleted. Delayed counters are proxies; availability/generation metadata does not independently prove timely capture. No statistical or follower attribution.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('forecast', type=Path)
    parser.add_argument('actual', type=Path)
    parser.add_argument('--forecast-sha256', required=True, help='Digest independently retained when forecast was frozen')
    parser.add_argument('--output', type=Path, help='New independent evaluation file; existing files are never overwritten')
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.resolve() in (args.forecast.resolve(), args.actual.resolve()):
            raise ValueError('output must be separate from both inputs')
        report = evaluate_forecast(args.forecast.read_bytes(), read_json(args.actual.read_bytes()), args.forecast_sha256)
        rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.output:
            with args.output.open('x') as output:
                output.write(rendered)
        else:
            print(rendered, end='')
    except (ValueError, OSError, TypeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
