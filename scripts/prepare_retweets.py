#!/usr/bin/env python3
"""Prepare local-only SEISMIC retweet data; never trains or publishes data.

Usage: python scripts/prepare_retweets.py --output /your/new/local/directory
Reuse verified downloads without network: add --existing-source-dir /your/cache
Outputs must be absent or empty. Partial failures are retained for diagnosis;
there is no automatic network resume or overwrite. Reuse requires two complete
pinned files and their original HTTP provenance, then a new output directory.
The dataset license is unresolved: do not publish/mirror raw or feature CSVs.
These 2011 retweet labels are not views, verified Home or current X forecasts.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

SOURCE = "https://snap.stanford.edu/seismic/"
PINNED = {
    "index.csv": (8323152, "edf23b4310e8c3c8454e7dcf6e9b72c1d795fdcb930f290f4703574a55c6ffdd"),
    "data.csv": (299132268, "916fb069b2227167e6031c95340d975d90c04ff751d0f07898e1cf64ed48bb08"),
}
INDEX_FIELDS = ["tweet_id", "post_time_day", "start_ind", "end_ind"]
EVENT_FIELDS = ["relative_time_second", "number_of_followers"]
FIELDS = ["cascade_id", "post_time_day", "cutoff_seconds", "paper_day_split",
          "strict_label_available_split", "observed_retweet_count",
          "first_observed_retweet_seconds", "last_observed_retweet_seconds",
          "future_retweets_to_24h", "total_retweets_at_24h", "label_available_day"]
IDENTITY_POLICY = ("Only raw ASCII decimal IDs matching [1-9][0-9]*; no strip, float or "
                   "scientific-notation restoration. Quarantine every noncanonical ID "
                   "segment and every segment belonging to a repeated raw ID.")


def clock():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def write_json(path, value):
    with Path(path).open("x") as output:
        json.dump(value, output, indent=2, allow_nan=False)
        output.write("\n")


def finite_nonnegative(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("Expected finite nonnegative time")
    return number


def split(day):
    if not 0 <= day < 15:
        raise ValueError("Source posting day outside reviewed first15-day coverage")
    paper = "train_candidate" if day < 7 else "evaluation_candidate"
    strict = ("train_candidate" if day + 1 <= 7 else
              "purged_label_overlap" if day < 7 else "evaluation_candidate")
    return paper, strict


def inspect_index(path):
    identities = Counter()
    days = Counter()
    next_row = 1
    low, high = math.inf, -math.inf
    with Path(path).open() as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != INDEX_FIELDS:
            raise ValueError("Unexpected source index schema")
        for row in reader:
            day = finite_nonnegative(row["post_time_day"])
            split(day)
            start, end = int(row["start_ind"]), int(row["end_ind"])
            if start != next_row or end < start:
                raise ValueError("Noncontiguous or invalid event ranges")
            next_row = end + 1
            identities[row["tweet_id"]] += 1
            days[int(day)] += 1
            low, high = min(low, day), max(high, day)
    if not identities:
        raise ValueError("Empty source index")
    excluded = {identity for identity, count in identities.items()
                if count != 1 or not re.fullmatch(r"[1-9][0-9]*", identity)}
    canonical = {identity: count for identity, count in identities.items()
                 if re.fullmatch(r"[1-9][0-9]*", identity)}
    coverage = dict(index_rows=sum(identities.values()), unique_raw_id_strings=len(identities),
                    canonical_unique_id_strings=len(canonical), canonical_segments=sum(canonical.values()),
                    noncanonical_segments=sum(n for identity, n in identities.items() if identity not in canonical),
                    repeated_id_count=sum(n > 1 for n in identities.values()),
                    quarantined_segments=sum(identities[x] for x in excluded),
                    usable_unique_cascades=sum(x not in excluded for x in identities),
                    min_post_time_day=low, max_post_time_day=high,
                    cascades_by_day=dict(sorted(days.items())), indexed_event_rows=next_row - 1)
    return identities, excluded, coverage


def prepare_table(index_path, data_path, output, http):
    output = Path(output)
    identities, excluded, coverage = inspect_index(index_path)
    stats, groups, quarantine = Counter(), {}, []
    line, minimum, maximum = 0, math.inf, 0.0
    feature_path = output / "retweet-features.csv"
    with Path(data_path).open() as data, Path(index_path).open() as index, feature_path.open("x", newline="") as target:
        events = csv.DictReader(data)
        if events.fieldnames != EVENT_FIELDS:
            raise ValueError("Unexpected event schema")
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        for sequence, item in enumerate(csv.DictReader(index), 1):
            identity, day = item["tweet_id"], float(item["post_time_day"])
            end = int(item["end_ind"])
            origin = next(events)
            line += 1
            if line != int(item["start_ind"]) or finite_nonnegative(origin["relative_time_second"]) != 0:
                raise ValueError("Missing first original event at t0")
            counts, first, last = {900: 0, 3600: 0, 86400: 0}, {900: None, 3600: None}, {900: None, 3600: None}
            previous, total = 0.0, 0
            while line < end:
                event = next(events)
                line += 1
                raw_time = event["relative_time_second"]
                t = finite_nonnegative(raw_time)
                stats["scientific_notation_event_times"] += "e" in raw_time.lower()
                stats["fractional_second_events"] += not t.is_integer()
                stats["unsorted_event_transitions"] += t < previous
                stats["events_beyond_14d"] += t > 1209600
                maximum, previous, total = max(maximum, t), t, total + 1
                for cutoff in counts:
                    if t <= cutoff:
                        counts[cutoff] += 1
                        if cutoff in first:
                            first[cutoff] = t if first[cutoff] is None else min(first[cutoff], t)
                            last[cutoff] = t if last[cutoff] is None else max(last[cutoff], t)
            minimum = min(minimum, total)
            stats["segments_below_documented_50_retweets"] += total < 50
            if identity in excluded:
                quarantine.append(dict(segment_index=sequence, raw_id_hash_prefix=hashlib.sha256(identity.encode()).hexdigest()[:12],
                                       post_time_day=day, start_ind=int(item["start_ind"]), end_ind=end,
                                       noncanonical_id=re.fullmatch(r"[1-9][0-9]*", identity) is None,
                                       repeated_raw_id=identities[identity] > 1))
                stats["quarantined_segments"] += 1
                continue
            paper, strict = split(day)
            for cutoff in (900, 3600):
                future = counts[86400] - counts[cutoff]
                writer.writerow(dict(cascade_id=f"cascade-{sequence:06d}", post_time_day=day, cutoff_seconds=cutoff,
                                     paper_day_split=paper, strict_label_available_split=strict,
                                     observed_retweet_count=counts[cutoff], first_observed_retweet_seconds=first[cutoff],
                                     last_observed_retweet_seconds=last[cutoff], future_retweets_to_24h=future,
                                     total_retweets_at_24h=counts[86400], label_available_day=day + 1))
                group = groups.setdefault(f"{cutoff}:{strict}", dict(rows=0, cold_at_cutoff=0, observed_total=0, future_total=0, future_positive=0))
                group["rows"] += 1
                group["cold_at_cutoff"] += counts[cutoff] == 0
                group["observed_total"] += counts[cutoff]
                group["future_total"] += future
                group["future_positive"] += future > 0
                stats["feature_rows"] += 1
            stats["cascades"] += 1
        if next(events, None) is not None or line != coverage["indexed_event_rows"]:
            raise ValueError("Event/index row mismatch")
    if stats["cascades"] != coverage["usable_unique_cascades"]:
        raise ValueError("Identity coverage mismatch")
    write_json(output / "http-provenance.json", http)
    write_json(output / "quarantined-id-segments.json", quarantine)
    write_json(output / "index-coverage.json", coverage)
    feature_sha = sha(feature_path)
    verification = verify_table(index_path, data_path, feature_path, identities, excluded)
    verification.update(features_sha256=feature_sha, verification_process_exit_code=0,
                        verification_kind="in-process independent table/source crosscheck", training_performed=False)
    write_json(output / "verification-result.json", verification)
    summary = dict(prepared_at=clock(), counts=dict(stats), groups=groups, coverage=coverage,
                   minimum_retweet_events_per_segment=minimum, maximum_event_second=maximum,
                   identity_policy=IDENTITY_POLICY, features_sha256=feature_sha,
                   quarantine_sha256=sha(output / "quarantined-id-segments.json"),
                   http_provenance_sha256=sha(output / "http-provenance.json"),
                   source_urls=[SOURCE, SOURCE + "seismic.pdf"], training_performed=False,
                   source_anomaly_counts_scope="Full source segments; feature/group counts cover canonical nonrepeated final table only",
                   limitation="2011 English/no-hashtag, future-popularity-selected corpus; literal >=50 retweets and paper14d completeness not assumed. No views, verified Home, text, author IDs or source labels. Dataset license unresolved; all CSVs local-only.",
                   target="additional_retweets_in_(cutoff,86400]_seconds")
    write_json(output / "prepared-summary.json", summary)
    return summary


def verify_table(index_path, data_path, feature_path, identities, excluded):
    # A fresh CSV pass verifies all pairs; an independent direct inequality
    # recomputes labels for up to1000 source cascades (not 24h-minus-observed).
    allowed = set()
    with Path(index_path).open() as source:
        for sequence, item in enumerate(csv.DictReader(source), 1):
            if item["tweet_id"] not in excluded:
                allowed.add(sequence)
    probes, count = {}, 0
    with feature_path.open() as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != FIELDS:
            raise ValueError("Feature schema mismatch")
        for early in reader:
            late = next(reader)
            sequence = int(early["cascade_id"].split("-")[1])
            if sequence not in allowed or early["cascade_id"] != late["cascade_id"]:
                raise ValueError("Unexpected/duplicate identity")
            allowed.remove(sequence)
            if [early["cutoff_seconds"], late["cutoff_seconds"]] != ["900", "3600"]:
                raise ValueError("Cutoff pairing mismatch")
            for row in (early, late):
                day, cutoff = float(row["post_time_day"]), int(row["cutoff_seconds"])
                if (row["paper_day_split"], row["strict_label_available_split"]) != split(day):
                    raise ValueError("Split mismatch")
                observed, future, total = (int(row[x]) for x in ("observed_retweet_count", "future_retweets_to_24h", "total_retweets_at_24h"))
                if min(observed, future) < 0 or observed + future != total or float(row["label_available_day"]) != day + 1:
                    raise ValueError("Invalid labels")
                if observed == 0:
                    if row["first_observed_retweet_seconds"] or row["last_observed_retweet_seconds"]:
                        raise ValueError("Cold times must remain missing")
                elif not 0 <= float(row["first_observed_retweet_seconds"]) <= float(row["last_observed_retweet_seconds"]) <= cutoff:
                    raise ValueError("Observed times exceed cutoff")
            if len(probes) < 1000:
                probes[sequence] = [int(early["future_retweets_to_24h"]), int(late["future_retweets_to_24h"])]
            count += 1
    if allowed:
        raise ValueError("Missing canonical source cascades")
    checked, line = 0, 0
    with Path(data_path).open() as data, Path(index_path).open() as index:
        events = csv.DictReader(data)
        for sequence, item in enumerate(csv.DictReader(index), 1):
            next(events)  # Exclude exactly the original, including when RTs also t0.
            line += 1
            expected = [0, 0]
            while line < int(item["end_ind"]):
                t = finite_nonnegative(next(events)["relative_time_second"])
                line += 1
                expected[0] += 900 < t <= 86400
                expected[1] += 3600 < t <= 86400
            if sequence in probes:
                if probes[sequence] != expected:
                    raise ValueError("Source label crosscheck failed")
                checked += 1
            if checked == len(probes):
                break
    return dict(feature_rows_verified=count * 2, canonical_unique_source_cascades=count,
                source_cascades_crosschecked=checked, paired_cutoffs_same_split=True)


def acquire(output, existing=None):
    if existing:
        existing = Path(existing)
        manifest = existing / "http-provenance.json"
        http = (json.loads(manifest.read_text()) if manifest.exists() else
                [json.loads((existing / (name + ".http.json")).read_text()) for name in PINNED])
        for name, (size, digest) in PINNED.items():
            path = existing / name
            record = next((r for r in http if r.get("url") == SOURCE + name), None)
            if (not record or record.get("sha256") != digest or record.get("actual_bytes") != size
                    or not record.get("started_at") or not record.get("completed_at")
                    or record.get("http_status") != 200 or path.stat().st_size != size or sha(path) != digest):
                raise ValueError("Existing source missing pinned bytes/hash/original HTTP evidence")
        # Benchmark requires a local index; large event file stays in its cache.
        with (existing / "index.csv").open("rb") as source, (output / "index.csv").open("xb") as target:
            shutil.copyfileobj(source, target, 1024 * 1024)
        write_json(output / "source-reuse.json", dict(verified_at=clock(), network_download_performed=False,
                                                     http_times="Preserved actual original retrieval times, not this reuse time"))
        return output / "index.csv", existing / "data.csv", http
    http = []
    for name, (size, digest) in PINNED.items():
        started, received, hasher = clock(), 0, hashlib.sha256()
        partial = output / (name + ".partial")
        with urlopen(SOURCE + name, timeout=90) as response, partial.open("xb") as target:
            if response.status != 200:
                raise ValueError("Expected complete HTTP200 download")
            while chunk := response.read(1024 * 1024):
                received += len(chunk)
                if received > size:
                    raise ValueError("Source exceeded reviewed size")
                hasher.update(chunk)
                target.write(chunk)
            if received != size or hasher.hexdigest() != digest:
                raise ValueError("Official source changed or download incomplete; review before using")
            http.append(dict(url=SOURCE + name, final_url=response.url, started_at=started, completed_at=clock(),
                             http_status=response.status, actual_bytes=received, sha256=hasher.hexdigest(),
                             content_length=response.headers.get("Content-Length"), last_modified=response.headers.get("Last-Modified")))
        partial.rename(output / name)
        # A separate checkpoint preserves retrieval evidence if the next download fails.
        write_json(output / (name + ".http.json"), http[-1])
    return output / "index.csv", output / "data.csv", http


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--existing-source-dir", type=Path)
    args = parser.parse_args()
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
        parser.error("Output must be absent or empty; no overwrite or automatic resume")
    args.output.mkdir(parents=True, exist_ok=True)
    index, data, http = acquire(args.output, args.existing_source_dir)
    summary = prepare_table(index, data, args.output, http)
    print(json.dumps(dict(counts=summary["counts"], features_sha256=summary["features_sha256"], training_performed=False)))


if __name__ == "__main__":
    main()
