# Reuse actual data before training a small model

[简体中文](data-reuse.md) · [Input contract](model-inputs.en.md) · [Statistical methods](growth-statistics.en.md)

Reuse existing counters, text and public research resources, then collect genuinely missing fixed-window observations. Readable resources, acquired samples, full downloads, encoded features, completed training and validated results are separate states.

## X: visible rows read, full export incomplete

The [X owner Content list](https://x.com/i/account_analytics/content) was actually viewed, with Date, Impressions, Likes, Replies, Reposts and truncated text. **Six actual snapshots from 2026-10-08 03:48:02.373 to 03:51:37.900 UTC** yielded **99 distinct posts, 146 capture records and zero parsing failures**. Repeated refreshes are not independent training samples; 99 is not the count of fully labeled training examples. [X metric definitions](https://business.x.com/help/tweet-activity-dashboard).

Displayed calendar dates span **2026-07-17 to 2026-10-08**, with unknown timezone and all `published_at` values null. Text-origin labels remain unknown; aggregation is retained as `unknown_report_window`. Coverage is partial, not a complete three-month dataset. Rows retain native fields, post links, filters and actual capture times. Records stay in ignored private `runs/`, without publishing raw text or identity lists.

The CSV download event timed out; no successful file is established. Browser policy prohibited access to download history, so collection switched to the visible list without bypassing that restriction. A complete three-month export is not claimed.

A historical post's currently visible count can only label **the current observation time and that UI's metric scope**; an unverified reporting window is not automatically lifetime impressions. Even a separately confirmed cumulative value cannot manufacture historical one-hour or 24-hour snapshots; those targets remain null. A displayed date does not establish an exact publication second. Retain truncation flags rather than claiming full text. Text edits, comments, media and counters each need actual `captured_at` and `available_at`; later collection cannot backfill earlier prediction inputs.

## TPIC2017: four small metadata samples

The authors' [TPIC2017 repository](https://github.com/social-media-prediction/TPIC2017) and [project page](https://social-media-prediction.github.io/TPIC2017/) link four ZIP files. Anonymous HTTP Range requests read the first 65,536 bytes of each, then decoded the first 100 lines of the first text entry in memory. All four returned HTTP 206; total bytes read were 264,192, including four earlier 512-byte probes. **No complete ZIP or images were downloaded.** The review conclusion was recorded at **2026-10-08 03:49:35 UTC**; exact HTTP acquisition times were not retained, so this is not a download timestamp.

| Text entry | Observed header |
| --- | --- |
| `USER_META.txt` | `pid uid commentcount haspeople titlelen deslen tagcount avgview groupcount avgmembercount` |
| `LABELS.txt` | `pid uid logviews` |
| `TIMEFLAG.txt` | `pid uid year month day hour_index` |
| `PHOTOURL.txt` | `pid uid url` |

`haspeople` means people appear in an image; it is not a human/AI/mixed text-origin label. Title length is not title text, and an image URL does not prove acquisition or encoding. The [original paper](https://www.ijcai.org/proceedings/2017/0427.pdf) defines popularity as `log2(total views / days since publication) + 1`. These files provide a static value without raw views, denominator days, collection times or repeated 1h/24h observations; those growth curves cannot be recovered.

`TIMEFLAG` provides year/month/day and four-hour bins, not exact publication times. Sampled dates include 2001–2006 and cannot be directly reconciled with the repository's stated 36-month coverage; full temporal coverage remains unverified. This is Flickr research data, not X impressions. The author pages request citation but provide no explicit data/image license found in this review. Anonymous downloadability does not establish permission to publish a mirror; retain that licensing gap.

## RAID: four origin samples read, no training

The [RAID author repository](https://github.com/liamdugan/raid) directly links the [author dataset card](https://huggingface.co/datasets/liamdugan/raid). In `train` / `extra`, `model == 'human'` identifies human source text; other named models identify generated origins. Public `test` origin labels are hidden. The 11 observed fields are `id, adv_source_id, source_id, model, decoding, repetition_penalty, attack, domain, title, prompt, generation`; there is no separate numeric label column.

Two anonymous HTTP 200 requests from **2026-10-08 03:52:40.357756 to 03:52:42.606995 UTC** read [2 human rows](https://datasets-server.huggingface.co/rows?dataset=liamdugan%2Fraid&config=raid&split=train&offset=0&length=2) and [2 mpt rows](https://datasets-server.huggingface.co/rows?dataset=liamdugan%2Fraid&config=raid&split=train&offset=100000&length=2), totaling 9,769 bytes for that round. This was partial schema/sample verification, not a full download, training or benchmark run. The mpt rows include the `perplexity_misspelling` attack and are not a clean, balanced test set.

Declared languages are en/cs/de, plus code, without a Chinese declaration. Article and Reddit data do not establish performance on X posts or provide mixed-origin labels under our contract. Origin inputs use only `generation` body text, excluding answer-leaking metadata such as `model`, missing prompts, attack and decoding. Group originals and variants using `source_id`, with `adv_source_id` for lineage; related variants cannot cross train/test splits.

The [code LICENSE](https://github.com/liamdugan/raid/blob/main/LICENSE) is MIT; the [dataset card](https://huggingface.co/datasets/liamdugan/raid/blob/main/README.md) separately declares `license: mit`. This does not independently establish the complete rights chain for every underlying news, book or other source passage.

## HC3: a small Chinese QA sample read

The [HC3 author repository](https://github.com/Hello-SimpleAI/chatgpt-comparison-detection) directly links [HC3-Chinese](https://huggingface.co/datasets/Hello-SimpleAI/HC3-Chinese). An anonymous Range request from **2026-10-08 03:54:02.415128 to 03:54:04.533263 UTC** read the first 8,192 bytes of [open_qa.jsonl](https://huggingface.co/datasets/Hello-SimpleAI/HC3-Chinese/resolve/main/open_qa.jsonl), returning HTTP 206 with a stated full size of 6,529,129 bytes. The first complete object contains only `question`, `human_answers` and `chatgpt_answers`; the answer groups provide human and early-ChatGPT provenance from which text labels can be derived under fixed rules. There is no numeric or mixed-origin label.

This remains sample/schema verification, without a large download or training. Chinese QA is not X short text or evidence of detection performance on 2026 models. The [author dataset card](https://huggingface.co/datasets/Hello-SimpleAI/HC3-Chinese/blob/main/README.md) declares CC-BY-SA-4.0 and requires stricter source terms to be followed. The original `open_qa` source being MIT does not make the released HC3 output MIT.

## SEISMIC: preparation-stage record, later training below

Using the authors' [SEISMIC project page](https://snap.stanford.edu/seismic/) and [paper](https://snap.stanford.edu/seismic/seismic.pdf), two source files were fully acquired from **2026-10-08 09:53:23.757982 to 09:57:36.848653 UTC**, both HTTP 200, totaling **307,455,420 actual bytes**. At the preparation verification recorded at **10:12:21.530980 UTC**, the derived table was complete and new training had not started. Download access does not establish permission to publish a data mirror. Raw IDs, CSV, text and individual information remain private; only aggregate preparation status and official source links are published here.

The final identity audit accepts only canonical ASCII decimal source IDs, without guessing identities from low-precision scientific notation. **139 noncanonical-ID segments** and **all 8 segments belonging to 4 repeated IDs** were quarantined: **147 segments in total**. The final table contains **165,929 unique, non-repeated source-post cascades and 331,858 derived rows**. The initial raw-string candidate is retired, not the final dataset size or a training table. Verification covers all canonical source identities and paired-window integrity, with derived results for **1,000 cascades** cross-checked against source events.

Each cascade has one row at **15 minutes** and one at **60 minutes**. Inputs use only cutoff seconds, the retweet count and first/last event times available by that cutoff; the target is **additional retweets after the cutoff through post age 24 hours** (`cutoff < t <= 86400`). Future events and target totals are excluded from inputs. Both rows from a source post remain in the same split and are not two independent posts. Different source IDs do not establish independent authors or topics; author, duplicate-text and topic groups remain unknown.

| Strict chronological split | Source-post cascades, each with two cutoffs |
| --- | ---: |
| Training candidates | 59,565 |
| Purged label-maturity overlap | 12,193 |
| Later evaluation candidates | 94,171 |

The split follows the historical relative first 7 days / next 8 days, additionally purging training candidates whose 24-hour labels mature after day 7. Historical availability is not invented from today's download time. These are prepared candidate splits, without model fitting, validation tuning or performance comparison yet.

The source is **2011 English, hashtag-free posts**, described by the authors as selected using at least 50 future retweets; this introduces success-selection bias. After excluding the original-post event, **1,280 full-source segments actually contain 49 retweets each**; the cause is unverified. The release's maximum event time is **604,799 seconds, less than 7 days**, so the paper's 14-day follow-up completeness is not established. These anomalies describe the full source, not every final-table row. The final table retains **1,743 zero-at-cutoff cases at 15 minutes and 720 at 60 minutes**, including the purged split, but all have retweets by 24 hours. They cannot validate performance on general zero-traffic posts; zero additional-retweet targets are also retained. Views, verified Home impressions, text and text-origin labels are unavailable; transfer to the current Chinese account is unvalidated.

## Supervise heat and origin separately

Heat and text origin are separate label tasks. Heat retains platform, metric, post age and observation window. Origin describes a specified body-text version, supported by author disclosure or authorized generation/editing records, with `label_policy`, evidence and `label_available_at`. Define human-written, AI-generated and mixed under fixed rules; inadequate evidence stays unknown. Detector guesses, badges, publishing methods and TPIC's `haspeople` cannot manufacture ground truth. Unknown-origin samples may still carry actual heat labels, while their origin loss is masked. [Origin-label rules](model-inputs.en.md#second-target-human-written-ai-generated-or-mixed-text).

## Reuse and validation order

1. Inventory actually acquired samples, metric definitions, licenses, versions and times. Mark incomplete coverage; keep raw text, media, identities and caches in private `runs/`.
2. Start with time/count baselines. Freeze pretrained encoder weights and preprocessing when reusing them; bind caches to content versions, weight fingerprints and actual availability. Train only a lightweight head. Encoder caching and semantic training are future steps, not completed features.
3. Prepare heat labels and provenance-supported human/AI/mixed labels separately. Origin ground truth is not a prediction input. Any origin prediction used by heat must be chronological out-of-fold output; never backfill past inputs with a future classifier.
4. Group posts, edits, duplicate text/media, conversations and authors, then hold out forward in time. Related content cannot cross train/test splits. Both tasks use the same isolation: fit normalization on training data only, select thresholds, features and hyperparameters on validation data, and reserve test data for final evaluation.
5. Report heat error, origin classification/calibration/abstention, coverage gaps and language transfer separately. Compare simple baselines with added features. Synthetic examples test formats, not actual training, predictions or follower growth.

The previously published views prototype consists of two separately fitted [per-post time/count curves](https://huggingface.co/LIghtJUNction/RISE-heat-baseline). The text-origin target is untrained. This page does not claim a generalizing semantic/multitask model or demonstrated high-quality follower acquisition. [Measured results](../README.en.md#statistics-and-prediction-test-against-actual-error).

## Subsequent training status: SEISMIC retweet-v2 completed

The experiment record at **2026-10-08 10:29:36.524651 UTC** confirms subsequent training completed; the earlier **10:12:21.530980 UTC** “not trained” statement remains the preparation state at that time. This experiment is separate from the published two-post view curves with the later HF publication and anonymous verification recorded below. The GitHub result artifacts contain only [aggregate evaluation](../public/retweet-benchmark.json) and [result charts](../README.en.md#statistics-and-prediction-test-against-actual-error) ; raw source IDs, CSV and per-row predictions are excluded.

Each tiny MLP actually has **241 parameters, 482 across both cutoffs**, using **one CPU thread**. The five actual inputs are `log1p_observed`, `first_fraction`, `last_fraction`, `cold_indicator` and `cutoff_fraction_24h`, using only events available by the cutoff. The target remains **additional retweets after the 15-minute / 60-minute cutoff through post age 24 hours**, not cumulative views, next-hour exposure, verified Home impressions or text origin.

The experiment uses the **165,929 canonical, non-repeated cascades and 331,858 paired rows** above, with chronological **59,565 training / 12,193 purge / 94,171 test cascades per cutoff**. Outer training is further split chronologically into **23,779 fit / 11,964 label-maturity-overlap purge / 23,822 validation**. Validation alone selected **14 epochs at 15 minutes and 10 at 60 minutes**, followed by refitting on all outer training data and **one** final outer-test evaluation. Two cutoffs from a post are not independent samples. Author, duplicate-text and topic groups remain unknown; their isolation is not established.

The five models' test MAEs at 15 / 60 minutes are: zero additional **109.18 / 76.34**; constant training-target median **77.85 / 59.33**; early constant rate **7,000.12 / 2,402.23**; training-count bucket median **63.18 / 47.08**; tiny MLP **60.40 / 45.71**. The overall **4.41% / 2.90%** reductions versus bucket are descriptive, with unknown confidence intervals. **For the 15-minute zero-retweet subgroup, n=881, MLP MAE 61.98825 exceeds bucket 61.72304. Across the 60-minute test, p90 absolute error 105.18341 also exceeds bucket 105.00000.** The model does not win everywhere.

The experiment retains the limitations of **2011 English hashtag-free data, future-success selection, unknown author / duplicate-text / topic groups and unresolved data licensing**; raw data are not mirrored. Current-account views, high-quality follower acquisition, verified Home impressions and text-origin classification are not validated. Language transfer and statistical superiority remain unknown.

## Reproduce preparation and training

The new retweet model is published on [Hugging Face](https://huggingface.co/LIghtJUNction/RISE-retweet-baseline), pinned to `1282fc5e88e64073bf680b0dda21663f19b73c69`, separately from the old views prototype. All seven anonymous file downloads matched their SHA values and synthetic inference passed. [Public release verification](../public/hf-retweet-release.json). MIT covers this project's code and numerical parameters, not relicensing the source data.

Use Python 3.11+ and PyTorch from its official distribution. The actual CPU run used Python 3.14.7, PyTorch 2.14.0 and one thread; different hardware or versions need not be bit-identical. The following downloads about 307 MB directly from the authors into a fresh local directory and does not upload data. Preparation outputs must be fresh/empty; training runs refuse overwrite.

```sh
python3 scripts/prepare_retweets.py --output runs/seismic-local
python3 scripts/retweet_benchmark.py plan --input runs/seismic-local/retweet-features.csv --provenance runs/seismic-local/prepared-summary.json --output runs/retweet-local --expected-input-sha256 f17d46503f68474ef777d59e4398e6c9faba9eb5ee9ed67238b861ae3768763b
python3 scripts/retweet_benchmark.py train --plan runs/retweet-local/plan.json
```

`plan` only validates and freezes sources, input, splits and configuration. `train` consumes the fixed plan once; numerical models and baselines freeze before the final test. An actual offline preparation reproduction matched the full input SHA exactly, preserved original HTTP retrieval times, verified paired rows and crosschecked 1,000 source cascade labels. It did not retrain or retune on the test set.
