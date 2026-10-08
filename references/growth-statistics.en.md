# Growth statistics: computable quantities, missing data, and hypotheses

Use **X post analytics and recorded follower snapshots**. Public popularity is not a demonstrated acquisition mechanism. See the [measurement specification](measurement.md) and [algorithm field guide](algorithm-field-guide.md). X ranking weights multiply predictions or continuous predicted values; an operator's action counts cannot be substituted into the ranking formula.

## What can be calculated now?

Use hours for durations. Preserve each metric's observation time, UI source, post identity, and version. `null` means insufficient evidence; zero requires an actual zero observation.

| Metric | Definition and denominator | Availability / missing evidence |
| --- | --- | --- |
| Follower stock `F(t)` | Profile total at an observation | Recorded; not the number of follow events in a window. The initial 175 has no exact time and must not yield a rate. |
| Average net rate `v` | `ΔF / Δt`, followers/hour | Computable for timed observations. Gains and losses are not separated; joins followed by departures within the window may be invisible. |
| Net-rate slope `a` | Difference between two average rates / distance between their window midpoints, followers/hour² | Descriptive with at least three valid timestamps. Show unequal durations; this is neither instantaneous acceleration nor a strategy effect. |
| Relative net growth rate | `ΔF / (F_start × Δt)`, per hour | Requires a positive starting stock and exact times. It is not a future exponential growth parameter. |
| Blue stock `B(t)` / new blue arrivals `N` | Stock: confirmed blue identities in the current list. Arrivals: new stable IDs in complete all-follower snapshots whose after badge is blue | Verified-list counts are not blue stock; badge upgrades are not new followers. Current confirmed acquisition evidence is insufficient. Total net growth cannot supply N. |
| Impression-event rate / slope | Same-post, same-version, same-surface `Δimpressions / Δt`; slope uses window midpoints | Requires two counts. Public views and owner impressions stay separate. Reconcile decreases; their delta is null meanwhile. |
| Engagement-event ratio | Same-post, same-window `engagement_events / impression_events` | Calculable from matching analytics. Repeated actions and displays are possible; it is neither user probability nor unique reach. |
| Detail / profile-visit / link-click ratios | Each event count separately divided by the post's same-window impression events | Missing counts or zero denominator yield null. These are not strictly nested funnel stages. |
| Post-attributed follow conversion | Validly attributed follow events / a defined exposure or visit denominator | Null without attribution. Concurrent account growth is not a post's conversion count. |
| 24 / 72-hour cohort retention | Fraction of initial stable IDs still present in complete later follower lists | Requires later complete snapshots. Unfinished windows have no result; a renamed handle does not establish churn. |
| High-quality acquisition efficiency / return | Confirmed new high-quality blue followers `H / Δt`; separately `H / active_work_hours` | Null without confirmed identities, completed assessment, or measured work time. Observation duration is not work time. No financial ROI without revenue and cost evidence. |

The current `2/5 = 40%` describes five **newly observed blue identities** that were assessed. It is neither a representative sample nor a confirmed full acquisition population. Do not attach a population confidence interval or describe a 40% probability that the next follower is high quality. A separate `2/2` from an incomplete list must not be merged into this denominator.

## Rates and slopes with unequal intervals

For actual observations `t_i, F_i`, define `d_i = t_i - t_(i-1)`:

```text
v_i = (F_i - F_(i-1)) / d_i
m_i = (t_i + t_(i-1)) / 2
a_i = (v_i - v_(i-1)) / (m_i - m_(i-1))
    = 2 × (v_i - v_(i-1)) / (d_i + d_(i-1))
```

`a_i` is the slope between two interval-average net rates. Do not replace midpoint distance with the latest refresh interval or read a five-minute zero followed by a seventy-minute increase as an instantaneous jump. A percentage rate increase from zero is undefined. Resolve duplicate/missing timestamps, stale UI values, and overlapping collections first. Show observations and window lengths; connecting lines do not reconstruct the unseen path.

Only complete event evidence supports `ΔF = G - L` and `v = G/Δt - L/Δt` for gross gains and losses. Endpoint identity differences instead record arrivals still present and departures still absent, excluding unobserved within-window cycles. “Speed” and “acceleration” here are mathematical differences, not physical mechanism laws.

## Prioritize post analytics without inventing funnel probabilities

For post `j` and actual window `[t0,t1]`, calculate separate changes in impressions `ΔI_j`, engagements `ΔE_j`, detail opens `ΔD_j`, profile visits `ΔP_j`, and link clicks `ΔC_j`. Use the same metric definition, post version, and analytics surface at both ends. A missing first observation is not an implicit zero. Record actual post age and collection lateness relative to the original publication.

