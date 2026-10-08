#!/usr/bin/env python3
"""Render a synthetic Responses field-linking diagram; no API or file-data input."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.text import Text


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'assets'
SOURCE_URL = 'https://developers.openai.com/api/docs/guides/function-calling'
BG = '#f5f1e9'
INK = '#193f39'
MUTED = '#64706a'
TEAL = '#21796f'
RED = '#a44935'
BORDER = '#ded8cd'
CARD = '#fcfaf5'
PALE_TEAL = '#e1eee7'
PALE_RED = '#f0e2d9'

# Deliberately synthetic identifiers and output. These are selected fields,
# not a complete API request, an observed response, or a server-error example.
CALL = {'id': 'fc_example', 'call_id': 'call_example', 'type': 'function_call'}
WRONG = {'type': 'function_call_output', 'call_id': CALL['id'], 'output': 'ok'}
CORRECT = {'type': 'function_call_output', 'call_id': CALL['call_id'], 'output': 'ok'}


def font() -> FontProperties:
    candidates = [Path('/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc')]
    for candidate in candidates:
        if candidate.is_file():
            return FontProperties(fname=str(candidate))
    raise RuntimeError('An installed CJK font is required; no fonts are downloaded')


def render() -> tuple[Path, Path]:
    plt.rcParams.update({
        'figure.facecolor': BG,
        'savefig.facecolor': BG,
        'font.family': 'DejaVu Sans',
        'svg.fonttype': 'path',
        'svg.hashsalt': 'rise-tool-call-ids-v1',
        'text.color': INK,
    })
    fig = plt.figure(figsize=(14, 9), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1400)
    ax.set_ylim(900, 0)
    ax.axis('off')
    chinese = font()
    texts: list[Text] = []

    def text(x: float, y: float, value: str, size: float = 18,
             color: str = INK, mono: bool = False, bold: bool = False,
             ha: str = 'left') -> Text:
        item = ax.text(x, y, value, fontsize=size, color=color,
                       fontfamily='DejaVu Sans Mono' if mono else None,
                       fontproperties=None if mono else chinese,
                       fontweight='bold' if bold else 'normal',
                       va='center', ha=ha)
        texts.append(item)
        return item

    def box(x: float, y: float, width: float, height: float,
            fill: str = CARD, edge: str = BORDER, radius: int = 16) -> None:
        ax.add_patch(FancyBboxPatch((x, y), width, height,
                                   boxstyle=f'round,pad=0,rounding_size={radius}',
                                   facecolor=fill, edgecolor=edge, linewidth=1))

    def code(x: float, y: float, obj: dict[str, str], highlight: str | None,
             color: str, size: float = 18, spacing: float = 33) -> None:
        for i, line in enumerate(json.dumps(obj, indent=2).splitlines()):
            chosen = highlight is not None and f'"{highlight}"' in line
            text(x, y + i * spacing, line, size=size, mono=True,
                 color=color if chosen else INK, bold=chosen)

    text(64, 72, '工具结果，该连哪个 ID？', size=35, bold=True)
    text(1336, 65, 'RISE · API FIELD NOTE', size=12, color=MUTED, ha='right')
    text(66, 132, 'Responses：同一条调用，同时有 id 与 call_id', size=20)
    text(66, 170, '同一份合成输入 · 字段摘录', size=13, color=MUTED)

    for x, label, english, accent, pale, value, source in [
        (60, '选错关联键', 'WRONG', RED, PALE_RED, WRONG, 'call.id'),
        (720, '取对关联键', 'MATCH', TEAL, PALE_TEAL, CORRECT, 'call.call_id'),
    ]:
        text(x + 5, 218, label, size=23, color=accent, bold=True)
        text(x + 615, 215, english, size=12, color=accent, ha='right')
        box(x, 250, 620, 194)
        code(x + 32, 273, CALL, 'id' if source == 'call.id' else 'call_id', accent,
             spacing=33)

        # The arrow connects the selected source key to the output object.
        # No arrow claims a network request or a measured server error.
        text(x + 32, 479, f'{source}  →  result.call_id', size=17, color=accent,
             mono=True, bold=True)
        ax.add_patch(FancyArrowPatch((x + 584, 449), (x + 584, 514),
                                    arrowstyle='-|>', mutation_scale=18,
                                    linewidth=2, color=accent))

        box(x, 522, 620, 207, edge=accent)
        box(x + 19, 594, 582, 34, fill=pale, edge=pale, radius=6)
        code(x + 32, 548, value, 'call_id', accent, spacing=33)

    text(64, 771, '结果关联：function_call_output.call_id = 原调用的 call_id',
         size=22, color=TEAL, bold=True)
    text(65, 817, 'Chat Completions: tool_call_id = tool_call.id', size=15,
         color=MUTED, mono=True)
    text(65, 865, 'Responses · 合成字段演示，未请求 API；依据 OpenAI 官方 function calling 指南',
         size=13, color=MUTED)
    source_label = text(1336, 865, '官方指南 ↗', size=13, color=TEAL, ha='right')
    source_label.set_url(SOURCE_URL)

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bounds = fig.bbox
    for item in texts:
        b = item.get_window_extent(renderer)
        if b.x0 < bounds.x0 or b.y0 < bounds.y0 or b.x1 > bounds.x1 or b.y1 > bounds.y1:
            raise ValueError(f'Text outside canvas: {item.get_text()}')

    OUTPUT.mkdir(exist_ok=True)
    svg = OUTPUT / 'tool-call-ids.svg'
    png = OUTPUT / 'tool-call-ids.png'
    metadata = {
        'Title': '工具结果，该连哪个 ID？',
        'Description': ('Synthetic selected-field comparison only. Responses function_call has '
                        'id=fc_example and call_id=call_example; function_call_output.call_id '
                        'uses the original call.call_id. No API request or observed error. '
                        f'Official source: {SOURCE_URL}'),
        'Creator': 'RISE',
        'Date': None,
    }
    fig.savefig(svg, metadata=metadata)
    fig.savefig(png, dpi=100, metadata={'Title': metadata['Title'], 'Description': metadata['Description']})
    plt.close(fig)
    # Avoid whitespace warnings in Matplotlib's path output; preserve geometry.
    svg_text = '\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n'
    svg_text = svg_text.replace('width="1008pt" height="648pt"', 'width="1400" height="900"', 1)
    svg.write_text(svg_text)
    ET.parse(svg)
    return svg, png


if __name__ == '__main__':
    for path in render():
        print(f'{path.relative_to(ROOT)} {path.stat().st_size} bytes '
              f'sha256={hashlib.sha256(path.read_bytes()).hexdigest()}')
