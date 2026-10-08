#!/usr/bin/env python3
"""Validate external text-origin estimates and generate time-safe soft features.

This module does not train or run an AI-text detector. Text origin is separate
from who clicked Publish, account identity, bot status, and writing quality.
No supplied model means unknown with null probabilities, never fabricated 50/50.
"""
import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

CLASSES = ('human_written', 'ai_generated', 'mixed')
STATES = CLASSES + ('unknown',)
CONTRACT = 'rise-authorship-1'
LABEL_CONTRACT = 'rise-authorship-label-1'
ISO_TIME = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z')
SHA256 = re.compile(r'[a-f0-9]{64}\Z')
FORBIDDEN_FEATURE_NAMES = {'label', 'target', 'truth_label', 'ground_truth', 'content_origin',
                           'human_written_label', 'ai_generated_label', 'authorship_label'}
LIMITATIONS = [
    'No classifier is implemented or trained here; scores are supplied by an external model.',
    'Model probabilities and declared provenance are not independently verified or calibrated.',
    'Human-written, AI-generated and mixed refer only to this content version, not account identity.',
    'Style, punctuation, blue badges and automated publication do not establish text origin.',
    'Labels with evidence remain separate from prediction inputs and soft auxiliary features.',
    'Checks cover declared post IDs, timestamps and supplied content-group IDs. Group assignments, canonical edit lineage, duplicate-text grouping and comment lineage are not independently verified.',
    'Prediction and parameter uncertainty intervals are unknown, not zero.']


def obj(value, allowed, required, name):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object')
    if set(value) - set(allowed):
        raise ValueError(f'{name} contains unsupported fields: {sorted(set(value) - set(allowed))}')
    if set(required) - set(value):
        raise ValueError(f'{name} is missing fields: {sorted(set(required) - set(value))}')
    return value


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a nonempty string')
    return value


def time(value, name):
    if not isinstance(value, str) or ISO_TIME.fullmatch(value) is None:
        raise ValueError(f'{name} must be an exact ISO datetime with a timezone')
    if value[-1] != 'Z' and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise ValueError(f'{name} has an invalid timezone offset')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError(f'invalid {name}') from exc


def iso(value):
    # Downstream validation reuses these times; never truncate real availability.
    return value.isoformat(timespec='microseconds').replace('+00:00', 'Z')


def identity(value):
    obj(value, ('platform', 'post_id', 'version', 'post_url', 'published_at', 'captured_at', 'content_group_id'),
        ('platform', 'post_id', 'version'), 'post')
    content_group(value)
    platform, post_id = group_key(value)
    result = {'platform': platform, 'post_id': post_id, 'version': text(value['version'], 'version')}
    if value.get('post_url') is not None:
        url = text(value['post_url'], 'post_url')
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError('post_url must be an exact HTTPS permalink')
        if result['platform'] == 'x':
            match = re.fullmatch(r'https://x\.com/[A-Za-z0-9_]{1,15}/status/([0-9]+)', url)
            if match is None or match.group(1) != result['post_id']:
                raise ValueError('X post_url must match post_id')
        result['post_url'] = url
    return result


def group_key(post):
    """Validate canonical native identity consistently for targets and training rows."""
    platform, post_id = text(post['platform'], 'platform'), text(post['post_id'], 'post_id')
    if re.fullmatch(r'[a-z][a-z0-9_-]*', platform) is None or platform == 'twitter':
        raise ValueError('platform must be an exact lowercase canonical label; use x, not X/twitter/aliases')
    if post_id != post_id.strip():
        raise ValueError('post_id must be exact with no leading/trailing whitespace')
    if platform == 'x' and re.fullmatch(r'[1-9][0-9]*', post_id) is None:
        raise ValueError('X post_id must be canonical positive ASCII decimal without leading zeros')
    return platform, post_id


def content_group(post):
    """Declared concrete event/material/edit group; never infer one from topic or ID."""
    value = post.get('content_group_id')
    if value is None:
        return None
    text(value, 'content_group_id')
    if value != value.strip() or value.lower() == 'unknown':
        raise ValueError('content_group_id must be a known exact group ID or null')
    return value


def probabilities(value):
    obj(value, CLASSES, CLASSES, 'probabilities')
    if any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
           for p in value.values()):
        raise ValueError('probabilities must be finite numeric values from 0 to 1; bool is invalid')
    if not math.isclose(sum(value.values()), 1.0, rel_tol=0, abs_tol=1e-8):
        raise ValueError('probabilities must sum to 1; scores are not silently normalized')
    return {key: float(value[key]) for key in CLASSES}


