#!/usr/bin/env python3
"""Fixed, private, retrospective SEISMIC added-retweet benchmark.

``plan`` validates and freezes an experiment without importing PyTorch or fitting.
``train`` consumes that immutable plan exactly once. All weights and row-level
predictions stay in the chosen private run directory. This is not a views,
verified-Home, text, authorship, or current-X-account predictor.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


CSV_FIELDS = [
    "cascade_id", "post_time_day", "cutoff_seconds", "paper_day_split",
    "strict_label_available_split", "observed_retweet_count",
    "first_observed_retweet_seconds", "last_observed_retweet_seconds",
    "future_retweets_to_24h", "total_retweets_at_24h", "label_available_day",
]
FEATURE_NAMES = ["log1p_observed", "first_fraction", "last_fraction", "cold_indicator", "cutoff_fraction_24h"]
CONFIG = {
    "schema": "rise-retweet-benchmark-v1",
    "target": "additional_retweets_in_(cutoff,86400]_seconds",
    "cutoffs_seconds": [900, 3600], "seed": 20261008,
    "hidden_widths": [16, 8], "max_epochs": 15, "batch_size": 4096,
    "learning_rate": 0.01, "weight_decay": 0.0,
    "training_loss": "smooth_l1_of_log1p_additional_count_beta_1",
    "selection_metric": "validation_raw_count_mae", "log_output_cap": 20.0,
    "inner_fit_rule": "post_time_day+1<=4",
    "inner_validation_rule": "4<=post_time_day<6",
    "inner_purge_rule": "3<post_time_day<4",
    "outer_fit_rule": "post_time_day+1<=7",
    "outer_test_rule": "post_time_day>=7",
    "outer_purge_rule": "6<post_time_day<7",
    "test_evaluations": 1, "cpu_threads": 1, "cpu_interop_threads": 1,
    "input_feature_names": FEATURE_NAMES,
    "bucket_rule": "floor(log2(observed_count+1)); train-only median; unseen bucket falls back to train median",
    "selection_tie_rule": "earliest_epoch", "parameter_count_per_cutoff": 241,
    "limitations": [
        "2011 English no-hashtag corpus selected using future retweet activity",
        "Released data have 49-retweet exceptions and do not verify paper 14-day completeness",
        "Different canonical original IDs are different cascades, not proven independent authors or deduplicated text",
        "No ordinary views, verified Home, text, media, comments, authorship or current-account calibration",
        "Dataset license unresolved; source files, weights and row-level predictions remain private",
        "Cold at cutoff is not an unbiased sample of truly low/zero-final-retweet posts",
    ],
}


def clock():
    return datetime.now(timezone.utc).isoformat()


def file_sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_new(path, value):
    """Exclusive private JSON creation: never overwrite an existing artifact."""
    fd = os.open(Path(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def finite_number(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name}: boolean is not a number")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name}: invalid numeric value") from error
    if not math.isfinite(result):
        raise ValueError(f"{name}: nonfinite numeric value")
    return result


def nonnegative_integer(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name}: boolean is not an integer")
    if isinstance(value, str):
        if not re.fullmatch(r"[0-9]+", value, flags=re.ASCII):
            raise ValueError(f"{name}: integer text must be ASCII decimal digits")
        number = int(value)
    elif isinstance(value, int):
        number = value
    elif isinstance(value, float) and math.isfinite(value) and value.is_integer():
        number = int(value)
    else:
        raise ValueError(f"{name}: invalid integer value")
    if number < 0 or number > 9007199254740991:
        raise ValueError(f"{name}: must be an exactly representable nonnegative integer <=2^53-1")
    return int(number)


def split_for_day(day):
    if not 0 <= day < 15:
        raise ValueError("post_time_day must be in [0,15)")
    return "train_candidate" if day + 1 <= 7 else ("purged_label_overlap" if day < 7 else "evaluation_candidate")


def inner_split(day):
    if day + 1 <= 4:
        return "fit"
    if 4 <= day < 6:
        return "validation"
    return "purged"


@dataclass(frozen=True, slots=True)
class Row:
    cascade_id: str
    day: float
    cutoff: int
    split: str
    observed: int
    first: float | None
    last: float | None
    target: int
    total: int


def validate_inference_input(cutoff, observed, first, last):
    cutoff = nonnegative_integer(cutoff, "cutoff_seconds")
    observed = nonnegative_integer(observed, "observed_retweet_count")
    if cutoff not in (900, 3600):
        raise ValueError("cutoff_seconds must be 900 or 3600")
    if observed == 0:
        if first is not None or last is not None:
            raise ValueError("cold cascades must have missing first/last times")
    else:
        if first is None or last is None:
            raise ValueError("nonzero observed count requires both first/last times")
        first = finite_number(first, "first_observed_retweet_seconds")
        last = finite_number(last, "last_observed_retweet_seconds")
        if not 0 <= first <= last <= cutoff:
            raise ValueError("observed times must obey 0<=first<=last<=cutoff")
        if observed == 1 and first != last:
            raise ValueError("one observed event must have identical first/last times")
    return cutoff, observed, first, last


def vector_from_values(cutoff, observed, first, last):
    cutoff, observed, first, last = validate_inference_input(cutoff, observed, first, last)
    return [math.log1p(observed), 0.0 if first is None else first / cutoff,
            0.0 if last is None else last / cutoff, float(observed == 0), cutoff / 86400.0]


def row_vector(row):
    # An explicit allowlist. No target, ID, day, split or source follower values.
    return vector_from_values(row.cutoff, row.observed, row.first, row.last)


def source_index_identity(index_path):
    """Quarantine repeated/noncanonical raw IDs independently of prepared metadata."""
    records = []
    counts = Counter()
    expected_start = 1
    with Path(index_path).open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["tweet_id", "post_time_day", "start_ind", "end_ind"]:
            raise ValueError("unexpected source index schema")
        for position, item in enumerate(reader, 1):
            raw_id = item["tweet_id"]
            canonical = re.fullmatch(r"[1-9][0-9]*", raw_id, flags=re.ASCII) is not None
            day = finite_number(item["post_time_day"], "index post_time_day")
            split_for_day(day)
            start = nonnegative_integer(item["start_ind"], "start_ind")
            end = nonnegative_integer(item["end_ind"], "end_ind")
            if start != expected_start or end < start:
                raise ValueError("noncontiguous or invalid source index event range")
            expected_start = end + 1
            if canonical:
                counts[raw_id] += 1
            records.append((position, raw_id, day, canonical))
    allowed = {f"cascade-{position:06d}": day for position, raw_id, day, canonical in records
               if canonical and counts[raw_id] == 1}
    audit = {"index_segments": len(records), "canonical_usable_cascades": len(allowed),
             "noncanonical_segments": sum(not item[3] for item in records),
             "repeated_canonical_segments": sum(canonical and counts[raw_id] > 1 for _, raw_id, _, canonical in records)}
    return allowed, audit


def parse_row(item):
    if set(item) != set(CSV_FIELDS):
        raise ValueError("unexpected/missing input column")
    cascade_id = item["cascade_id"]
    if not re.fullmatch(r"cascade-[0-9]{6}", cascade_id, flags=re.ASCII):
        raise ValueError("invalid anonymous cascade ID")
    day = finite_number(item["post_time_day"], "post_time_day")
    split = split_for_day(day)
    paper = "train_candidate" if day < 7 else "evaluation_candidate"
    if item["strict_label_available_split"] != split or item["paper_day_split"] != paper:
        raise ValueError("unknown or mismatched split")
    label_day = finite_number(item["label_available_day"], "label_available_day")
    if not math.isclose(label_day, day + 1, rel_tol=0, abs_tol=1e-10):
        raise ValueError("label_available_day must equal post_time_day+1")
    first = None if item["first_observed_retweet_seconds"] == "" else item["first_observed_retweet_seconds"]
    last = None if item["last_observed_retweet_seconds"] == "" else item["last_observed_retweet_seconds"]
    cutoff, observed, first, last = validate_inference_input(item["cutoff_seconds"], item["observed_retweet_count"], first, last)
    target = nonnegative_integer(item["future_retweets_to_24h"], "future_retweets_to_24h")
    total = nonnegative_integer(item["total_retweets_at_24h"], "total_retweets_at_24h")
    if total != observed + target:
        raise ValueError("target/observed/total identity failed")
    return Row(cascade_id, day, cutoff, split, observed, first, last, target, total)


def load_table(path, allowed):
    by_cutoff = {900: [], 3600: []}
    groups = defaultdict(dict)
    with Path(path).open(newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != CSV_FIELDS:
            raise ValueError("input CSV must have exactly the documented 11 fields in order")
        for item in reader:
            row = parse_row(item)
            if row.cascade_id not in allowed:
                raise ValueError("feature cascade absent from canonical non-repeated source index")
            if not math.isclose(row.day, allowed[row.cascade_id], rel_tol=0, abs_tol=1e-10):
                raise ValueError("feature/source-index day mismatch")
            if row.cutoff in groups[row.cascade_id]:
                raise ValueError("duplicate (cascade_id, cutoff_seconds)")
            groups[row.cascade_id][row.cutoff] = row
            by_cutoff[row.cutoff].append(row)
    if set(groups) != set(allowed):
        raise ValueError("prepared table omitted canonical usable source cascades")
    for pair in groups.values():
        if set(pair) != {900, 3600}:
            raise ValueError("each cascade must have exactly both paired cutoffs")
        early, late = pair[900], pair[3600]
        if early.day != late.day or early.split != late.split or early.total != late.total:
            raise ValueError("paired cascade metadata/split/24h-total mismatch")
        if early.observed > late.observed:
            raise ValueError("paired observed count decreased")
        if early.observed == 0 and late.observed > 0 and late.first <= 900:
            raise ValueError("cold early cascade cannot have a later first event before its early cutoff")
        if late.observed > early.observed and late.last <= 900:
            raise ValueError("new late observed events must occur after the early cutoff")
        if early.observed and (early.first != late.first or early.last > late.last):
            raise ValueError("paired first/last event history inconsistent")
        if early.observed == late.observed and (early.first != late.first or early.last != late.last):
            raise ValueError("unchanged count must retain identical first/last times")
    counts = Counter(row.split for row in by_cutoff[900])
    inner = Counter(inner_split(row.day) for row in by_cutoff[900] if row.split == "train_candidate")
    if not all(counts[name] for name in ("train_candidate", "evaluation_candidate")) or not inner["fit"] or not inner["validation"]:
        raise ValueError("empty required temporal training/validation/test partition")
    audit = {"cascades": len(groups), "paired_cutoff_rows": len(groups) * 2,
             "outer_cascades": dict(counts), "inner_cascades_within_outer_train": dict(inner),
             "by_cutoff": {str(cutoff): {"rows": len(rows), "cold_by_outer_split": dict(Counter(row.split for row in rows if row.observed == 0))}
                           for cutoff, rows in by_cutoff.items()},
             "author_disjoint": None, "text_deduplicated": None,
             "independent_author_or_content_count": None}
    return by_cutoff, audit


def verify_input(path, provenance_path, expected_sha):
    path, provenance_path = Path(path), Path(provenance_path)
    actual_sha = file_sha(path)
    provenance = json.loads(provenance_path.read_text())
    if actual_sha != expected_sha or provenance.get("features_sha256") != actual_sha:
        raise ValueError("input SHA does not match expected and preparation provenance")
    if not str(provenance.get("identity_policy", "")).startswith("Only raw ASCII decimal IDs"):
        raise ValueError("final canonical-only preparation provenance required")
    http_path = provenance_path.parent / "http-provenance.json"
    index_path = provenance_path.parent / "index.csv"
    http = json.loads(http_path.read_text())
    index_record = next((item for item in http if item.get("url") == "https://snap.stanford.edu/seismic/index.csv"), None)
    if not index_record or index_record.get("sha256") != file_sha(index_path):
        raise ValueError("source index digest not bound to HTTP provenance")
    allowed, identity = source_index_identity(index_path)
    rows, audit = load_table(path, allowed)
    if provenance.get("counts", {}).get("cascades") != audit["cascades"] or provenance.get("counts", {}).get("feature_rows") != audit["paired_cutoff_rows"]:
        raise ValueError("preparation count mismatch")
    quarantine_path = provenance_path.parent / "quarantined-id-segments.json"
    verification_path = provenance_path.parent / "verification-result.json"
    verification = json.loads(verification_path.read_text())
    if provenance.get("quarantine_sha256") != file_sha(quarantine_path) or provenance.get("http_provenance_sha256") != file_sha(http_path):
        raise ValueError("final quarantine/HTTP manifest digests mismatch")
    if (verification.get("features_sha256") != actual_sha
            or verification.get("verification_process_exit_code") != 0
            or verification.get("canonical_unique_source_cascades") != audit["cascades"]
            or verification.get("feature_rows_verified") != audit["paired_cutoff_rows"]
            or verification.get("source_cascades_crosschecked", 0) < min(1000, audit["cascades"])):
        raise ValueError("final prepared-table verification missing, stale or unsuccessful")
    audit["identity"] = identity
    meta = {"input": str(path.resolve()), "input_sha256": actual_sha,
            "input_bytes": path.stat().st_size, "provenance_path": str(provenance_path.resolve()),
            "provenance_sha256": file_sha(provenance_path), "preparation_provenance": provenance,
            "http_provenance_path": str(http_path.resolve()), "http_provenance_sha256": file_sha(http_path),
            "http_provenance": http, "index_path": str(index_path.resolve()), "index_sha256": file_sha(index_path),
            "quarantine_path": str(quarantine_path.resolve()), "quarantine_sha256": file_sha(quarantine_path),
            "verification_path": str(verification_path.resolve()), "verification_sha256": file_sha(verification_path),
            "verification": verification}
    return rows, audit, meta


def make_plan(input_path, provenance_path, output_path, expected_sha):
    started = clock()
    _, audit, metadata = verify_input(input_path, provenance_path, expected_sha)
    output = Path(output_path)
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    plan = {"config": CONFIG, "data": metadata, "audit": audit,
            "code_path": str(Path(__file__).resolve()), "code_sha256": file_sha(__file__),
            "plan_started_at": started, "plan_frozen_at": clock(), "training_performed": False,
            "output_directory": str(output.resolve())}
    write_new(output / "plan.json", plan)
    return plan


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def count_metrics(actual, predicted):
    if len(actual) != len(predicted):
        raise ValueError("metric prediction/target count mismatch")
    if not actual:
        return {"n_cascades": 0, "mae": None, "log1p_mae": None, "median_absolute_error": None,
                "p90_absolute_error": None, "wape": None, "sum_actual": 0}
    truth = [finite_number(value, "actual") for value in actual]
    guesses = [finite_number(value, "predicted") for value in predicted]
    if any(value < 0 for value in truth + guesses):
        raise ValueError("counts and predictions must be nonnegative")
    errors = [abs(a - p) for a, p in zip(truth, guesses)]
    total = sum(truth)
    return {"n_cascades": len(truth), "mae": statistics.mean(errors),
            "log1p_mae": statistics.mean(abs(math.log1p(a) - math.log1p(p)) for a, p in zip(truth, guesses)),
            "median_absolute_error": statistics.median(errors), "p90_absolute_error": percentile(errors, 0.9),
            "wape": sum(errors) / total if total else None, "sum_actual": total,
            "bias_predicted_minus_actual": statistics.mean(p - a for a, p in zip(truth, guesses)),
            "rmse": math.sqrt(statistics.mean(error * error for error in errors))}


def bucket_for_count(count):
    return (count + 1).bit_length() - 1


def fit_baselines(rows):
    if not rows or any(row.split != "train_candidate" for row in rows):
        raise ValueError("baselines fit exclusively on nonempty outer training rows")
    buckets = defaultdict(list)
    for row in rows:
        buckets[bucket_for_count(row.observed)].append(row.target)
    return {"constant_median": statistics.median(row.target for row in rows),
            "bucket_medians": {str(key): statistics.median(values) for key, values in buckets.items()},
            "bucket_training_counts": {str(key): len(values) for key, values in buckets.items()},
            "training_cascades": len(rows)}


def baseline_predictions(rows, fitted):
    return {"zero_additional_keep_last_count": [0.0 for _ in rows],
            "constant_train_median": [float(fitted["constant_median"]) for _ in rows],
            "early_constant_rate": [row.observed * (86400 - row.cutoff) / row.cutoff for row in rows],
            "train_log_count_bucket_median": [float(fitted["bucket_medians"].get(str(bucket_for_count(row.observed)), fitted["constant_median"])) for row in rows]}


def normalizer_from_rows(rows):
    vectors = [row_vector(row) for row in rows]
    mean = [statistics.mean(values) for values in zip(*vectors)]
    scale = [statistics.pstdev(values) or 1.0 for values in zip(*vectors)]
    return {"mean": mean, "scale": scale, "fit_cascades": len(rows)}


def softplus(value):
    return max(value, 0.0) + math.log1p(math.exp(-abs(value)))


def predict_stdlib(state, cutoff, observed, first=None, last=None):
    if state.get("schema") != "rise-retweet-state-v1" or state.get("feature_names") != FEATURE_NAMES:
        raise ValueError("unsupported model state schema or feature order")
    cutoff, observed, first, last = validate_inference_input(cutoff, observed, first, last)
    model = state["models"].get(str(cutoff))
    if model is None or model.get("cutoff_seconds") != cutoff or model.get("target") != "additional_retweets_in_(cutoff,86400]_seconds":
        raise ValueError("model cutoff/target mismatch")
    norm = model["normalizer"]
    vector = vector_from_values(cutoff, observed, first, last)
    if (len(norm["mean"]) != 5 or len(norm["scale"]) != 5
            or any(not math.isfinite(x) or isinstance(x, bool) for x in norm["mean"])
            or any(not math.isfinite(x) or isinstance(x, bool) or x <= 0 for x in norm["scale"])):
        raise ValueError("invalid normalizer")
    vector = [(value - mean) / scale for value, mean, scale in zip(vector, norm["mean"], norm["scale"])]
    expected_widths = [(5, 16), (16, 8), (8, 1)]
    if len(model["layers"]) != 3:
        raise ValueError("invalid layer count")
    for index, (layer, (input_width, output_width)) in enumerate(zip(model["layers"], expected_widths)):
        weight, bias = layer["weight"], layer["bias"]
        if len(weight) != output_width or len(bias) != output_width or any(len(row) != input_width for row in weight):
            raise ValueError("invalid layer dimensions")
        if any(not math.isfinite(value) for row in weight for value in row) or any(not math.isfinite(value) for value in bias):
            raise ValueError("nonfinite layer values")
        vector = [sum(w * value for w, value in zip(row, vector)) + b for row, b in zip(weight, bias)]
        if index < 2:
            vector = [max(0.0, value) for value in vector]
    return math.expm1(min(20.0, softplus(vector[0])))


def inference_source():
    functions = [finite_number, nonnegative_integer, validate_inference_input, vector_from_values, softplus, predict_stdlib]
    source = "#!/usr/bin/env python3\nfrom __future__ import annotations\nimport argparse\nimport json\nimport math\nimport re\n"
    source += "FEATURE_NAMES = " + repr(FEATURE_NAMES) + "\n\n"
    source += "\n\n".join(inspect.getsource(function) for function in functions)
    source += '''\n\nif __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Private SEISMIC additional-retweet inference; not views/Home")
    parser.add_argument("--state", required=True)
    parser.add_argument("--cutoff", type=int, required=True, choices=[900, 3600])
    parser.add_argument("--observed", type=int, required=True)
    parser.add_argument("--first", type=float)
    parser.add_argument("--last", type=float)
    args = parser.parse_args()
    with open(args.state) as stream:
        state = json.load(stream)
    result = predict_stdlib(state, args.cutoff, args.observed, args.first, args.last)
    print(json.dumps({"additional_retweets_by_24h": result, "total_retweets_by_24h": args.observed + result,
                      "cutoff_seconds": args.cutoff, "scope": "2011 retweet-conditioned corpus only"}, allow_nan=False))
'''
    return source


def export_model(model, normalizer, cutoff, selected_epochs):
    layers = [{"weight": model[index].weight.detach().cpu().tolist(), "bias": model[index].bias.detach().cpu().tolist()}
              for index in (0, 2, 4)]
    return {"cutoff_seconds": cutoff, "target": CONFIG["target"], "layers": layers,
            "normalizer": normalizer, "selected_epochs": selected_epochs,
            "parameter_count": sum(parameter.numel() for parameter in model.parameters())}


def build_model(torch, seed):
    torch.manual_seed(seed)
    return torch.nn.Sequential(torch.nn.Linear(5, 16), torch.nn.ReLU(), torch.nn.Linear(16, 8),
                               torch.nn.ReLU(), torch.nn.Linear(8, 1), torch.nn.Softplus())


def tensor_features(torch, rows, normalizer):
    raw = torch.tensor([row_vector(row) for row in rows], dtype=torch.float32, device="cpu")
    mean = torch.tensor(normalizer["mean"], dtype=torch.float32)
    scale = torch.tensor(normalizer["scale"], dtype=torch.float32)
    return (raw - mean) / scale


def torch_predictions(torch, model, features):
    model.eval()
    with torch.no_grad():
        return torch.expm1(torch.clamp(model(features).reshape(-1), max=CONFIG["log_output_cap"])).tolist()


def fit_network(torch, rows, cutoff, epochs, validation=None):
    """No evaluation-candidate rows may enter optimizer or selection."""
    if not rows or any(row.cutoff != cutoff or row.split != "train_candidate" for row in rows):
        raise ValueError("network fit needs same-cutoff outer train rows only")
    if validation is not None:
        if any(inner_split(row.day) != "fit" for row in rows):
            raise ValueError("selection fit contains non-inner-fit rows")
        if not validation or any(row.cutoff != cutoff or row.split != "train_candidate" or inner_split(row.day) != "validation" for row in validation):
            raise ValueError("selection validation contains non-inner-validation rows")
    seed = CONFIG["seed"] + cutoff
    model = build_model(torch, seed)
    normalizer = normalizer_from_rows(rows)
    features = tensor_features(torch, rows, normalizer)
    labels = torch.tensor([math.log1p(row.target) for row in rows], dtype=torch.float32).reshape(-1, 1)
    val_features = tensor_features(torch, validation, normalizer) if validation is not None else None
    optimizer = torch.optim.Adam(model.parameters(), lr=CONFIG["learning_rate"], weight_decay=CONFIG["weight_decay"])
    generator = torch.Generator(device="cpu").manual_seed(seed)
    history, selected, best = [], None, math.inf
    started = clock()
    for epoch in range(1, epochs + 1):
        model.train()
        order = torch.randperm(len(rows), generator=generator)
        loss_sum = 0.0
        for start in range(0, len(rows), CONFIG["batch_size"]):
            indices = order[start:start + CONFIG["batch_size"]]
            optimizer.zero_grad(set_to_none=True)
            loss = torch.nn.functional.smooth_l1_loss(model(features[indices]), labels[indices], beta=1.0)
            loss.backward()
            optimizer.step()
            loss_sum += float(loss.detach()) * len(indices)
        record = {"epoch": epoch, "train_log1p_smooth_l1": loss_sum / len(rows)}
        if validation is not None:
            predictions = torch_predictions(torch, model, val_features)
            metrics = count_metrics([row.target for row in validation], predictions)
            record["validation_metrics"] = metrics
            if metrics["mae"] < best:
                best, selected = metrics["mae"], epoch
        history.append(record)
    return model, normalizer, {"fit_started_at": started, "fit_completed_at": clock(), "seed": seed,
                              "training_cascades": len(rows), "validation_cascades": len(validation) if validation is not None else 0,
                              "epochs": epochs, "selected_epoch": selected, "history": history}


def check_export_agreement(torch, model, normalizer, state, cutoff, training_rows):
    probes = training_rows[:32] + training_rows[-32:]
    probes += [Row("probe", 0, cutoff, "train_candidate", 0, None, None, 0, 0),
               Row("probe", 0, cutoff, "train_candidate", 1, 0.0, 0.0, 0, 1),
               Row("probe", 0, cutoff, "train_candidate", 1, float(cutoff), float(cutoff), 0, 1),
               Row("probe", 0, cutoff, "train_candidate", 1000000, 0.0, float(cutoff), 0, 1000000)]
    torch_values = torch_predictions(torch, model, tensor_features(torch, probes, normalizer))
    plain = [predict_stdlib(state, row.cutoff, row.observed, row.first, row.last) for row in probes]
    differences = [abs(a - b) for a, b in zip(torch_values, plain)]
    if any(abs(a - b) > 1e-4 + 2e-5 * max(abs(a), abs(b)) for a, b in zip(torch_values, plain)):
        raise ValueError("exported stdlib inference disagrees with torch float32")
    return {"n_training_or_synthetic_probes": len(probes), "test_rows_used": 0,
            "max_absolute_difference": max(differences), "absolute_tolerance": 1e-4, "relative_tolerance": 2e-5}


def verify_frozen_artifacts(output):
    manifest_path = output / "models-frozen-before-test.json"
    if not manifest_path.is_file():
        raise ValueError("models must be frozen before any final test predictions")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("test_predictions_computed") is not False:
        raise ValueError("invalid pre-test freeze marker")
    for key, filename in [("state_sha256", "model-state.json"), ("baselines_sha256", "train-only-baselines.json"),
                          ("training_log_sha256", "training-log.json"), ("inference_sha256", "inference.py")]:
        path = output / filename
        if not path.is_file() or manifest.get(key) != file_sha(path):
            raise ValueError(f"frozen artifact missing or changed: {filename}")


def evaluate_test_once(torch, by_cutoff, models, fitted_baselines, output):
    """The single final evaluation transaction, after every model is frozen."""
    verify_frozen_artifacts(output)
    write_new(output / "test-evaluation-started.json", {"started_at": clock(), "evaluation_index": 1})
    report = {}
    fd = os.open(output / "test-predictions.csv", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["cascade_id", "cutoff_seconds", "cold_at_cutoff", "actual_additional_retweets", "model", "predicted_additional_retweets"])
        for cutoff in CONFIG["cutoffs_seconds"]:
            test = [row for row in by_cutoff[cutoff] if row.split == "evaluation_candidate"]
            model, normalizer = models[cutoff]
            predictions = baseline_predictions(test, fitted_baselines[cutoff])
            predictions["tiny_mlp_log1p"] = torch_predictions(torch, model, tensor_features(torch, test, normalizer))
            summaries = {}
            for name, values in predictions.items():
                summaries[name] = {}
                for stratum, indices in [("all", list(range(len(test)))),
                                         ("cold_at_cutoff", [i for i, row in enumerate(test) if row.observed == 0]),
                                         ("warm_at_cutoff", [i for i, row in enumerate(test) if row.observed > 0])]:
                    summaries[name][stratum] = count_metrics([test[i].target for i in indices], [values[i] for i in indices])
                for row, predicted in zip(test, values):
                    writer.writerow([row.cascade_id, cutoff, int(row.observed == 0), row.target, name, repr(predicted)])
            report[str(cutoff)] = {"test_cascades": len(test), "models": summaries}
    return {"completed_at": clock(), "test_evaluations": 1, "cutoffs": report,
            "pooled_cutoff_metric": None, "metric_units": "additional retweets; WAPE is a ratio",
            "p90_rule": "linear interpolation at (n-1)*0.9", "wape_if_actual_sum_zero": None,
            "confidence_interval": None, "independent_author_count": None}


def run_plan(plan_path):
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text())
    output = Path(plan["output_directory"])
    if plan_path.resolve() != (output / "plan.json").resolve() or plan["config"] != CONFIG:
        raise ValueError("unexpected plan path or altered fixed configuration")
    if plan["code_sha256"] != file_sha(__file__) or plan["code_path"] != str(Path(__file__).resolve()):
        raise ValueError("code changed since experiment plan was frozen")
    if file_sha(plan["data"]["provenance_path"]) != plan["data"]["provenance_sha256"]:
        raise ValueError("preparation provenance changed since frozen plan")
    rows, audit, data = verify_input(plan["data"]["input"], plan["data"]["provenance_path"], plan["data"]["input_sha256"])
    if audit != plan["audit"] or data != plan["data"]:
        raise ValueError("data or source provenance changed since frozen plan")
    write_new(output / "training-started.json", {"started_at": clock(), "plan_sha256": file_sha(plan_path), "code_sha256": file_sha(__file__)})
    try:
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["MKL_NUM_THREADS"] = "1"
        import torch
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
        if torch.get_num_threads() != 1 or torch.get_num_interop_threads() != 1:
            raise ValueError("CPU thread setting failed")
        models, baselines, training, exported = {}, {}, {}, {}
        for cutoff in CONFIG["cutoffs_seconds"]:
            train = [row for row in rows[cutoff] if row.split == "train_candidate"]
            inner_fit = [row for row in train if inner_split(row.day) == "fit"]
            validation = [row for row in train if inner_split(row.day) == "validation"]
            _, _, selection = fit_network(torch, inner_fit, cutoff, CONFIG["max_epochs"], validation)
            epochs = selection["selected_epoch"]
            model, normalizer, final_fit = fit_network(torch, train, cutoff, epochs)
            models[cutoff], baselines[cutoff] = (model, normalizer), fit_baselines(train)
            exported[str(cutoff)] = export_model(model, normalizer, cutoff, epochs)
            if exported[str(cutoff)]["parameter_count"] != CONFIG["parameter_count_per_cutoff"]:
                raise ValueError("unexpected architecture parameter count")
            training[str(cutoff)] = {"selection": selection, "full_outer_train_fit": final_fit}
        state = {"schema": "rise-retweet-state-v1", "feature_names": FEATURE_NAMES, "models": exported,
                 "input_sha256": data["input_sha256"], "code_sha256": file_sha(__file__),
                 "config": CONFIG, "frozen_at": clock()}
        agreement = {str(cutoff): check_export_agreement(torch, *models[cutoff], state, cutoff,
                                                       [row for row in rows[cutoff] if row.split == "train_candidate"])
                     for cutoff in CONFIG["cutoffs_seconds"]}
        write_new(output / "model-state.json", state)
        write_new(output / "train-only-baselines.json", {str(key): value for key, value in baselines.items()})
        write_new(output / "training-log.json", training)
        fd = os.open(output / "inference.py", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(inference_source())
        frozen = {"frozen_at": clock(), "state_sha256": file_sha(output / "model-state.json"),
                  "baselines_sha256": file_sha(output / "train-only-baselines.json"),
                  "training_log_sha256": file_sha(output / "training-log.json"),
                  "inference_sha256": file_sha(output / "inference.py"), "export_agreement": agreement,
                  "test_predictions_computed": False}
        write_new(output / "models-frozen-before-test.json", frozen)
        evaluation = evaluate_test_once(torch, rows, models, baselines, output)
        report = {"schema": "rise-retweet-benchmark-report-v1", "config": CONFIG, "data_audit": audit,
                  "input_sha256": data["input_sha256"], "code_sha256": file_sha(__file__),
                  "state_sha256": frozen["state_sha256"], "predictions_sha256": file_sha(output / "test-predictions.csv"),
                  "runtime": {"python": sys.version, "python_executable": sys.executable, "torch": torch.__version__,
                              "device": "cpu", "dtype": "float32", "threads": torch.get_num_threads(), "interop_threads": torch.get_num_interop_threads()},
                  "training": training, "export_agreement": agreement, "evaluation": evaluation,
                  "completed_at": clock(), "public_release_performed": False}
        write_new(output / "report.json", report)
        write_new(output / "training-completed.json", {"completed_at": clock(), "report_sha256": file_sha(output / "report.json")})
        return report
    except BaseException as error:
        write_new(output / "training-failed.json", {"failed_at": clock(), "type": type(error).__name__, "message": str(error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="validate and freeze only; no torch import or training")
    plan.add_argument("--input", required=True)
    plan.add_argument("--provenance", required=True)
    plan.add_argument("--output", required=True)
    plan.add_argument("--expected-input-sha256", required=True)
    train = commands.add_parser("train", help="one CPU fitting and final evaluation attempt from frozen plan")
    train.add_argument("--plan", required=True)
    args = parser.parse_args()
    result = (make_plan(args.input, args.provenance, args.output, args.expected_input_sha256)
              if args.command == "plan" else run_plan(args.plan))
    print(json.dumps({"command": args.command, "output": result.get("output_directory", str(Path(args.plan).parent) if hasattr(args, "plan") else None),
                      "input_sha256": result.get("input_sha256", result.get("data", {}).get("input_sha256")),
                      "training_performed": args.command == "train"}, allow_nan=False))


if __name__ == "__main__":
    main()
