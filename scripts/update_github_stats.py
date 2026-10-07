#!/usr/bin/env python3
"""Refresh public GitHub counters only; does not collect X data or create observations."""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    repository = os.getenv('GITHUB_REPOSITORY', 'LIghtJUNction/x-quality-growth')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('invalid repository')
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'RISE-public-metrics', 'X-GitHub-Api-Version': '2022-11-28'}
    token = os.getenv('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with urlopen(Request('https://api.github.com/repos/'+repository, headers=headers), timeout=20) as response:
        observed = json.load(response)
    path = ROOT/'public/metrics.json'
    data = json.loads(path.read_text())
    data['github'] = {'stars': observed['stargazers_count'], 'forks': observed['forks_count'],
                      'observed_at': datetime.now(timezone.utc).isoformat(), 'url': observed['html_url']}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    print('Updated public GitHub counters; X observations and timestamps were preserved.')


if __name__ == '__main__':
    main()