def feature_availability(features, cutoff, post):
    if not isinstance(features, list):
        raise ValueError('input_features must be a list')
    names = set()
    for feature in features:
        obj(feature, ('name', 'kind', 'captured_at', 'available_at', 'latest_event_at', 'version'),
            ('name', 'kind', 'captured_at', 'available_at', 'version'), 'input feature')
        name = text(feature['name'], 'feature name')
        if name in names or name.lower() in FORBIDDEN_FEATURE_NAMES:
            raise ValueError('feature names must be unique and cannot be labels or targets')
        names.add(name)
        if feature['kind'] not in ('text', 'media', 'comments', 'metadata'):
            raise ValueError('feature kind must be text, media, comments or metadata, never label/target')
        if feature['version'] != post['version']:
            raise ValueError('feature content version must match the predicted post version')
        captured = time(feature['captured_at'], 'feature captured_at')
        available = time(feature['available_at'], 'feature available_at')
        if not captured <= available <= cutoff:
            raise ValueError('late capture/availability cannot be backfilled into an earlier prediction')
        if feature['kind'] == 'comments' and 'latest_event_at' not in feature:
            raise ValueError('comments require latest_event_at for the sampled comment range')
        if 'latest_event_at' in feature:
            event = time(feature['latest_event_at'], 'latest_event_at')
            if event > captured or event > cutoff:
                raise ValueError('future text edits/comments/events cannot enter a prediction')
    return len(features)


def provenance(value, post, cutoff, generated_at, required=False, strict_cross_post=False):
    """Check declared training rows; this cannot inspect the actual external model."""
    if value is None:
        if required or strict_cross_post:
            raise ValueError('auxiliary features require auditable training provenance')
        return None
    fields = ('strategy', 'training_cutoff', 'trained_at', 'training_groups', 'fold_id')
    obj(value, fields, fields[:-1], 'provenance')
    strategy = value['strategy']
    if strategy not in ('chronological', 'out_of_fold', 'in_sample', 'unknown'):
        raise ValueError('unsupported prediction strategy')
    training_cutoff = time(value['training_cutoff'], 'training_cutoff')
    trained_at = time(value['trained_at'], 'trained_at')
    if not training_cutoff <= trained_at <= generated_at <= cutoff:
        raise ValueError('training/capture chronology is inconsistent with prediction cutoff')
    if strategy == 'out_of_fold':
        text(value.get('fold_id'), 'out_of_fold fold_id')
    groups = value['training_groups']
    if not isinstance(groups, list) or not groups:
        raise ValueError('training_groups must contain declared training records')
    seen, target_seen, target_group_seen = set(), False, False
    target_publication = time(post['published_at'], 'published_at') if post.get('published_at') else None
    target_group = content_group(post)
    groups_complete = target_group is not None
    if strict_cross_post and (target_publication is None or target_group is None):
        raise ValueError('strict cross-post validation requires actual first published_at and a known content_group_id')
    for row in groups:
        obj(row, ('platform', 'post_id', 'published_at', 'latest_input_available_at', 'label_available_at', 'content_group_id'),
            ('platform', 'post_id', 'published_at', 'latest_input_available_at', 'label_available_at'), 'training group')
        declared_group = content_group(row)
        groups_complete = groups_complete and declared_group is not None
        if strict_cross_post and declared_group is None:
            raise ValueError('strict cross-post validation requires a known content_group_id for every training post')
        if target_group is not None and declared_group == target_group:
            target_group_seen = True
        key = group_key(row)
        if key in seen:
            raise ValueError('training_groups must be unique native-post groups')
        seen.add(key)
        publication = time(row['published_at'], 'training published_at')
        available = time(row['latest_input_available_at'], 'training input availability')
        label_available = time(row['label_available_at'], 'training label availability')
        if publication > available or max(publication, available, label_available) > training_cutoff:
            raise ValueError('future training posts, inputs or labels cannot be backfilled')
        if key == group_key(post):
            target_seen = True
        elif target_publication and publication >= target_publication:
            raise ValueError('future/same-time posts cannot train a historical authorship feature')
    checks_passed = strategy in ('chronological', 'out_of_fold') and not target_seen and not target_group_seen
    if (required or strict_cross_post) and not checks_passed:
        raise ValueError('auxiliary predictions must be chronological/OOF and exclude the declared target post ID and content group')
    return {'strategy': strategy, 'training_cutoff': iso(training_cutoff),
            'trained_at': iso(trained_at), 'training_group_count': len(groups),
            'target_declared_post_id_excluded': not target_seen,
            'declared_content_groups_complete': groups_complete,
            'target_declared_content_group_excluded': False if target_group_seen else True if groups_complete else None,
            'strict_cross_post_eligible': checks_passed and groups_complete and target_publication is not None,
            'auxiliary_eligible': checks_passed,
            'eligibility_scope': ('declared_post_ids_content_groups_and_timestamps_only' if groups_complete
                                  else 'declared_post_ids_and_timestamps_only') + '; not a proof of leakage-free training',
            'canonical_lineage_verified': False, 'duplicate_text_grouping_verified': False,
            'comment_lineage_verified': False,
            'fold_id': value.get('fold_id'), 'verification': 'checked_declared_provenance_only'}


