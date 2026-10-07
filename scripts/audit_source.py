#!/usr/bin/env python3
"""Extract pinned public-code evidence from an independent local upstream checkout."""
import argparse
import ast
import hashlib
import json
import re
import subprocess
import math
from pathlib import Path

FILES = (
    'README.md', 'home-mixer/params/param.rs', 'home-mixer/params/config.rs',
    'home-mixer/scorers/value_model.rs', 'home-mixer/scorers/vm_ranker.rs',
    'home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs',
    'home-mixer/filters/age_filter.rs', 'home-mixer/filters/oon_retweet_reply_filter.rs',
    'home-mixer/sources/simclusters_source.rs',
    'xai-value-model/scoring.rs', 'xai-value-model/inputs.rs', 'xai-value-model/weights.rs',
    'vm-ranker/params.rs', 'vm-ranker/scoring/value_model.rs',
    'vm-ranker/scoring/mod.rs', 'home-mixer/scorers/vm_ranker_request.rs',
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
    'NewUserAgeThresholdSecs', 'NewUserOonWeightFactor',
}
VM_ONLY = {'EnableAuthorDiversity', 'AuthorDiversityDecay', 'AuthorDiversityFloor',
           'OonWeightFactor', 'TopicOonWeightFactor',
           'EnableOonRescoreForInNetworkRepliesRetweets', 'ComputeValueModel',
           'NewUserAgeThresholdSecs', 'NewUserOonWeightFactor'}
HOME_ONLY = {'EnablePhoenixOonReplies', 'EnableRanking'}
REQUIRED = {'home-mixer/params/param.rs': SELECTED - VM_ONLY,
            'vm-ranker/params.rs': SELECTED - HOME_ONLY}
OFFICIAL_URL = 'https://github.com/xai-org/x-algorithm.git'


def strip_comments(content):
    """Preserve line numbers while excluding commented-out parameter macros."""
    chars = list(content)
    position = 0
    while position < len(content):
        if content[position] == '"':
            position += 1
            while position < len(content):
                if content[position] == '\\':
                    position += 2
                elif content[position] == '"':
                    position += 1
                    break
                else:
                    position += 1
        elif content.startswith('//', position):
            end = content.find('\n', position)
            end = len(content) if end == -1 else end
            chars[position:end] = ' ' * (end - position)
            position = end
        elif content.startswith('/*', position):
            start = position
            position += 2
            depth = 1
            while position < len(content) and depth:
                if content.startswith('/*', position):
                    depth += 1
                    position += 2
                elif content.startswith('*/', position):
                    depth -= 1
                    position += 2
                else:
                    position += 1
            if depth:
                raise ValueError('unterminated source comment; manual review required')
            chars[start:position] = ['\n' if c == '\n' else ' ' for c in content[start:position]]
        else:
            position += 1
    return ''.join(chars)


def extract_parameters(content, path):
    records = {}
    for match in PARAM.finditer(strip_comments(content)):
        name, kind, switch, literal = match.groups()
        if name not in REQUIRED[path]:
            continue
        if name in records:
            raise ValueError(f'duplicate parameter {name} in {path}')
        if kind == 'bool':
            if literal not in ('true', 'false'):
                raise ValueError(f'invalid boolean default for {name}')
            value = literal == 'true'
        elif kind == 'u64':
            value = int(literal.replace('_', ''))
            if value < 0:
                raise ValueError(f'negative u64 default for {name}')
        else:
            value = float(literal.replace('_', ''))
            if not math.isfinite(value):
                raise ValueError(f'non-finite default for {name}')
        records[name] = {'default': value, 'feature_switch': switch,
                         'line': content.count('\n', 0, match.start()) + 1}
    missing = REQUIRED[path] - records.keys()
    if missing:
        raise ValueError(f'parameter extraction incomplete in {path}: {", ".join(sorted(missing))}; review upstream syntax or removals')
    return records


def extract_max_post_age(content):
    match = re.search(r'pub const MAX_POST_AGE:\s*u64\s*=\s*([^;]+);', strip_comments(content))
    if not match:
        raise ValueError('MAX_POST_AGE missing; review upstream age-filter configuration')
    expression = match[1].strip()
    def integer_product(node):
        if isinstance(node, ast.Constant) and type(node.value) is int and node.value >= 0:
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            return integer_product(node.left) * integer_product(node.right)
        raise ValueError('unsupported MAX_POST_AGE expression; manual review required')
    value = integer_product(ast.parse(expression, mode='eval').body)
    return {'value': value, 'unit': 'seconds', 'expression': expression,
            'line': content.count('\n', 0, match.start()) + 1}


def audit(source, check_latest=False):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()
    commit = git('rev-parse', 'HEAD')
    if git('status', '--porcelain', '--untracked-files=all'):
        raise ValueError('upstream checkout must be clean')
    origin = git('remote', 'get-url', 'origin')
    if origin not in ('https://github.com/xai-org/x-algorithm.git', 'git@github.com:xai-org/x-algorithm.git', 'https://github.com/xai-org/x-algorithm'):
        raise ValueError('expected official xai-org/x-algorithm origin')
    if check_latest:
        latest = subprocess.check_output(['git', 'ls-remote', OFFICIAL_URL, 'HEAD'],
                                         text=True, timeout=30).split()
        if not latest or latest[0] != commit:
            raise ValueError('upstream HEAD differs from reviewed checkout; inspect changes before updating evidence')
    # Read committed blobs rather than trusting worktree flags such as assume-unchanged.
    contents = {}
    records = []
    for name in FILES:
        data = subprocess.check_output(['git', '-C', str(source), 'show', f'{commit}:{name}'])
        contents[name] = data.decode('utf-8')
        records.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(),
                        'url': f'https://github.com/xai-org/x-algorithm/blob/{commit}/{name}'})
    parameters = {}
    for name in ('home-mixer/params/param.rs', 'vm-ranker/params.rs'):
        parameters[name] = extract_parameters(contents[name], name)
    return {'repository': 'https://github.com/xai-org/x-algorithm', 'commit': commit,
            'upstream_commit_time': git('show', '-s', '--format=%cI'),
            'interpretation': 'Public defaults, not per-request production guarantees. Weights multiply predictions, not raw counts.',
            'files': records, 'parameters': parameters,
            'constants': {'home-mixer/params/config.rs': {
                'MAX_POST_AGE': extract_max_post_age(contents['home-mixer/params/config.rs'])}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--output', type=Path, help='write extracted evidence after source review')
    mode.add_argument('--check', type=Path, help='verify existing evidence without overwriting it')
    parser.add_argument('--check-latest', action='store_true', help='also require reviewed commit to equal current official HEAD (network)')
    args = parser.parse_args()
    try:
        data = audit(args.source, args.check_latest)
        if args.check:
            if json.loads(args.check.read_text()) != data:
                raise ValueError('manifest differs from committed source; review hashes, parameters and constants before regenerating')
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    except (ValueError, OSError, SyntaxError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        parser.exit(2, f'Cannot audit source: {e}\n')
    print(f'{"Verified" if args.check else "Pinned"} {data["commit"]}: {len(data["files"])} source hashes -> {args.check or args.output}')


if __name__ == '__main__':
    main()
