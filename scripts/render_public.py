#!/usr/bin/env python3
"""Render public aggregate metrics and multilingual README blocks. No fabricated observations."""
import json
import re
from datetime import datetime
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


def count(value, label, nullable=False):
    if nullable and value is None:
        return
    if type(value) is not int or value < 0:
        raise ValueError(f'{label} must be a nonnegative integer' + (' or null' if nullable else ''))


def timestamp(value, label, nullable=True):
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ValueError(f'{label} must be an ISO timestamp')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'{label} must be an ISO timestamp') from exc
    if parsed.utcoffset() is None:
        raise ValueError(f'{label} needs a timezone')
    return parsed


def post_url(value, account):
    if not isinstance(value, str) or not re.fullmatch(
            r'https://x\.com/' + re.escape(account) + r'/status/[0-9]+', value, re.I):
        raise ValueError('post URL must be a permanent X status URL for the measured account')


def github_url(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value):
        raise ValueError('invalid GitHub repository URL')


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('public metrics must be an object')
    account = data.get('account')
    if not isinstance(account, str) or not re.fullmatch(r'[A-Za-z0-9_]{1,15}', account):
        raise ValueError('invalid measured X account')
    c = data.get('blue_cohort')
    if not isinstance(c, dict):
        raise ValueError('blue_cohort must be an object')
    for key in ('high', 'not_high', 'unknown', 'observed_arrivals'):
        count(c.get(key), 'quality ' + key)
    if c['high'] + c['not_high'] + c['unknown'] != c['observed_arrivals']:
        raise ValueError('quality partition must match observed arrivals')
    count(c.get('confirmed_new_followers'), 'confirmed new followers', nullable=True)
    if c.get('confirmed_new_followers') is not None and c['confirmed_new_followers'] > c['observed_arrivals']:
        raise ValueError('confirmed new followers exceed observed arrivals')
    timestamp(c.get('window_ended_at'), 'cohort observation')
    for collection, field in (('follower_observations', 'total'), ('blue_observations', 'count')):
        rows = data.get(collection)
        if not isinstance(rows, list):
            raise ValueError(collection + ' must be a list')
        previous = None
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(collection + ' rows must be objects')
            count(row.get(field), collection + ' ' + field)
            observed = timestamp(row.get('observed_at'), collection + ' timestamp')
            if observed and previous and observed < previous:
                raise ValueError(collection + ' timestamps must be chronological')
            if observed:
                previous = observed
    posts = data.get('posts')
    if not isinstance(posts, list):
        raise ValueError('posts must be a list')
    for row in posts:
        if not isinstance(row, dict) or not isinstance(row.get('kind'), str):
            raise ValueError('post rows need an object and kind')
        post_url(row.get('url'), account)
        timestamp(row.get('observed_at'), 'post observation')
        for key in ('views', 'replies', 'likes', 'reposts', 'bookmarks'):
            count(row.get(key), 'post ' + key, nullable=True)
    launch = data.get('launch_post')
    if launch is not None:
        post_url(launch, account)
    updates = data.get('progress_updates', [])
    if not isinstance(updates, list):
        raise ValueError('progress_updates must be a list')
    for update in updates:
        if not isinstance(update, dict):
            raise ValueError('progress update must be an object')
        post_url(update.get('url'), account)
        post_url(update.get('parent'), account)
        timestamp(update.get('reported_profile_observation'), 'progress observation')
    stats = data.get('github')
    if not isinstance(stats, dict):
        raise ValueError('github must be an object')
    for field in ('stars', 'forks'):
        count(stats.get(field), 'GitHub ' + field, nullable=True)
    timestamp(stats.get('observed_at'), 'GitHub observation')
    if stats.get('observed_at') and (stats.get('stars') is None or stats.get('forks') is None):
        raise ValueError('observed GitHub stats need both counters')
    if stats.get('url') is not None:
        github_url(stats['url'])


def quality_bounds(cohort):
    n = cohort['observed_arrivals']
    return (cohort['high'] / n, (cohort['high'] + cohort['unknown']) / n) if n else (None, None)


def observed_date(row):
    return (row or {}).get('observed_at') or 'Timestamp unavailable'