- `ΔE_j / ΔI_j` is an event ratio. A person may generate multiple actions or displays, so it may exceed 1; this is not a user probability above 100%.
- Show `ΔD_j/ΔI_j`, `ΔP_j/ΔI_j`, and `ΔC_j/ΔI_j` independently. A click need not pass through a detail open or profile visit. Do not multiply these ratios into a follow probability.
- Label cumulative ratios and interval-change ratios separately. Summed post impressions are event totals, not unique people. Edited versions and a shared conversation cannot be treated as disjoint audiences.
- `1000 × ΔF / ΣΔI` is at most a same-window co-observed net follower change per thousand impression events. It may be negative and is not attributed follow conversion. Disclose incomplete exposure coverage, including other posts, search, profiles, and concurrent operators.

Log owner likes, replies, page opens, and other actions separately. If they cannot be removed from totals, independent-audience counts remain unknown; never guess a deduction. Unobserved negative feedback also remains unknown. Do not encourage repeated or artificial interactions to inflate a ratio.

## Quality, follower/following balance, and retention

Keep the `public-v1` content gates: relevance, originality, and substance. Review at least three recent originals and preserve public evidence. All three must pass for high; insufficient evidence is unknown. Blue is a scope condition. An attractive ratio must not rewrite historical classifications or relax the gates.

When a single profile observation supplies followers `f` and following `g`, report a separate network signal `s = ln((f+1)/(g+1))`. `ln` means natural logarithm; `+1` only smooths zeros. This is **not a quality cutoff, authenticity judgment, or mutual-follow rate**. Missing counts or times yield null. The raw `f/g` is undefined at `g=0`; the smoothed signal is not the raw ratio. Initially use it to order manual reviews; any improvement in discovering relevant high-quality accounts requires future labeled evidence, rather than a threshold chosen after a few successes.

Keep two denominators distinct:

- **New-blue quality share:** `H_new / N_new`. Unknown quality U remains in N, giving classification bounds `[H_new/N_new, (H_new+U)/N_new]`, not confidence intervals. N=0 is undefined. Partial or verified-only lists describe captured cohorts; full-window share is null.
- **Stock quality density:** high-quality blue identities in a complete current all-follower list, `H_stock / F_stock`. If all badges are known but some blue quality is unclassified, bounds are `[H_stock/F_stock, (H_stock+U_blue)/F_stock]`. Assessing only arrivals does not support an account-wide density. Incomplete coverage means population density is null.

Freeze the initial blue cohort and its high-quality subset. Measure identity retention and blue-badge retention separately at 24/72 hours. Keep initial eligible stable IDs as the denominator despite losses or later reclassification. Preserve actual subsequent snapshot times. If only first observation is known, call it retention since first observation, not since the actual follow. Zero denominator, incomplete lists, unstable identity, or an unobserved deadline mean full retention is null.

## Testing joint exposure and acquisition patterns

Preregister a single-variable post experiment: primary outcome (prefer confirmed new high-quality blue followers/hour; use analytics first at post level), minimum practically valuable difference δ, decision rule, fixed windows, and stopping rule. Form comparable blocks using topic, format, post age, time slot, and date; randomize the one changed variable and publication order within blocks. Record parallel posts, paid promotion, follow actions, and audience size. Blocking controlled nuisance factors and randomizing others follows [NIST's randomized-block design guidance](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm); this specific X design remains the skill's proposed experiment.

Observe at 60 minutes, 24 hours, and 72 hours after publication. Keep early/late actual times. Refreshes are not new experimental units: repeated samples of one post, replies to one author, and overlapping windows are dependent. For uncertainty analysis, resample the actual assignment/dependence units, such as post or date blocks, rather than individual page refreshes. Too few blocks support description only.

There is no universal “30 people proves significance” threshold. Use a pilot to estimate variability, clustering/repetition, and observation cost; plan the number of post/date blocks for δ and the required power before formal collection. Without sufficient inputs, do not claim power or valid confidence intervals. A completely assessed cohort's H/N is its observed composition. Binomial intervals such as Wilson require an explicit representative, independent sampling interpretation; the current five-identity cohort does not support population inference. Repeatedly checking until a favorable result appears is not a preregistered win.

With adequate cross-day data, nonnegative confirmed arrival counts, and reliable exposure windows, compare a **candidate** negative-binomial model: `Y_t ~ NB(μ_t, k)` and `log μ_t = log(exposure_t) + content/time/date covariates + preregistered lag terms`, with strictly positive exposure. [MASS's official glm.nb documentation](https://stat.ethz.ch/R-manual/R-devel/library/MASS/html/glm.nb.html) supports negative-binomial fitting and a formula offset. Suitability for this account and the offset's fixed exposure elasticity of one still require validation.

Y must be a consistently defined nonnegative arrival count. A potentially negative net follower change cannot be a Poisson/negative-binomial response. With G/L evidence, consider separate gain and loss models; with net totals alone, retain descriptive analysis. Exposure and acquisition can share causes such as content or concurrent operations; lagged association is not causation. Until fitted, validated, and assessed for confounding, model parameters, future success probabilities, and exponential forecasts remain unavailable.
