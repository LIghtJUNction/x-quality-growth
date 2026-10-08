# Model input contract: text, media, comments, and platforms

This is the proposed `rise-input-draft-1` contract, **not a format fully supported by the current parser**. It specifies evidence for a future model, not proof of trained semantic modeling or follower growth. See [growth statistics](growth-statistics.en.md) and the [algorithm field guide](algorithm-field-guide.md).

## Current implementation boundary

[predict_heat.py](../scripts/predict_heat.py) currently reads one post's publication time, observation times, and public views / owner impressions. It keeps surfaces separate, provides last-value and recent-rate baselines, and implements optional PyTorch CPU fitting of `I(t)=b+A×(1−exp(−t/τ))`. The three parameters are b, A, and τ; this is not a language or multimodal model. Fitting code does not establish a verified real-post training run or validated forecast. Text, images, video, subtitles, and comment semantics do not enter this predictor. There is no verifiable implementation evidence that a frozen encoder has been used.

**Text origin is a second prediction target. Current training does not include it; there are no measured origin-classification, calibration, or downstream heat improvements.** [authorship.py](../scripts/authorship.py) implements separate label validation, external-probability ingestion and auxiliary feature output, without running a detector. It checks declared IDs, timestamps and supplied material/event group IDs; actual group assignments, edited-post lineage, duplicate text and comment relationships remain independently unverified. The semantic and joint model still requires implementation and evaluation.

## Every sample needs identity and time

| Field | Contract |
| --- | --- |
| `platform` / `post_id` / `version` | Joint identity of the native post and content version. Do not join identities across platforms or count an edit as a second original. Targets and training rows use exact lowercase canonical platform labels without spaces; X uses `x`, rejecting `X`, `twitter`, `x.com`, and aliases rather than silently converting them. `post_id` has no surrounding whitespace; X IDs are positive ASCII decimal without leading zeros, while other platforms retain exact native IDs. Retain original/latest permalinks. |
| `published_at` | Actual first publication time with timezone; null before publication. Store `edited_at` separately; edits do not restart fixed observation windows. |
| `captured_at` / `prediction_at` | Actual sample collection time / prediction cutoff. Later backfilling must not impersonate historical availability. |
| Per-feature `available_at` | When the input was actually usable for the prediction. Text, counters, comments, and media features have separate availability times. |
| `count_sources` / `exposure_unit` | Native name, UI source, unit, capture time, and availability for each counter. Views and impressions retain their separate display-event definitions; neither defaults to unique people. Video plays are a separate metric. |
| `counts` / `aggregation` | Nonnegative integers or null; distinguish cumulative since publication, platform report period, and explicit intervals. Difference only matching metric/source/version counters. Missing is not zero; reconcile decreases first. |
| `text` | Available full body, language, and truncation/cleaning version. Characters and tokens differ; token lengths also require tokenizer version. Retain edits instead of substituting final text into early predictions. |
| `media` | Ordered assets with image/video/audio/GIF type, MIME, bytes, image/frame dimensions, video/audio duration, source version, and availability. Unknown size/duration is null. |
| `visual_embeddings` / `subtitles` | Encoder/transcription model version, weight fingerprint, extraction settings, actual sampling times, and availability. Unencoded/untranscribed values are null; automatic-transcription error remains unknown unless measured. |
| `preexisting_comments` | Visible pre-cutoff comments and coverage. Separate external comment count, `external_author_unique_count`, substantive comments, questions, and self comments; total replies are not unique external authors. |
| `missing_masks` / `privacy` | Missing-feature reasons and scope. Raw text/media, identities, screenshots, and embedding caches stay in private runs. Public output contains reviewed aggregates and authorized public links, not identity lists. |

Substantive/question labels can overlap and must not be summed into a total. Multiple comments by one author count as one external author. Without reliable identity deduplication, disclose the observed scope or use null rather than claiming true unique people. A brief “OK” is not automatically substantive technical feedback.

## Prepublication and postpublication are different tasks

**Prepublish** uses existing draft text/media and known publication plans. Exclude future post counters, future comments, and follower outcomes. A reply may separately use already-existing parent context, but it is not audience feedback to the unpublished reply. Planned time is not actual publication time.