def metric_art(data):
    validate(data)
    followers, blues = data['follower_observations'], data['blue_observations']
    first, last = (followers[0], followers[-1]) if followers else (None, None)
    b1, b2 = (blues[0], blues[-1]) if blues else (None, None)
    c = data['blue_cohort']
    delta = last['total'] - first['total'] if first and last else None
    share = c['high'] / c['observed_arrivals'] if c['observed_arrivals'] else None
    date = observed_date(last)
    body = ''
    body += text(38, 72, 'Growth is measured. Causality is not assumed.', 29, '#191b1b')
    cards = [(38, f'{delta:+d}' if delta is not None else 'N/A', 'Total follower change', '#191b1b'),
             (390, f'+{c["observed_arrivals"]}', 'Newly observed blue accounts', '#b73825'),
             (742, 'PENDING' if c['unknown'] else f'{share:.0%}' if share is not None else 'N/A', 'High-quality share', '#8b5520')]
    for x, value, label, color in cards:
        body += f'<rect x="{x}" y="113" width="320" height="117" rx="12" fill="#eae4da"/>'
        body += text(x+20, 168, value, 42 if value != 'PENDING' else 31, color, 'font-weight="700"')
        body += text(x+20, 204, label, 15)
    body += text(38, 271, 'Total followers / absolute scale starts at zero', 17, '#191b1b')
    maxv = max(first['total'], last['total'], 1) * 1.2 if first else 1
    bars = [(301, 'First check', first['total']), (352, 'Latest check', last['total'])] if first else []
    if not bars:
        body += text(38, 337, 'N/A — no follower observations recorded', 18, '#8b5520')
    for y, label, value in bars:
        body += text(38, y+22, label, 15)
        body += f'<rect x="180" y="{y}" width="{value/maxv*430:.1f}" height="30" fill="#b73825"/>'
        body += text(180+value/maxv*430+12, y+22, value, 18, '#191b1b')
    body += text(180, 411, '0', 13)
    blue_label = f'Blue list: {b1["count"]} → {b2["count"]} | latest {observed_date(b2)}' if b1 else 'Blue list: N/A — no observations recorded'
    body += text(38, 448, blue_label, 16, '#191b1b')
    body += text(38, 484, f'Quality: {c["high"]} high / {c["not_high"]} not matched / {c["unknown"]} unclassified, n={c["observed_arrivals"]}', 17)
    low, high = quality_bounds(c)
    bound_label = f'Observed cohort quality: confirmed lower bound {low:.1%}; possible upper bound {high:.1%}.' if low is not None else 'Observed cohort quality: N/A — no observed arrivals.'
    body += text(38, 516, bound_label, 15, '#8b5520')
    body += text(38, 550, 'Blue badges may be upgrades or renamed accounts; profile and cohort dates differ.', 14, '#8b5520')
    body += text(38, 579, 'Observed changes include concurrent activity; no causal growth claim.', 15)
    body += text(38, 610, f'Latest profile observation: {date}', 13, '#636660')
    return svg(body, height=642)


def feedback_art(data):
    validate(data)
    rows = [r for r in data['posts'] if r.get('observed_at')]
    body = ''
    body += text(38, 70, 'Visibility is evidence to inspect, not a proof of lift.', 27, '#191b1b')
    columns = [('views', 'Views'), ('replies', 'Replies'), ('likes', 'Likes'), ('reposts', 'Reposts'), ('bookmarks', 'Bookmarks')]
    for i, (key, label) in enumerate(columns):
        body += text(300+i*146, 133, label, 15)
    for j, row in enumerate(rows):
        y = 185+j*68
        label = {'launch': 'Launch post', 'prompt': 'Prompt experiment', 'initial_prompt': 'Prompt experiment', 'reply': 'Contextual reply', 'technical_reply': 'Technical reply', 'measurement_reply': 'Measurement reply'}.get(row['kind'], row['kind'])
        body += text(38, y, label, 16, '#191b1b')
        for i, (key, _) in enumerate(columns):
            body += text(300+i*146, y, row.get(key) if row.get(key) is not None else 'N/A', 24, '#b73825')
        body += text(38, y+24, row['observed_at'], 11, '#636660')
    if not rows:
        body += text(38, 185, 'N/A — no observed post counters recorded', 18, '#8b5520')
    footer = 185+max(len(rows), 1)*68
    body += text(38, footer+20, 'Public counters can include the account owner; independent endorsements are unknown.', 14, '#8b5520')
    body += text(38, footer+48, 'Each row retains its own X observation time; GitHub refreshes do not update it.', 14)
    return svg(body, height=footer+80, title='RISE public post feedback')


