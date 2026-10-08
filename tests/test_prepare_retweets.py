"""Synthetic preparation tests: no network, training or real source IDs."""
import csv
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("prepare_retweets", Path(__file__).parents[1] / "scripts" / "prepare_retweets.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PreparationTests(unittest.TestCase):
    def fixture(self, root, cascades):
        source, output = root / "source", root / "output"
        source.mkdir()
        output.mkdir()
        next_row = 1
        with (source / "index.csv").open("w", newline="") as index, (source / "data.csv").open("w", newline="") as data:
            iw, dw = csv.writer(index), csv.writer(data)
            iw.writerow(prepare.INDEX_FIELDS)
            dw.writerow(prepare.EVENT_FIELDS)
            for identity, day, events in cascades:
                iw.writerow([identity, day, next_row, next_row + len(events) - 1])
                for time in events:
                    dw.writerow([time, 123])  # Unused synthetic follower values.
                next_row += len(events)
        return source, output

    def run_fixture(self, root, cascades):
        source, output = self.fixture(root, cascades)
        summary = prepare.prepare_table(source / "index.csv", source / "data.csv", output, [])
        with (output / "retweet-features.csv").open() as result:
            rows = list(csv.DictReader(result))
        return source, output, summary, rows

    def test_duplicate_and_noncanonical_identity_quarantine(self):
        with tempfile.TemporaryDirectory() as temp:
            _, output, summary, rows = self.run_fixture(Path(temp), [
                ("101", 1, [0, 1]), ("101", 1, [0, 2]),
                ("1.02e+02", 2, [0, 3]), ("0103", 2, [0, 4]),
                ("１０４", 2, [0, 5]), (" 105", 2, [0, 6]),
                ("106", 7, [0, 7]),
            ])
            self.assertEqual(summary["counts"]["cascades"], 1)
            self.assertEqual(summary["coverage"]["quarantined_segments"], 6)
            self.assertEqual([row["cascade_id"] for row in rows], ["cascade-000007"] * 2)
            quarantined = json.loads((output / "quarantined-id-segments.json").read_text())
            self.assertEqual(sum(row["repeated_raw_id"] for row in quarantined), 2)
            self.assertTrue(summary["identity_policy"].startswith("Only raw ASCII decimal IDs"))

    def test_original_only_exclusion_simultaneous_events_and_boundaries(self):
        with tempfile.TemporaryDirectory() as temp:
            _, output, summary, rows = self.run_fixture(Path(temp), [
                ("201", 1, [0, 0, 900, 901, 3600, 3601, "8.64e4", 86401]),
            ])
            early, late = rows
            self.assertEqual((int(early["observed_retweet_count"]), int(early["future_retweets_to_24h"])), (2, 4))
            self.assertEqual((int(late["observed_retweet_count"]), int(late["future_retweets_to_24h"])), (4, 2))
            self.assertEqual(int(early["total_retweets_at_24h"]), 6)
            self.assertEqual(float(early["first_observed_retweet_seconds"]), 0)
            self.assertEqual(summary["counts"]["scientific_notation_event_times"], 1)
            self.assertEqual(summary["counts"]["segments_below_documented_50_retweets"], 1)
            verification = json.loads((output / "verification-result.json").read_text())
            self.assertEqual(verification["source_cascades_crosschecked"], 1)
            self.assertEqual(verification["features_sha256"], prepare.sha(output / "retweet-features.csv"))

    def test_temporal_purge_and_cold_cases_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            _, _, summary, rows = self.run_fixture(Path(temp), [
                ("301", 6, [0, 7200]), ("302", 6.01, [0, 7200]),
                ("303", 7, [0, 90000]),
            ])
            self.assertEqual([rows[i]["strict_label_available_split"] for i in (0, 2, 4)],
                             ["train_candidate", "purged_label_overlap", "evaluation_candidate"])
            self.assertEqual(summary["counts"]["cascades"], 3)
            for row in rows:
                self.assertEqual(row["observed_retweet_count"], "0")
                self.assertEqual(row["first_observed_retweet_seconds"], "")
                self.assertEqual(row["last_observed_retweet_seconds"], "")
            self.assertEqual(rows[4]["future_retweets_to_24h"], "0")

    def test_missing_origin_and_invalid_times_rejected(self):
        for times in ([1, 2], [0, "NaN"], [0, "inf"], [0, -1]):
            with self.subTest(times=times), tempfile.TemporaryDirectory() as temp:
                source, output = self.fixture(Path(temp), [("401", 1, times)])
                with self.assertRaises(ValueError):
                    prepare.prepare_table(source / "index.csv", source / "data.csv", output, [])

    def test_reuse_verifies_bytes_and_preserves_original_retrieval_times(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output = self.fixture(Path(temp), [("501", 1, [0, 1])])
            pinned = {name: ((source / name).stat().st_size, prepare.sha(source / name)) for name in prepare.PINNED}
            records = [dict(url=prepare.SOURCE + name, actual_bytes=size, sha256=digest,
                            http_status=200, started_at="synthetic-original-start", completed_at="synthetic-original-end")
                       for name, (size, digest) in pinned.items()]
            (source / "http-provenance.json").write_text(json.dumps(records))
            with patch.dict(prepare.PINNED, pinned, clear=True), patch.object(prepare, "urlopen", side_effect=AssertionError("No network")):
                index, data, http = prepare.acquire(output, source)
                self.assertEqual(http, records)
                self.assertEqual(data, source / "data.csv")
                self.assertEqual(prepare.sha(index), pinned["index.csv"][1])
                reuse = json.loads((output / "source-reuse.json").read_text())
                self.assertFalse(reuse["network_download_performed"])
                (source / "data.csv").write_text("tampered")
                with self.assertRaises(ValueError):
                    prepare.acquire(output, source)

    def test_cli_refuses_nonempty_output_before_any_network(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            sentinel = directory / "unrelated.txt"
            sentinel.write_text("preserve")
            with patch("sys.argv", ["prepare_retweets.py", "--output", str(directory)]), patch.object(prepare, "urlopen", side_effect=AssertionError("No network")):
                with self.assertRaises(SystemExit):
                    prepare.main()
            self.assertEqual(sentinel.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
