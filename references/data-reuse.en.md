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

## Supervise heat and origin separately

Heat and text origin are separate label tasks. Heat retains platform, metric, post age and observation window. Origin describes a specified body-text version, supported by author disclosure or authorized generation/editing records, with `label_policy`, evidence and `label_available_at`. Define human-written, AI-generated and mixed under fixed rules; inadequate evidence stays unknown. Detector guesses, badges, publishing methods and TPIC's `haspeople` cannot manufacture ground truth. Unknown-origin samples may still carry actual heat labels, while their origin loss is masked. [Origin-label rules](model-inputs.en.md#second-target-human-written-ai-generated-or-mixed-text).

## Reuse and validation order

1. Inventory actually acquired samples, metric definitions, licenses, versions and times. Mark incomplete coverage; keep raw text, media, identities and caches in private `runs/`.
2. Start with time/count baselines. Freeze pretrained encoder weights and preprocessing when reusing them; bind caches to content versions, weight fingerprints and actual availability. Train only a lightweight head. Encoder caching and semantic training are future steps, not completed features.
3. Prepare heat labels and provenance-supported human/AI/mixed labels separately. Origin ground truth is not a prediction input. Any origin prediction used by heat must be chronological out-of-fold output; never backfill past inputs with a future classifier.
4. Group posts, edits, duplicate text/media, conversations and authors, then hold out forward in time. Related content cannot cross train/test splits. Both tasks use the same isolation: fit normalization on training data only, select thresholds, features and hyperparameters on validation data, and reserve test data for final evaluation.
5. Report heat error, origin classification/calibration/abstention, coverage gaps and language transfer separately. Compare simple baselines with added features. Synthetic examples test formats, not actual training, predictions or follower growth.

Existing actual training remains the published [per-post time/count curves](https://huggingface.co/LIghtJUNction/RISE-heat-baseline). The text-origin target is untrained. This page does not claim a generalizing semantic/multitask model or demonstrated high-quality follower acquisition. [Measured results](../README.en.md#statistics-and-prediction-test-against-actual-error).
