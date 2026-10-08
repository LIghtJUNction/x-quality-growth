#!/usr/bin/env python3
"""Private, selection-only SEISMIC experiment. Never evaluate the old final test.

plan freezes input/code hashes without fitting; train consumes that plan once.
Only the historical outer-train cascades are loaded. All reported errors and
interval coverage use the inner validation that also selects model/epoch, so
they are not an independent final assessment. No new samples or modalities.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path

try:
    from scripts import retweet_benchmark as old
except ModuleNotFoundError:
    import retweet_benchmark as old


CANDIDATES = ("original_smooth_l1", "ordered_quantile_pinball")
QUANTILES = (0.1, 0.5, 0.9)
CONFIG = {
    "schema": "rise-retweet-validation-plan-v1",
    "evaluation_scope": "inner_validation", "selection_used": True,
    "target": old.CONFIG["target"], "input_feature_names": old.FEATURE_NAMES,
    "outer_train_rule": "post_time_day+1<=7",
    "inner_fit_rule": "post_time_day+1<=4",
    "inner_validation_rule": "4<=post_time_day<6",
    "inner_purge_rule": "3<post_time_day<4 or post_time_day==6",
    "cutoffs_seconds": [900, 3600], "candidates": list(CANDIDATES),
    "quantiles": list(QUANTILES), "nominal_interval_coverage": 0.8,
    "quantile_parameterization": "q10_log=relu(raw0); q50_log=q10_log+softplus(raw1); q90_log=q50_log+softplus(raw2); inference_log_cap=20",
    "seed": 20261008, "max_epochs": 15, "batch_size": 4096,
    "learning_rate": 0.01, "weight_decay": 0.0, "log_output_cap": 20.0,
    "selection_metric": "validation_raw_median_mae",
    "selection_tie_rule": "earliest_epoch_then_declared_candidate_order",
    "parameter_counts": {CANDIDATES[0]: 241, CANDIDATES[1]: 259},
    "cpu_threads": 1, "cpu_interop_threads": 1, "test_evaluations": 0,
    "new_samples": 0, "multimodal": False,
}


def load_train_table(path, source_ids):
    """Drop non-train CSV records before constructing/parsing any label row.

    The posting-day cell alone determines admission. Test/embargo label cells
    may even be nonnumeric: they are never parsed or passed to a Row object.
    """
    allowed = {identity: day for identity, day in source_ids.items() if day + 1 <= 7}
    groups, skipped = {}, 0
    with Path(path).open(newline="") as stream:
        reader = csv.reader(stream)
        if next(reader, None) != old.CSV_FIELDS:
            raise ValueError("unexpected feature CSV schema")
        for cells in reader:
            if len(cells) != len(old.CSV_FIELDS):
                raise ValueError("unexpected feature CSV row width")
            day = old.finite_number(cells[1], "post_time_day")
            old.split_for_day(day)
            if day + 1 > 7:
                skipped += 1
                continue
            if cells[0] not in allowed or not math.isclose(day, allowed[cells[0]], rel_tol=0, abs_tol=1e-10):
                raise ValueError("outer-train feature/source identity or day mismatch")
            row = old.parse_row(dict(zip(old.CSV_FIELDS, cells)))
            pair = groups.setdefault(row.cascade_id, {})
            if row.cutoff in pair:
                raise ValueError("duplicate outer-train cascade/cutoff")
            pair[row.cutoff] = row
    if set(groups) != set(allowed):
        raise ValueError("incomplete canonical outer-train source coverage")
    by_cutoff = {900: [], 3600: []}
    for pair in groups.values():
        if set(pair) != {900, 3600}:
            raise ValueError("outer-train cascades require paired cutoffs")
        early, late = pair[900], pair[3600]
        if early.day != late.day or early.total != late.total or early.observed > late.observed:
            raise ValueError("inconsistent paired metadata/counts")
        if early.observed == 0 and late.observed > 0 and late.first <= 900:
            raise ValueError("early-cold history inconsistent with late first event")
        if late.observed > early.observed and late.last <= 900:
            raise ValueError("new observed events must be after early cutoff")
        if early.observed and (early.first != late.first or early.last > late.last):
            raise ValueError("inconsistent paired first/last events")
        if early.observed == late.observed and (early.first != late.first or early.last != late.last):
            raise ValueError("unchanged observed count must retain first/last")
        for cutoff in by_cutoff:
            by_cutoff[cutoff].append(pair[cutoff])
    partitions = Counter(old.inner_split(row.day) for row in by_cutoff[900])
    if not partitions["fit"] or not partitions["validation"]:
        raise ValueError("empty inner-fit or validation partition")
    return by_cutoff, {
        "outer_train_cascades_loaded": len(groups), "paired_rows_loaded": 2 * len(groups),
        "inner_partition_cascades": dict(partitions), "non_train_rows_skipped_before_label_parsing": skipped,
        "final_test_label_rows_loaded": 0, "test_evaluations": 0,
        "author_disjoint": None, "text_deduplicated": None,
    }


def verify_input(input_path, provenance_path, expected_sha):
    """Check pinned preparation evidence without old.verify_input/load_table."""
    input_path, provenance_path = Path(input_path), Path(provenance_path)
    actual_sha = old.file_sha(input_path)
    provenance = json.loads(provenance_path.read_text())
    if actual_sha != expected_sha or provenance.get("features_sha256") != actual_sha:
        raise ValueError("input digest does not match preparation and requested SHA")
    if not provenance.get("identity_policy", "").startswith("Only raw ASCII decimal IDs"):
        raise ValueError("canonical-only final preparation required")
    directory = provenance_path.parent
    paths = {name: directory / name for name in ("index.csv", "http-provenance.json", "quarantined-id-segments.json", "verification-result.json")}
    digests = {name: old.file_sha(path) for name, path in paths.items()}
    http = json.loads(paths["http-provenance.json"].read_text())
    index_record = next((item for item in http if item.get("url") == "https://snap.stanford.edu/seismic/index.csv"), None)
    if not index_record or index_record.get("sha256") != digests["index.csv"]:
        raise ValueError("index/HTTP provenance digest mismatch")
    if provenance.get("http_provenance_sha256") != digests["http-provenance.json"] or provenance.get("quarantine_sha256") != digests["quarantined-id-segments.json"]:
        raise ValueError("preparation manifest digest mismatch")
    allowed, identity = old.source_index_identity(paths["index.csv"])
    verification = json.loads(paths["verification-result.json"].read_text())
    if (provenance.get("counts", {}).get("cascades") != len(allowed)
            or provenance.get("counts", {}).get("feature_rows") != 2 * len(allowed)
            or verification.get("features_sha256") != actual_sha
            or verification.get("verification_process_exit_code") != 0
            or verification.get("canonical_unique_source_cascades") != len(allowed)
            or verification.get("feature_rows_verified") != 2 * len(allowed)
            or verification.get("source_cascades_crosschecked", 0) < min(1000, len(allowed))):
        raise ValueError("preparation verification missing, stale or unsuccessful")
    rows, audit = load_train_table(input_path, allowed)
    audit["source_identity"] = identity
    metadata = {"input_path": str(input_path.resolve()), "input_sha256": actual_sha,
                "provenance_path": str(provenance_path.resolve()), "provenance_sha256": old.file_sha(provenance_path),
                "evidence_paths": {name: str(path.resolve()) for name, path in paths.items()}, "evidence_sha256": digests}
    return rows, audit, metadata


def code_identity():
    return {"validation_path": str(Path(__file__).resolve()), "validation_sha256": old.file_sha(__file__),
            "benchmark_path": str(Path(old.__file__).resolve()), "benchmark_sha256": old.file_sha(old.__file__)}


def make_plan(input_path, provenance_path, output_path, expected_sha):
    _, audit, metadata = verify_input(input_path, provenance_path, expected_sha)
    output = Path(output_path)
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    plan = {"config": CONFIG, "data": metadata, "audit": audit, "code": code_identity(),
            "output_directory": str(output.resolve()), "frozen_at": old.clock(),
            "training_performed": False, "evaluation_scope": "inner_validation", "selection_used": True}
    old.write_new(output / "plan.json", plan)
    return plan


def ordered_log_quantiles(torch, raw):
    increments = torch.cat((torch.nn.functional.relu(raw[..., :1]), torch.nn.functional.softplus(raw[..., 1:])), dim=-1)
    return torch.cumsum(increments, dim=-1)


def pinball_loss(torch, predicted, labels):
    quantiles = torch.tensor(QUANTILES, dtype=predicted.dtype, device=predicted.device)
    residual = labels - predicted
    return torch.maximum(quantiles * residual, (quantiles - 1) * residual).mean()


def build_model(torch, candidate, seed):
    if candidate not in CANDIDATES:
        raise ValueError("unknown fixed candidate")
    torch.manual_seed(seed)
    if candidate == CANDIDATES[0]:
        return old.build_model(torch, seed)
    return torch.nn.Sequential(torch.nn.Linear(5, 16), torch.nn.ReLU(), torch.nn.Linear(16, 8),
                               torch.nn.ReLU(), torch.nn.Linear(8, 3))


def predict_tensor(torch, model, features, candidate):
    model.eval()
    with torch.no_grad():
        output = model(features)
        logs = output if candidate == CANDIDATES[0] else ordered_log_quantiles(torch, output)
        values = torch.expm1(torch.clamp(logs, max=CONFIG["log_output_cap"])).tolist()
    if candidate == CANDIDATES[0]:
        return {"median": [row[0] for row in values], "lower": None, "upper": None}
    return {"lower": [row[0] for row in values], "median": [row[1] for row in values], "upper": [row[2] for row in values]}


def validation_metrics(rows, predictions):
    if len(predictions["median"]) != len(rows) or ((predictions["lower"] is None) != (predictions["upper"] is None)):
        raise ValueError("prediction/row or interval pairing mismatch")
    if predictions["lower"] is not None and (len(predictions["lower"]) != len(rows) or len(predictions["upper"]) != len(rows)):
        raise ValueError("interval/row length mismatch")
    result = {}
    for stratum in ("all", "cold_at_cutoff", "warm_at_cutoff", "zero_target"):
        indices = [i for i, row in enumerate(rows) if stratum == "all"
                   or (stratum == "zero_target" and row.target == 0)
                   or (stratum == "cold_at_cutoff" and row.observed == 0)
                   or (stratum == "warm_at_cutoff" and row.observed > 0)]
        actual = [rows[i].target for i in indices]
        metrics = old.count_metrics(actual, [predictions["median"][i] for i in indices])
        if predictions["lower"] is None:
            coverage, width = None, None
        else:
            intervals = [(predictions["lower"][i], predictions["median"][i], predictions["upper"][i]) for i in indices]
            if any(not 0 <= lower <= median <= upper for lower, median, upper in intervals):
                raise ValueError("nonnegative ordered interval invariant failed")
            coverage = sum(lower <= truth <= upper for truth, (lower, _, upper) in zip(actual, intervals)) / len(actual) if actual else None
            width = sum(upper - lower for lower, _, upper in intervals) / len(intervals) if intervals else None
        result[stratum] = {**metrics, "raw_median_mae": metrics["mae"], "interval_80_empirical_coverage": coverage,
                           "interval_80_mean_width": width, "evaluation_scope": "inner_validation", "selection_used": True}
    return result


def predict_state_stdlib(state, cutoff, candidate, observed, first=None, last=None):
    """Apply private exported numeric state without importing PyTorch."""
    if state.get("schema") != "rise-retweet-validation-state-v1" or candidate not in CANDIDATES:
        raise ValueError("unsupported validation model state/candidate")
    vector = old.vector_from_values(cutoff, observed, first, last)
    model = state["models"][str(cutoff)][candidate]
    if model.get("feature_names") != old.FEATURE_NAMES or model.get("cutoff_seconds") != cutoff or model.get("target") != CONFIG["target"]:
        raise ValueError("exported input feature/cutoff/target mismatch")
    norm = model["normalizer"]
    if len(norm["mean"]) != 5 or len(norm["scale"]) != 5:
        raise ValueError("invalid normalizer width")
    means = [old.finite_number(value, "normalizer mean") for value in norm["mean"]]
    scales = [old.finite_number(value, "normalizer scale") for value in norm["scale"]]
    if any(value <= 0 for value in scales):
        raise ValueError("normalizer scale must be positive")
    vector = [(value - mean) / scale for value, mean, scale in zip(vector, means, scales)]
    widths = [(5, 16), (16, 8), (8, 1 if candidate == CANDIDATES[0] else 3)]
    if len(model["layers"]) != len(widths):
        raise ValueError("invalid exported layer count")
    for index, (layer, (input_width, output_width)) in enumerate(zip(model["layers"], widths)):
        weight, bias = layer["weight"], layer["bias"]
        if len(weight) != output_width or len(bias) != output_width or any(len(row) != input_width for row in weight):
            raise ValueError("invalid exported layer dimensions")
        weight = [[old.finite_number(value, "weight") for value in row] for row in weight]
        bias = [old.finite_number(value, "bias") for value in bias]
        vector = [sum(w * value for w, value in zip(row, vector)) + b for row, b in zip(weight, bias)]
        if index < 2:
            vector = [max(0.0, value) for value in vector]
    positive = ([old.softplus(vector[0])] if candidate == CANDIDATES[0]
                else [max(0.0, vector[0]), old.softplus(vector[1]), old.softplus(vector[2])])
    logs = positive if candidate == CANDIDATES[0] else [sum(positive[:i + 1]) for i in range(3)]
    values = [math.expm1(min(CONFIG["log_output_cap"], value)) for value in logs]
    if candidate == CANDIDATES[0]:
        return {"lower": None, "median": values[0], "upper": None}
    return {"lower": values[0], "median": values[1], "upper": values[2]}


def check_export_agreement(torch, model, normalizer, record, candidate, cutoff, fit):
    probes = fit[:16] + fit[-16:]
    probes += [old.Row("probe", 0, cutoff, "train_candidate", 0, None, None, 0, 0),
               old.Row("probe", 0, cutoff, "train_candidate", 1, 0.0, 0.0, 0, 1),
               old.Row("probe", 0, cutoff, "train_candidate", 1000000, 0.0, float(cutoff), 0, 1000000)]
    state = {"schema": "rise-retweet-validation-state-v1", "models": {str(cutoff): {candidate: record}}}
    tensors = predict_tensor(torch, model, old.tensor_features(torch, probes, normalizer), candidate)
    differences = []
    for index, row in enumerate(probes):
        plain = predict_state_stdlib(state, cutoff, candidate, row.observed, row.first, row.last)
        for name in ("lower", "median", "upper"):
            if tensors[name] is None:
                if plain[name] is not None:
                    raise ValueError("exported interval presence mismatch")
                continue
            value = tensors[name][index]
            difference = abs(value - plain[name])
            differences.append(difference)
            if difference > 1e-4 + 2e-5 * max(abs(value), abs(plain[name])):
                raise ValueError("exported stdlib validation inference disagrees with torch")
    return {"fit_or_synthetic_probes": len(probes), "validation_rows_used": 0, "final_test_rows_used": 0,
            "max_absolute_difference": max(differences), "absolute_tolerance": 1e-4, "relative_tolerance": 2e-5,
            "evaluation_scope": "inner_validation", "selection_used": True}


def fit_candidate(torch, fit, validation, cutoff, candidate):
    if not fit or any(row.cutoff != cutoff or row.split != "train_candidate" or old.inner_split(row.day) != "fit" for row in fit):
        raise ValueError("optimizer accepts inner-fit rows only")
    if not validation or any(row.cutoff != cutoff or row.split != "train_candidate" or old.inner_split(row.day) != "validation" for row in validation):
        raise ValueError("selection accepts inner-validation rows only")
    seed = CONFIG["seed"] + cutoff
    model = build_model(torch, candidate, seed)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    if parameter_count != CONFIG["parameter_counts"][candidate]:
        raise ValueError("candidate parameter count mismatch")
    normalizer = old.normalizer_from_rows(fit)
    features = old.tensor_features(torch, fit, normalizer)
    val_features = old.tensor_features(torch, validation, normalizer)
    labels = torch.tensor([math.log1p(row.target) for row in fit], dtype=torch.float32).reshape(-1, 1)
    optimizer = torch.optim.Adam(model.parameters(), lr=CONFIG["learning_rate"], weight_decay=CONFIG["weight_decay"])
    generator = torch.Generator(device="cpu").manual_seed(seed)
    best, selected, checkpoint, history = math.inf, None, None, []
    for epoch in range(1, CONFIG["max_epochs"] + 1):
        model.train()
        order = torch.randperm(len(fit), generator=generator)
        loss_sum = 0.0
        for start in range(0, len(fit), CONFIG["batch_size"]):
            indices = order[start:start + CONFIG["batch_size"]]
            optimizer.zero_grad(set_to_none=True)
            raw = model(features[indices])
            loss = (torch.nn.functional.smooth_l1_loss(raw, labels[indices], beta=1.0) if candidate == CANDIDATES[0]
                    else pinball_loss(torch, ordered_log_quantiles(torch, raw), labels[indices]))
            if not bool(torch.isfinite(loss)):
                raise ValueError("nonfinite training loss")
            loss.backward()
            optimizer.step()
            loss_sum += float(loss.detach()) * len(indices)
        predictions = predict_tensor(torch, model, val_features, candidate)
        metrics = validation_metrics(validation, predictions)
        mae = metrics["all"]["raw_median_mae"]
        history.append({"epoch": epoch, "fit_loss": loss_sum / len(fit), "validation": metrics,
                        "evaluation_scope": "inner_validation", "selection_used": True})
        if mae < best:
            best, selected, checkpoint = mae, epoch, copy.deepcopy(model.state_dict())
    model.load_state_dict(checkpoint)
    predictions = predict_tensor(torch, model, val_features, candidate)
    state = {"candidate": candidate, "cutoff_seconds": cutoff, "target": CONFIG["target"],
             "feature_names": old.FEATURE_NAMES, "normalizer": normalizer,
             "layers": [{"weight": model[i].weight.detach().tolist(), "bias": model[i].bias.detach().tolist()} for i in (0, 2, 4)],
             "quantiles": list(QUANTILES) if candidate == CANDIDATES[1] else None,
             "selected_epoch": selected, "parameter_count": parameter_count,
             "evaluation_scope": "inner_validation", "selection_used": True,
             "fit_cascades": len(fit), "validation_cascades": len(validation)}
    agreement = check_export_agreement(torch, model, normalizer, state, candidate, cutoff, fit)
    return state, predictions, {"selected_epoch": selected, "seed": seed, "history": history,
                                "export_agreement": agreement,
                                "evaluation_scope": "inner_validation", "selection_used": True}


def execute_validation(torch, by_cutoff, output):
    """Only fit and validation subsets reach models or prediction functions."""
    states, logs, report = {}, {}, {}
    fd = os.open(output / "validation-predictions.csv", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["cascade_id", "cutoff_seconds", "cold_at_cutoff", "actual_additional_retweets", "model", "lower_10", "median", "upper_90", "evaluation_scope", "selection_used"])
        for cutoff in CONFIG["cutoffs_seconds"]:
            fit = [row for row in by_cutoff[cutoff] if old.inner_split(row.day) == "fit"]
            validation = [row for row in by_cutoff[cutoff] if old.inner_split(row.day) == "validation"]
            baselines = old.fit_baselines(fit)
            prediction_map = {name: {"median": values, "lower": None, "upper": None}
                              for name, values in old.baseline_predictions(validation, baselines).items()}
            states[str(cutoff)], logs[str(cutoff)] = {}, {}
            for candidate in CANDIDATES:
                state, predictions, log = fit_candidate(torch, fit, validation, cutoff, candidate)
                states[str(cutoff)][candidate], prediction_map[candidate], logs[str(cutoff)][candidate] = state, predictions, log
            metrics = {name: validation_metrics(validation, prediction) for name, prediction in prediction_map.items()}
            selected = min(CANDIDATES, key=lambda name: (metrics[name]["all"]["raw_median_mae"], states[str(cutoff)][name]["selected_epoch"], CANDIDATES.index(name)))
            report[str(cutoff)] = {"fit_cascades": len(fit), "validation_cascades": len(validation),
                                   "models": metrics, "selected_candidate": selected,
                                   "evaluation_scope": "inner_validation", "selection_used": True}
            for name, prediction in prediction_map.items():
                for index, row in enumerate(validation):
                    writer.writerow([row.cascade_id, cutoff, int(row.observed == 0), row.target, name,
                                     None if prediction["lower"] is None else repr(prediction["lower"][index]),
                                     repr(prediction["median"][index]), None if prediction["upper"] is None else repr(prediction["upper"][index]),
                                     "inner_validation", True])
    return states, logs, report


def run_plan(plan_path):
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text())
    output = Path(plan["output_directory"])
    if plan_path.resolve() != (output / "plan.json").resolve() or plan["config"] != CONFIG or plan["code"] != code_identity():
        raise ValueError("plan path/config/code changed after freezing")
    rows, audit, data = verify_input(plan["data"]["input_path"], plan["data"]["provenance_path"], plan["data"]["input_sha256"])
    if audit != plan["audit"] or data != plan["data"]:
        raise ValueError("input evidence changed after freezing")
    old.write_new(output / "training-started.json", {"started_at": old.clock(), "plan_sha256": old.file_sha(plan_path),
                                                    "evaluation_scope": "inner_validation", "selection_used": True})
    try:
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["MKL_NUM_THREADS"] = "1"
        import torch
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
        if torch.get_num_threads() != 1 or torch.get_num_interop_threads() != 1:
            raise ValueError("CPU thread setting failed")
        states, logs, cutoffs = execute_validation(torch, rows, output)
        old.write_new(output / "model-state.private.json", {"schema": "rise-retweet-validation-state-v1", "models": states,
                                                           "input_sha256": data["input_sha256"], "code": plan["code"],
                                                           "evaluation_scope": "inner_validation", "selection_used": True})
        old.write_new(output / "training-log.private.json", logs)
        report = {"schema": "rise-retweet-validation-report-v1", "config": CONFIG, "data_audit": audit,
                  "input_sha256": data["input_sha256"], "code_sha256": plan["code"]["validation_sha256"],
                  "cutoffs": cutoffs, "evaluation_scope": "inner_validation", "selection_used": True,
                  "test_evaluations": 0, "pooled_cutoff_metric": None, "completed_at": old.clock(),
                  "private_artifact_sha256": {name: old.file_sha(output / name) for name in
                                              ("model-state.private.json", "training-log.private.json", "validation-predictions.csv")},
                  "limitations": ["Validation selected models and epochs; no independent final evaluation or calibrated-coverage claim",
                                  "2011 future-success-selected English no-hashtag retweets; no current views or verified Home",
                                  "No new samples, text/media/comment inputs, authorship labels or current-account transfer validation",
                                  "Paired cutoffs are correlated; author/text/topic independence and confidence intervals unknown",
                                  "Cutoff-cold posts are not an unbiased sample of ordinary zero-final-traffic posts"],
                  "runtime": {"python": sys.version, "torch": torch.__version__, "device": "cpu", "dtype": "float32",
                              "threads": torch.get_num_threads(), "interop_threads": torch.get_num_interop_threads()},
                  "public_release_performed": False}
        old.write_new(output / "aggregate-report.json", report)
        old.write_new(output / "training-completed.json", {"completed_at": old.clock(), "report_sha256": old.file_sha(output / "aggregate-report.json"),
                                                          "evaluation_scope": "inner_validation", "selection_used": True})
        return report
    except BaseException as error:
        old.write_new(output / "training-failed.json", {"failed_at": old.clock(), "type": type(error).__name__, "message": str(error),
                                                       "evaluation_scope": "inner_validation", "selection_used": True})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="verify outer-train-only loading and freeze; no fitting")
    plan.add_argument("--input", required=True)
    plan.add_argument("--provenance", required=True)
    plan.add_argument("--output", required=True)
    plan.add_argument("--expected-input-sha256", required=True)
    train = commands.add_parser("train", help="one CPU fitting attempt; inner validation only; never final test")
    train.add_argument("--plan", required=True)
    args = parser.parse_args()
    result = (make_plan(args.input, args.provenance, args.output, args.expected_input_sha256) if args.command == "plan" else run_plan(args.plan))
    print(json.dumps({"command": args.command, "evaluation_scope": "inner_validation", "selection_used": True,
                      "training_performed": args.command == "train", "test_evaluations": 0,
                      "input_sha256": result.get("input_sha256", result.get("data", {}).get("input_sha256"))}, allow_nan=False))


if __name__ == "__main__":
    main()
