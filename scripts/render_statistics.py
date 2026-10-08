#!/usr/bin/env python3
"""Render recorded growth and descriptive heat backtests; never invent observations.

The three public JSON reports keep their own clocks. This renderer does not train
a model, recalculate attribution, join sources, or create forecast actuals.
Requires Matplotlib; output is standalone SVG suitable for rsvg-convert.
"""
import argparse
import io
import json
import math
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
from matplotlib.figure import Figure

ROOT = Path(__file__).resolve().parents[1]
CREAM, INK, MUTED, TEAL = '#f5f1e9', '#191b1b', '#636660', '#21796f'
GRID, PANEL = '#d8d1c6', '#eee8de'
MODELS = ('constant', 'recent_rate', 'torch_saturation')
MODEL_LABELS = {'constant': 'Constant', 'recent_rate': 'Recent rate', 'torch_saturation': 'Torch curve'}
MODEL_COLORS = {'constant': '#999b92', 'recent_rate': TEAL, 'torch_saturation': '#b73825'}
SHORT_LABELS = {
    'launch': 'Launch post', 'initial_prompt': 'Prompt experiment',
    'reach_recovery_original': 'Reach experiment', 'technical_original': 'Technical original',
    'technical_original_edited_version': 'Technical original (edit)',
    'git_matrix_original': 'Git matrix', 'algorithm_source_original': 'Algorithm source',
    'scoped_review_reply': 'Scoped review', 'harness_feedback_reply': 'Agent harness',
    'luna_decisions_advice_reply': 'Luna decisions', 'cohort_progress_reply': 'Cohort progress',
    'matrix_progress_reply': 'Matrix progress', 'annotation_method_reply': 'Annotation method',
    'annotation_temporal_feedback_followup': 'Temporal labels',
    'annotated_keyframes_delivery': 'Keyframe delivery', 'annotated_video_delivery': 'Video delivery',
}
HORIZONS = {
    '0_to_15_minutes': '0-15 min', '15_to_60_minutes': '15-60 min',
    '1_to_6_hours': '1-6 h', '6_to_24_hours': '6-24 h', 'over_24_hours': '>24 h',
}


def parse_time(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.utcoffset() is None:
        raise ValueError('source timestamps require a timezone')
    return parsed.astimezone(timezone.utc)


def clock(value, seconds=False):
    if not value:
        return 'N/A'
    return parse_time(value).strftime('%m-%d %H:%M:%S' if seconds else '%m-%d %H:%M')


def number(value, digits=1):
    if value is None:
        return 'N/A'
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('plotted values must be finite numbers or null')
    return f'{value:,}' if isinstance(value, int) else f'{value:,.{digits}f}'


def short_label(kind, url=''):
    raw = SHORT_LABELS.get(kind, (kind or ('Post ' + url.rsplit('/', 1)[-1][-6:])).replace('_', ' '))
    return textwrap.shorten(raw, width=25, placeholder='...')


def figure(title, subtitle):
    fig = Figure(figsize=(14, 8.25), facecolor=CREAM)
    fig.text(.055, .951, title, fontsize=24, weight='bold', color=INK)
    fig.text(.057, .913, subtitle, fontsize=10, color=MUTED)
    return fig


def clean_axes(ax):
    ax.set_facecolor(CREAM)
    ax.spines[['top', 'right']].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9, length=0, pad=6)
    ax.grid(axis='y', color=GRID, linewidth=.65)
    ax.set_axisbelow(True)


def table(ax, rows, columns, widths):
    ax.axis('off')
    rendered = ax.table(cellText=rows, colLabels=columns, colWidths=widths,
                        cellLoc='left', colLoc='left', bbox=[0, 0, 1, 1])
    rendered.auto_set_font_size(False)
    rendered.set_fontsize(8.5)
    for (row, col), cell in rendered.get_celld().items():
        cell.set_edgecolor(GRID)
        cell.set_linewidth(.5)
        cell.set_facecolor(PANEL if row == 0 else CREAM)
        cell.get_text().set_color(INK if row == 0 else MUTED)
        if row == 0:
            cell.get_text().set_weight('bold')
        cell.PAD = .06
    return rendered


def as_svg(fig, title, description):
    output = io.StringIO()
    fig.savefig(output, format='svg', facecolor=CREAM,
                metadata={'Title': title, 'Description': description, 'Date': None, 'Creator': 'RISE'})
    return '\n'.join(line.rstrip() for line in output.getvalue().splitlines()) + '\n'