def block(data, en=False):
    validate(data)
    rows = data['follower_observations']
    a, b = (rows[0], rows[-1]) if rows else (None, None)
    c = data['blue_cohort']
    share = (f'{c["high"] / c["observed_arrivals"]:.1%}'
             if c['observed_arrivals'] and not c['unknown'] else None)
    low, high = quality_bounds(c)
    bounds = f'{low:.1%}–{high:.1%}' if low is not None else 'N/A'
    quality_en = share or ('Pending classification; unknown is not zero' if c['unknown'] else 'N/A; no observed arrivals')
    quality_zh = share or ('分类尚未完成，不能把未知当 0%' if c['unknown'] else '不适用；没有观察到新蓝 V')
    confirmed = c.get('confirmed_new_followers')
    confirmed_en = str(confirmed) if confirmed is not None else 'unknown'
    confirmed_zh = f'已确认新增粉丝 {confirmed}' if confirmed is not None else '精确新增粉丝未确认'
    if en:
        lines = ['| Actual observation | Value |', '| --- | --- |',
                 (f'| Total followers | {a["total"]} → {b["total"]} ({b["total"]-a["total"]:+d}) |' if a else '| Total followers | N/A; no observations |'),
                 f'| Newly observed blue accounts | {c["observed_arrivals"]}; confirmed new followers: {confirmed_en} |',
                 f'| Quality classification | {c["high"]} high / {c["not_high"]} not matched / {c["unknown"]} unclassified |',
                 f'| High-quality share | {quality_en} |',
                 f'| Latest profile observation | {observed_date(b)} |']
    else:
        lines = ['| 真实观察 | 当前结果 |', '| --- | --- |',
                 (f'| 总粉丝 | {a["total"]} → {b["total"]}，净变化 **{b["total"]-a["total"]:+d}** |' if a else '| 总粉丝 | 尚无观察数据 |'),
                 f'| 新观察到的蓝 V | **{c["observed_arrivals"]}** 个；{confirmed_zh} |',
                 f'| 质量分类 | {c["high"]} 确认高质 / {c["not_high"]} 未匹配主题 / {c["unknown"]} 待判定 |',
                 f'| 高质量占比 | {quality_zh} |',
                 f'| 最新账号采集 | {observed_date(b)} |']
    blues = data['blue_observations']
    blue_date = observed_date(blues[-1] if blues else None)
    first_date = observed_date(a)
    if en:
        lines += [f'| Observed-cohort quality lower / possible upper bound | {bounds} |', f'| First profile observation | {first_date} |', f'| Latest blue-list observation (separate window) | {blue_date} |']
    else:
        lines += [f'| 观察队列质量：已确认下界 / 可能上界 | {bounds} |', f'| 首次账号采集 | {first_date} |', f'| 最新蓝 V 名单采集（独立窗口） | {blue_date} |']
    caveat = ('Bounds describe the observed blue cohort, not confirmed new followers. Badge upgrades and handle changes remain possible. Public post counters may include self-interactions.' if en else '上下界描述观察到的蓝 V 队列，并非已确认新增粉丝；无法排除认证升级及改名。公开互动计数可能包含账号自身操作。')
    stats = data['github']
    if stats['observed_at']:
        lines += [f'| GitHub stars / forks | {stats["stars"]} / {stats["forks"]} · {stats["observed_at"]} |']
    lines += ['', caveat]
    launch = data.get('launch_post')
    lines += ['', f'[RISE launch post]({launch})' if launch else ('Launch post will be linked after publication.' if en else '技能介绍帖发布后补入永久链接。')]
    updates = data.get('progress_updates', [])
    if updates:
        label = 'Latest progress in the pinned thread' if en else '置顶帖下的最新进展'
        lines += ['', f'[{label}]({updates[-1]["url"]})']
    return '\n'.join(lines)


def replace_block(content, replacement):
    if content.count(START) != 1 or content.count(END) != 1:
        raise ValueError('Expected exactly one controlled metrics block')
    head, tail = content.split(START, 1)
    if END not in tail:
        raise ValueError('Controlled metrics markers are out of order')
    _, foot = tail.split(END, 1)
    return head + START + '\n' + replacement + '\n' + END + foot


def main():
    data = json.loads((ROOT/'public/metrics.json').read_text())
    validate(data)
    # Validate every output before writing any file.
    outputs = {ROOT/'assets/metrics.svg': metric_art(data),
               ROOT/'assets/feedback.svg': feedback_art(data)}
    for filename, en in [('README.md', False), ('README.en.md', True)]:
        path = ROOT/filename
        outputs[path] = replace_block(path.read_text(), block(data, en))
    (ROOT/'assets').mkdir(exist_ok=True)
    for path, content in outputs.items():
        path.write_text(content)
    print('Updated two README metric blocks and two SVGs from recorded observations.')


if __name__ == '__main__':
    main()
