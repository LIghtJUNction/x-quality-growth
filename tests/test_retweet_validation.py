"""Selection-only boundary checks; no test invokes a real optimizer."""
import copy
import csv
import importlib.util
import json
import math
import os
import sys
import tempfile
import types
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from scripts import retweet_validation as validation


old = validation.old


def record(cascade=1, day=0.5, cutoff=900, observed=2, first=0, last=10, total=7):
    return {
        "cascade_id": f"cascade-{cascade:06d}", "post_time_day": str(day),
        "cutoff_seconds": str(cutoff),
        "paper_day_split": "train_candidate" if day < 7 else "evaluation_candidate",
        "strict_label_available_split": old.split_for_day(day),
        "observed_retweet_count": str(observed),
        "first_observed_retweet_seconds": "" if first is None else str(first),
        "last_observed_retweet_seconds": "" if last is None else str(last),
        "future_retweets_to_24h": str(total - observed),
        "total_retweets_at_24h": str(total), "label_available_day": str(day + 1),
    }


def fixture_records():
    # Include both label-maturity boundaries, both inner purges and final test.
    days = [0.5, 3, 3.5, 4, 5.999, 6, 6.5, 7, 14.999]
    allowed, records = {}, []
    for cascade, day in enumerate(days, 1):
        allowed[f"cascade-{cascade:06d}"] = day
        records.extend(record(cascade, day, cutoff) for cutoff in (900, 3600))
    return records, allowed


def write_csv(folder, records):
    path = Path(folder) / "features.csv"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=old.CSV_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    return path


def write_preparation(folder, records, allowed):
    """Build tiny synthetic provenance; no source data is read or downloaded."""
    folder = Path(folder)
    input_path = write_csv(folder, records)
    index_path = folder / "index.csv"
    with index_path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["tweet_id", "post_time_day", "start_ind", "end_ind"])
        for position, (_, day) in enumerate(allowed.items(), 1):
            writer.writerow([position, day, position, position])
    quarantine_path = folder / "quarantined-id-segments.json"
    quarantine_path.write_text("[]")
    http_path = folder / "http-provenance.json"
    http_path.write_text(json.dumps([{
        "url": "https://snap.stanford.edu/seismic/index.csv",
        "sha256": old.file_sha(index_path),
    }]))
    digest = old.file_sha(input_path)
    (folder / "verification-result.json").write_text(json.dumps({
        "features_sha256": digest, "verification_process_exit_code": 0,
        "canonical_unique_source_cascades": len(allowed),
        "feature_rows_verified": 2 * len(allowed),
        "source_cascades_crosschecked": len(allowed),
    }))
    provenance_path = folder / "prepared-summary.json"
    provenance_path.write_text(json.dumps({
        "features_sha256": digest,
        "identity_policy": "Only raw ASCII decimal IDs; synthetic test fixture",
        "http_provenance_sha256": old.file_sha(http_path),
        "quarantine_sha256": old.file_sha(quarantine_path),
        "counts": {"cascades": len(allowed), "feature_rows": 2 * len(allowed)},
    }))
    return input_path, provenance_path, digest


def fake_runtime():
    """Import-compatible runtime with thread settings and no optimizer API."""
    runtime = types.ModuleType("torch")
    runtime.__version__ = "synthetic-no-optimizer"
    for name in ("set_num_threads", "set_num_interop_threads", "use_deterministic_algorithms"):
        setattr(runtime, name, mock.Mock())
    runtime.get_num_threads = mock.Mock(return_value=1)
    runtime.get_num_interop_threads = mock.Mock(return_value=1)
    return runtime


