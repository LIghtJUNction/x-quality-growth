#!/usr/bin/env python3
"""Predict recorded post exposure, with time-ordered holdouts and no invented zero.

Public views and owner impressions are different series. This is an exploratory
within-post forecast, not X's hidden ranking score, a causal growth model, or a
forecast of when the account reaches a follower target. PyTorch is optional and
loaded only for --model torch; CPU is deliberately the only training device.
"""
import argparse
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POST_URL = re.compile(r'https://x\.com/[A-Za-z0-9_]{1,15}/status/[0-9]+\Z')
ISO_DATETIME = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\Z')
SOURCES = {'public_views': 'views', 'owner_impressions': 'impressions'}
MIN_TORCH_POINTS = 6
MIN_TORCH_SPAN_SECONDS = 900
ALGORITHM_COMMIT = '78460ca8b65c57ddd3a05f9217c8aaeba214b628'
POPULAR_SOURCE = f'https://github.com/xai-org/x-algorithm/blob/{ALGORITHM_COMMIT}/home-mixer/util/popular_posts.rs#L33-L52'


def timestamp(value, name):
    if value is None:
        return None
    if not isinstance(value, str) or ISO_DATETIME.fullmatch(value) is None:
        raise ValueError(f'{name} must be an ISO datetime with a timezone')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'invalid {name}') from exc
    if parsed.utcoffset() is None:
        raise ValueError(f'{name} must include a timezone')
    return parsed.astimezone(timezone.utc)


def iso(value):
    return value.isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def counter(value, name):
    if value is not None and (type(value) is not int or value < 0):
        raise ValueError(f'{name} must be a nonnegative integer or null')
    return value


def load_series(data):
    """Validate relevant rows, reconcile duplicates, and retain exclusion reasons.

    A decreasing cumulative counter invalidates the entire series for rate-based
    prediction. It is retained as a revision issue rather than clamped to zero.
    Edited URLs remain separate; original_published_at is not substituted for a
    missing publication timestamp of a different URL.
    """
    if not isinstance(data, dict):
        raise ValueError('metrics must be an object')
    rows, publications, skipped = [], {}, []
    for collection in ('posts', 'post_observations', 'analytics_observations'):
        entries = data.get(collection, [])
        if not isinstance(entries, list):
            raise ValueError(f'{collection} must be a list')
        for index, row in enumerate(entries):
            if not isinstance(row, dict):
                raise ValueError(f'{collection}[{index}] must be an object')
            url = row.get('url')
            if not isinstance(url, str) or POST_URL.fullmatch(url) is None:
                raise ValueError(f'{collection}[{index}] needs an exact X post URL')
            published = timestamp(row.get('published_at'), 'published_at')
            observed = timestamp(row.get('observed_at'), 'observed_at')
            if published is not None:
                if url in publications and publications[url] != published:
                    raise ValueError(f'conflicting published_at for {url}')
                publications[url] = published
            # Reject invalid counters even if this row will be skipped for time.
            for name in ('views', 'impressions', 'replies', 'likes', 'reposts',
                         'bookmarks', 'engagements', 'profile_visits',
                         'detail_expands', 'link_clicks'):
                if name in row:
                    counter(row[name], name)
            source = ('owner_impressions' if collection == 'analytics_observations'
                      else 'public_views')
            value = row.get(SOURCES[source])
            if observed is None or value is None:
                skipped.append({'collection': collection, 'index': index,
                                'url': url, 'source': source,
                                'reason': ('missing_observed_at' if observed is None
                                           else 'missing_counter')})
                continue
            rows.append((url, source, observed, value))
    grouped = defaultdict(dict)
    for url, source, observed, value in rows:
        if url not in publications:
            skipped.append({'url': url, 'source': source,
                            'observed_at': iso(observed), 'reason': 'missing_published_at'})
            continue
        if observed < publications[url]:
            raise ValueError(f'observed_at precedes publication for {url}')
        by_time = grouped[(url, source)]
        if observed in by_time and by_time[observed] != value:
            raise ValueError(f'conflicting counters at the same time for {url}/{source}')
        by_time[observed] = value
    series = []
    for (url, source), by_time in sorted(grouped.items()):
        publication = publications[url]
        observations = [{'observed_at': iso(time),
                         'age_seconds': (time - publication).total_seconds(),
                         'value': value} for time, value in sorted(by_time.items())]
        revisions = [{'before_at': previous['observed_at'],
                      'after_at': current['observed_at'],
                      'before': previous['value'], 'after': current['value']}
                     for previous, current in zip(observations, observations[1:])
                     if current['value'] < previous['value']]
        series.append({'url': url, 'source': source, 'published_at': iso(publication),
                       'observations': observations,
                       'status': 'counter_revision' if revisions else 'usable',
                       'counter_revisions': revisions})
    return series, skipped


