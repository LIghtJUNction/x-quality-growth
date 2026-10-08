#!/usr/bin/env python3
"""Private HC3 Chinese answer-source experiment, separate from heat prediction.

acquire: bounded official download; plan: freeze provenance/config/groups, no fit;
train: consume one plan once, choose on validation, freeze, evaluate test once;
infer: default X domain is refused. Never emits invented three-class probabilities.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import statistics
import sys
import unicodedata
import urllib.request


DATASET = "Hello-SimpleAI/HC3-Chinese"
MAX_DOWNLOAD_BYTES = 10_000_000
FEATURE_BUCKETS = 16384
CONFIG = {
    "schema": "rise-hc3-authorship-binary-v1", "seed": 20261008,
    "task": "HC3_Chinese_open_qa_human_answer_vs_early_ChatGPT_answer",
    "positive_class": "ai_generated", "classes": ["human_written", "ai_generated"],
    "mixed_trained": False, "source_time": "unknown",
    "split_method": "question_and_duplicate_answer_connected_component_holdout",
    "split_group_fractions": [0.70, 0.15, 0.15], "time_holdout": False,
    "normalization": "NFKC_casefold_whitespace_collapse_v1",
    "answer_exclusion_policy": "null_or_empty_excluded; conflicting_normalized_answer_labels_excluded; same_label_duplicates_deduplicated",
    "features": {"input": "answer_text_only", "buckets": FEATURE_BUCKETS,
                 "ngram_lengths": [2, 3, 4], "hash": "blake2b_64_person_hc3char_v1",
                 "signed": True, "normalization": "l2", "boundary_padding": False},
    "model": "sparse_linear_binary_logistic", "parameter_count": 16385,
    "baseline": "train_standardized_log1p_normalized_answer_length_linear_logistic",
    "baseline_parameter_count": 2, "max_epochs": 12,
    "optimizer": "Adam", "learning_rate": 0.05, "weight_decay": 0.0,
    "batch": "full_train_partition", "loss": "binary_cross_entropy_with_logits",
    "selection_metric": "validation_negative_log_likelihood",
    "temperature_candidates": [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 8.0],
    "tie_rule": "earliest_epoch_then_temperature_nearest_one_then_smallest",
    "cpu_threads": 1, "cpu_interop_threads": 1, "test_evaluations": 1,
    "decision_threshold": 0.5, "ece": "10_equal_width_predicted_confidence_bins",
    "short_text_max_codepoints": 280,
    "inference_domain": "hc3_chinese_open_qa", "default_domain": "x_short_post",
    "limitations": [
        "Only released human answers versus early ChatGPT answers; no mixed supervision",
        "No original creation times; connected-group holdout is not time holdout",
        "Unknown real-author independence; exact normalized deduplication does not detect paraphrases",
        "Chinese QA domain does not validate X short posts or current generation models",
        "No views, impressions, verified Home, follower quality or heat auxiliary features",
        "Raw answers and row-level metadata remain private; data are not mirrored in model release",
    ],
}


def clock():
    return datetime.now(timezone.utc).isoformat()


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_new(path, value):
    fd = os.open(Path(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def private_empty_directory(path):
    path = Path(path).absolute()
    if path.is_symlink():
        raise ValueError("output directory must not be a symlink")
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise ValueError("output must be a new or empty directory")
    else:
        path.mkdir(parents=True, mode=0o700)
    path.chmod(0o700)
    return path


def normalize(text):
    if not isinstance(text, str):
        raise ValueError("answer/question must be a string")
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bounded_get(url, limit, destination=None):
    """Anonymous bounded GET; no retries and no unbounded responses."""
    started = clock()
    request = urllib.request.Request(url, headers={"User-Agent": "RISE-HC3-provenance/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        size = response.headers.get("Content-Length")
        if size is not None and int(size) > limit:
            raise ValueError("HTTP declared size exceeds the download bound")
        final_url, status = response.geturl(), response.status
        blocks, total = [], 0
        output = None
        try:
            if destination is not None:
                fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                output = os.fdopen(fd, "wb")
            while True:
                block = response.read(min(65536, limit + 1 - total))
                if not block:
                    break
                total += len(block)
                if total > limit:
                    raise ValueError("HTTP body exceeds the download bound")
                blocks.append(block)
                if output:
                    output.write(block)
        finally:
            if output:
                output.close()
    body = b"".join(blocks)
    if status != 200 or (size is not None and len(body) != int(size)):
        raise ValueError("expected complete HTTP 200 response")
    return body, {"url": url, "final_url": final_url, "http_status": status,
                  "started_at": started, "completed_at": clock(),
                  "content_length": int(size) if size is not None else None,
                  "bytes_read": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def acquire(output):
    output = private_empty_directory(output).resolve()
    metadata, metadata_http = bounded_get(f"https://huggingface.co/api/datasets/{DATASET}", 262144)
    metadata = json.loads(metadata)
    revision = metadata["sha"]
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("dataset revision is not a commit SHA")
    if metadata.get("cardData", {}).get("license") != "cc-by-sa-4.0":
        raise ValueError("official data card license has changed; review before acquisition")
    prefix = f"https://huggingface.co/datasets/{DATASET}/resolve/{revision}"
    card, card_http = bounded_get(f"{prefix}/README.md", 262144, output / "dataset-card.md")
    if b"license: cc-by-sa-4.0" not in card:
        raise ValueError("fixed-revision card does not confirm CC-BY-SA-4.0")
    _, source_http = bounded_get(f"{prefix}/open_qa.jsonl", MAX_DOWNLOAD_BYTES,
                                 output / "open_qa.jsonl")
    provenance = {"schema": "rise-hc3-acquisition-v1", "recorded_at": clock(),
                  "dataset": DATASET, "subset": "open_qa", "revision": revision,
                  "dataset_license": "CC-BY-SA-4.0", "upstream_license": "MIT",
                  "upstream_license_evidence": "https://github.com/Hello-SimpleAI/chatgpt-comparison-detection#dataset-copyright",
                  "data_license_scope": "HC3 publication follows CC-BY-SA or stricter upstream terms; not relicensed MIT",
                  "raw_redistribution": "not included in model publication",
                  "http": {"metadata": metadata_http, "card": card_http, "source": source_http},
                  "source_sha256": source_http["sha256"], "source_bytes": source_http["bytes_read"],
                  "source_path": str(output / "open_qa.jsonl"), "source_creation_time": "unknown"}
    write_new(output / "acquisition.json", provenance)
    return {"output": str(output), "revision": revision, "source_bytes": provenance["source_bytes"],
            "source_sha256": provenance["source_sha256"], "dataset_license": provenance["dataset_license"]}


class UnionFind:
    def __init__(self):
        self.parents = {}

    def find(self, key):
        if key not in self.parents:
            self.parents[key] = key
        root = key
        while self.parents[root] != root:
            root = self.parents[root]
        while self.parents[key] != key:
            parent = self.parents[key]
            self.parents[key] = root
            key = parent
        return root

    def union(self, left, right):
        left, right = self.find(left), self.find(right)
        if left != right:
            self.parents[max(left, right)] = min(left, right)


def build_dataset(path):
    """Connect all source edges BEFORE deduplication or conflict exclusions."""
    union, records, answer_owner = UnionFind(), [], {}
    totals = Counter()
    with Path(path).open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict) or set(obj) != {"question", "human_answers", "chatgpt_answers"}:
                raise ValueError(f"unexpected HC3 object schema at line {number}")
            question = normalize(obj["question"])
            if not question:
                raise ValueError("empty question cannot establish a source group")
            group = "q-" + text_sha(question)
            union.find(group)
            totals["source_questions"] += 1
            for label, key in enumerate(("human_answers", "chatgpt_answers")):
                answers = obj[key]
                if not isinstance(answers, list):
                    raise ValueError("HC3 answers must be lists")
                for answer in answers:
                    totals["source_answer_occurrences"] += 1
                    totals[f"source_label_{label}_occurrences"] += 1
                    if answer is None:
                        totals["missing_answer_occurrences_excluded"] += 1
                        continue
                    text = normalize(answer)
                    if not text:
                        totals["empty_answer_occurrences_excluded"] += 1
                        continue
                    fingerprint = text_sha(text)
                    if fingerprint in answer_owner:
                        union.union(group, answer_owner[fingerprint])
                    else:
                        answer_owner[fingerprint] = group
                    records.append((group, fingerprint, label, text))
    by_answer = defaultdict(list)
    for group, fingerprint, label, text in records:
        by_answer[fingerprint].append((union.find(group), label, text))
    rows = []
    for fingerprint, occurrences in sorted(by_answer.items()):
        labels = {item[1] for item in occurrences}
        if len(labels) > 1:
            totals["conflicting_label_unique_answers_excluded"] += 1
            totals["conflicting_label_answer_occurrences_excluded"] += len(occurrences)
            continue
        groups = {item[0] for item in occurrences}
        if len(groups) != 1:
            raise AssertionError("duplicate-answer component was not connected")
        totals["same_label_duplicate_occurrences_excluded"] += len(occurrences) - 1
        rows.append({"answer_sha256": fingerprint, "group_id": occurrences[0][0],
                     "label": occurrences[0][1], "text": occurrences[0][2]})
    components = sorted({r["group_id"] for r in rows},
                        key=lambda g: text_sha(f"{CONFIG['seed']}:{g}"))
    if len(components) < 10:
        raise ValueError("at least ten independent retained components are required")
    first, second = int(len(components) * 0.70), int(len(components) * 0.85)
    assigned = {g: ("train" if i < first else "validation" if i < second else "test")
                for i, g in enumerate(components)}
    for row in rows:
        row["split"] = assigned[row["group_id"]]
    summaries = {}
    for split in ("train", "validation", "test"):
        selected = [r for r in rows if r["split"] == split]
        labels = Counter(r["label"] for r in selected)
        summaries[split] = {"answers": len(selected), "groups": len({r["group_id"] for r in selected}),
                            "human_written": labels[0], "ai_generated": labels[1]}
        if not labels[0] or not labels[1]:
            raise ValueError(f"{split} must contain both binary classes")
    totals["retained_unique_answers"] = len(rows)
    totals["retained_connected_groups"] = len(components)
    totals["unique_normalized_questions"] = len(union.parents)
    totals["largest_retained_group_answers"] = max(Counter(r["group_id"] for r in rows).values())
    manifest = [{k: r[k] for k in ("answer_sha256", "group_id", "label", "split")} for r in rows]
    return rows, {"counts": dict(totals), "splits": summaries,
                  "retained_answer_occurrence_coverage": len(rows) / totals["source_answer_occurrences"],
                  "split_manifest_sha256": digest_json(manifest),
                  "source_creation_time": "unknown", "time_holdout": False}, manifest


def validate_provenance(input_path, provenance_path):
    provenance = json.loads(Path(provenance_path).read_text())
    revision = provenance.get("revision", "")
    if (provenance.get("schema") != "rise-hc3-acquisition-v1"
            or provenance.get("dataset") != DATASET or provenance.get("subset") != "open_qa"
            or provenance.get("dataset_license") != "CC-BY-SA-4.0"
            or provenance.get("upstream_license") != "MIT"
            or len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision)):
        raise ValueError("unsupported source provenance")
    source = provenance.get("http", {}).get("source", {})
    expected = f"https://huggingface.co/datasets/{DATASET}/resolve/{revision}/open_qa.jsonl"
    if source.get("url") != expected or source.get("http_status") != 200:
        raise ValueError("source must be the bounded official fixed-revision HTTP 200 download")
    times = []
    for value in (source.get("started_at"), source.get("completed_at"), provenance.get("recorded_at")):
        if not isinstance(value, str):
            raise ValueError("source acquisition needs actual UTC timestamps")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError("source acquisition timestamps must be UTC")
        times.append(parsed)
    if not times[0] <= times[1] <= times[2]:
        raise ValueError("source acquisition UTC timestamps are out of order")
    card = provenance.get("http", {}).get("card", {})
    card_path = Path(provenance_path).resolve().parent / "dataset-card.md"
    if (card.get("url") != expected.replace("open_qa.jsonl", "README.md")
            or card.get("http_status") != 200 or not card_path.is_file()
            or file_sha(card_path) != card.get("sha256")
            or card_path.stat().st_size != card.get("bytes_read")
            or b"license: cc-by-sa-4.0" not in card_path.read_bytes()):
        raise ValueError("fixed-revision official data card/license proof changed or missing")
    actual_sha, actual_bytes = file_sha(input_path), Path(input_path).stat().st_size
    if (actual_sha != provenance.get("source_sha256") or actual_sha != source.get("sha256")
            or actual_bytes != provenance.get("source_bytes") or actual_bytes != source.get("bytes_read")
            or not 0 < actual_bytes <= MAX_DOWNLOAD_BYTES):
        raise ValueError("source bytes/SHA do not match acquisition")
    return provenance


def plan(input_path, provenance_path, output):
    input_path, provenance_path = Path(input_path).resolve(), Path(provenance_path).resolve()
    provenance = validate_provenance(input_path, provenance_path)
    rows, coverage, manifest = build_dataset(input_path)
    output = private_empty_directory(output).resolve()
    code_path = Path(__file__).resolve()
    frozen = {"schema": "rise-hc3-plan-v1", "created_at": clock(), "config": CONFIG,
              "output_path": str(output), "input_path": str(input_path), "input_sha256": file_sha(input_path),
              "provenance_path": str(provenance_path), "provenance_sha256": file_sha(provenance_path),
              "code_path": str(code_path), "code_sha256": file_sha(code_path),
              "source": {k: provenance[k] for k in ("dataset", "subset", "revision", "dataset_license",
                                                   "upstream_license", "source_bytes")},
              "coverage": coverage, "python_version": sys.version,
              "training_performed": False, "test_performance_evaluated": False}
    write_new(output / "split-manifest.private.json", manifest)
    frozen["split_manifest_file_sha256"] = file_sha(output / "split-manifest.private.json")
    write_new(output / "plan.json", frozen)
    write_new(output / "plan-seal.json", {"plan_sha256": file_sha(output / "plan.json"),
                                          "frozen_at": clock(), "training_performed": False})
    return {"plan": str(output / "plan.json"), "plan_sha256": file_sha(output / "plan.json"),
            "coverage": coverage, "parameter_count": CONFIG["parameter_count"], "training_performed": False}


def verify_plan(plan_path):
    plan_path = Path(plan_path).resolve()
    frozen = json.loads(plan_path.read_text())
    seal = json.loads((plan_path.parent / "plan-seal.json").read_text())
    if plan_path != Path(frozen["output_path"]).resolve() / "plan.json":
        raise ValueError("frozen plan moved; once-only consumption is bound to its original directory")
    if seal.get("plan_sha256") != file_sha(plan_path) or frozen.get("config") != CONFIG:
        raise ValueError("frozen plan/config changed")
    if (Path(frozen["code_path"]).resolve() != Path(__file__).resolve()
            or file_sha(__file__) != frozen["code_sha256"]):
        raise ValueError("frozen experiment code changed")
    for key in ("input", "provenance"):
        if file_sha(frozen[f"{key}_path"]) != frozen[f"{key}_sha256"]:
            raise ValueError(f"frozen {key} changed")
    if file_sha(plan_path.parent / "split-manifest.private.json") != frozen["split_manifest_file_sha256"]:
        raise ValueError("frozen split manifest changed")
    validate_provenance(frozen["input_path"], frozen["provenance_path"])
    rows, coverage, _ = build_dataset(frozen["input_path"])
    if coverage != frozen["coverage"]:
        raise ValueError("recomputed groups/splits do not match frozen plan")
    return frozen, rows


def feature_items(answer):
    text = normalize(answer)
    buckets = defaultdict(float)
    for n in (2, 3, 4):
        for i in range(max(0, len(text) - n + 1)):
            value = int.from_bytes(hashlib.blake2b(text[i:i+n].encode(), digest_size=8,
                                                  person=b"hc3char_v1").digest(), "little")
            buckets[value % FEATURE_BUCKETS] += -1.0 if value & (1 << 63) else 1.0
    scale = math.sqrt(sum(v * v for v in buckets.values()))
    return [(k, buckets[k] / scale) for k in sorted(buckets) if buckets[k]] if scale else []


def feature_signature():
    return digest_json({"normalize_code": inspect.getsource(normalize),
                        "feature_code": inspect.getsource(feature_items),
                        "feature_config": CONFIG["features"], "buckets": FEATURE_BUCKETS,
                        "unicode_version": unicodedata.unidata_version})


def sigmoid(logit):
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    exp = math.exp(logit)
    return exp / (1.0 + exp)


def probabilities(logits, temperature):
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("temperature must be finite and positive")
    return [sigmoid(float(value) / temperature) for value in logits]


def nll(logits, labels, temperature):
    if len(logits) != len(labels) or not labels:
        raise ValueError("nonempty equal-sized logits and labels required")
    if (not math.isfinite(temperature) or temperature <= 0
            or any(not math.isfinite(float(value)) for value in logits)
            or any(label not in (0, 1) for label in labels)):
        raise ValueError("finite logits, positive temperature, and binary labels required")
    losses = []
    for logit, label in zip(logits, labels):
        scaled = float(logit) / temperature
        losses.append(max(scaled, 0.0) - label * scaled + math.log1p(math.exp(-abs(scaled))))
    return statistics.fmean(losses)


def selection_key(logits, labels, epoch, temperature):
    return (nll(logits, labels, temperature), epoch, abs(math.log(temperature)), temperature)


def binary_metrics(labels, probs):
    if len(labels) != len(probs) or any(y not in (0, 1) for y in labels):
        raise ValueError("binary labels and equally sized probabilities required")
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probs):
        raise ValueError("probabilities must be finite in [0,1]")
    n = len(labels)
    if not n:
        return {"n": 0, "class_counts": {"human_written": 0, "ai_generated": 0},
                "accuracy": None, "f1_ai": None, "f1_macro": None,
                "auroc": None, "brier": None, "ece": None, "small_group": True}
    prediction = [int(p >= 0.5) for p in probs]
    tp = sum(y == 1 and pred == 1 for y, pred in zip(labels, prediction))
    tn = sum(y == 0 and pred == 0 for y, pred in zip(labels, prediction))
    fp, fn = sum(y == 0 for y in labels) - tn, sum(y == 1 for y in labels) - tp
    positive, negative = sum(labels), n - sum(labels)
    f1_ai = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    f1_human = 2 * tn / (2 * tn + fp + fn) if 2 * tn + fp + fn else None
    # AUROC from average ranks, including ties. One-class groups are undefined.
    auc, rank_sum, offset = None, 0.0, 0
    ordered = sorted(zip(probs, labels))
    while offset < n:
        end = offset + 1
        while end < n and ordered[end][0] == ordered[offset][0]:
            end += 1
        rank_sum += (offset + 1 + end) / 2 * sum(y for _, y in ordered[offset:end])
        offset = end
    if positive and negative:
        auc = (rank_sum - positive * (positive + 1) / 2) / (positive * negative)
    bins = defaultdict(list)
    for y, pred, p in zip(labels, prediction, probs):
        confidence = p if pred else 1 - p
        bins[min(9, int(confidence * 10))].append((int(y == pred), confidence))
    reliability = [{"bin": i, "lower": i / 10, "upper": (i+1) / 10,
                    "upper_inclusive": i == 9, "n": len(bins[i]),
                    "accuracy": statistics.fmean(v[0] for v in bins[i]) if bins[i] else None,
                    "mean_confidence": statistics.fmean(v[1] for v in bins[i]) if bins[i] else None}
                   for i in range(10)]
    ece = sum(item["n"] / n * abs(item["accuracy"] - item["mean_confidence"])
              for item in reliability if item["n"])
    return {"n": n, "class_counts": {"human_written": negative, "ai_generated": positive},
            "accuracy": (tp + tn) / n, "f1_ai": f1_ai,
            "f1_macro": (f1_ai + f1_human) / 2 if f1_ai is not None and f1_human is not None else None,
            "auroc": auc, "brier": statistics.fmean((p-y)**2 for p, y in zip(probs, labels)),
            "ece": ece, "reliability_bins": reliability,
            "negative_log_likelihood": -statistics.fmean(math.log(max(1e-15, p if y else 1-p))
                                                         for p, y in zip(probs, labels)),
            "brier_definition": "binary_positive_class_probability_MSE_range_0_1",
            "small_group": n < 30,
            "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn}}


def text_groups(text):
    cjk = sum("\u3400" <= c <= "\u9fff" for c in text)
    letters = sum(c.isalpha() for c in text)
    groups = ["contains_cjk" if cjk else "no_cjk", "short_le280_codepoints" if len(text) <= 280 else "long_gt280_codepoints"]
    if letters and cjk / letters >= 0.5:
        groups.append("predominantly_cjk_letters")
    if cjk and len(text) > CONFIG["short_text_max_codepoints"]:
        groups.append("inference_supported_long_cjk")
    return groups


def subgroup_metrics(rows, probs):
    result = {"all": binary_metrics([r["label"] for r in rows], probs)}
    for group in ("contains_cjk", "no_cjk", "predominantly_cjk_letters",
                  "short_le280_codepoints", "long_gt280_codepoints", "inference_supported_long_cjk"):
        indexes = [i for i, r in enumerate(rows) if group in text_groups(r["text"])]
        result[group] = binary_metrics([rows[i]["label"] for i in indexes], [probs[i] for i in indexes])
    return result


def sparse_tensor(torch, rows):
    row_indexes, columns, values = [], [], []
    for i, row in enumerate(rows):
        for column, value in feature_items(row["text"]):
            row_indexes.append(i); columns.append(column); values.append(value)
    return torch.sparse_coo_tensor(torch.tensor([row_indexes, columns], dtype=torch.int64),
                                   torch.tensor(values, dtype=torch.float32),
                                   (len(rows), FEATURE_BUCKETS), check_invariants=True).coalesce()


def length_stats(rows):
    values = [math.log1p(len(row["text"])) for row in rows]
    if not values:
        raise ValueError("length normalization needs training answers")
    mean = statistics.fmean(values)
    scale = math.sqrt(statistics.fmean((value-mean)**2 for value in values)) or 1.0
    return mean, scale


def length_items(rows, mean, scale):
    if not math.isfinite(mean) or not math.isfinite(scale) or scale <= 0:
        raise ValueError("invalid train-fitted length normalization")
    return [[(math.log1p(len(row["text"]))-mean)/scale] for row in rows]


def fit_model(torch, features, labels, val_features, val_labels, sparse):
    width = features.shape[1]
    weight = torch.nn.Parameter(torch.zeros((width, 1), dtype=torch.float32))
    bias = torch.nn.Parameter(torch.zeros(1, dtype=torch.float32))
    optimizer = torch.optim.Adam([weight, bias], lr=CONFIG["learning_rate"])
    best_key, best_state, history = None, None, []
    multiply = torch.sparse.mm if sparse else torch.mm
    for epoch in range(1, CONFIG["max_epochs"] + 1):
        optimizer.zero_grad()
        logits = (multiply(features, weight) + bias).squeeze(1)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels)
        if not bool(torch.isfinite(loss)):
            raise ValueError("training loss is nonfinite; do not freeze or evaluate test")
        loss.backward(); optimizer.step()
        with torch.no_grad():
            validation = (multiply(val_features, weight) + bias).squeeze(1).tolist()
        candidates = [(selection_key(validation, val_labels, epoch, temp), temp)
                      for temp in CONFIG["temperature_candidates"]]
        key, temperature = min(candidates)
        history.append({"epoch": epoch, "train_nll": float(loss.detach()),
                        "validation_nll": key[0], "temperature": temperature})
        if best_key is None or key < best_key:
            best_key = key
            best_state = {"weights": weight.detach().squeeze(1).tolist(), "bias": float(bias.detach()[0]),
                          "selected_epoch": epoch, "temperature": temperature,
                          "validation_nll": key[0]}
    return best_state, history


def train(plan_path):
    frozen, rows = verify_plan(plan_path)
    output = Path(frozen["output_path"])
    # Exclusive consumption precedes importing Torch or fitting; no resume/retry.
    write_new(output / "training-started.json", {"started_at": clock(), "plan_sha256": file_sha(plan_path)})
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.manual_seed(CONFIG["seed"])
    torch.use_deterministic_algorithms(True)
    partitions = {name: [r for r in rows if r["split"] == name] for name in ("train", "validation", "test")}
    fit, validation = partitions["train"], partitions["validation"]
    fit_y = torch.tensor([r["label"] for r in fit], dtype=torch.float32)
    val_y = [r["label"] for r in validation]
    model, model_history = fit_model(torch, sparse_tensor(torch, fit), fit_y,
                                     sparse_tensor(torch, validation), val_y, True)
    mean, scale = length_stats(fit)
    length_features = lambda part: torch.tensor(length_items(part, mean, scale), dtype=torch.float32)
    baseline, baseline_history = fit_model(torch, length_features(fit), fit_y,
                                           length_features(validation), val_y, False)
    baseline["train_length_mean"], baseline["train_length_scale"] = mean, scale
    state = {"schema": "rise-hc3-binary-model-v1", "created_at": clock(), "config": CONFIG,
             "source": frozen["source"], "plan_sha256": file_sha(plan_path),
             "code_sha256": frozen["code_sha256"], "model": model, "length_baseline": baseline,
             "feature_signature_sha256": feature_signature(),
             "python_version": sys.version, "torch_version": torch.__version__,
             "mixed_trained": False, "in_domain": "hc3_chinese_open_qa"}
    write_new(output / "model-state.json", state)
    write_new(output / "validation-selection.json", {"model": model_history, "length_baseline": baseline_history})
    write_new(output / "models-frozen-before-test.json", {"frozen_at": clock(),
              "model_sha256": file_sha(output / "model-state.json"), "plan_sha256": file_sha(plan_path),
              "test_performance_evaluated": False})
    write_new(output / "test-evaluation-started.json", {"started_at": clock(),
              "model_sha256": file_sha(output / "model-state.json"), "test_evaluations": 1})
    test = partitions["test"]
    # Test text features are first encoded only after validation selection and freeze.
    with torch.no_grad():
        logits = torch.sparse.mm(sparse_tensor(torch, test), torch.tensor(model["weights"]).reshape(-1, 1)).squeeze(1)
        logits = (logits + model["bias"]).tolist()
        length_logits = (length_features(test).squeeze(1) * baseline["weights"][0] + baseline["bias"]).tolist()
    report = {"schema": "rise-hc3-binary-evaluation-v1", "completed_at": clock(),
              "task": CONFIG["task"], "source": frozen["source"], "coverage": frozen["coverage"],
              "test_evaluations": 1, "model_sha256": file_sha(output / "model-state.json"),
              "model": subgroup_metrics(test, probabilities(logits, model["temperature"])),
              "length_baseline": subgroup_metrics(test, probabilities(length_logits, baseline["temperature"])),
              "uncalibrated_model": subgroup_metrics(test, probabilities(logits, 1.0)),
              "uncalibrated_length_baseline": subgroup_metrics(test, probabilities(length_logits, 1.0)),
              "selected": {"model": {k: model[k] for k in ("selected_epoch", "temperature", "validation_nll")},
                           "length_baseline": {k: baseline[k] for k in ("selected_epoch", "temperature", "validation_nll")}},
              "metric_definitions": {"f1_ai": "positive=early_ChatGPT_answer", "ece": CONFIG["ece"],
                                     "language": "CJK codepoint heuristics, not verified language labels",
                                     "short": "normalized codepoint length<=280, not X weighted-character validation"},
              "decision_coverage": {"benchmark_forced_binary_test": 1.0,
                   "hc3_inference_policy_if_domain_declared": sum("inference_supported_long_cjk" in text_groups(r["text"]) for r in test)/len(test),
                   "x_short_posts": 0.0, "three_class_origin": 0.0},
              "mixed_trained": False, "time_holdout": False, "source_creation_time": "unknown",
              "limitations": CONFIG["limitations"], "raw_text_included": False}
    write_new(output / "evaluation.json", report)
    write_new(output / "model-card.json", {
        "schema": "rise-hc3-binary-model-card-v1", "task": CONFIG["task"],
        "source": frozen["source"], "data_license": "CC-BY-SA-4.0; stricter upstream terms apply",
        "data_redistribution": "No source answers, row-level manifests, or raw dataset mirrored",
        "model_parameter_count": CONFIG["parameter_count"], "input": "normalized answer text only",
        "evaluation": report, "mixed_trained": False,
        "x_short_post_inference": "unknown/null: out of domain",
        "three_class_origin_probabilities": "null: independent binary model only",
        "limitations": CONFIG["limitations"], "code_sha256": frozen["code_sha256"],
        "model_sha256": file_sha(output / "model-state.json"),
    })
    write_new(output / "training-completed.json", {"completed_at": clock(), "test_evaluations": 1,
              "model_sha256": file_sha(output / "model-state.json"), "report_sha256": file_sha(output / "evaluation.json")})
    return {"output": str(output), "model": report["model"]["all"],
            "length_baseline": report["length_baseline"]["all"], "test_evaluations": 1,
            "mixed_trained": False, "x_short_post_decision": "unknown"}


def infer(state, answer, domain="x_short_post", requested_task="binary"):
    refusal = {"decision": "unknown", "binary_probabilities": None,
               "origin_probabilities": {"human_written": None, "ai_generated": None, "mixed": None},
               "mixed_trained": False, "domain": domain}
    if state.get("schema") != "rise-hc3-binary-model-v1" or state.get("config") != CONFIG:
        raise ValueError("unsupported model/config")
    if state.get("feature_signature_sha256") != feature_signature():
        raise ValueError("model featurizer/Unicode version changed")
    text = normalize(answer)
    if requested_task != "binary":
        return {**refusal, "reason": "mixed_and_three_class_origin_not_trained"}
    if domain != "hc3_chinese_open_qa":
        return {**refusal, "reason": "out_of_domain_X_or_unvalidated_content"}
    if len(text) <= CONFIG["short_text_max_codepoints"]:
        return {**refusal, "reason": "short_text_not_validated_for_deployment"}
    if "contains_cjk" not in text_groups(text):
        return {**refusal, "reason": "non_Chinese_content_not_validated_for_deployment"}
    model = state["model"]
    weights = model["weights"]
    def valid_number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    if (not isinstance(weights, (list, tuple)) or len(weights) != FEATURE_BUCKETS
            or any(not valid_number(w) for w in weights)):
        raise ValueError("invalid linear model weights")
    if (not valid_number(model["bias"]) or not valid_number(model["temperature"])
            or model["temperature"] <= 0):
        raise ValueError("invalid model bias/temperature")
    logit = model["bias"] + sum(weights[i] * value for i, value in feature_items(text))
    if not math.isfinite(logit):
        raise ValueError("invalid nonfinite prediction logit")
    probability = probabilities([logit], model["temperature"])[0]
    return {**refusal, "decision": "ai_generated" if probability >= 0.5 else "human_written",
            "reason": "conditional_binary_HC3_domain_estimate_only",
            "binary_probabilities": {"human_written": 1-probability, "ai_generated": probability}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    get = sub.add_parser("acquire"); get.add_argument("--output", required=True)
    prepare = sub.add_parser("plan")
    prepare.add_argument("--input", required=True); prepare.add_argument("--provenance", required=True)
    prepare.add_argument("--output", required=True)
    fit = sub.add_parser("train"); fit.add_argument("--plan", required=True)
    predict = sub.add_parser("infer"); predict.add_argument("--model", required=True)
    predict.add_argument("--input", required=True, help="private UTF-8 answer file")
    predict.add_argument("--domain", default="x_short_post")
    predict.add_argument("--task", choices=("binary", "three_class"), default="binary")
    args = parser.parse_args(argv)
    if args.command == "acquire": result = acquire(args.output)
    elif args.command == "plan": result = plan(args.input, args.provenance, args.output)
    elif args.command == "train": result = train(args.plan)
    else:
        result = infer(json.loads(Path(args.model).read_text()), Path(args.input).read_text(), args.domain, args.task)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
