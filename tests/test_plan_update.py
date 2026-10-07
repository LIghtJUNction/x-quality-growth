import copy
import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("plan_update", ROOT / "scripts/plan_update.py")
planner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(planner)


def metrics():
    return {
        "account": "example", "launch_post": "https://x.com/example/status/123",
        "quality_rubric": "relevant original substantive",
        "follower_observations": [{"total": 10, "observed_at": "2026-10-08T01:00:00Z"}],
        "blue_observations": [{"count": 4, "observed_at": "2026-10-08T00:50:00Z"}],
        "blue_cohort": {"observed_arrivals": 2, "confirmed_new_followers": None,
                        "high": 1, "not_high": 0, "unknown": 1,
                        "window_ended_at": "2026-10-08T00:50:00Z"},
        "posts": [{"likes": 1}],
    }


NOW = datetime(2026, 10, 8, 2, tzinfo=timezone.utc)


def evidence():
    return {"source": "browser", "confirmed": True, "method": "thread_reply",
            "url": "https://x.com/example/status/456", "parent": "https://x.com/example/status/123",
            "verified_at": "2026-10-08T02:01:00Z", "observation": "Reopened reply, text and parent verified"}


class PinnedUpdateTests(unittest.TestCase):
    def baseline(self):
        plan = planner.make_plan(metrics(), now=NOW)
        return planner.record_publication(plan, evidence())

    def test_initial_draft_preserves_unknown_and_separate_times(self):
        plan = planner.make_plan(metrics(), now=NOW)
        self.assertTrue(plan["should_update"])
        self.assertIn("未分类 1/2 (50.0%)", plan["draft"])
        self.assertIn("高质量 1/2", plan["draft"])
        self.assertIn("未确认", plan["draft"])
        self.assertIn("下界", plan["draft"])
        self.assertIn("2026-10-08T00:50:00Z", plan["draft"])

    def test_repeated_data_and_new_timestamps_do_not_trigger(self):
        data = metrics()
        data["follower_observations"][0]["observed_at"] = "2026-10-08T03:00:00Z"
        plan = planner.make_plan(data, self.baseline(), now=NOW.replace(hour=4))
        self.assertEqual(plan["reason"], "no_material_change")
        self.assertIsNone(plan["draft"])

    def test_self_engagement_and_github_counts_not_triggers(self):
        data = metrics()
        data["posts"][0]["likes"] = 100
        data["github"] = {"stars": 100}
        plan = planner.make_plan(data, self.baseline(), now=NOW.replace(hour=4))
        self.assertFalse(plan["should_update"])

    def test_quality_classification_progress_triggers(self):
        data = metrics()
        data["blue_cohort"].update(high=2, unknown=0)
        plan = planner.make_plan(data, self.baseline(), now=NOW.replace(hour=4), language="en")
        self.assertTrue(plan["should_update"])
        self.assertIn("High-quality: 2/2", plan["draft"])
        self.assertNotIn("lower bound", plan["draft"])

    def test_operator_interval_defers_changed_data(self):
        data = metrics()
        data["follower_observations"][0]["total"] = 11
        plan = planner.make_plan(data, self.baseline(), now=NOW.replace(minute=30))
        self.assertEqual(plan["reason"], "operating_interval")
        self.assertIsNone(plan["draft"])
        self.assertIn("not a platform", plan["interval_basis"])

    def test_legacy_public_update_suppresses_already_reported_total(self):
        data = metrics()
        data["progress_updates"] = [{"parent": data["launch_post"],
                                     "reported_profile_observation": "2026-10-08T01:00:00Z"}]
        self.assertFalse(planner.make_plan(data, now=NOW)["should_update"])
        data["follower_observations"].append({"total": 11, "observed_at": "2026-10-08T01:30:00Z"})
        self.assertTrue(planner.make_plan(data, now=NOW)["should_update"])

    def test_legacy_baseline_does_not_claim_past_quality_snapshot(self):
        data = metrics()
        data["progress_updates"] = [{"parent": data["launch_post"],
                                     "reported_profile_observation": "2026-10-08T01:00:00Z"}]
        previous = planner.public_baseline(data, planner.snapshot(data))
        self.assertNotIn("quality", previous["material"])
        self.assertTrue(planner.make_plan(data, now=NOW)["legacy_quality_baseline_unknown"])
        data["blue_cohort"].update(high=2, unknown=0, classified_at="2026-10-08T01:30:00Z")
        plan = planner.make_plan(data, now=NOW)
        self.assertTrue(plan["should_update"])
        self.assertIn("quality", plan["changed_fields"])
        self.assertIn("2026-10-08T01:30:00Z", plan["draft"])
        self.assertEqual(plan["snapshot"]["observations"]["cohort_window"], "2026-10-08T00:50:00Z")

    def test_actual_code_change_can_trigger_once(self):
        data = metrics()
        plan = planner.make_plan(data, self.baseline(), now=NOW.replace(hour=4), changes=["Fix incomplete-count labels"])
        state = planner.record_publication(plan, dict(evidence(), verified_at="2026-10-08T04:01:00Z"), self.baseline())
        self.assertFalse(planner.make_plan(data, state, now=NOW.replace(hour=6))["should_update"])
        self.assertFalse(planner.make_plan(data, state, now=NOW.replace(hour=6), changes=["Fix incomplete-count labels"])["should_update"])

    def test_zero_cohort_is_undefined(self):
        data = metrics()
        data["blue_cohort"].update(observed_arrivals=0, high=0, unknown=0)
        self.assertIn("高质量 未定义", planner.make_plan(data, now=NOW)["draft"])

    def test_invalid_partition_and_bool_counts_rejected(self):
        for patch in ({"high": 2}, {"high": True}, {"confirmed_new_followers": 3}):
            data = metrics()
            data["blue_cohort"].update(patch)
            with self.assertRaises(ValueError):
                planner.make_plan(data, now=NOW)

    def test_future_and_naive_times_rejected(self):
        for value in ("2026-10-09T01:00:00Z", "2026-10-08T01:00:00"):
            data = metrics()
            data["follower_observations"][0]["observed_at"] = value
            with self.assertRaises(ValueError):
                planner.make_plan(data, now=NOW)

    def test_wrong_fixed_account_rejected(self):
        data = metrics()
        data["launch_post"] = "https://x.com/another/status/123"
        with self.assertRaises(ValueError):
            planner.make_plan(data, now=NOW)

    def test_old_measurement_cannot_replace_published_snapshot(self):
        data = metrics()
        data["follower_observations"][0]["observed_at"] = "2026-10-08T00:00:00Z"
        data["follower_observations"][0]["total"] = 9
        with self.assertRaises(ValueError):
            planner.make_plan(data, self.baseline(), now=NOW.replace(hour=4))

    def test_offset_timestamps_are_rendered_as_utc(self):
        data = metrics()
        data["follower_observations"][0]["observed_at"] = "2026-10-08T09:00:00+08:00"
        draft = planner.make_plan(data, now=NOW)["draft"]
        self.assertIn("2026-10-08T01:00:00Z", draft)
        self.assertNotIn("09:00:00", draft)

    def test_missing_blue_list_is_not_zero(self):
        data = metrics()
        data["blue_observations"] = []
        draft = planner.make_plan(data, now=NOW)["draft"]
        self.assertIn("蓝 V 名单 未采集", draft)
        self.assertNotIn("None", draft)

    def test_browser_attempt_is_not_publication(self):
        plan = planner.make_plan(metrics(), now=NOW)
        for patch in ({"confirmed": False}, {"source": "composer"}, {"parent": "https://x.com/example/status/999"},
                      {"observation": ""}, {"verified_at": "2026-10-08T01:00:00Z"}):
            with self.assertRaises(ValueError):
                planner.record_publication(plan, dict(evidence(), **patch))

    def test_edit_requires_same_fixed_url(self):
        plan = planner.make_plan(metrics(), now=NOW)
        with self.assertRaises(ValueError):
            planner.record_publication(plan, dict(evidence(), method="edit"))
        result = planner.record_publication(plan, dict(evidence(), method="edit", url=metrics()["launch_post"]))
        self.assertEqual(result["last_published"]["method"], "edit")

    def test_tampered_plan_and_duplicate_record_rejected(self):
        plan = planner.make_plan(metrics(), now=NOW)
        modified = copy.deepcopy(plan)
        modified["snapshot"]["material"]["total_followers"] = 999
        with self.assertRaises(ValueError):
            planner.record_publication(modified, evidence())
        state = planner.record_publication(plan, evidence())
        with self.assertRaises(ValueError):
            planner.record_publication(plan, dict(evidence(), verified_at="2026-10-08T05:00:00Z"), state)

    def test_state_cannot_cross_account_and_private_path_cannot_escape(self):
        state = self.baseline()
        state["last_published"]["material"]["account"] = "another"
        with self.assertRaises(ValueError):
            planner.make_plan(metrics(), state, now=NOW)
        with self.assertRaises(ValueError):
            planner.private_path(ROOT / "public/state.json")
        self.assertTrue(planner.private_path(ROOT / "runs/state.json").is_relative_to(ROOT / "runs"))


    def test_malformed_state_and_evidence_have_clean_errors(self):
        for state in ([], {"last_published": []}, {"last_published": {}}, {"history": {}},
                      {"last_published": {"material": None}}):
            with self.assertRaises(ValueError):
                planner.make_plan(metrics(), state, now=NOW)
        plan = planner.make_plan(metrics(), now=NOW)
        for bad in ([], None, {"confirmed": True, "source": "browser", "url": 123}):
            with self.assertRaises(ValueError):
                planner.record_publication(plan, bad)

    def test_each_observation_clock_cannot_regress(self):
        for field in ("blue_observations", "blue_cohort"):
            data = metrics()
            if field == "blue_observations":
                data[field][0]["observed_at"] = "2026-10-08T00:00:00Z"
            else:
                data[field]["window_ended_at"] = "2026-10-08T00:00:00Z"
            with self.assertRaises(ValueError):
                planner.make_plan(data, self.baseline(), now=NOW.replace(hour=4))


if __name__ == "__main__":
    unittest.main()
