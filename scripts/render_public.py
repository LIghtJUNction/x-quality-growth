#!/usr/bin/env python3
"""Render public aggregate metrics and multilingual README blocks. No fabricated observations."""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START, END = '<!-- RISE:METRICS:START -->', '<!-- RISE:METRICS:END -->'


def text(x, y, content, size=16, fill='#454a48', extra=''):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" {extra}>{escape(str(content))}</text>'


def svg(body, width=1100, height=620, title='RISE observed metrics'):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">'
            f'<title>{escape(title)}</title><rect width="{width}" height="{height}" rx="24" fill="#f5f1e9"/>'
            f'<g font-family="Arial, sans-serif">{body}</g></svg>\n')


def validate(data):
    c = data['blue_cohort']
    if c['high'] + c['not_high'] + c['unknown'] != c['observed_arrivals']:
        raise ValueError('quality partition must match observed arrivals')
    for key in ('high', 'not_high', 'unknown', 'observed_arrivals'):
        if type(c[key]) is not int or c[key] < 0:
            raise ValueError('quality counts must be nonnegative integers')
    for row in data['follower_observations']:
        if type(row['total']) is not int or row['total'] < 0:
            raise ValueError('invalid total follower observation')
    for row in data['posts']:
        for key in ('views', 'replies', 'likes', 'reposts', 'bookmarks'):
            v = row.get(key)
            if v is not None and (type(v) is not int or v < 0):
                raise ValueError('post counters must be nonnegative integers or null')


def metric_art(data):
    validate(data)
    first, last = data['follower_observations'][0], data['follower_observations'][-1]
    b1, b2 = data['blue_observations'][0], data['blue_observations'][-1]
    c = data['blue_cohort']
    delta = last['total'] - first['total']
    share = c['high'] / c['observed_arrivals'] if c['observed_arrivals'] else None
    date = last['observed_at'] or 'Timestamp unavailable'
    body = ''
    body += text(38, 72, 'Growth is measured. Causality is not assumed.', 29, '#191b1b')
    cards = [(38, f'{delta:+d}', 'Total follower change', '#191b1b'),
             (390, f'+{c["observed_arrivals"]}', 'Newly observed blue accounts', '#b73825'),
             (742, 'PENDING' if c['unknown'] else f'{share:.0%}' if share is not None else 'N/A', 'High-quality share', '#8b5520')]
    for x, value, label, color in cards:
        body += f'<rect x="{x}" y="113" width="320" height="117" rx="12" fill="#eae4da"/>'
        body += text(x+20, 168, value, 42 if value != 'PENDING' else 31, color, 'font-weight="700"')
        body += text(x+20, 204, label, 15)
    body += text(38, 271, 'Total followers / absolute scale starts at zero', 17, '#191b1b')
    maxv = max(first['total'], last['total'], 1) * 1.2
    for y, label, value in [(301, 'First check', first['total']), (352, 'Latest check', last['total'])]:
        body += text(38, y+22, label, 15)
        body += f'<rect x="180" y="{y}" width="{value/maxv*430:.1f}" height="30" fill="#b73825"/>'
        body += text(180+value/maxv*430+12, y+22, value, 18, '#191b1b')
    body += text(180, 411, '0', 13)
    body += text(38, 448, f'Blue list: {b1["count"]} → {b2["count"]}  |  Cohort ended: {b2["observed_at"]}', 17, '#191b1b')
    body += text(38, 484, f'Quality: {c["high"]} high / {c["not_high"]} not matched / {c["unknown"]} unclassified, n={c["observed_arrivals"]}', 17)
    body += text(38, 518, 'Verified-only lists cannot rule out old followers gaining a badge.', 15, '#8b5520')
    body += text(38, 550, 'Observed changes include concurrent activity; no causal growth claim.', 15)
    body += text(38, 588, f'Latest profile observation: {date}', 13, '#636660')
    return svg(body)


