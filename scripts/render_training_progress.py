#!/usr/bin/env python3
"""Render the public temporal-validation aggregates, without loading row data."""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.text import Text


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'public/retweet-validation.json'
OUTPUT = ROOT / 'assets'
BG = '#f5f1e9'
INK = '#191b1b'
MUTED = '#636660'
TEAL = '#21796f'
ORANGE = '#a65632'
GREY = '#919c95'
GRID = '#d8d1c6'


def number(value: object) -> float | None:
    """Keep unavailable measurements unavailable, including interval fields."""
    if value is None:
        return None
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError('Non-finite aggregate measurement')
    return converted


def shown(value: float | None, digits: int = 4, percent: bool = False) -> str:
    if value is None:
        return 'N/A'
    return f'{100 * value:.{digits}f}%' if percent else f'{value:.{digits}f}'


def style_axis(ax: plt.Axes) -> None:
    ax.set_facecolor(BG)
    ax.spines[['top', 'right', 'left']].set_visible(False)
    ax.spines['bottom'].set_color(GRID)
    ax.tick_params(axis='both', colors=MUTED, labelsize=12, length=0, pad=9)
    ax.set_axisbelow(True)
    ax.grid(axis='x', color=GRID, linewidth=0.7)


def render() -> tuple[Path, Path]:
    report = json.loads(SOURCE.read_text())
    if report['evaluation_scope'] != 'inner_validation' or report['selection_used'] is not True:
        raise ValueError('This figure requires model-selection temporal validation')
    if report['test_evaluations'] != 0 or report['data_audit']['final_test_label_rows_loaded'] != 0:
        raise ValueError('The figure must not describe a new final-test evaluation')
    if report['config']['new_samples'] != 0 or report['config']['multimodal'] is not False:
        raise ValueError('Source scope changed; revise the explanatory text first')
    nominal = number(report['config']['nominal_interval_coverage'])
    if nominal is None or not 0 <= nominal <= 1:
        raise ValueError('Invalid nominal coverage')

    rows = []
    for key, label in [('900', '15m'), ('3600', '60m')]:
        cutoff = report['cutoffs'][key]
        original = cutoff['models']['original_smooth_l1']['all']
        quantile = cutoff['models']['ordered_quantile_pinball']['all']
        zero = cutoff['models']['ordered_quantile_pinball']['zero_target']
        if cutoff['selected_candidate'] != 'ordered_quantile_pinball':
            raise ValueError('Selected model changed; revise the figure')
        if original['n_cascades'] != quantile['n_cascades']:
            raise ValueError('MAE comparisons have unequal validation denominators')
        coverage = number(quantile['interval_80_empirical_coverage'])
        zero_coverage = number(zero['interval_80_empirical_coverage'])
        for value in [coverage, zero_coverage]:
            if value is not None and not 0 <= value <= 1:
                raise ValueError('Coverage must be a fraction')
        rows.append({
            'label': label,
            'n': quantile['n_cascades'],
            'original_mae': number(original['raw_median_mae']),
            'quantile_mae': number(quantile['raw_median_mae']),
            'coverage': coverage,
            'width': number(quantile['interval_80_mean_width']),
            'zero_n': zero['n_cascades'],
            'zero_coverage': zero_coverage,
        })
    if rows[0]['n'] != rows[1]['n']:
        raise ValueError('Paired cutoff validation denominators changed')

    plt.rcParams.update({
        'font.family': 'DejaVu Sans',
        'text.color': INK,
        'axes.labelcolor': MUTED,
        'svg.fonttype': 'path',
        'svg.hashsalt': 'rise-training-progress-v1',
        'figure.facecolor': BG,
        'savefig.facecolor': BG,
    })
    fig = plt.figure(figsize=(14, 10), dpi=100)
    fig.text(0.055, 0.94, 'RISE · Prediction ranges', fontsize=31, fontweight='bold')
    fig.text(0.055, 0.892,
             'Temporal validation · model/epoch selected here · no new final test',
             fontsize=16, color=ORANGE, fontweight='bold')
    fig.text(0.055, 0.851,
             f'{rows[0]["n"]:,} validation cascades per cutoff · paired histories · Quantile q10–q90 nominal {nominal:.0%}',
             fontsize=13, color=MUTED)

    fig.text(0.055, 0.795, 'Point estimate: validation MAE', fontsize=18, fontweight='bold')
    mae = fig.add_axes([0.205, 0.49, 0.365, 0.28])
    style_axis(mae)
    values = [rows[0]['original_mae'], rows[0]['quantile_mae'],
              rows[1]['original_mae'], rows[1]['quantile_mae']]
    labels = ['15m · Smooth L1', '15m · Quantile', '60m · Smooth L1', '60m · Quantile']
    for y, value, color in zip([3, 2, 1, 0], values, [GREY, TEAL, GREY, TEAL]):
        if value is not None:
            mae.barh(y, value, height=0.43, color=color, zorder=3)
            mae.text(value + 1.2, y, shown(value), va='center', fontsize=13, fontweight='bold')
        else:
            mae.text(1.2, y, 'N/A', va='center', fontsize=13)
    mae.set_yticks([3, 2, 1, 0], labels, fontsize=13, color=INK)
    mae.set_xlim(0, 80)
    mae.set_ylim(-0.6, 3.6)
    mae.set_xticks([0, 20, 40, 60, 80])
    mae.set_xlabel('MAE · additional retweets by age 24h · lower is better', fontsize=12, labelpad=15)

    coverage = fig.add_axes([0.68, 0.646, 0.27, 0.13])
    style_axis(coverage)
    coverage.set_title(f'Coverage · nominal {nominal:.0%}', loc='left', fontsize=16, fontweight='bold', pad=17)
    coverage.axvline(nominal * 100, color=ORANGE, linestyle=(0, (3, 3)), linewidth=1.7, zorder=1)
    for y, row in zip([1, 0], rows):
        value = row['coverage']
        if value is not None:
            coverage.barh(y, 100 * value, height=0.4, color=TEAL, zorder=2)
            coverage.text(100 * value - 3, y, shown(value, percent=True),
                          va='center', ha='right', color=BG, fontsize=13, fontweight='bold', zorder=3)
        else:
            coverage.text(3, y, 'N/A', va='center', fontsize=13)
    coverage.set_yticks([1, 0], [row['label'] for row in rows], fontsize=13, color=INK)
    coverage.set_xlim(0, 100)
    coverage.set_ylim(-0.6, 1.6)
    coverage.set_xticks([0, 50, 100], ['0%', '50%', '100%'])

    width = fig.add_axes([0.68, 0.449, 0.27, 0.115])
    style_axis(width)
    width.set_title('Mean predicted interval width', loc='left', fontsize=16, fontweight='bold', pad=17)
    for y, row in zip([1, 0], rows):
        value = row['width']
        if value is not None:
            if value < 0:
                raise ValueError('Negative interval width')
            width.barh(y, value, height=0.4, color=GREY, zorder=2)
            width.text(value + 4, y, shown(value, digits=3), va='center', fontsize=13, fontweight='bold')
        else:
            width.text(4, y, 'N/A', va='center', fontsize=13)
    width.set_yticks([1, 0], [row['label'] for row in rows], fontsize=13, color=INK)
    width.set_xlim(0, 285)
    width.set_ylim(-0.6, 1.6)
    width.set_xticks([0, 100, 200])
    width.set_xlabel('Additional retweets · q10–q90 range', fontsize=12, labelpad=13)

    box = FancyBboxPatch((0.055, 0.19), 0.89, 0.166,
                         boxstyle='round,pad=0.006,rounding_size=0.012',
                         transform=fig.transFigure, facecolor='#eee3d6',
                         edgecolor='#c8a58f', linewidth=0.9, zorder=0)
    fig.add_artist(box)
    fig.text(0.075, 0.322, 'Zero future target subgroup · additional retweets = 0',
             fontsize=18, fontweight='bold', color=ORANGE)
    for x, row, color in [(0.075, rows[0], ORANGE), (0.52, rows[1], INK)]:
        n_label = 'N/A' if row['zero_n'] is None else f'{row["zero_n"]:,}'
        fig.text(x, 0.271, f'{row["label"]} · n = {n_label}', fontsize=18, color=MUTED)
        fig.text(x + 0.195, 0.264, shown(row['zero_coverage'], digits=0, percent=True),
                 fontsize=30, fontweight='bold', color=color)
    fig.text(0.075, 0.215, 'Observed coverage differs sharply by subgroup; overall coverage is not a calibration guarantee.',
             fontsize=12, color=MUTED)

    fig.text(0.055, 0.143,
             '2011 selected-success retweets · not current views, verified Home, or text-origin validation',
             fontsize=12, color=INK)
    fig.text(0.055, 0.105,
             'Same five count/time features; no new samples. Validation differences are descriptive, not independent-test gains.',
             fontsize=12, color=MUTED)
    clock = report['completed_at'].replace('T', ' ').replace('+00:00', ' UTC')
    fig.text(0.055, 0.062, f'Report completed: {clock}', fontsize=11, color=MUTED)
    fig.text(0.055, 0.032, 'Source: public/retweet-validation.json · SEISMIC / snap.stanford.edu/seismic',
             fontsize=11, color=MUTED)

    fig.canvas.draw()
    frame = fig.bbox
    for item in fig.findobj(Text):
        if not item.get_visible() or not item.get_text().strip():
            continue
        bounds = item.get_window_extent(fig.canvas.get_renderer())
        if bounds.x0 < -0.5 or bounds.y0 < -0.5 or bounds.x1 > frame.x1 + 0.5 or bounds.y1 > frame.y1 + 0.5:
            raise ValueError(f'Text exceeds export bounds: {item.get_text()}')

    OUTPUT.mkdir(exist_ok=True)
    svg_path = OUTPUT / 'training-progress.svg'
    png_path = OUTPUT / 'training-progress.png'
    fig.savefig(svg_path, metadata={
        'Date': None,
        'Title': 'RISE · Prediction ranges',
        'Description': 'Temporal validation selected models and epochs; no new final test. Coverage and widths are empirical validation aggregates, not calibrated guarantees.',
    })
    svg_path.write_text('\n'.join(line.rstrip() for line in svg_path.read_text().splitlines()) + '\n')
    fig.savefig(png_path, dpi=100, metadata={'Description': 'Public aggregate temporal-validation figure; no new final test.'})
    plt.close(fig)
    return svg_path, png_path


if __name__ == '__main__':
    paths = render()
    print(json.dumps({'source': 'public/retweet-validation.json',
                      'outputs': [path.relative_to(ROOT).as_posix() for path in paths]}, indent=2))
