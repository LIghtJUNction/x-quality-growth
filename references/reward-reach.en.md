# Third objective: original verified Home impressions

Alongside total followers and newly acquired high-quality blue-verified followers, optimize **original-content verified Home Timeline impressions over the past 90 days**. Relevant eligibility thresholds include **500,000 verified Home Timeline impressions in 90 days** and **500 verified followers**. Replies are excluded from the impression threshold. Reaching these numbers does not establish that all enrollment requirements are met. [X Original Content Rewards](https://help.x.com/en/using-x/original-content-rewards)

The actual baseline at `2026-10-08T04:02:12.455Z`, observed in the [Original Content Rewards dashboard](https://x.com/i/jf/creators/original_content_rewards), was **167 verified followers** and **534 verified Home Timeline impressions in the past 90 days**, with replies explicitly excluded. The gaps were **333 followers** and **499,466 impressions**; impression progress was **0.1068%**. This is a dated observation. Use the latest [public aggregate metrics](../public/reward-observations.json) for subsequent readings. Verified followers have not necessarily been individually classified as blue or high quality.

## Separate eligibility from earnings

The eligibility dashboard's rolling count and earnings-qualified impressions are separate targets. Qualified-impression conditions additionally involve Premium viewers, the Home Timeline, at least 50% visibility, one count per viewer per post, and exclusions for paid or artificially generated impressions. Public views cannot substitute for either metric, and verification alone does not establish earnings qualification. [X impression conditions](https://help.x.com/en/using-x/original-content-rewards)

X lists content created or posted with automated systems as ineligible for earnings. Content exclusively about monetization coaching, discussion, or maximizing payouts is also ineligible. Do not record previous Codex-posted public views as qualified earnings impressions. If the dashboard does not explain whether automated content contributes to its eligibility threshold, leave that question unknown rather than inferring its accounting from the earnings exclusions. [X content eligibility](https://help.x.com/en/using-x/original-content-rewards)

## Execute the next round

Focus on the account's existing AI tools, development, and product topics. The user should personally create original cases, insights, or work, using their own source images, demonstrations, and verifiable experiment material. Provide useful information for relevant verified audiences and answer real questions. Automation may assist research, candidate drafts, data preparation, and backtesting. User review or a manual publish click does not automatically make machine-generated content earnings-eligible. Platform rules and review determine eligibility; the model cannot adjudicate it.

Change one content variable per round and compare original posts at matching ages. Replies support real discussion but their views are excluded from this earnings-reach experiment. Avoid mechanical follow exchanges, owner-generated engagement, repetitive promotion, or disguising automated creation as human work. Without a new case, prioritize research and measurement instead of filling a posting quota.

## Record and predict the actual target

**Per post:** build future one-hour and 24-hour labels only when official detail provides a verifiable cumulative original verified Home count `I(t)`: `Y_h = I(t+h) - I(t)`. Preserve the permalink, publication time, actual collection times, post ages, dashboard source, and counter definition. Exclude replies and retain the real window when late. Public views, ordinary impressions, and counters without Home/verified breakdowns cannot replace this label. Investigate counter revisions or definition changes before calculating a delta.

**Account level:** use the same backend definition for the rolling 90-day count:

```text
V90(t+h) = V90(t) + newly entering counts - counts expiring in that interval
```

A current total without daily history, expiry distribution, and matching incoming data cannot establish an ETA. Do not multiply a short-term daily estimate by 90. Expiring impressions mean incoming growth is not necessarily the rolling count's net growth.

Forecasts should retain `target_name`, `target_source`, `data_scope`, `observed_at`, `forecast_as_of`, `horizon_hours`, `predicted_value`, `uncertainty`, and `model_status`. Describe the uncertainty method and scope. Missing data leaves predictions and intervals `null`, with the gap explained; unknown does not mean zero. Name and validate eligibility counts, earnings-qualified impressions, and public views separately.

**Existing training covers total views only; this verified Home target has not been trained.** Neither that model nor the [popular-pool reference score](algorithm-time.md) can be relabeled as a trained earnings forecast. With enough real target labels, evaluate error on later observations held out by time and report sample size, windows, and remaining gaps. Forecasts do not guarantee revenue, eligibility, or causal effects.
