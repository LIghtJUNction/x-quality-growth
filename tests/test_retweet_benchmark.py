import copy
import csv
import importlib.util
import json
import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from scripts import retweet_benchmark as benchmark


def item(cascade=1, day=0.5, cutoff=900, observed=2, first=0, last=10, total=7):
    return dict(cascade_id=f"cascade-{cascade:06d}", post_time_day=str(day),
                cutoff_seconds=str(cutoff), paper_day_split="train_candidate" if day < 7 else "evaluation_candidate",
                strict_label_available_split=benchmark.split_for_day(day), observed_retweet_count=str(observed),
                first_observed_retweet_seconds="" if first is None else str(first),
                last_observed_retweet_seconds="" if last is None else str(last),
                future_retweets_to_24h=str(total - observed), total_retweets_at_24h=str(total),
                label_available_day=str(day + 1))


def paired_fixture():
    records = []
    allowed = {}
    for cascade, day in enumerate([0.5, 3, 3.5, 4, 6.5, 7], 1):
        allowed[f"cascade-{cascade:06d}"] = day
        records += [item(cascade, day, 900), item(cascade, day, 3600)]
    return records, allowed


class RetweetBenchmarkTests(unittest.TestCase):
    def write_csv(self, folder, records, fields=None):
        path = Path(folder) / "fixture.csv"
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields or benchmark.CSV_FIELDS)
            writer.writeheader()
            writer.writerows(records)
        return path

    def test_temporal_label_maturity_boundaries(self):
        self.assertEqual(benchmark.split_for_day(6), "train_candidate")
        self.assertEqual(benchmark.split_for_day(6.0001), "purged_label_overlap")
        self.assertEqual(benchmark.split_for_day(7), "evaluation_candidate")
        self.assertEqual(benchmark.inner_split(3), "fit")
        self.assertEqual(benchmark.inner_split(3.0001), "purged")
        self.assertEqual(benchmark.inner_split(4), "validation")
        self.assertEqual(benchmark.inner_split(6), "purged")
        for day in [-1, 15, math.inf, math.nan]:
            with self.subTest(day=day), self.assertRaises(ValueError):
                benchmark.parse_row(item(day=day))

    def test_complete_group_counts_are_cascades_not_pooled_independent_rows(self):
        records, allowed = paired_fixture()
        with tempfile.TemporaryDirectory() as folder:
            rows, audit = benchmark.load_table(self.write_csv(folder, records), allowed)
        self.assertEqual(audit["cascades"], 6)
        self.assertEqual(audit["paired_cutoff_rows"], 12)
        self.assertEqual(audit["outer_cascades"], {"train_candidate": 4, "purged_label_overlap": 1, "evaluation_candidate": 1})
        self.assertEqual(audit["inner_cascades_within_outer_train"], {"fit": 2, "purged": 1, "validation": 1})
        self.assertIsNone(audit["independent_author_or_content_count"])
        self.assertEqual([row.cascade_id for row in rows[900]], [row.cascade_id for row in rows[3600]])

    def test_missing_duplicate_foreign_and_inconsistent_pairs_fail(self):
        originals, allowed = paired_fixture()
        cases = []
        cases.append(originals[:-1])
        cases.append(originals + [copy.deepcopy(originals[0])])
        changed = copy.deepcopy(originals)
        changed[0]["cascade_id"] = "cascade-999999"
        cases.append(changed)
        for early_count, late_first, late_last in [(0, 0, 1000), (2, 0, 800)]:
            changed = copy.deepcopy(originals)
            changed[0] = item(1, 0.5, 900, early_count, None if early_count == 0 else 0,
                              None if early_count == 0 else 10)
            changed[1] = item(1, 0.5, 3600, 3, late_first, late_last)
            cases.append(changed)
        for field, value in [("total_retweets_at_24h", "8"), ("post_time_day", "0.6"),
                             ("observed_retweet_count", "1"), ("last_observed_retweet_seconds", "11")]:
            changed = copy.deepcopy(originals)
            changed[1][field] = value
            if field == "total_retweets_at_24h":
                changed[1]["future_retweets_to_24h"] = "6"
            if field == "post_time_day":
                changed[1]["label_available_day"] = "1.6"
            if field == "observed_retweet_count":
                changed[1]["future_retweets_to_24h"] = "6"
                changed[1]["last_observed_retweet_seconds"] = "0"
            cases.append(changed)
        for records in cases:
            with self.subTest(records=records[:2]), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):
                    benchmark.load_table(self.write_csv(folder, records), allowed)

    def test_split_label_and_unknown_column_rejected(self):
        for field, value in [("strict_label_available_split", "unknown"), ("paper_day_split", "evaluation_candidate"),
                             ("label_available_day", "7"), ("future_retweets_to_24h", "4"), ("cutoff_seconds", "901")]:
            record = item()
            record[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                benchmark.parse_row(record)
        record = item()
        record["future_actor_followers"] = "123"
        with self.assertRaises(ValueError):
            benchmark.parse_row(record)

    def test_nonfinite_negative_fractional_and_bad_missing_values_rejected(self):
        for field in ["observed_retweet_count", "future_retweets_to_24h", "total_retweets_at_24h"]:
            for value in ["nan", "inf", "-1", "1.5", "True", "9007199254740993", "1.0000000000000001", "9007199254740990.1"]:
                record = item()
                record[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    benchmark.parse_row(record)
        for args in [(900, 0, 0, 0), (900, 1, None, None), (900, 1, 0, 1),
                     (900, 2, -1, 10), (900, 2, 20, 10), (900, 2, 0, 901), (900, 2, 0, math.inf)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                benchmark.validate_inference_input(*args)
        self.assertEqual(benchmark.vector_from_values(900, 0, None, None)[1:4], [0, 0, 1])
        self.assertEqual(benchmark.vector_from_values(900, 1, 0, 0)[1:4], [0, 0, 0])

    def test_features_invariant_to_id_day_split_and_labels(self):
        row = benchmark.parse_row(item())
        changed = replace(row, cascade_id="different", day=14, split="evaluation_candidate", target=999, total=1001)
        self.assertEqual(benchmark.row_vector(row), benchmark.row_vector(changed))
        self.assertEqual(len(benchmark.row_vector(row)), 5)
        self.assertFalse(any(word in " ".join(benchmark.FEATURE_NAMES) for word in ["target", "day", "id", "followers"]))

    def test_raw_source_canonical_ids_and_all_duplicate_segments_quarantined(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "index.csv"
            with path.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["tweet_id", "post_time_day", "start_ind", "end_ind"])
                for i, raw in enumerate(["1", "2", "2", "1e2", "01", "３", "7"], 1):
                    writer.writerow([raw, 0.5, i, i])
            allowed, audit = benchmark.source_index_identity(path)
        self.assertEqual(set(allowed), {"cascade-000001", "cascade-000007"})
        self.assertEqual(audit["noncanonical_segments"], 3)
        self.assertEqual(audit["repeated_canonical_segments"], 2)

    def test_metrics_have_separate_raw_log_and_zero_denominator_semantics(self):
        result = benchmark.count_metrics([0, 3], [2, 1])
        self.assertEqual(result["mae"], 2)
        self.assertEqual(result["median_absolute_error"], 2)
        self.assertEqual(result["p90_absolute_error"], 2)
        self.assertAlmostEqual(result["wape"], 4 / 3)
        self.assertAlmostEqual(result["log1p_mae"], (math.log(3) + math.log(2)) / 2)
        self.assertIsNone(benchmark.count_metrics([0], [1])["wape"])
        self.assertIsNone(benchmark.count_metrics([], [])["mae"])
        for actual, predicted in [([0], []), ([math.nan], [0]), ([0], [-1])]:
            with self.assertRaises(ValueError):
                benchmark.count_metrics(actual, predicted)

    def test_baseline_fits_train_only_and_unseen_bins_use_train_median(self):
        rows = [benchmark.parse_row(item(observed=count, first=None if count == 0 else 0,
                                          last=None if count == 0 else 0, total=count + target))
                for count, target in [(0, 5), (1, 10), (2, 20)]]
        fitted = benchmark.fit_baselines(rows)
        self.assertEqual(fitted["constant_median"], 10)
        test = benchmark.parse_row(item(day=7, observed=1024, total=1029))
        guesses = benchmark.baseline_predictions([test], fitted)
        self.assertEqual(guesses["train_log_count_bucket_median"], [10])
        self.assertEqual(guesses["zero_additional_keep_last_count"], [0])
        with self.assertRaises(ValueError):
            benchmark.fit_baselines([test])

    def test_network_rejects_outer_test_or_wrong_inner_rows_before_torch_calls(self):
        test = benchmark.parse_row(item(day=7))
        inner_fit = benchmark.parse_row(item(day=0.5))
        validation = benchmark.parse_row(item(day=4))
        for fit_rows, validation_rows in [([test], None), ([validation], [validation]), ([inner_fit], [test])]:
            with self.subTest(fit_rows=fit_rows), self.assertRaises(ValueError):
                benchmark.fit_network(None, fit_rows, 900, 1, validation_rows)

    def test_exclusive_output_and_final_test_transaction_runs_once(self):
        records, _ = paired_fixture()
        rows = {cutoff: [benchmark.parse_row(record) for record in records if int(record["cutoff_seconds"]) == cutoff]
                for cutoff in (900, 3600)}
        baselines = {cutoff: benchmark.fit_baselines([row for row in group if row.split == "train_candidate"])
                     for cutoff, group in rows.items()}
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            benchmark.write_new(output / "exclusive.json", {"first": True})
            with self.assertRaises(FileExistsError):
                benchmark.write_new(output / "exclusive.json", {"first": False})
            with mock.patch.object(benchmark, "tensor_features", return_value=None), \
                    mock.patch.object(benchmark, "torch_predictions", return_value=[1.0]) as prediction:
                with self.assertRaises(ValueError):
                    benchmark.evaluate_test_once(None, rows, {900: (None, None), 3600: (None, None)}, baselines, output)
                self.assertEqual(prediction.call_count, 0)
                frozen = {"test_predictions_computed": False}
                for key, filename in [("state_sha256", "model-state.json"), ("baselines_sha256", "train-only-baselines.json"),
                                      ("training_log_sha256", "training-log.json"), ("inference_sha256", "inference.py")]:
                    (output / filename).write_text("fixture")
                    frozen[key] = benchmark.file_sha(output / filename)
                benchmark.write_new(output / "models-frozen-before-test.json", frozen)
                (output / "model-state.json").write_text("changed")
                with self.assertRaises(ValueError):
                    benchmark.evaluate_test_once(None, rows, {900: (None, None), 3600: (None, None)}, baselines, output)
                self.assertEqual(prediction.call_count, 0)
                (output / "model-state.json").write_text("fixture")
                result = benchmark.evaluate_test_once(None, rows, {900: (None, None), 3600: (None, None)}, baselines, output)
                self.assertEqual(prediction.call_count, 2)
                with self.assertRaises(FileExistsError):
                    benchmark.evaluate_test_once(None, rows, {900: (None, None), 3600: (None, None)}, baselines, output)
                self.assertEqual(prediction.call_count, 2)
            self.assertEqual(result["test_evaluations"], 1)
            self.assertIsNone(result["pooled_cutoff_metric"])
            self.assertEqual(result["cutoffs"]["900"]["models"]["tiny_mlp_log1p"]["all"]["n_cascades"], 1)

    def test_plan_freezes_without_fitting_and_refuses_existing_run(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "run"
            with mock.patch.object(benchmark, "verify_input", return_value=({}, {"cascades": 2}, {"input_sha256": "f" * 64})), \
                    mock.patch.object(benchmark, "fit_network", side_effect=AssertionError("no fit in plan")):
                result = benchmark.make_plan("input", "provenance", destination, "f" * 64)
                self.assertFalse(result["training_performed"])
                self.assertEqual(result["config"], benchmark.CONFIG)
                with self.assertRaises(FileExistsError):
                    benchmark.make_plan("input", "provenance", destination, "f" * 64)

    @unittest.skipUnless(importlib.util.find_spec("torch"), "optional torch runtime unavailable")
    def test_exported_stdlib_matches_untrained_torch_forward_without_optimizer(self):
        import torch
        model = benchmark.build_model(torch, 1)
        normalizer = {"mean": [0] * 5, "scale": [1] * 5, "fit_cascades": 0}
        state = {"schema": "rise-retweet-state-v1", "feature_names": benchmark.FEATURE_NAMES,
                 "models": {"900": benchmark.export_model(model, normalizer, 900, 0)}}
        self.assertEqual(state["models"]["900"]["parameter_count"], 241)
        rows = [benchmark.parse_row(item(observed=0, first=None, last=None)), benchmark.parse_row(item())]
        agreement = benchmark.check_export_agreement(torch, model, normalizer, state, 900, rows)
        self.assertEqual(agreement["test_rows_used"], 0)
        namespace = {"__name__": "test_inference"}
        exec(benchmark.inference_source(), namespace)
        for args in [(900, 0, None, None), (900, 1, 900, 900), (900, 1000000, 0, 900)]:
            self.assertEqual(namespace["predict_stdlib"](state, *args), benchmark.predict_stdlib(state, *args))
        changed = copy.deepcopy(state)
        changed["feature_names"] = list(reversed(benchmark.FEATURE_NAMES))
        with self.assertRaises(ValueError):
            benchmark.predict_stdlib(changed, 900, 0)
        for invalid in [math.nan, math.inf, True]:
            changed = copy.deepcopy(state)
            changed["models"]["900"]["normalizer"]["mean"][0] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                benchmark.predict_stdlib(changed, 900, 0)


if __name__ == "__main__":
    unittest.main()
