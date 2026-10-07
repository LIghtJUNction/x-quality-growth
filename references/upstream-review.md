# Weekly official algorithm revision review

`.github/workflows/review-upstream.yml` runs every Monday at 03:43 UTC and supports `workflow_dispatch`. After publication, a successful dispatched run is required before describing this workflow as verified operational.

The workflow clones the official `xai-org/x-algorithm` default branch and compares its HEAD with `references/upstream.json`. An unchanged SHA succeeds without a report commit or empty PR. A new SHA creates a deterministic public `references/pending-upstream-review.md` report with reviewed/new commit links, full upstream comparison, and changed/deleted/unchanged status and hashes for every bound evidence file.

**发现新版本不等于已完成语义复核。** This workflow does not update the reviewed manifest, algorithm conclusions, strategies, or public experiment measurements. A human or an authorized Codex iteration must inspect execution paths, configuration and relevant files outside the evidence set before approving a new source revision.

The draft PR targets only the repository running this workflow. It uses `automation/upstream-review`, reuses an open PR, and only adds a report commit when content changes. An existing branch must contain exclusively recognizable bot report commits; otherwise the workflow stops and preserves it. Pushes are normal fast-forward pushes, never forced. GitHub Actions settings must permit PR creation for the provided repository token; a permission rejection is a failed publication, not a completed PR.

This schedule does **not** configure another user's fork, submit cross-repository contributions, or schedule X browser operations. Personal forks and contribution PRs still follow `contributing.md`.

Local read-only source review:

```sh
python3 scripts/review_upstream.py --source /path/to/clean/official/x-algorithm
```

Output is JSON. No changed revision means no output-file write. New-version reports contain no volatile timestamps, so repeated review of the same old/new revisions produces no artificial diff.