**Postpublish** may add counters and comments actually available by the cutoff. Every feature must satisfy `available_at <= prediction_at`, with its real capture time retained. Later comments, final exposure, later text/subtitles, and 24/72-hour outcomes cannot be backfilled as early features. Store future outcomes separately as `target` labels, available only for later evaluation and never as contemporaneous prediction inputs.

## Second target: human-written, AI-generated, or mixed text

`content_origin` describes the **body text of a specified version**. Image/video provenance is separate and cannot be inferred from a text label. Manual versus automated publishing is outside this task; limited body text cannot establish backend publishing control either.

| Label | Apply a fixed, predefined `label_policy` |
| --- | --- |
| `human_written` | Evidence supports human authorship of substantive body text without generative-AI writing or rewriting. Treat ordinary spelling checks and formatting under fixed rules. |
| `ai_generated` | Evidence supports generative-AI production of substantive text, with human selection/formatting that does not materially rewrite it. |
| `mixed` | Both humans and generative AI materially write or rewrite the text, including human revision of AI drafts and AI revision of human drafts. This does not mean “exactly 50% AI.” |
| `unknown` | Reliable provenance is missing, contradictory, or ambiguous in scope. It is not a negative example of human authorship or an invented fourth origin class. |

Accept label evidence only from author disclosures tied to the post/version, or authorized records that establish generation/editing history. Publishing logs showing a click method do not establish text origin. Store `scope`, `label_policy`, evidence type/coverage, reliability, and `label_available_at`; distinguish self-reports from inspectable records. Define quotations, translation, AI polishing, and short-text boundaries in advance. Insufficient evidence stays unknown; style impressions, another detector's output, and blue badges cannot manufacture ground truth. Unknown-origin samples may still support a labeled heat task, but mask their origin supervision and exclude them from origin-accuracy denominators.