def validate_prediction(record, require_auxiliary=False, strict_cross_post=False):
    if type(strict_cross_post) is not bool:
        raise ValueError('strict_cross_post must be a bool')
    obj(record, ('contract_version', 'post', 'prediction_at', 'external_prediction'),
        ('contract_version', 'post', 'prediction_at'), 'prediction record')
    if record['contract_version'] != CONTRACT:
        raise ValueError(f'contract_version must be {CONTRACT}')
    native = identity(record['post'])
    cutoff = time(record['prediction_at'], 'prediction_at')
    post = dict(record['post'])
    if post.get('published_at') is not None and time(post['published_at'], 'published_at') > cutoff:
        raise ValueError('a future planned publication is not an actual published_at; use null for a draft')
    if post.get('captured_at') is not None:
        captured = time(post['captured_at'], 'post captured_at')
        if captured > cutoff:
            raise ValueError('post captured after prediction cutoff')
        if post.get('published_at') and captured < time(post['published_at'], 'published_at'):
            raise ValueError('captured_at cannot precede actual publication')
    external = record.get('external_prediction')
    if external is None:
        if strict_cross_post:
            raise ValueError('strict cross-post validation requires auditable external-model provenance')
        return {'post': native, 'prediction_at': iso(cutoff), 'probabilities': None,
                'model': None, 'provenance': None, 'input_feature_count': 0}
    fields = ('model_id', 'model_version', 'weights_sha256', 'generated_at', 'available_at',
              'probabilities', 'input_features', 'provenance')
    obj(external, fields, ('model_id', 'model_version', 'generated_at', 'available_at',
                           'probabilities', 'input_features'), 'external prediction')
    model_id, model_version = text(external['model_id'], 'model_id'), text(external['model_version'], 'model_version')
    digest = external.get('weights_sha256')
    if digest is not None and (not isinstance(digest, str) or SHA256.fullmatch(digest) is None):
        raise ValueError('weights_sha256 must be 64 lowercase hex characters or null')
    generated = time(external['generated_at'], 'generated_at')
    available = time(external['available_at'], 'prediction available_at')
    if not generated <= available <= cutoff:
        raise ValueError('future-generated/available predictions cannot be early features')
    input_count = feature_availability(external['input_features'], generated, post)
    if require_auxiliary and not input_count:
        raise ValueError('auxiliary predictions require recorded input availability')
    prov = provenance(external.get('provenance'), post, cutoff, generated, require_auxiliary, strict_cross_post)
    return {'post': native, 'prediction_at': iso(cutoff), 'probabilities': probabilities(external['probabilities']),
            'model': {'id': model_id, 'version': model_version, 'weights_sha256': digest,
                      'generated_at': iso(generated), 'available_at': iso(available)},
            'provenance': prov, 'input_feature_count': input_count}


def entropy(distribution):
    return -sum(p * math.log(p) for p in distribution.values() if p > 0) / math.log(len(CLASSES))


def predict(record):
    result = validate_prediction(record)
    distribution = result['probabilities']
    if distribution is None:
        estimated = 'unknown'
    else:
        best = max(distribution.values())
        winners = [name for name, score in distribution.items() if score == best]
        estimated = winners[0] if len(winners) == 1 else 'unknown'
    return {'contract_version': CONTRACT, **result,
            'status': 'unavailable' if distribution is None else 'unverified_external_model_estimate',
            'estimated_content_origin': estimated, 'verified_content_origin': None,
            'uncertainty': {'normalized_entropy': None if distribution is None else entropy(distribution),
                            'calibration': 'not_verified', 'probability_interval': None},
            'limitations': list(LIMITATIONS)}