def errors(actual, prediction):
    """sMAPE uses 200|p-y|/(|p|+|y|); zero versus zero is exactly zero."""
    if not all(type(x) in (int, float) and math.isfinite(x) and x >= 0
               for x in (actual, prediction)):
        raise ValueError('actual and prediction must be finite nonnegative numbers')
    signed = prediction - actual
    denominator = abs(prediction) + abs(actual)
    return {'signed_error': signed, 'absolute_error': abs(signed),
            'squared_error': signed * signed,
            'smape_percent': 0.0 if denominator == 0 else 200 * abs(signed) / denominator}


def summarize(rows):
    if not rows:
        return {'status': 'insufficient_data', 'n_predictions': 0, 'n_posts': 0,
                'mae': None, 'rmse': None, 'bias_predicted_minus_actual': None,
                'smape_percent': None}
    count = len(rows)
    return {'status': 'descriptive_within_post_only', 'n_predictions': count,
            'n_posts': len({row['url'] for row in rows}),
            'mae': sum(row['absolute_error'] for row in rows) / count,
            'rmse': math.sqrt(sum(row['squared_error'] for row in rows) / count),
            'bias_predicted_minus_actual': sum(row['signed_error'] for row in rows) / count,
            'smape_percent': sum(row['smape_percent'] for row in rows) / count,
            'confidence_interval': None,
            'dependence': 'Repeated origins from one post are correlated; not independent trials.'}


def baseline_predictions(train, target_age):
    previous, last = train[-2:]
    span = last['age_seconds'] - previous['age_seconds']
    if span <= 0 or target_age <= last['age_seconds']:
        raise ValueError('prediction target must be later than the ordered training points')
    increase = last['value'] - previous['value']
    if increase < 0:
        raise ValueError('counter revision cannot be used as a growth rate')
    horizon = target_age - last['age_seconds']
    return {'constant': float(last['value']),
            'recent_rate': last['value'] + increase / span * horizon}


def horizon_bucket(seconds):
    """Operating bins for comparable errors; not official X time thresholds."""
    if seconds <= 900:
        return '0_to_15_minutes'
    if seconds <= 3600:
        return '15_to_60_minutes'
    if seconds <= 21600:
        return '1_to_6_hours'
    if seconds <= 86400:
        return '6_to_24_hours'
    return 'over_24_hours'


def popular_pool_score(views, age_seconds):
    """Official popular-pool quality score, NOT an observed/fitted 24h total."""
    counter(views, 'views')
    if views is None or type(age_seconds) not in (int, float) or not math.isfinite(age_seconds) or age_seconds < 0:
        raise ValueError('score requires nonnegative views and finite post age')
    if age_seconds > 86400:
        return None  # Official selector excludes posts older than its 24h window.
    decay_per_hour = math.log(2) / 8
    return views * -math.expm1(-decay_per_hour * 24) / -math.expm1(-decay_per_hour * max(age_seconds / 3600, 0.5))


def torch_gate(train):
    if len(train) < MIN_TORCH_POINTS:
        return 'insufficient_data'
    if train[-1]['age_seconds'] - train[0]['age_seconds'] < MIN_TORCH_SPAN_SECONDS:
        return 'insufficient_time_span'
    return None


def saturation_value(parameters, age_seconds):
    return parameters['b'] + parameters['A'] * -math.expm1(-age_seconds / parameters['tau_seconds'])


def anchored_saturation_prediction(parameters, train, target_age):
    """Use the fitted curve's future increment; keep the actual origin counter."""
    origin = train[-1]
    if target_age <= origin['age_seconds']:
        raise ValueError('prediction target must be later than origin')
    increment = saturation_value(parameters, target_age) - saturation_value(parameters, origin['age_seconds'])
    if increment < 0:
        raise ValueError('saturation parameters must imply nonnegative increments')
    return origin['value'] + increment


