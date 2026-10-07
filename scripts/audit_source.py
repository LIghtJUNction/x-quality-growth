#!/usr/bin/env python3
"""Extract pinned public-code evidence from an independent local upstream checkout."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

FILES = (
    'README.md', 'home-mixer/params/param.rs', 'home-mixer/params/config.rs',
    'home-mixer/scorers/value_model.rs', 'home-mixer/scorers/vm_ranker.rs',
    'home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs',
    'home-mixer/filters/age_filter.rs', 'home-mixer/filters/oon_retweet_reply_filter.rs',
    'home-mixer/sources/simclusters_source.rs',
    'xai-value-model/scoring.rs', 'xai-value-model/inputs.rs', 'xai-value-model/weights.rs',
    'vm-ranker/params.rs', 'vm-ranker/scoring/value_model.rs',
    'docs/BIDIRECTIONAL_BOOST_CHANGE.md',
)
PARAM = re.compile(r'param!\(\s*(\w+),\s*(f64|bool|u64),\s*"([^"]+)",\s*(-?[\d._]+|true|false)\s*\)', re.S)
SELECTED = {
    'FavoriteWeight', 'ReplyWeight', 'RetweetWeight', 'QuoteWeight', 'FollowAuthorWeight',
    'ShareWeight', 'ShareViaDmWeight', 'ShareViaCopyLinkWeight', 'ProfileClickWeight',
    'DwellWeight', 'ContDwellTimeWeight', 'ContClickDwellTimeWeight', 'NotInterestedWeight',
    'BlockAuthorWeight', 'MuteAuthorWeight', 'ReportWeight', 'NotDwelledWeight',
    'BidirectionalFollowReplyWeightBoost', 'BidirectionalFollowDwellWeightBoost',
    'EnableAuthorDiversity', 'AuthorDiversityDecay', 'AuthorDiversityFloor',
    'OonWeightFactor', 'TopicOonWeightFactor', 'EnablePhoenixOonReplies',
    'EnableOonRescoreForInNetworkRepliesRetweets', 'ComputeValueModel', 'EnableRanking',
}


def audit(source):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()
    commit = git('rev-parse', 'HEAD')
    if git('status', '--porcelain', '--untracked-files=all'):
        raise ValueError('upstream checkout must be clean')
    origin = git('remote', 'get-url', 'origin')
    if origin not in ('https://github.com/xai-org/x-algorithm.git', 'git@github.com:xai-org/x-algorithm.git', 'https://github.com/xai-org/x-algorithm'):
        raise ValueError('expected official xai-org/x-algorithm origin')
    records = []
    for name in FILES:
        data = (source / name).read_bytes()
        records.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(),
                        'url': f'https://github.com/xai-org/x-algorithm/blob/{commit}/{name}'})
    parameters = {}
    for name in ('home-mixer/params/param.rs', 'vm-ranker/params.rs'):
        content = (source / name).read_text()
        parameters[name] = {
            m[1]: {'default': m[4] == 'true' if m[2] == 'bool' else float(m[4].replace('_', '')),
                   'feature_switch': m[3], 'line': content.count('\n', 0, m.start()) + 1}
            for m in PARAM.finditer(content) if m[1] in SELECTED
        }
    return {'repository': 'https://github.com/xai-org/x-algorithm', 'commit': commit,
            'upstream_commit_time': git('show', '-s', '--format=%cI'),
            'interpretation': 'Public defaults, not per-request production guarantees. Weights multiply predictions, not raw counts.',
            'files': records, 'parameters': parameters}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        data = audit(args.source)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        parser.exit(2, f'Cannot audit source: {e}\n')
    print(f'Pinned {data["commit"]}: {len(data["files"])} source hashes -> {args.output}')


if __name__ == '__main__':
    main()
