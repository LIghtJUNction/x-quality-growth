# RISE — Recursive Iterative Social Expansion

<p align="center"><img src="assets/rise-hero.svg" width="100%" alt="RISE · Recursive Iterative Social Expansion: X and GitHub reference each other, with actual evidence improving each iteration" /></p>

<p align="center"><a href="references/algorithm.md"><img src="assets/badge-source.svg" alt="Based on the open-source X algorithm" /></a> <a href="public/metrics.json"><img src="assets/badge-evidence.svg" alt="Observed data, no guaranteed lift" /></a> <a href="LICENSE"><img src="assets/badge-license.svg" alt="MIT license" /></a></p>

<p align="center"><b>Recursive self-growth is the core idea.</b><br/>A Codex skill for X audience growth and higher-quality blue-check connections.<br/><a href="README.md">简体中文</a> · <a href="README.en.md">English</a></p>

## The recursive self-growth loop

**Share useful work on X → open-source the skill on GitHub → use, feedback and pull requests → publish reviewed observations → share new value on X → repeat.**

The X launch post links this repository. This README links that post and displays its actual feedback. Popularity is something to measure, not proof that the skill caused audience growth. No new value or evidence means no repeated promotional post.

**This skill is based on X's open-source recommendation algorithm, [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm).** It uses action, observation, feedback and iteration to optimize both new blue-check followers and their high-quality share. Quality means relevant, original, substantive public content—not merely a badge. Growth is an optimization goal requiring validation, not an established or exponential-growth guarantee. This is not an official X or xAI product.

## Real observations

<img src="assets/metrics.svg" width="100%" alt="Actual follower observations, blue-list changes and incomplete quality classification" />

<!-- RISE:METRICS:START -->
| Actual observation | Value |
| --- | --- |
| Total followers | 175 → 221 (+46) |
| Newly observed blue accounts | 12; confirmed new followers: unknown |
| Quality classification | 0 high / 2 not matched / 10 unclassified |
| High-quality share | Pending classification; unknown is not zero |
| Latest profile observation | 2026-10-07T21:20:36.728Z |
| GitHub stars / forks | 1 / 0 · 2026-10-07T21:21:51.187743+00:00 |

[RISE launch post](https://x.com/LIghtJUNction_x/status/2107943767382847844)
<!-- RISE:METRICS:END -->

Source: [public aggregate records](public/metrics.json). The exact time of the first total-follower check was not retained. Concurrent account activity was visible, and the first measurements predate the completed skill. Total follower change is not blue-follower growth. Verified-list arrivals may include existing followers receiving a badge. Quality classification remains incomplete. We keep those limitations visible.

## X × GitHub feedback

<img src="assets/feedback.svg" width="100%" alt="Observed public engagement for the experiment and launch posts" />

Actual published examples:

- [Initial Codex prompt experiment](https://x.com/LIghtJUNction_x/status/2107934424151335154)
- [Technical reply: what git diff does not show](https://x.com/LIghtJUNction_x/status/2107936031907737758)
- [Creator discussion: measuring follower quality](https://x.com/LIghtJUNction_x/status/2107936390185193718)

The pinned launch post is the stable entry point: edit it when new evidence or improvements exist, or append a timestamped progress reply when editing is unavailable.

GitHub stars and forks refresh every six hours through GitHub Actions. X feedback refreshes only after an authorized browser observation. A GitHub refresh never changes the timestamp of old X data. No unattended X scheduler has been configured.

## Install and run

```sh
git clone https://github.com/LIghtJUNction/x-quality-growth.git ~/.codex/skills/x-quality-growth
```

For an existing source checkout, install with a symlink and keep iterating in that source directory. Do not overwrite an existing skill.

```text
Use $x-quality-growth on my currently signed-in X account.
Audience: AI tools, independent developers and product builders.
Authorized actions: original posts, likes, substantive replies, selected quotes,
following relevant blue-check accounts and following back blue-check followers.
Record a baseline, execute one small batch and verify persistent results.
Optimize new blue-check followers and their high-quality share, then report evidence.
Stop the affected action if the platform limits it.
```

The skill drives Codex in an available, authenticated browser. Its scripts are offline measurement tools, not an always-on X bot, credential store or private-API client. Scheduled browser sessions require an available scheduler to be actually configured.

## Reproducible measurement

Python 3.10+, standard library only:

```sh
python3 scripts/measure.py examples/before.json examples/after.json
python3 -m unittest discover -s tests -v
python3 scripts/audit_source.py --source /path/to/x-algorithm --output references/upstream.json
python3 scripts/render_public.py
```

[Skill entry point](SKILL.md) · [Pinned algorithm evidence](references/algorithm.md) · [Measurement rules](references/measurement.md) · [Source manifest](references/upstream.json)

Weights multiply predicted values, not counts. No "one reply equals ten likes" arithmetic. Stable IDs, incomplete lists, badge upgrades, renames, unknown classifications and unavailable counters are handled separately. Unknown data is not zero; zero arrivals have no quality rate. Source defaults do not establish every production request's configuration.

## Fork, iterate and contribute upstream

With accessible GitHub MCP or authenticated `gh`, the skill checks and creates a personal fork, iterates there and syncs upstream. At the review cadence, submit or update a PR only for actual improvements. Reuse forks, branches and existing PRs; preserve unrelated changes. The upstream author works directly on the source repository.

See [contribution workflow](references/contributing.md). The default cadence is a weekly review; configure it only when a scheduler is available. No empty PRs or fictional background schedules.

## Keep the evidence current

Maintain the code in the source checkout. Private account lists stay in ignored `runs/`; only reviewed aggregate observations enter this public repository. Re-render both language tables and SVGs after a real X measurement. Re-read changed upstream code before updating algorithm conclusions.

MIT for original code and documentation. The referenced X algorithm is Apache-2.0; it is not bundled here. No controlled growth experiment or proven growth rate is claimed.