def auxiliary_features(record, downstream_at=None, strict_cross_post=False):
    """Generate probabilities, masks and entropy, never a hard/true origin label.

    Both OOF and chronological predictions must have been available at the
    downstream cutoff. OOF alone is insufficient if it trains on later posts.
    strict_cross_post requires known concrete content/event groups and actual
    first publication times. Group assignments still need upstream review;
    checking declared IDs does not prove leakage-free external model training.
    """
    result = validate_prediction(record, require_auxiliary=True, strict_cross_post=strict_cross_post)
    cutoff = time(result['prediction_at'], 'prediction_at')
    downstream = time(downstream_at, 'downstream_at') if downstream_at else cutoff
    if cutoff > downstream or (result['model'] and time(result['model']['available_at'], 'available_at') > downstream):
        raise ValueError('authorship predictions unavailable at downstream cutoff')
    distribution = result['probabilities']
    numeric = {f'authorship_p_{name}': None if distribution is None else distribution[name] for name in CLASSES}
    numeric.update(authorship_entropy=None if distribution is None else entropy(distribution),
                   authorship_missing=distribution is None, authorship_is_model_estimate=distribution is not None)
    return {'contract_version': CONTRACT, 'post': result['post'], 'prediction_at': result['prediction_at'],
            'downstream_at': iso(downstream), 'features': numeric,
            'provenance': result['provenance'], 'calibration': 'not_verified',
            'verified_label_included': False, 'probability_interval': None,
            'warning': 'Soft unverified model outputs only. Declared IDs/times and supplied content groups are checked; actual group assignments, canonical edit, duplicate-text and comment relationships remain unverified.'}


def validate_label(label):
    fields = ('contract_version', 'post', 'scope', 'label_policy', 'content_origin', 'label_available_at', 'evidence')
    obj(label, fields, fields, 'label')
    if label['contract_version'] != LABEL_CONTRACT or label['content_origin'] not in STATES:
        raise ValueError('invalid label contract or content_origin')
    if label['scope'] != 'text.body':
        raise ValueError('label scope must be text.body, not account or publishing control')
    policy = text(label['label_policy'], 'label_policy')
    native = identity(label['post'])
    available = time(label['label_available_at'], 'label_available_at')
    evidence = label['evidence']
    if not isinstance(evidence, list) or (label['content_origin'] != 'unknown' and not evidence):
        raise ValueError('known source labels require documented evidence')
    for row in evidence:
        obj(row, ('method', 'reference', 'available_at'), ('method', 'reference', 'available_at'), 'label evidence')
        if row['method'] not in ('author_disclosure', 'controlled_generation', 'documented_creation'):
            raise ValueError('style/badge/detector guesses cannot serve as true source labels')
        text(row['reference'], 'evidence reference')
        if time(row['available_at'], 'evidence available_at') > available:
            raise ValueError('label cannot precede its evidence availability')
    return {'post': native, 'scope': 'text.body', 'label_policy': policy,
            'content_origin': label['content_origin'], 'label_available_at': iso(available),
            'evidence_count': len(evidence), 'evidence_status': 'declared_evidence_not_independently_verified'}


def evaluate(record, label, evaluation_at, strict_cross_post=False):
    """Evaluate separate evidence labels after availability; never export them as features."""
    result = validate_prediction(record, require_auxiliary=True, strict_cross_post=strict_cross_post)
    truth = validate_label(label)
    if any(result['post'][key] != truth['post'][key] for key in ('platform', 'post_id', 'version')):
        raise ValueError('prediction and label must identify the same native post/content version')
    at = time(evaluation_at, 'evaluation_at')
    if max(time(result['prediction_at'], 'prediction_at'), time(truth['label_available_at'], 'label_available_at')) > at:
        raise ValueError('evaluation cannot use a future prediction or unavailable label')
    distribution, target = result['probabilities'], truth['content_origin']
    score = {'brier': None, 'log_loss': None, 'log_loss_reason': None}
    status = 'unavailable_prediction' if distribution is None else 'unknown_label' if target == 'unknown' else 'descriptive_evaluation'
    if status == 'descriptive_evaluation':
        score['brier'] = sum((distribution[name] - int(name == target)) ** 2 for name in CLASSES)
        if distribution[target] == 0:
            score['log_loss_reason'] = 'infinite_for_zero_target_probability; not encoded as NaN/Infinity'
        else:
            score['log_loss'] = -math.log(distribution[target])
    return {'post': result['post'], 'prediction_at': result['prediction_at'], 'evaluation_at': iso(at),
            'status': status, 'label': truth, **score,
            'calibration': 'not_established_from_one_prediction', 'label_used_as_feature': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--auxiliary', action='store_true')
    parser.add_argument('--strict-cross-post', action='store_true',
                        help='with --auxiliary, require known concrete content/event groups and first publication times')
    parser.add_argument('--downstream-at')
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.resolve() == args.record.resolve():
            raise ValueError('output must not overwrite the input record')
        if args.strict_cross_post and not args.auxiliary:
            raise ValueError('--strict-cross-post requires --auxiliary')
        record = json.loads(args.record.read_text())
        result = auxiliary_features(record, args.downstream_at, args.strict_cross_post) if args.auxiliary else predict(record)
        encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded)
        else:
            print(encoded, end='')
    except (ValueError, TypeError, OSError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