def feedback_art(data):
    rows = [r for r in data['posts'] if r.get('observed_at')]
    body = ''
    body += text(38, 70, 'Visibility is evidence to inspect, not a proof of lift.', 27, '#191b1b')
    columns = [('views', 'Views'), ('replies', 'Replies'), ('likes', 'Likes'), ('reposts', 'Reposts'), ('bookmarks', 'Bookmarks')]
    for i, (key, label) in enumerate(columns):
        body += text(300+i*146, 133, label, 15)
    for j, row in enumerate(rows):
        y = 185+j*68
        label = {'launch': 'Launch post', 'prompt': 'Prompt experiment', 'initial_prompt': 'Prompt experiment', 'reply': 'Contextual reply'}.get(row['kind'], row['kind'])
        body += text(38, y, label, 16, '#191b1b')
        for i, (key, _) in enumerate(columns):
            body += text(300+i*146, y, row.get(key) if row.get(key) is not None else 'N/A', 24, '#b73825')
        body += text(38, y+24, row['observed_at'], 11, '#636660')
    body += text(38, 185+len(rows)*68+30, 'X values refresh only after a real authorized browser observation.', 15, '#8b5520')
    return svg(body, height=260+len(rows)*68, title='RISE public post feedback')


def block(data, en=False):
    validate(data)
    a, b = data['follower_observations'][0], data['follower_observations'][-1]
    c = data['blue_cohort']
    share = (f'{c["high"] / c["observed_arrivals"]:.1%}'
             if c['observed_arrivals'] and not c['unknown'] else None)
    quality_en = share or ('Pending classification; unknown is not zero' if c['unknown'] else 'N/A; no observed arrivals')
    quality_zh = share or ('分类尚未完成，不能把未知当 0%' if c['unknown'] else '不适用；没有观察到新蓝 V')
    if en:
        lines = ['| Actual observation | Value |', '| --- | --- |',
                 f'| Total followers | {a["total"]} → {b["total"]} ({b["total"]-a["total"]:+d}) |',
                 f'| Newly observed blue accounts | {c["observed_arrivals"]}; confirmed new followers: unknown |',
                 f'| Quality classification | {c["high"]} high / {c["not_high"]} not matched / {c["unknown"]} unclassified |',
                 f'| High-quality share | {quality_en} |',
                 f'| Latest profile observation | {b["observed_at"]} |']
    else:
        lines = ['| 真实观察 | 当前结果 |', '| --- | --- |',
                 f'| 总粉丝 | {a["total"]} → {b["total"]}，净变化 **{b["total"]-a["total"]:+d}** |',
                 f'| 新观察到的蓝 V | **{c["observed_arrivals"]}** 个；精确新增粉丝未确认 |',
                 f'| 质量分类 | {c["high"]} 确认高质 / {c["not_high"]} 未匹配主题 / {c["unknown"]} 待判定 |',
                 f'| 高质量占比 | {quality_zh} |',
                 f'| 最新账号采集 | {b["observed_at"]} |']
    stats = data['github']
    if stats['observed_at']:
        lines += [f'| GitHub stars / forks | {stats["stars"]} / {stats["forks"]} · {stats["observed_at"]} |']
    launch = data.get('launch_post')
    lines += ['', f'[RISE launch post]({launch})' if launch else ('Launch post will be linked after publication.' if en else '技能介绍帖发布后补入永久链接。')]
    return '\n'.join(lines)


def main():
    data = json.loads((ROOT/'public/metrics.json').read_text())
    out = ROOT/'assets'
    out.mkdir(exist_ok=True)
    (out/'metrics.svg').write_text(metric_art(data))
    (out/'feedback.svg').write_text(feedback_art(data))
    for filename, en in [('README.md', False), ('README.en.md', True)]:
        path = ROOT/filename
        content = path.read_text()
        if START not in content or END not in content:
            raise ValueError(f'Missing controlled metrics markers in {filename}')
        head, tail = content.split(START, 1)
        _, foot = tail.split(END, 1)
        path.write_text(head+START+'\n'+block(data, en)+'\n'+END+foot)
    print('Updated two README metric blocks and two SVGs from recorded observations.')


if __name__ == '__main__':
    main()
