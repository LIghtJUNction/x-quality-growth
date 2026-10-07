#!/usr/bin/env python3
"""Offline pinned-thread update planning; never sends anything to X."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://github.com/LIghtJUNction/x-quality-growth"
STATUS = re.compile(r"https://x\.com/([A-Za-z0-9_]+)/status/([0-9]+)$")


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("An exact timezone-aware observation timestamp is required")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return result.astimezone(timezone.utc)


def count(value, label, nullable=False):
    if nullable and value is None:
        return value
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Invalid {label}")
    return value


def utc_label(value):
    return timestamp(value).isoformat().replace("+00:00", "Z")


def snapshot(metrics, changes=()):
    account = metrics["account"]
    launch = metrics["launch_post"]
    match = STATUS.fullmatch(launch)
    if not match or match[1].lower() != account.lower():
        raise ValueError("Fixed launch URL must belong to the measured account")
    rows = metrics["follower_observations"]
    dated = [(timestamp(row["observed_at"]), row) for row in rows if row.get("observed_at")]
    if not dated:
        raise ValueError("No exactly dated follower observation")
    _, latest = max(dated, key=lambda item: item[0])
    total = count(latest["total"], "follower total")
    blue_rows = metrics.get("blue_observations", [])
    blue = max(blue_rows, key=lambda row: timestamp(row["observed_at"])) if blue_rows else None
    cohort = metrics["blue_cohort"]
    n = count(cohort["observed_arrivals"], "observed blue arrivals")
    high = count(cohort["high"], "high-quality count")
    not_high = count(cohort["not_high"], "not-high count")
    unknown = count(cohort["unknown"], "unknown count")
    confirmed = count(cohort.get("confirmed_new_followers"), "confirmed new followers", True)
    if high + not_high + unknown != n or (confirmed is not None and confirmed > n):
        raise ValueError("Invalid quality cohort partition")
    if not cohort.get("window_ended_at"):
        raise ValueError("Quality cohort needs its own observation timestamp")
    timestamp(cohort["window_ended_at"])
    classified_at = cohort.get("classified_at")
    if classified_at is not None:
        timestamp(classified_at)
    material = {
        "account": account,
        "launch_post": launch,
        "total_followers": total,
        "observed_blue_count": count(blue["count"], "blue count") if blue else None,
        "quality": {"observed_arrivals": n, "confirmed_new_followers": confirmed,
                    "high": high, "not_high": not_high, "unknown": unknown},
        "quality_rubric": metrics["quality_rubric"],
        "changes": sorted(set(change.strip() for change in changes if change.strip())),
    }
    return {"material": material, "observations": {
        "followers": utc_label(latest["observed_at"]),
        "blue": utc_label(blue["observed_at"]) if blue else None,
        "quality": utc_label(classified_at or cohort["window_ended_at"]),
        "cohort_window": utc_label(cohort["window_ended_at"]),
    }}


def fingerprint(material):
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def public_baseline(metrics, current):
    """Legacy public updates lack full snapshots: suppress unsupported repeat claims."""
    progress = [row for row in metrics.get("progress_updates", [])
                if row.get("parent") == current["material"]["launch_post"]
                and row.get("reported_profile_observation")]
    if not progress:
        return None
    update = max(progress, key=lambda row: timestamp(row["reported_profile_observation"]))
    reported_at = timestamp(update["reported_profile_observation"])
    eligible = [row for row in metrics["follower_observations"]
                if row.get("observed_at") and timestamp(row["observed_at"]) <= reported_at]
    if not eligible:
        return None
    baseline = {key: current["material"][key] for key in ("account", "launch_post")}
    baseline["total_followers"] = max(eligible, key=lambda row: timestamp(row["observed_at"]))["total"]
    return {"material": baseline, "verified_at": update.get("verified_at"),
            "legacy_baseline": True, "legacy_reported_at": update["reported_profile_observation"]}


def _make_plan(metrics, state=None, *, now=None, language="zh", changes=(), min_interval_minutes=60):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or min_interval_minutes < 0:
        raise ValueError("Timezone-aware planning time and nonnegative operating interval required")
    current = snapshot(metrics, changes)
    if any(timestamp(value) > now for value in current["observations"].values() if value):
        raise ValueError("Observation cannot be in the future")
    material = current["material"]
    previous = (state or {}).get("last_published") or public_baseline(metrics, current)
    if previous and (previous["material"]["account"] != material["account"]
                     or previous["material"]["launch_post"] != material["launch_post"]):
        raise ValueError("State belongs to another account or pinned entrance")
    if previous:
        for field, value in previous.get("observations", {}).items():
            observed = current["observations"].get(field)
            if value and (not observed or timestamp(observed) < timestamp(value)):
                raise ValueError("Observation is older than the last published measurement")
    baseline = previous["material"] if previous else None
    reasons = [key for key in material if not baseline or material[key] != baseline.get(key)]
    if previous and previous.get("legacy_baseline"):
        # Legacy records prove the reported total, not a historical quality snapshot.
        cutoff = timestamp(previous["legacy_reported_at"])
        reasons = [key for key in reasons if key != "quality_rubric"
                   and (key != "quality" or timestamp(current["observations"]["quality"]) > cutoff)
                   and (key != "observed_blue_count" or (current["observations"]["blue"]
                        and timestamp(current["observations"]["blue"]) > cutoff))]
    # A previously announced change need not be announced again when --change is omitted.
    if baseline and not material["changes"] and "changes" in reasons:
        reasons.remove("changes")
    due = None
    if previous and previous.get("verified_at"):
        due = timestamp(previous["verified_at"]) + timedelta(minutes=min_interval_minutes)
    actionable = bool(reasons) and (due is None or now >= due)
    q = material["quality"]
    n = q["observed_arrivals"]
    share = f"{q['high']}/{n}" if n else ("未定义" if language == "zh" else "undefined")
    unknown_share = f"{q['unknown']}/{n} ({q['unknown'] / n:.1%})" if n else "0/0 (undefined)"
    at = current["observations"]
    blue_count = material["observed_blue_count"]
    blue_display = blue_count if blue_count is not None else ("未采集" if language == "zh" else "not observed")
    blue_time = at["blue"] or ("时间未知" if language == "zh" else "timestamp unknown")
    if language == "zh":
        draft = (f"RISE 进展｜数据观察时间（UTC）\n"
                 f"总粉丝 {material['total_followers']}（{at['followers']}）；"
                 f"蓝 V 名单 {blue_display}（{blue_time}）。\n"
                 f"本轮新观察到蓝 V {n}；确认新增：{q['confirmed_new_followers'] if q['confirmed_new_followers'] is not None else '未确认'}。"
                 f"高质量 {share}；未分类 {unknown_share}（{at['quality']}）。"
                 f"{'质量判定尚未完成；这个比例只是已确认高质量的下界。' if q['unknown'] else ''}\n"
                 f"{'技能改进：' + '；'.join(material['changes']) + '。' if material['changes'] else ''}\n"
                 f"上述是观察变化，不能证明由技能造成。公开互动计数可能包含账号自己的互动，不作为独立效果。\n"
                 f"源码：{SOURCE}\n固定入口：{material['launch_post']}")
    elif language == "en":
        draft = (f"RISE progress | observation timestamps (UTC)\n"
                 f"Followers: {material['total_followers']} ({at['followers']}); "
                 f"verified-list count: {blue_display} ({blue_time}).\n"
                 f"Newly observed blue accounts: {n}; confirmed new followers: "
                 f"{q['confirmed_new_followers'] if q['confirmed_new_followers'] is not None else 'unconfirmed'}. "
                 f"High-quality: {share}; unclassified: {unknown_share} ({at['quality']}). "
                 f"{'Classification is incomplete; the quality share is a lower bound.' if q['unknown'] else ''}\n"
                 f"{'Skill improvements: ' + '; '.join(material['changes']) + '.' if material['changes'] else ''}\n"
                 f"Observed changes do not establish causality. Public counters can include owner activity; they are not independent effects.\n"
                 f"Source: {SOURCE}\nFixed entrance: {material['launch_post']}")
    else:
        raise ValueError("Language must be zh or en")
    return {"schema_version": 1, "should_update": actionable,
            "reason": "material_change" if actionable else ("operating_interval" if reasons else "no_material_change"),
            "changed_fields": reasons, "planned_at": now.isoformat(),
            "not_before": due.isoformat() if due and now < due else None,
            "min_interval_minutes": min_interval_minutes,
            "interval_basis": "Operator budget, not a platform safety threshold",
            "snapshot": current, "fingerprint": fingerprint(material),
            "language": language, "draft": draft if actionable else None,
            "publication_method": "Check edit availability on the fixed post; otherwise reply in its existing thread",
            "background_status": "No unattended X scheduler configured by this script",
            "legacy_quality_baseline_unknown": bool(previous and previous.get("legacy_baseline")),
            "requires_browser_verification": True}


def _record_publication(plan, evidence, state=None):
    """Record an explicit post-publish browser observation, never an attempted send."""
    if not plan.get("should_update") or plan.get("fingerprint") != fingerprint(plan["snapshot"]["material"]):
        raise ValueError("Only an actionable, unmodified plan can be recorded")
    fixed = plan["snapshot"]["material"]["launch_post"]
    account = plan["snapshot"]["material"]["account"]
    method = evidence.get("method")
    match = STATUS.fullmatch(evidence.get("url", ""))
    if evidence.get("confirmed") is not True or evidence.get("source") != "browser":
        raise ValueError("Explicit confirmed browser evidence is required")
    if not match or match[1].lower() != account.lower():
        raise ValueError("Verified published URL must belong to this account")
    if method == "edit":
        if evidence["url"] != fixed:
            raise ValueError("Edited URL must be the fixed entrance")
    elif method == "thread_reply":
        if evidence.get("parent") != fixed or evidence["url"] == fixed:
            raise ValueError("Reply must be verified under the fixed entrance")
    else:
        raise ValueError("Method must be edit or thread_reply")
    verified = timestamp(evidence.get("verified_at"))
    if verified < timestamp(plan["planned_at"]):
        raise ValueError("Browser verification predates the plan")
    if not isinstance(evidence.get("observation"), str) or not evidence["observation"].strip():
        raise ValueError("Describe what the reopened browser page verified")
    published = {"material": plan["snapshot"]["material"], "fingerprint": plan["fingerprint"],
                 "observations": plan["snapshot"]["observations"],
                 "verified_at": evidence["verified_at"], "url": evidence["url"], "method": method}
    result = json.loads(json.dumps(state or {}))
    existing = result.get("last_published")
    if existing and (existing["material"]["account"] != account or existing["material"]["launch_post"] != fixed):
        raise ValueError("State belongs to another account or pinned entrance")
    if existing and verified <= timestamp(existing["verified_at"]):
        raise ValueError("Publication records must move forward in time")
    if existing and (existing.get("fingerprint") == plan["fingerprint"]
                     or timestamp(plan["planned_at"]) <= timestamp(existing["verified_at"])):
        raise ValueError("Duplicate or stale publication plan")
    result.setdefault("history", []).append(published)
    result["last_published"] = published
    return result


def validate_state(state):
    if state is None:
        return
    if not isinstance(state, dict):
        raise ValueError("State must be a JSON object")
    if "history" in state and not isinstance(state["history"], list):
        raise ValueError("State history must be a list")
    if "last_published" in state:
        previous = state["last_published"]
        if not isinstance(previous, dict) or not isinstance(previous.get("material"), dict):
            raise ValueError("last_published must contain a material object")
        if not previous["material"].get("account") or not previous["material"].get("launch_post"):
            raise ValueError("Published material needs account and fixed entrance")
        timestamp(previous.get("verified_at"))


def make_plan(metrics, state=None, **options):
    try:
        if not isinstance(metrics, dict) or (state is not None and not isinstance(state, dict)):
            raise ValueError("Metrics and state must be JSON objects")
        validate_state(state)
        return _make_plan(metrics, state, **options)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError) as error:
        raise ValueError(f"Malformed planning input: {error}") from None


def record_publication(plan, evidence, state=None):
    try:
        if not isinstance(plan, dict) or not isinstance(evidence, dict) or (state is not None and not isinstance(state, dict)):
            raise ValueError("Plan, browser evidence and state must be JSON objects")
        validate_state(state)
        return _record_publication(plan, evidence, state)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError) as error:
        raise ValueError(f"Malformed publication input: {error}") from None


def private_path(value):
    path = Path(value).resolve()
    if not path.is_relative_to(ROOT / "runs"):
        raise ValueError("State and plan artifacts must stay in ignored runs/")
    return path


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    planning = sub.add_parser("plan")
    planning.add_argument("--metrics", type=Path, default=ROOT / "public/metrics.json")
    planning.add_argument("--state", default=str(ROOT / "runs/pinned-update-state.json"))
    planning.add_argument("--output", default=str(ROOT / "runs/pinned-update-plan.json"))
    planning.add_argument("--language", choices=("zh", "en"), default="zh")
    planning.add_argument("--change", action="append", default=[])
    planning.add_argument("--min-interval-minutes", type=int, default=60)
    recording = sub.add_parser("record")
    recording.add_argument("--plan", default=str(ROOT / "runs/pinned-update-plan.json"))
    recording.add_argument("--browser-evidence", type=Path, required=True)
    recording.add_argument("--state", default=str(ROOT / "runs/pinned-update-state.json"))
    args = parser.parse_args()
    try:
        state_path = private_path(args.state)
        state = json.loads(state_path.read_text()) if state_path.exists() else None
        if args.command == "plan":
            if private_path(args.output) == state_path:
                raise ValueError("Plan output cannot overwrite publication state")
            metrics = json.loads(args.metrics.read_text())
            result = make_plan(metrics, state, language=args.language, changes=args.change,
                               min_interval_minutes=args.min_interval_minutes)
            write_json(private_path(args.output), result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            plan = json.loads(private_path(args.plan).read_text())
            evidence = json.loads(args.browser_evidence.read_text())
            result = record_publication(plan, evidence, state)
            write_json(state_path, result)
            print(json.dumps({"recorded": True, "url": result["last_published"]["url"]}))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, f"Invalid update record: {error}\n")


if __name__ == "__main__":
    main()