def timed_endpoints(dynamics):
    intervals = dynamics.get('intervals', [])
    if not intervals:
        return []
    points = [(intervals[0]['started_at'], intervals[0]['count_before'])]
    for interval in intervals:
        if parse_time(interval['ended_at']) <= parse_time(interval['started_at']):
            raise ValueError('growth interval must have increasing timestamps')
        points.append((interval['ended_at'], interval['count_after']))
    return points


def statistics_svg(growth, posts):
    """Draw actual interval endpoints, midpoints, and latest analytics captures."""
    dynamics = growth['follower_dynamics']
    points = timed_endpoints(dynamics)
    latest = points[-1] if points else (None, None)
    fig = figure('RISE / What actually changed',
                 'Timed count observations and owner analytics. No follower acquisition attribution.')
    ax = fig.add_axes([.066, .573, .59, .263])
    clean_axes(ax)
    ax.set_title(f'Total followers | {len(points)} timed observations', loc='left', fontsize=12, color=INK, pad=10)
    ax.set_ylabel('Followers', fontsize=10, color=MUTED)
    if points:
        times, values = zip(*[(parse_time(at), value) for at, value in points])
        ax.plot(times, values, color=TEAL, linewidth=2.2, marker='o', markersize=3.4)
        ax.set_ylim(0, max(max(values)*1.14, 1))
        ax.set_xlim(times[0], times[-1])
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M', tz=timezone.utc))
    else:
        ax.text(.05, .45, 'N/A: no timed intervals', transform=ax.transAxes, color=MUTED)
        ax.set_ylim(0, 1)
    ax.tick_params(axis='x', labelbottom=False)

    velocity = fig.add_axes([.066, .360, .59, .132], sharex=ax)
    clean_axes(velocity)
    velocity.set_title('Interval net velocity | dots at actual time midpoints', loc='left', fontsize=11, color=INK, pad=9)
    velocity.set_ylabel('Followers / h', fontsize=9, color=MUTED)
    rates = []
    for interval in dynamics.get('intervals', []):
        rate = interval['net_rate_per_hour']
        number(rate)
        rates.append(rate)
        velocity.hlines(rate, parse_time(interval['started_at']), parse_time(interval['ended_at']),
                        color=TEAL, linewidth=1.5, alpha=.6)
        velocity.scatter(parse_time(interval['midpoint_at']), rate, color=TEAL, s=15, zorder=3)
    velocity.axhline(0, color=MUTED, linewidth=.8)
    if rates:
        velocity.set_ylim(min(0, min(rates))*1.15, max(max(rates)*1.15, 1))
    velocity.set_xlabel('Actual observation time (UTC)', fontsize=9, color=MUTED, labelpad=8)

    side = fig.add_axes([.706, .353, .244, .485])
    side.axis('off')
    side.text(0, .97, 'Latest total', color=MUTED, fontsize=11)
    side.text(0, .853, number(latest[1]), color=INK, fontsize=34, weight='bold')
    side.text(0, .804, 'Captured ' + clock(latest[0], True) + ' UTC', color=MUTED, fontsize=9)
    average = dynamics.get('duration_weighted_average')
    if average:
        side.text(0, .726, f'Timed net {average["net_delta"]:+d} | mean {average["net_rate_per_hour"]:.1f} / h', color=TEAL, fontsize=11, weight='bold')
    blues = timed_endpoints(growth.get('blue_membership_dynamics', {}))
    side.text(0, .606, 'Latest measured blue stock', color=MUTED, fontsize=11)
    side.text(0, .538, number(blues[-1][1]) if blues else 'N/A', color=INK, fontsize=18, weight='bold')
    side.text(0, .485, clock(blues[-1][0], True) + ' UTC' if blues else 'No timed blue interval', color=MUTED, fontsize=9)
    current_blue = blues[-1][1] if blues and latest[0] and parse_time(blues[-1][0]) == parse_time(latest[0]) else None
    side.text(0, .425, 'Blue stock at latest total: ' + number(current_blue), color=MUTED, fontsize=9)
    cohort = growth.get('observed_cohort_quality', {})
    share = cohort.get('lower_bound')
    side.text(0, .307, 'Observed cohort quality', color=MUTED, fontsize=11)
    side.text(0, .237, f'{number(cohort.get("high"))} / {number(cohort.get("observed_arrivals"))} high' + (f' ({share:.0%})' if share is not None else ' (N/A)'), color=TEAL, fontsize=16, weight='bold')
    side.text(0, .181, 'Unknown: ' + number(cohort.get('unknown')), color=MUTED, fontsize=9)
    side.text(0, .127, 'Window end ' + clock(cohort.get('window_ended_at'), True) + ' UTC', color=MUTED, fontsize=9)
    side.text(0, .069, 'Observed membership; not confirmed new followers.', color=MUTED, fontsize=8.3)
    skipped = dynamics.get('skipped_observations', [])
    untimed = [row for row in skipped if row.get('reason') == 'missing_exact_timestamp']
    if untimed:
        note = ', '.join(number(row.get('count')) for row in untimed[:3])
        fig.text(.068, .875, f'Untimed count(s) excluded from line: {note}', fontsize=8.5, color=MUTED)

    analytics = [(row, row['latest_owner_analytics']) for row in posts.get('per_post', []) if row.get('latest_owner_analytics')]
    analytics.sort(key=lambda item: parse_time(item[1]['observed_at']))
    selected = analytics[-6:]
    fig.text(.058, .293, f'Owner-analytics event table | latest {len(selected)} of {len(analytics)} posts, ordered by capture time', fontsize=11, color=INK, weight='bold')
    data_rows = []
    for post, capture in selected:
        counts, ratios = capture['counts'], capture.get('event_ratios', {})
        profile_ratio, click_ratio = ratios.get('profile_visits_per_impression'), ratios.get('link_clicks_per_impression')
        data_rows.append([short_label(post.get('kind'), post['url']), clock(capture['observed_at'], True),
                          number(capture.get('age_seconds') / 60 if capture.get('age_seconds') is not None else None),
                          number(counts.get('impressions')), number(counts.get('engagements')),
                          number(profile_ratio*1000 if profile_ratio is not None else None),
                          number(click_ratio*1000 if click_ratio is not None else None)])
    table(fig.add_axes([.056, .082, .895, .189]), data_rows or [['N/A']*7],
          ['Post', 'Captured (UTC)', 'Age (min)', 'Impressions', 'Eng. events', 'Profiles / 1k', 'Clicks / 1k'],
          [.22, .18, .10, .12, .12, .13, .13])
    fig.text(.058, .049, 'Rates: counted events / 1,000 impressions, not people. N/A means unknown; different post ages are not effect rankings.', fontsize=8.5, color=MUTED)
    fig.text(.058, .024, 'Public views differ from impressions. Cohort and profile clocks differ; no conversion or causal growth claim.', fontsize=8.5, color=MUTED)
    return as_svg(fig, 'RISE real growth statistics', 'Timed observations only; separate analytics clocks, event rates and cohort scope.')