class RetweetValidationTests(unittest.TestCase):
    def test_only_outer_train_is_parsed_even_with_poisoned_final_labels(self):
        records, allowed = fixture_records()
        for item in records:
            if float(item["post_time_day"]) + 1 > 7:
                for field in old.CSV_FIELDS:
                    if field != "post_time_day":
                        item[field] = "FINAL-TEST-MUST-NOT-BE-PARSED"
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(old, "parse_row", wraps=old.parse_row) as parse:
            by_cutoff, audit = validation.load_train_table(write_csv(folder, records), allowed)
        self.assertEqual(parse.call_count, 12)
        self.assertTrue(all(float(call.args[0]["post_time_day"]) + 1 <= 7
                            for call in parse.call_args_list))
        self.assertEqual(audit["outer_train_cascades_loaded"], 6)
        self.assertEqual(audit["paired_rows_loaded"], 12)
        self.assertEqual(audit["inner_partition_cascades"], {"fit": 2, "purged": 2, "validation": 2})
        self.assertEqual(audit["non_train_rows_skipped_before_label_parsing"], 6)
        self.assertEqual(audit["final_test_label_rows_loaded"], 0)
        self.assertEqual(audit["test_evaluations"], 0)
        self.assertEqual([row.cascade_id for row in by_cutoff[900]],
                         [row.cascade_id for row in by_cutoff[3600]])
        self.assertIn(6, [row.day for row in by_cutoff[900]])

    def test_foreign_identity_source_day_missing_and_duplicate_rows_fail(self):
        originals, allowed = fixture_records()
        cases = {}
        changed = copy.deepcopy(originals)
        changed[0]["cascade_id"] = "cascade-999999"
        cases["foreign identity"] = changed
        changed = copy.deepcopy(originals)
        changed[0]["post_time_day"], changed[0]["label_available_day"] = "0.6", "1.6"
        cases["source day mismatch"] = changed
        cases["whole cascade missing"] = originals[2:]
        cases["paired cutoff missing"] = originals[1:]
        cases["duplicate cutoff"] = originals + [copy.deepcopy(originals[0])]
        for name, records in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):
                    validation.load_train_table(write_csv(folder, records), allowed)

    def test_forged_train_day_on_final_identity_fails_before_label_parsing(self):
        _, allowed = fixture_records()
        forged = record(cascade=8, day=0.5)
        forged["future_retweets_to_24h"] = "not-a-number"
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(old, "parse_row", side_effect=AssertionError("must reject identity first")) as parse:
            with self.assertRaises(ValueError):
                validation.load_train_table(write_csv(folder, [forged]), allowed)
            parse.assert_not_called()

    def test_paired_counts_and_event_history_must_agree(self):
        originals, allowed = fixture_records()
        pairs = [
            (record(), record(cutoff=3600, total=8)),
            (record(), record(cutoff=3600, observed=1, last=0)),
            (record(observed=0, first=None, last=None),
             record(cutoff=3600, observed=3, first=500, last=1000)),
            (record(), record(cutoff=3600, observed=3, last=800)),
            (record(), record(cutoff=3600, observed=3, first=1, last=1000)),
            (record(), record(cutoff=3600, last=11)),
        ]
        for early, late in pairs:
            changed = copy.deepcopy(originals)
            changed[:2] = [early, late]
            with self.subTest(early=early, late=late), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):
                    validation.load_train_table(write_csv(folder, changed), allowed)

    def test_missing_inner_partition_and_bad_schema_fail(self):
        for day in (0.5, 4):
            rows = [record(day=day, cutoff=cutoff) for cutoff in (900, 3600)]
            with self.subTest(day=day), tempfile.TemporaryDirectory() as folder:
                with self.assertRaisesRegex(ValueError, "empty inner-fit or validation"):
                    validation.load_train_table(write_csv(folder, rows), {"cascade-000001": day})
        records, allowed = fixture_records()
        for change in ("header", "width", "invalid posting day"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                path = write_csv(folder, records)
                content = path.read_text().splitlines()
                if change == "header":
                    content[0] = content[0].replace("cascade_id", "private_source_id")
                elif change == "width":
                    content[1] += ",unexpected"
                else:
                    cells = content[-1].split(",")
                    cells[1] = "nan"
                    content[-1] = ",".join(cells)
                path.write_text("\n".join(content) + "\n")
                with self.assertRaises(ValueError):
                    validation.load_train_table(path, allowed)

    def test_preparation_verification_does_not_use_old_full_table_paths(self):
        records, allowed = fixture_records()
        for item in records:
            if float(item["post_time_day"]) >= 7:
                item["future_retweets_to_24h"] = "not-a-number"
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(old, "verify_input", side_effect=AssertionError("old full verify forbidden")), \
                mock.patch.object(old, "load_table", side_effect=AssertionError("old full load forbidden")), \
                mock.patch.object(old, "evaluate_test_once", side_effect=AssertionError("final evaluation forbidden")):
            input_path, provenance_path, digest = write_preparation(folder, records, allowed)
            rows, audit, metadata = validation.verify_input(input_path, provenance_path, digest)
        self.assertEqual(len(rows[900]), 6)
        self.assertEqual(audit["source_identity"]["canonical_usable_cascades"], len(allowed))
        self.assertEqual(metadata["input_sha256"], digest)
        self.assertEqual(audit["final_test_label_rows_loaded"], 0)

    def test_stale_or_failed_preparation_is_rejected(self):
        records, allowed = fixture_records()
        for tamper in ("input", "http", "quarantine", "verification", "counts"):
            with self.subTest(tamper=tamper), tempfile.TemporaryDirectory() as folder:
                input_path, provenance_path, digest = write_preparation(folder, records, allowed)
                if tamper == "input":
                    input_path.write_text(input_path.read_text() + "\n")
                elif tamper == "http":
                    (Path(folder) / "http-provenance.json").write_text("[]")
                elif tamper == "quarantine":
                    (Path(folder) / "quarantined-id-segments.json").write_text("[{}]")
                elif tamper == "verification":
                    path = Path(folder) / "verification-result.json"
                    evidence = json.loads(path.read_text())
                    evidence["verification_process_exit_code"] = 1
                    path.write_text(json.dumps(evidence))
                else:
                    evidence = json.loads(provenance_path.read_text())
                    evidence["counts"]["cascades"] -= 1
                    provenance_path.write_text(json.dumps(evidence))
                with self.assertRaises(ValueError):
                    validation.verify_input(input_path, provenance_path, digest)

    def test_fit_candidate_rejects_wrong_partitions_before_model_or_optimizer(self):
        fit = old.parse_row(record())
        selection = old.parse_row(record(day=4))
        wrong_fit = [[], [selection], [replace(fit, day=3.5)],
                     [replace(fit, day=7, split="evaluation_candidate")], [replace(fit, cutoff=3600)]]
        wrong_validation = [[], [fit], [replace(selection, day=6)],
                            [replace(selection, day=7, split="evaluation_candidate")], [replace(selection, cutoff=3600)]]
        with mock.patch.object(validation, "build_model", side_effect=AssertionError("must reject before model")) as build:
            for fit_rows, validation_rows in [(rows, [selection]) for rows in wrong_fit] + \
                    [([fit], rows) for rows in wrong_validation]:
                with self.subTest(fit=fit_rows, validation=validation_rows), self.assertRaises(ValueError):
                    validation.fit_candidate(None, fit_rows, validation_rows, 900, validation.CANDIDATES[0])
            build.assert_not_called()

    def test_feature_vectors_ignore_identity_day_and_targets(self):
        row = old.parse_row(record())
        changed = replace(row, cascade_id="unseen-source", day=14, split="evaluation_candidate",
                          target=10**8, total=10**8 + row.observed)
        self.assertEqual(old.row_vector(row), old.row_vector(changed))
        self.assertEqual(len(old.row_vector(row)), 5)
        self.assertEqual(validation.CONFIG["input_feature_names"], old.FEATURE_NAMES)
        self.assertTrue(set(validation.CONFIG["input_feature_names"]).isdisjoint({
            "cascade_id", "post_time_day", "future_retweets_to_24h", "total_retweets_at_24h", "target", "day", "id",
        }))

    def test_normalizer_and_fit_labels_use_fit_only_without_creating_optimizer(self):
        fit = [old.parse_row(record(cascade=1)),
               old.parse_row(record(cascade=2, day=3, observed=3, total=9))]
        selection = [old.parse_row(record(cascade=3, day=4, observed=10**7, total=10**7 + 999))]
        model = mock.Mock()
        model.parameters.return_value = [types.SimpleNamespace(numel=lambda: 241)]
        tensor = mock.Mock()
        tensor.reshape.return_value = tensor
        runtime = types.SimpleNamespace(float32="fake-float32", tensor=mock.Mock(return_value=tensor),
                                        optim=types.SimpleNamespace(Adam=mock.Mock(side_effect=RuntimeError("stop-before-optimizer"))))
        with mock.patch.object(validation, "build_model", return_value=model), \
                mock.patch.object(old, "normalizer_from_rows", wraps=old.normalizer_from_rows) as normalize, \
                mock.patch.object(old, "tensor_features", return_value=object()) as features:
            with self.assertRaisesRegex(RuntimeError, "stop-before-optimizer"):
                validation.fit_candidate(runtime, fit, selection, 900, validation.CANDIDATES[0])
        normalize.assert_called_once_with(fit)
        expected = old.normalizer_from_rows(fit)
        self.assertNotEqual(expected["mean"], old.normalizer_from_rows(fit + selection)["mean"])
        self.assertEqual([call.args[1] for call in features.call_args_list], [fit, selection])
        self.assertEqual([call.args[2] for call in features.call_args_list], [expected, expected])
        self.assertEqual(runtime.tensor.call_args.args[0], [math.log1p(row.target) for row in fit])

    def test_execute_only_passes_fit_and_validation_and_fits_baselines_on_fit(self):
        records, _ = fixture_records()
        # Huge validation targets expose any accidental baseline-label leakage.
        for item in records:
            if old.inner_split(float(item["post_time_day"])) == "validation":
                item["future_retweets_to_24h"], item["total_retweets_at_24h"] = "999", "1001"
        rows = {cutoff: [old.parse_row(item) for item in records if int(item["cutoff_seconds"]) == cutoff]
                for cutoff in (900, 3600)}

        def no_training(runtime, fit, selection, cutoff, candidate):
            self.assertTrue(all(old.inner_split(row.day) == "fit" for row in fit))
            self.assertTrue(all(old.inner_split(row.day) == "validation" for row in selection))
            self.assertEqual(len(fit), 2)
            self.assertEqual(len(selection), 2)
            return {"selected_epoch": 1}, {"median": [5.0] * len(selection), "lower": None, "upper": None}, {}

        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(validation, "fit_candidate", side_effect=no_training) as fit_model, \
                mock.patch.object(old, "fit_baselines", wraps=old.fit_baselines) as baseline, \
                mock.patch.object(old, "evaluate_test_once", side_effect=AssertionError("final evaluation forbidden")), \
                mock.patch.object(old, "verify_input", side_effect=AssertionError("old full verify forbidden")), \
                mock.patch.object(old, "load_table", side_effect=AssertionError("old full load forbidden")):
            _, _, report = validation.execute_validation(None, rows, Path(folder))
            with (Path(folder) / "validation-predictions.csv").open(newline="") as stream:
                predictions = list(csv.DictReader(stream))
        self.assertEqual(fit_model.call_count, 4)
        self.assertEqual(baseline.call_count, 2)
        self.assertTrue(all(all(old.inner_split(row.day) == "fit" for row in call.args[0])
                            for call in baseline.call_args_list))
        self.assertEqual({row["cascade_id"] for row in predictions}, {"cascade-000004", "cascade-000005"})
        self.assertTrue(all(row["evaluation_scope"] == "inner_validation" and row["selection_used"] == "True"
                            for row in predictions))
        for cutoff in ("900", "3600"):
            self.assertEqual(report[cutoff]["models"]["constant_train_median"]["all"]["raw_median_mae"], 994)
            self.assertEqual(report[cutoff]["fit_cascades"], 2)
            self.assertEqual(report[cutoff]["validation_cascades"], 2)

    def test_candidate_mae_ties_choose_earlier_epoch_then_declared_order(self):
        rows = {cutoff: [old.parse_row(record(day=day, cutoff=cutoff)) for day in (0.5, 4)]
                for cutoff in (900, 3600)}
        for epochs, expected in [((10, 3), validation.CANDIDATES[1]), ((3, 3), validation.CANDIDATES[0])]:
            def no_training(runtime, fit, selection, cutoff, candidate):
                epoch = epochs[validation.CANDIDATES.index(candidate)]
                return {"selected_epoch": epoch}, {"median": [5.0], "lower": None, "upper": None}, {}
            with self.subTest(epochs=epochs), tempfile.TemporaryDirectory() as folder, \
                    mock.patch.object(validation, "fit_candidate", side_effect=no_training):
                _, _, report = validation.execute_validation(None, rows, Path(folder))
            self.assertTrue(all(result["selected_candidate"] == expected for result in report.values()))

    def test_interval_metrics_reveal_zero_target_coverage_and_enforce_order(self):
        rows = [old.parse_row(record(observed=0, first=None, last=None, total=0)),
                old.parse_row(record(cascade=2, total=7))]
        predictions = {"lower": [0.01, 4.0], "median": [0.1, 5.0], "upper": [0.2, 6.0]}
        metrics = validation.validation_metrics(rows, predictions)
        self.assertEqual(metrics["all"]["interval_80_empirical_coverage"], 0.5)
        self.assertEqual(metrics["zero_target"]["n_cascades"], 1)
        self.assertEqual(metrics["zero_target"]["interval_80_empirical_coverage"], 0)
        self.assertEqual(metrics["zero_target"]["raw_median_mae"], 0.1)
        zero_inclusive = copy.deepcopy(predictions)
        zero_inclusive["lower"][0] = 0
        self.assertEqual(validation.validation_metrics(rows, zero_inclusive)["zero_target"]
                         ["interval_80_empirical_coverage"], 1)
        self.assertTrue(metrics["all"]["selection_used"])
        self.assertEqual(metrics["all"]["evaluation_scope"], "inner_validation")
        for lower, median, upper in [(-1, 0, 1), (2, 1, 3), (0, 3, 2)]:
            invalid = {"lower": [lower, 4], "median": [median, 5], "upper": [upper, 6]}
            with self.subTest(interval=(lower, median, upper)), self.assertRaises(ValueError):
                validation.validation_metrics(rows, invalid)
        plain = validation.validation_metrics(rows, {"lower": None, "median": [0.1, 5], "upper": None})
        self.assertIsNone(plain["zero_target"]["interval_80_empirical_coverage"])

    def plan_fixture(self, folder):
        destination = Path(folder) / "run"
        metadata = {"input_path": str(Path(folder) / "fixture.csv"), "provenance_path": str(Path(folder) / "provenance.json"),
                    "input_sha256": "f" * 64}
        audit = {"final_test_label_rows_loaded": 0, "test_evaluations": 0}
        return destination, ({900: [], 3600: []}, audit, metadata)

    def test_plan_freezes_without_fitting_importing_torch_or_overwriting(self):
        with tempfile.TemporaryDirectory() as folder:
            destination, verified = self.plan_fixture(folder)
            with mock.patch.object(validation, "verify_input", return_value=verified), \
                    mock.patch.object(validation, "fit_candidate", side_effect=AssertionError("plan cannot fit")), \
                    mock.patch.object(validation, "execute_validation", side_effect=AssertionError("plan cannot execute")), \
                    mock.patch.dict(sys.modules, {"torch": None}):
                plan = validation.make_plan("input", "provenance", destination, "f" * 64)
                self.assertFalse(plan["training_performed"])
                self.assertEqual(plan["config"]["test_evaluations"], 0)
                self.assertEqual(plan["evaluation_scope"], "inner_validation")
                self.assertTrue(plan["selection_used"])
                self.assertEqual(json.loads((destination / "plan.json").read_text()), plan)
                self.assertEqual((destination / "plan.json").stat().st_mode & 0o777, 0o600)
                self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
                self.assertFalse((destination / "training-started.json").exists())
                with self.assertRaises(FileExistsError):
                    validation.make_plan("input", "provenance", destination, "f" * 64)

    def test_plan_is_consumed_once_even_if_execution_fails(self):
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as folder:
                destination, verified = self.plan_fixture(folder)
                runtime = fake_runtime()

                def no_training(runtime, rows, output):
                    (output / "validation-predictions.csv").write_text("synthetic-no-fitting\n")
                    (output / "validation-predictions.csv").chmod(0o600)
                    return {}, {}, {}

                with mock.patch.object(validation, "verify_input", return_value=verified), \
                        mock.patch.dict(sys.modules, {"torch": runtime}), \
                        mock.patch.dict(os.environ), \
                        mock.patch.object(validation, "execute_validation", side_effect=no_training) as execute:
                    validation.make_plan("input", "provenance", destination, "f" * 64)
                    if fail:
                        execute.side_effect = RuntimeError("synthetic execution failure")
                        with self.assertRaisesRegex(RuntimeError, "synthetic execution failure"):
                            validation.run_plan(destination / "plan.json")
                        self.assertTrue((destination / "training-failed.json").exists())
                    else:
                        report = validation.run_plan(destination / "plan.json")
                        self.assertEqual(report["test_evaluations"], 0)
                        self.assertFalse(report["public_release_performed"])
                        self.assertTrue((destination / "training-completed.json").exists())
                    with self.assertRaises(FileExistsError):
                        validation.run_plan(destination / "plan.json")
                    execute.assert_called_once()
                    runtime.set_num_threads.assert_called_once_with(1)
                    runtime.set_num_interop_threads.assert_called_once_with(1)

    def test_changed_plan_or_evidence_rejected_before_consumption(self):
        for change in ("config", "code", "audit", "data", "path"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                destination, verified = self.plan_fixture(folder)
                with mock.patch.object(validation, "verify_input", return_value=verified), \
                        mock.patch.object(validation, "execute_validation", side_effect=AssertionError("changed plan cannot execute")):
                    validation.make_plan("input", "provenance", destination, "f" * 64)
                    path = destination / "plan.json"
                    plan = json.loads(path.read_text())
                    if change == "config":
                        plan["config"]["max_epochs"] += 1
                    elif change == "code":
                        plan["code"]["validation_sha256"] = "stale"
                    elif change == "audit":
                        plan["audit"]["test_evaluations"] = 1
                    elif change == "data":
                        plan["data"]["input_sha256"] = "stale"
                    else:
                        path = destination / "copied-plan.json"
                    path.write_text(json.dumps(plan))
                    with self.assertRaises(ValueError):
                        validation.run_plan(path)
                    self.assertFalse((destination / "training-started.json").exists())

    @unittest.skipUnless(importlib.util.find_spec("torch"), "optional torch runtime unavailable")
    def test_quantiles_and_pinball_arithmetic_without_optimizer(self):
        import torch
        with torch.no_grad(), mock.patch.object(torch.optim, "Adam", side_effect=AssertionError("no optimizer in math tests")):
            raw = torch.tensor([[-1000.0, 0.0, 1000.0], [0.1, -2.0, 3.0]])
            logs = validation.ordered_log_quantiles(torch, raw)
            counts = torch.expm1(torch.clamp(logs, max=validation.CONFIG["log_output_cap"]))
            self.assertEqual(float(counts[0, 0]), 0)
            self.assertTrue(bool(torch.isfinite(counts).all()))
            self.assertTrue(bool((counts >= 0).all()))
            self.assertTrue(bool((counts[:, 0] <= counts[:, 1]).all()))
            self.assertTrue(bool((counts[:, 1] <= counts[:, 2]).all()))
            predicted = torch.tensor([[1.0, 2.0, 3.0], [3.0, 3.0, 3.0]])
            labels = torch.tensor([[2.0], [1.0]])
            self.assertAlmostEqual(float(validation.pinball_loss(torch, predicted, labels)), 3.2 / 6, places=6)
            self.assertEqual(float(validation.pinball_loss(torch, labels.expand(-1, 3), labels)), 0)
            for candidate in validation.CANDIDATES:
                model = validation.build_model(torch, candidate, seed=1)
                self.assertEqual(sum(parameter.numel() for parameter in model.parameters()),
                                 validation.CONFIG["parameter_counts"][candidate])
                result = validation.predict_tensor(torch, model, torch.zeros((2, 5)), candidate)
                self.assertEqual(len(result["median"]), 2)
                self.assertTrue(all(math.isfinite(value) and value >= 0 for value in result["median"]))
                if result["lower"] is not None:
                    self.assertTrue(all(0 <= lower <= median <= upper for lower, median, upper in
                                        zip(result["lower"], result["median"], result["upper"])))

    @unittest.skipUnless(importlib.util.find_spec("torch"), "optional torch runtime unavailable")
    def test_exported_state_matches_untrained_forward_using_only_fit_or_synthetic_probes(self):
        import torch
        fit = [old.parse_row(record()), old.parse_row(record(cascade=2, day=3, observed=0,
                                                          first=None, last=None, total=0))]
        normalizer = old.normalizer_from_rows(fit)
        with torch.no_grad(), mock.patch.object(torch.optim, "Adam", side_effect=AssertionError("no optimizer in export test")):
            for candidate in validation.CANDIDATES:
                model = validation.build_model(torch, candidate, seed=1)
                exported = {"candidate": candidate, "cutoff_seconds": 900, "target": validation.CONFIG["target"],
                            "feature_names": old.FEATURE_NAMES, "normalizer": normalizer,
                            "layers": [{"weight": model[index].weight.detach().tolist(),
                                        "bias": model[index].bias.detach().tolist()} for index in (0, 2, 4)]}
                with mock.patch.object(old, "tensor_features", wraps=old.tensor_features) as features:
                    agreement = validation.check_export_agreement(torch, model, normalizer, exported, candidate, 900, fit)
                self.assertEqual(agreement["validation_rows_used"], 0)
                self.assertEqual(agreement["final_test_rows_used"], 0)
                self.assertTrue(all(old.inner_split(row.day) == "fit" for row in features.call_args.args[1]))
                state = {"schema": "rise-retweet-validation-state-v1", "models": {"900": {candidate: exported}}}
                for observed, first, last in [(0, None, None), (1, 0, 0), (1000000, 0, 900)]:
                    plain = validation.predict_state_stdlib(state, 900, candidate, observed, first, last)
                    self.assertTrue(math.isfinite(plain["median"]) and plain["median"] >= 0)
                    if plain["lower"] is not None:
                        self.assertTrue(0 <= plain["lower"] <= plain["median"] <= plain["upper"])
                changed = copy.deepcopy(state)
                changed["models"]["900"][candidate]["feature_names"] = list(reversed(old.FEATURE_NAMES))
                with self.assertRaises(ValueError):
                    validation.predict_state_stdlib(changed, 900, candidate, 0)


if __name__ == "__main__":
    unittest.main()