def fit_saturation(train, epochs=400):
    """CPU-only, three positive parameters, log-count loss, training rows only.

    I(age) = b + A*(1-exp(-age/tau)). b is fitted, not an invented zero
    observation. This one-component curve cannot establish saturation or capture
    recirculation peaks. Six points is an engineering gate, not a power analysis.
    """
    problem = torch_gate(train)
    if problem:
        return {'status': problem}
    try:
        import torch
    except ImportError:
        return {'status': 'torch_unavailable'}
    torch.set_num_threads(min(torch.get_num_threads(), 4))
    torch.manual_seed(0)
    device = torch.device('cpu')
    dtype = torch.float64
    ages = torch.tensor([row['age_seconds'] / 3600 for row in train], dtype=dtype, device=device)
    counts = torch.tensor([row['value'] for row in train], dtype=dtype, device=device)
    initial = [max(train[0]['value'] * 0.5, 0.1),
               max((train[-1]['value'] - train[0]['value']) * 1.5, 1),
               max((train[-1]['age_seconds'] - train[0]['age_seconds']) / 3600, 0.1)]
    inverse_softplus = [value + math.log(-math.expm1(-value)) for value in initial]
    raw = torch.nn.Parameter(torch.tensor(inverse_softplus, dtype=dtype, device=device))
    optimizer = torch.optim.Adam([raw], lr=0.03)
    for _ in range(epochs):
        optimizer.zero_grad()
        positive = torch.nn.functional.softplus(raw)
        b, amplitude, tau_hours = positive.unbind()
        tau_hours = tau_hours + 1 / 3600
        predicted = b + amplitude * -torch.expm1(-ages / tau_hours)
        loss = torch.mean((torch.log1p(predicted) - torch.log1p(counts)) ** 2)
        if not bool(torch.isfinite(loss)):
            return {'status': 'numerical_failure'}
        loss.backward()
        optimizer.step()
    positive = torch.nn.functional.softplus(raw.detach()).tolist()
    parameters = {'b': positive[0], 'A': positive[1],
                  'tau_seconds': (positive[2] + 1 / 3600) * 3600}
    if not all(math.isfinite(value) and value > 0 for value in parameters.values()):
        return {'status': 'numerical_failure'}
    predictions = [saturation_value(parameters, row['age_seconds']) for row in train]
    final_loss = sum((math.log1p(prediction) - math.log1p(row['value'])) ** 2
                     for row, prediction in zip(train, predictions)) / len(train)
    return {'status': 'experimental_fit', 'device': 'cpu', 'torch_version': torch.__version__,
            'epochs': epochs, 'parameters': parameters, 'loss': 'mean_squared_log1p_count',
            'training_loss': final_loss, 'n_training_points': len(train),
            'training_cutoff': train[-1]['observed_at'], 'parameter_intervals': None,
            'trainable_parameter_count': 3,
            'trainable_state': {'name': 'raw_positive_parameters', 'shape': [3],
                                'dtype': 'float64', 'values': raw.detach().tolist()},
            'architecture': 'softplus-constrained b, A, tau; tau floor is 1 second'}


