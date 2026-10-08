# Freeze the forecast before reading the outcome

This is a real prospective baseline experiment. **The target is post age 60 minutes, not one hour after the forecast origin.** One target-window observation is complete; the exact age-60-minute count remains unknown. Outcomes live in a separate evaluation artifact; never backfill the sealed forecast.

## Sealed case

Post: [2108064574675247167](https://x.com/LIghtJUNction_x/status/2108064574675247167). The [forecast](../public/forecasts/rise-2108064574675247167-60m.json) concerns this post's cumulative `public_views`, not unique people, verified Home impressions, or followers.

| Item | UTC / value |
| --- | --- |
| Actual publication | 2026-10-08 05:18:55 |
| Initial verification | 05:19:44.193, views=null; never an invented zero |
| First numeric observation | 05:33:06.364, 6 views |
| Second numeric observation | 14 views; capture 05:49:55.368–05:49:55.484, with completion as a conservative availability anchor |
| Actual freeze | 05:52:29.751596 |
| Target | 06:18:55, post age 3,600 seconds |
| Origin age / forecast horizon | 1,860.484 seconds (31.008 minutes) / 1,739.516 seconds (28.992 minutes) |
| Constant / recent-rate prediction | 14 / 27.79035991755193 views |

The recent-rate rule is `14 + (14−6)/1009.12 × 1739.516`. Only two real same-source numeric observations enter the calculation; there is no synthetic zero at publication. Score errors using the sealed full-precision values. Neither baseline trains a model. Existing PyTorch parameters were separately fitted to older posts and cannot simply transfer here; Torch and verified Home predictions are null.

Public evidence: [commit e792e377](https://github.com/LIghtJUNction/x-quality-growth/commit/e792e3771668e3f4945a0b90f257eb84a5a44bfa) and [CI 37734667646](https://github.com/LIghtJUNction/x-quality-growth/actions/runs/37734667646), created at 05:53:29Z and updated to completed/success at 05:53:39Z, before the target. Forecast SHA256:

```text
cce55596ad1674e503e5f92f38a163c55b2ef5d6e47a8695669e64a9fe5579ab
```

The [separate evaluation](../public/forecasts/rise-2108064574675247167-60m.evaluation.json) and [result chart](../assets/prospective.svg) record **26 public views at 06:19:28.906Z**, the first numeric post-target capture according to the operator declaration. Actual age is **60 minutes 33.906 seconds**, **33.906 seconds late**, within the declared budget. This is a window proxy, with `exact_target_actual=null`. Absolute errors are **12** for the constant baseline and **1.7903599175519282** for recent rate. Recent rate was closer on this one outcome; `n=1` establishes neither stable superiority nor follower-growth causality. The sealed forecast remains unchanged, with its outcome null.

## Capture and evaluate

The declared late budget is **0–300 seconds**, 06:18:55Z–06:23:55Z. This is an operating budget, not an X algorithm parameter. Select the first successful same-source numeric read after the target and retain failed/missing reads. Captures starting before or straddling the target, or completing after the budget, are excluded from the primary matched-window comparison; numeric diagnostic errors remain recorded. A delayed read retains its actual age/lateness and is a window proxy, with `exact_target_actual=null`.

This is an **uncaptured template, not an actual target result**. `observations=[]` means no outcome; do not supply guessed counts. Save privately, for example as `runs/quality-followup-20261008/actual.json`:

```json
{
  "contract_version": "rise-prospective-actual-1",
  "forecast_id": "rise-2108064574675247167-60m",
  "post_url": "https://x.com/LIghtJUNction_x/status/2108064574675247167",
  "version": "published_version_no_edit_evidence",
  "source": "public_views",
  "metric": "views",
  "first_successful_numeric_read_at_or_after_target": false,
  "observations": []
}
```

After real capture, each observation requires `actual` (nonnegative integer or null), `observation_started_at`, `observation_completed_at`, and `observed_at` equal to completion. Set the first-read declaration true only when justified; alternatively declare `observation_history_complete_since_target=true` and supply the complete range. **The evaluator checks supplied records; first-read/completeness assertions do not independently prove no omitted reads or backfilled timestamps.** Do not mix owner impressions or edited-version counters.

```bash
sha256sum public/forecasts/rise-2108064574675247167-60m.json
python scripts/evaluate_forecast.py \
  public/forecasts/rise-2108064574675247167-60m.json \
  runs/quality-followup-20261008/actual.json \
  --forecast-sha256 cce55596ad1674e503e5f92f38a163c55b2ef5d6e47a8695669e64a9fe5579ab \
  --output runs/quality-followup-20261008/evaluation.json
```

The [evaluator](../scripts/evaluate_forecast.py) verifies forecast/input-snapshot hashes, performs no training, and never rewrites the forecast or an existing output. The empty template yields pending, not a completed observation.

Errors are `prediction−actual`, absolute error, and squared error. sMAPE is `200×|prediction−actual|/(|prediction|+|actual|)`, with zero versus zero defined as 0. Missing outcomes have no error. A later count below 14 retains diagnostic errors and an apparent-revision flag, but is excluded from primary comparison until reconciled; never clamp a negative increment to zero. One outcome (`n=1`) supplies a descriptive error, not stable model superiority, calibration, or follower-growth causality. Operator opens may contribute to views.