def prediction_svg(report, posts):
    """Compare matched public-view origins by horizon; show real held-out cases."""
    fig = figure('RISE / Heat prediction, checked against reality',
                 'Public views only. Rolling-origin held-out counts; matched MAE is descriptive, not a model superiority claim.')
    matched = []
    for row in report.get('matched_origin_comparison', []):
        if row.get('source') != 'public_views':
            continue
        models = row.get('models', {})
        signatures = {(models[name].get('n_predictions'), models[name].get('n_posts')) for name in MODELS if name in models}
        if len(signatures) != 1 or len(models) != len(MODELS):
            raise ValueError('MAE comparison needs all models with matched sample counts')
        if models['torch_saturation'].get('n_predictions', 0):
            matched.append(row)
    order = list(HORIZONS)
    matched.sort(key=lambda row: order.index(row['horizon_bucket']) if row['horizon_bucket'] in order else len(order))
    ax = fig.add_axes([.146, .515, .513, .315])
    clean_axes(ax)
    ax.set_title('Matched-origin MAE by forecast horizon', loc='left', fontsize=12, color=INK, pad=12)
    ax.set_xlabel('Mean absolute error (public views)', fontsize=10, color=MUTED, labelpad=9)
    ticks, ticklabels, max_mae = [], [], 0
    for group, row in enumerate(matched):
        tick = group*4+1
        ticks.append(tick)
        summary = row['models']['torch_saturation']
        ticklabels.append(f'{HORIZONS.get(row["horizon_bucket"], row["horizon_bucket"])}\n{summary["n_predictions"]} origin(s) / {summary["n_posts"]} post(s)')
        for index, model in enumerate(MODELS):
            value = row['models'][model]['mae']
            number(value)
            if value is None:
                raise ValueError('an evaluated matched MAE must not be null')
            max_mae = max(max_mae, value)
            ax.barh(group*4+index, value, height=.66, color=MODEL_COLORS[model], label=MODEL_LABELS[model] if group == 0 else None)
            ax.annotate(f'{value:.2f}', (value, group*4+index), xytext=(5, 0), textcoords='offset points', fontsize=9, color=INK, va='center')
    if matched:
        ax.set_yticks(ticks, ticklabels)
        ax.set_xlim(0, max(max_mae*1.20, 1))
        ax.invert_yaxis()
        handles, legend_labels = ax.get_legend_handles_labels()
        fig.legend(handles, legend_labels, loc='lower left', bbox_to_anchor=(.142, .425),
                   ncol=3, frameon=False, fontsize=8.5)
    else:
        ax.text(.05, .5, 'N/A: no torch-eligible matched origins', transform=ax.transAxes, color=MUTED)
        ax.set_yticks([])
        ax.set_xlim(0, 1)
    public_series = [series for series in report.get('series', []) if series.get('source') == 'public_views']
    origins = {(series['url'], row['target_at']) for series in public_series for row in series.get('predictions', []) if row.get('model') == 'torch_saturation'}
    unique_posts = {url for url, _ in origins}
    side = fig.add_axes([.717, .49, .23, .345])
    side.axis('off')
    notes = [('Matched evaluation', MUTED, 11),
             (f'{len(origins)} origins / {len(unique_posts)} post(s)', INK, 19),
             ('One account; repeated origins are correlated.', MUTED, 9),
             ('Cross-post generalization: untested', MUTED, 10),
             ('Text / media / comments: not trained', MUTED, 10),
             ('Prediction intervals: N/A', MUTED, 10),
             ('No follower-arrival forecast', TEAL, 10)]
    for index, (note, color, size) in enumerate(notes):
        side.text(0, .94-index*.134, note, color=color, fontsize=size, weight='bold' if index == 1 else 'normal')
    kind_by_url = {row['url']: row.get('kind') for row in posts.get('per_post', [])}
    examples = []
    for series in public_series:
        latest = {row['model']: row for row in series.get('predictions', []) if row.get('latest_holdout')}
        selected = latest.get('torch_saturation') or latest.get('recent_rate')
        if selected:
            examples.append(selected)
    examples.sort(key=lambda row: parse_time(row['target_at']))
    examples = examples[-6:]
    fig.text(.058, .390, 'Latest held-out examples | Torch when evaluated; otherwise recent-rate baseline', fontsize=11, color=INK, weight='bold')
    data_rows = [[short_label(kind_by_url.get(row['url']), row['url']), clock(row['origin_at']), clock(row['target_at']),
                  number(row['actual']), number(row['prediction']), number(row['absolute_error']), MODEL_LABELS[row['model']]] for row in examples]
    table(fig.add_axes([.056, .173, .895, .19]), data_rows or [['N/A']*7],
          ['Post', 'Origin (UTC)', 'Target (UTC)', 'Actual', 'Predicted', 'Abs. error', 'Model'],
          [.23, .17, .17, .10, .11, .11, .11])
    fig.text(.058, .134, 'Examples are selected by capture time, not error. Edited status IDs remain separate; missing publication times are excluded.', fontsize=8.5, color=MUTED)
    fig.text(.058, .103, 'MAE bars use the same eligible origins within each horizon. Samples from one post do not prove performance on other posts.', fontsize=8.5, color=MUTED)
    fig.text(.058, .072, 'Official popular-pool normalization: 8h half-life / 0.5h age floor / 24h window. This pool score is not a 24h forecast.', fontsize=8.5, color=MUTED)
    fig.text(.058, .035, 'Sparse single-account evidence. Content effects, independent audience conversion and causal growth remain unknown.', fontsize=9, color=TEAL)
    return as_svg(fig, 'RISE descriptive heat prediction backtest', 'Matched origins by source and horizon; real held-out examples, no generalization or growth guarantee.')


def load(path):
    def reject(value):
        raise ValueError('nonfinite JSON constant ' + value)
    data = json.loads(path.read_text(), parse_constant=reject)
    if not isinstance(data, dict):
        raise ValueError(str(path) + ' must contain a JSON object')
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--growth', type=Path, default=ROOT/'public/growth-dynamics.json')
    parser.add_argument('--posts', type=Path, default=ROOT/'public/post-statistics.json')
    parser.add_argument('--heat', type=Path, default=ROOT/'public/heat-prediction.json')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'assets')
    args = parser.parse_args(argv)
    try:
        growth, posts, heat = load(args.growth), load(args.posts), load(args.heat)
        if growth.get('account') != posts.get('account'):
            raise ValueError('growth and post reports must describe the same account')
        with matplotlib.rc_context({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none', 'svg.hashsalt': 'RISE-statistics-v1'}):
            rendered = {'statistics.svg': statistics_svg(growth, posts), 'prediction.svg': prediction_svg(heat, posts)}
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, content in rendered.items():
            (args.output_dir/name).write_text(content)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('Cannot render recorded statistics: ' + str(exc), file=sys.stderr)
        return 2
    print(json.dumps({'written': [str(args.output_dir/name) for name in rendered], 'source_clocks_preserved': True}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