def build_report(data, model='baseline', forecast_hours=24, epochs=400, fit_fn=None):
    if model not in ('baseline', 'torch'):
        raise ValueError('model must be baseline or torch')
    if type(forecast_hours) not in (int, float) or not math.isfinite(forecast_hours) or forecast_hours <= 0:
        raise ValueError('forecast_hours must be finite and positive')
    if type(epochs) is not int or not 1 <= epochs <= 10000:
        raise ValueError('epochs must be an integer from 1 to 10000')
    fit_fn = fit_fn or fit_saturation
    loaded, skipped = load_series(data)
    report = {'schema_version': 1, 'requested_model': model,
              'text_features_included': False, 'comment_features_included': False,
              'model_trainable_parameter_count': 3 if model == 'torch' else 0,
              'target': 'cumulative exposure, not an algorithm ranking score',
              'evaluation': 'rolling_origin: first two observations predict the next; latest is held out',
              'limitations': [
                  'Only real published_at values are used; no synthetic observation at age zero.',
                  'Public views and owner impressions are never pooled.',
                  'Same-post repeated predictions are correlated; cross-post generalization is untested.',
                  'Public counts can include operator opens; engagement and follower causality are unknown.',
                  'Text, media and comments are not model inputs; a future content model needs frozen-cutoff data and ablation.',
                  'A saturating curve is a hypothesis; recommendation can create multiple bursts.',
                  'Forecast and parameter uncertainty intervals are unknown, not zero.',
                  'No follower-target arrival forecast is produced.'],
              'series': [], 'skipped_observations': skipped, 'summaries': []}
    all_predictions = []
    fit_count = 0
    for series in loaded:
        result = dict(series)
        result.update(predictions=[], latest_holdout={}, future_forecasts=[], torch_fit=None,
                      official_popular_pool_score=None)
        observations = series['observations']
        if series['source'] == 'public_views':
            latest = observations[-1]
            score = popular_pool_score(latest['value'], latest['age_seconds'])
            result['official_popular_pool_score'] = {
                'name': 'popular_pool_24h_equivalent_score', 'score': score,
                'observed_at': latest['observed_at'], 'age_seconds': latest['age_seconds'],
                'views': latest['value'], 'half_life_hours': 8.0, 'age_floor_hours': 0.5,
                'window_hours': 24.0, 'source': POPULAR_SOURCE,
                'status': 'candidate_pool_score' if score is not None else 'outside_official_selection_window',
                'meaning': 'Age-normalized popular candidate quality; not a calibrated 24h prediction or full recommendation score.'}
        if series['status'] != 'usable':
            report['series'].append(result)
            continue
        if len(observations) < 3:
            result['status'] = 'insufficient_data'
        for index in range(2, len(observations)):
            train, actual = observations[:index], observations[index]
            candidates = baseline_predictions(train, actual['age_seconds'])
            fit = None
            if model == 'torch':
                problem = torch_gate(train)
                fit = {'status': problem} if problem else fit_fn(train, epochs=epochs)
                if fit['status'] == 'experimental_fit':
                    candidates['torch_saturation'] = anchored_saturation_prediction(fit['parameters'], train, actual['age_seconds'])
            for name, prediction in candidates.items():
                row = {'url': series['url'], 'source': series['source'], 'model': name,
                       'published_at': series['published_at'],
                       'origin_at': train[-1]['observed_at'], 'target_at': actual['observed_at'],
                       'training_observations': [dict(point) for point in train],
                       'training_points': len(train), 'actual': actual['value'], 'prediction': prediction,
                       'origin_age_seconds': train[-1]['age_seconds'],
                       'target_age_seconds': actual['age_seconds'],
                       'forecast_horizon_seconds': actual['age_seconds'] - train[-1]['age_seconds'],
                       'horizon_bucket': horizon_bucket(actual['age_seconds'] - train[-1]['age_seconds']),
                       'latest_holdout': index == len(observations) - 1,
                       **errors(actual['value'], prediction)}
                if name == 'torch_saturation':
                    row['fit'] = fit
                    row['forecast_anchor'] = 'last_actual_counter_plus_fitted_future_increment'
                result['predictions'].append(row)
                all_predictions.append(row)
            if index == len(observations) - 1:
                result['latest_holdout'] = {'target_at': actual['observed_at'],
                                           'baseline_status': 'evaluated',
                                           'torch_status': fit['status'] if fit else 'not_requested'}
        if model == 'torch':
            problem = torch_gate(observations)
            final_fit = {'status': problem} if problem else fit_fn(observations, epochs=epochs)
            result['torch_fit'] = final_fit
            fit_count += final_fit['status'] == 'experimental_fit'
        target_age = forecast_hours * 3600
        if len(observations) >= 2 and target_age > observations[-1]['age_seconds']:
            candidates = baseline_predictions(observations, target_age)
            if model == 'torch' and result['torch_fit']['status'] == 'experimental_fit':
                candidates['torch_saturation'] = anchored_saturation_prediction(result['torch_fit']['parameters'], observations, target_age)
            publication = timestamp(series['published_at'], 'published_at')
            for name, prediction in candidates.items():
                result['future_forecasts'].append({
                    'model': name, 'status': 'experimental_extrapolation',
                    'origin_at': observations[-1]['observed_at'],
                    'target_at': iso(publication + timedelta(seconds=target_age)),
                    'target_age_seconds': target_age,
                    'forecast_horizon_seconds': target_age - observations[-1]['age_seconds'],
                    'prediction': prediction, 'actual': None, 'error': None,
                    'prediction_interval': None,
                    'warning': 'Outside observed ages; 24-hour popularity is unconfirmed. No coverage guarantee.'})
        report['series'].append(result)
    names = ['constant', 'recent_rate'] + (['torch_saturation'] if model == 'torch' else [])
    for source in SOURCES:
        buckets = sorted({row['horizon_bucket'] for row in all_predictions if row['source'] == source}) or ['no_evaluable_horizon']
        for bucket in buckets:
            for name in names:
                selected = [row for row in all_predictions if row['source'] == source and row['model'] == name
                            and row['horizon_bucket'] == bucket]
                report['summaries'].append({'source': source, 'model': name, 'horizon_bucket': bucket,
                                           **summarize(selected),
                                           'latest_holdout': summarize([row for row in selected if row['latest_holdout']])})
            if model == 'torch':
                # Compare all models on exactly the origins eligible for torch.
                keys = {(row['url'], row['target_at']) for row in all_predictions
                        if row['source'] == source and row['horizon_bucket'] == bucket
                        and row['model'] == 'torch_saturation'}
                report.setdefault('matched_origin_comparison', []).append({
                    'source': source, 'horizon_bucket': bucket,
                    'models': {name: summarize([row for row in all_predictions
                                               if row['source'] == source and row['model'] == name
                                               and row['horizon_bucket'] == bucket
                                               and (row['url'], row['target_at']) in keys]) for name in names},
                    'conclusion': 'descriptive_only; no independent cross-post superiority claim'})
    torch_rows = [row for row in all_predictions if row['model'] == 'torch_saturation']
    report['status'] = (('evaluated_experimental' if torch_rows else
                         'insufficient_validation_data' if fit_count else 'insufficient_data')
                        if model == 'torch' else
                        'evaluated_baselines' if all_predictions else 'insufficient_data')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metrics', type=Path, default=ROOT / 'public/metrics.json')
    parser.add_argument('--outputpath', '--output', type=Path, default=ROOT / 'runs/heat-prediction.json')
    parser.add_argument('--model', choices=('baseline', 'torch'), default='baseline')
    parser.add_argument('--model-outputpath', type=Path,
                        help='Optional JSON model artifact with three-scalar tensor states and training cutoffs')
    parser.add_argument('--forecast-hours', type=float, default=24)
    parser.add_argument('--epochs', type=int, default=400)
    args = parser.parse_args(argv)
    try:
        if args.metrics.resolve() == args.outputpath.resolve():
            raise ValueError('output path must not overwrite input metrics')
        if args.model_outputpath and args.model_outputpath.resolve() in (args.metrics.resolve(), args.outputpath.resolve()):
            raise ValueError('model artifact path must be distinct from metrics and report')
        report = build_report(json.loads(args.metrics.read_text()), model=args.model,
                              forecast_hours=args.forecast_hours, epochs=args.epochs)
        args.outputpath.parent.mkdir(parents=True, exist_ok=True)
        args.outputpath.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        models = [{'url': row['url'], 'source': row['source'], 'published_at': row['published_at'],
                   **row['torch_fit']} for row in report['series']
                  if row['torch_fit'] and row['torch_fit']['status'] == 'experimental_fit']
        if args.model_outputpath and models:
            args.model_outputpath.parent.mkdir(parents=True, exist_ok=True)
            args.model_outputpath.write_text(json.dumps({
                'schema_version': 1, 'architecture': 'three-scalar constrained exposure saturation',
                'text_features_included': False, 'comment_features_included': False,
                'validation': report['status'], 'models': models,
                'limitations': report['limitations']}, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    except (ValueError, OSError, TypeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    print(json.dumps({'status': report['status'], 'output': str(args.outputpath),
                      'model_artifact_written': bool(args.model_outputpath and models),
                      'summaries': report['summaries']}, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