A future `origin_prediction` may independently output probabilities for `human_written` / `ai_generated` / `mixed`, model/calibration versions, prediction time, a decision, and rejection reasons. Available probabilities sum to 1; an untrained or unavailable prediction is null. These are model estimates within a specified training/evaluation scope, not verified provenance; `p(ai_generated)` is not the fraction of AI-written characters. Short text, unfamiliar domains/languages, or low confidence may yield `decision=unknown` rather than a forced binary answer. Origin probabilities are not content quality and do not change the established high-quality blue-follower rubric. Domain shifts, unseen generators, and rewriting can affect detection; published scores cannot simply be transferred to X posts. See the [RAID benchmark](https://aclanthology.org/2024.acl-long.674/) and [detection robustness research](https://arxiv.org/abs/2303.11156).

### Joint heat prediction without answer leakage

A future design may share text encoding while producing separate heat and origin outputs. Origin labels supervise that task's loss only; they are not inputs to either predictor. Labels obtained later can enter a later training run only after their availability cutoff; they must not rewrite historical inputs or predictions. Provenance evidence containing the direct answer is not merged into encoded body text.

If origin probabilities become heat features, generate **chronological out-of-fold predictions** for heat-training samples: fit the origin model and calibrator using earlier posts whose labels were already available, then predict later posts absent from their fitting data. Keep a post, its edits, and duplicate text in the same group. Future held-out data cannot select thresholds or calibration. Retain model identity, training cutoff, `available_at`, and original predictions; never backfill historical features with a future model. Both prepublish and postpublish retain their input-time rules. Missing compliant historical probabilities remain null with a missing mask.

For strict cross-post acceptance, call `auxiliary_features(record, strict_cross_post=True)` or use CLI `--auxiliary --strict-cross-post`. The target `post` and every `provenance.training_groups` row supply `content_group_id`. Original/edit chains, duplicate text/material, and derivatives of the same concrete event or trend share one group, including across platforms; merge groups connected by any such relationship. A broad subject such as “AI tools” is not one event group, and different native IDs do not establish independent content. Split by **actual first publication time**, then remove training members whose groups overlap held-out groups; never move future posts into training.

Upstream must freeze grouping evidence and the manifest before training or inspecting held-out errors. Strict validation requires the target's first `published_at` and all group IDs to be known; missing/null/explicit unknown groups cause rejection. The validator neither infers material relationships nor invents exact publication times. Different native IDs in the same group cannot supply auxiliary features, and input/label availability checks still apply. Legacy calls remain compatible, but records missing groups have `strict_cross_post_eligible=false`. Output establishes declared-group intersection checks only; `*_lineage_verified` remains false. There is no cross-post training result, measured origin detection, or certified Home model, and the existing n=1 prospective record gains no stronger status.

### Evaluate provenance and downstream heat separately

- **Classification:** On provenance-labeled held-out posts, report a three-class confusion matrix, class counts/prevalence, and per-class one-versus-rest PR-AUC. Specify curve integration versus average precision rather than treating them as interchangeable; absent classes yield null scores. Report unknown-label counts and exclusion reasons separately.
- **Probabilities:** Report Brier probability error with its multiclass scaling convention. ECE compares confidence with observed correctness by probability bin; publish bin rules, bin counts, and reliability diagrams. Small samples or changed bins do not establish stable calibration, and neither metric proves an individual post's origin. See the [official Brier documentation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.brier_score_loss.html) and [calibration research](https://proceedings.mlr.press/v70/guo17a.html).
- **Abstention:** Separate `label_coverage=labeled posts/collected posts` from `decision_coverage=three-class decisions/applicable prediction posts`. Also report decision coverage and decided-sample error within the labeled subset. Rejection is not a correct classification. Fix thresholds on validation data and evaluate only on test data. The coverage/error trade-off is described in [selective classification research](https://papers.nips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html).
- **Transfer:** Break down results by language, domain, length, author, known generator, and degree of mixing/rewriting. Preserve author/similar-text groups and chronological holdouts. Give sample counts for small groups; do not turn unknown into AI or force mixed text into binary labels. Publicly disclosed examples may differ from all posts; disclose that sampling bias.
- **Heat benefit:** With matched chronological splits, horizons, inputs, and budgets, compare heat-only training, heat plus an origin auxiliary task, and heat plus chronological out-of-fold origin probabilities. Report origin performance and heat error separately; tune task-loss weights only on training/validation data. Shared tasks can hurt each other, so improvement in heat or follower growth is not guaranteed. No such multitask ablation results currently exist.

## How media would enter a model

Keep original assets private and distinguish local/uploaded versions when they differ. Freeze a reproducible sampling policy first: fixed video intervals, maximum frame count, and resize settings. Record requested and actually decoded timestamps. Freeze subtitle/audio settings too; OCR may be an additional source rather than silently merged into body text. Do not select frames after seeing the engagement result.

A future design can cache outputs from existing pretrained text/vision/audio encoders, freeze their weights, and train a fusion layer with roughly **10,000–50,000 trainable parameters**. This is a design budget, not a trained model size or performance claim. Frozen encoders themselves may be much larger and are not used by the current implementation. Avoid training large encoders from scratch. Cache by content version, weight/preprocessing/sampling fingerprints. Missing media uses a missing mask, not a zero vector pretending encoding succeeded.

Compare matched-window ablations: time/count baseline, plus text, plus media, plus pre-cutoff comments, and full fusion. Keep a whole post and its versions/comments on one side of a split. Hold out posts or dates and evaluate forward in time; fitting, encoder selection, and thresholds use training data only. Refreshes do not create independent training samples. These ablations and cross-post validation have not been implemented.

## Lightweight schema draft and synthetic example

The snippet constrains only the outer structure. Per-feature provenance, platform mapping, and chronological comparisons require runtime checks. See the [official JSON Schema 2020-12 validation specification](https://json-schema.org/draft/2020-12/json-schema-validation) for structural/format vocabulary. This draft is not wired into a script.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Proposed RISE model input",
  "type": "object",
  "required": ["contract_version", "platform", "post_id", "version", "stage", "published_at", "captured_at", "prediction_at", "features", "missing_masks"],
  "properties": {
    "contract_version": {"const": "rise-input-draft-1"},
    "platform": {"type": "string", "minLength": 1},
    "post_id": {"type": "string", "minLength": 1},
    "version": {"type": "string", "minLength": 1},
    "stage": {"enum": ["prepublish", "postpublish"]},
    "published_at": {"type": ["string", "null"], "format": "date-time"},
    "captured_at": {"type": "string", "format": "date-time"},
    "prediction_at": {"type": "string", "format": "date-time"},
    "features": {"type": "object"},
    "missing_masks": {"type": "object"},
    "origin_labels": {
      "type": "object",
      "required": ["content_origin", "scope", "label_policy", "evidence", "label_available_at"],
      "properties": {
        "content_origin": {"enum": ["human_written", "ai_generated", "mixed", "unknown"]},
        "scope": {"const": "text.body"},
        "label_policy": {"type": "string", "minLength": 1},
        "evidence": {"type": "array"},
        "label_available_at": {"type": ["string", "null"], "format": "date-time"}
      }
    },
    "origin_prediction": {"type": "object"}
  }
}
```

**Entirely synthetic: not account evidence or a stored media artifact.** The example.com address, times, counts, and paths illustrate the contract. Media features have not been extracted in this example.

```json
{
  "contract_version": "rise-input-draft-1",
  "platform": "synthetic",
  "post_id": "synthetic-001",
  "version": "v1",
  "post_url": "https://example.com/posts/synthetic-001",
  "stage": "postpublish",
  "published_at": "2026-10-08T09:00:00+08:00",
  "captured_at": "2026-10-08T09:10:00+08:00",
  "prediction_at": "2026-10-08T09:10:00+08:00",
  "features": {
    "exposure_unit": "impression_events_not_unique_people",
    "counts": {"impressions": 40, "engagements": 3, "profile_visits": null},
    "count_sources": {
      "impressions": {"source": "synthetic_owner_analytics", "native_name": "impressions", "aggregation": "cumulative_since_publication", "captured_at": "2026-10-08T09:10:00+08:00", "available_at": "2026-10-08T09:10:00+08:00"},
      "engagements": {"source": "synthetic_owner_analytics", "native_name": "engagements", "aggregation": "cumulative_since_publication", "captured_at": "2026-10-08T09:10:00+08:00", "available_at": "2026-10-08T09:10:00+08:00"}
    },
    "text": {"body": "Synthetic example only.", "language": "en", "available_at": "2026-10-08T09:00:00+08:00"},
    "media": [{"type": "video", "duration_seconds": 12, "width": 1280, "height": 720, "file_size_bytes": null, "available_at": "2026-10-08T09:00:00+08:00", "private_asset_ref": "runs/synthetic/video.mp4", "frame_policy": "uniform-v1", "requested_frame_seconds": [0, 4, 8], "actual_frame_seconds": null, "visual_embeddings": null, "subtitles": null}],
    "preexisting_comments": {"captured_at": "2026-10-08T09:10:00+08:00", "available_at": "2026-10-08T09:10:00+08:00", "sample_complete": false, "external_count": 3, "external_author_unique_count": 2, "substantive_count": 1, "question_count": 1, "self_count": 1}
  },
  "missing_masks": {"profile_visits": "not_collected", "file_size_bytes": "unknown", "visual_embeddings": "not_encoded", "subtitles": "not_transcribed", "comment_population": "partial"},
  "privacy": {"raw_assets_and_identities": "private", "public_output": "reviewed_aggregates_only"},
  "target": {"metric": "impressions", "horizon_seconds": 3600, "value": null, "label_available_at": null},
  "origin_labels": {"content_origin": "unknown", "scope": "text.body", "label_policy": "synthetic-origin-policy-v1", "evidence": [], "label_available_at": null},
  "origin_prediction": {"probabilities": null, "decision": "unknown", "abstained": true, "reason": "not_trained", "model_version": null, "calibration_version": null, "prediction_at": "2026-10-08T09:10:00+08:00"}
}
```

## Shared measurement is not a universal recommendation model

Input and time rules can be shared. Each platform adapter retains native definitions, units, sources, and versions and verifies actual collection capabilities. X metric collection/statistics paths exist; other adapters remain unverified. Video plays cannot substitute for impressions, event totals are not unique users, and play counters with different thresholds must not be pooled blindly.

Define badges, stable identity, the quality rubric, and follower/subscription meanings per platform. X blue does not automatically map to another platform's verification or payment status. Source models, recommendation mechanisms, and calibration require separate evidence; this document makes no claim about another platform's current algorithm.

With enough data, consider platform-ID embeddings or platform-specific fine-tuning. With limited data, start with separate simple baselines and calibrations. Shared field names do not establish cross-platform generalization. Impression/engagement counts may be overdispersed; inspect distributions and align target horizons such as 60 minutes, 24 hours, and 72 hours. Partial comment samples, edits, concurrent publications, and traffic sources are confounders. Profile follower differences still do not provide post attribution. Report source observations, predictions, and verified growth separately on every platform.
