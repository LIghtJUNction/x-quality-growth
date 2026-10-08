# 算法中的时间参数 / Time parameters in the algorithm

核对来源：X 官方 `xai-org/x-algorithm`，固定提交 **`78460ca8b65c57ddd3a05f9217c8aaeba214b628`**。下面区分候选硬过滤、排名资格、训练标签、模型特征、缓存和请求超时。公开默认不是本账号的线上配置；请求会匹配 feature switches，并可接受覆盖值。[配置入口][fs]

Reviewed source: the official X repository at the commit above. Candidate filters, ranking eligibility, training labels, model features, caches, and request deadlines serve different purposes. Public defaults do not establish this account's effective production configuration; recipient feature switches and overrides can change request parameters.[配置入口 / Configuration entry][fs]

**源码没有支持“发帖后黄金 5 分钟或 30 分钟必爆”的结论。** 30 分钟确实出现在年龄监控分组和热门池公式下限中；5 分钟出现在行为聚合请求、后台任务间隔等位置，不能混成一个增长窗口。

**These findings do not establish a guaranteed first-five-minute or first-thirty-minute growth window.** The same duration can appear in unrelated monitoring, normalization, request, and background-job settings.

## 候选范围与时间特征 / Candidate scope and time features

| 参数 / Parameter | 数值与条件 / Value and conditions | 含义 / Meaning |
| --- | --- | --- |
| Home Phoenix `MAX_POST_AGE` | **172,800 秒 / seconds = 48 小时 / hours**。[常量][max-age]；[AgeFilter 接线][pipeline-age] | 根据 `candidate.tweet_id` 求年龄；超过上限或无法求年龄则移除。[过滤实现][age-filter] **此管线硬过滤 / Hard filter in this pipeline**, not a universal lifetime for all X posts. |
| Thunder 留存 / retention | CLI 默认 **172,800 秒 / seconds**。[启动参数][thunder-args]；[插入过滤][thunder-store] | 存储接收的帖子对象必须早于当前时间且年龄不超过留存期。A storage eligibility rule; not a guarantee of distribution for 48 hours. |
| 转贴时间 / Repost time | Thunder 保存转贴事件自己的 `created_at_secs` 与 `post_id`；原帖 ID 另存。[事件][retweet-event]；[候选映射][thunder-map] | 上述 Home 年龄过滤看候选 ID，不能统一改成原帖的年龄。This path retains the repost object's identity separately from its source; it does not guarantee that reposting restores reach. |
| TweetMixer 候选 / candidates | 本地年龄上限 **48 小时 / hours**。[本地过滤][tweetmixer]；源开关默认 **false**。[开关][source-flags] | 还需非 `in_network_only`、无已有候选缓存。Conditional source-level filter, not evidence that the source is active for this account. |
| SimClusters | 候选默认上限 **48 小时 / hours**；种子帖子创建年龄上限 **90 天 / days**。[参数][sim-age]；[种子常量][sim-seed-limit]；[种子与条件][sim-seeds] | 源默认开启，还需非纯内圈、无候选缓存、有帖子行为信号。90 days refers to seed-post creation age, **not** a 90-day lookback of when interactions occurred. |
| Following reverse chronology | recall 最大范围 **365 天 / days**。[范围与查询][following-age]；[管线接线][following-pipeline] | 有关注列表才启用，按时间召回。A different feed path; this is why the Home 48-hour filter cannot be generalized to all X surfaces. |
| Home 冷启动插入 / cold-start insertion | 帖子年龄默认 **≤7,200 秒 / seconds = 2 小时 / hours**。[默认][cold-default]；[候选资格][cold-rank] | 还需非回复/转贴、作者粉丝不超过默认 50,000、Home 展示低于默认 200、排名位置和实验分组符合条件。[其他条件][cold-conditions] Ranking eligibility for a selected candidate; not a universal recommendation cutoff. |
| 检索冷池 / Retrieval cold pool | 默认年龄参数 **7,200 秒 / seconds**，但 `split_home_checkpoint=False` 默认。[配置][cold-pool-config]；[常量][cold-pool-limit] | HOME_COLD/HOT 分片才按新旧分池，HOT 取反；导出与推理条件满足才修剪冷池，乱序时跳过，并保留至少 `large_k` 个最新项。[分片][cold-pool-load]；[导出][cold-pool-export]；[推理][cold-pool-infer] Conditional pool trimming with a minimum retained population, not a global two-hour cutoff. |
| 帖子年龄特征桶 / Post-age feature buckets | 默认粒度 **60 分钟 / minutes**，范围 **4,800 分钟 / minutes = 80 小时 / hours**。[实现][age-buckets] | 超范围进入 overflow；未知或未来时间进入桶 0，**不删除候选**。An embedding feature, not a hard filter or a best posting time. |
| 年龄监控分组 / Monitoring groups | **≤30 分钟、≤1/6/12 小时、≥24 小时 / minutes and hours**。[常量及分类][age-metrics] | 仅标记 `true_tweet_types`。Monitoring labels, not first-thirty-minute ranking rules. |

## 热门池公式 / Popular-post pool formula

热门池的 `quality()` 有明确公式，但不是已校准的未来浏览预测。[公式与默认][popular-formula]

The popular-post pool has an explicit age-normalized `quality()` heuristic; it is not a calibrated prediction of future views.[Formula and defaults][popular-formula]

令当前浏览为 `V`，帖子年龄为 `t` 小时：

Let `V` be current views and `t` be post age in hours:

```text
lambda = ln(2) / 8
Q(V, t) = V * (1 - exp(-lambda * 24))
              / (1 - exp(-lambda * max(t, 0.5)))
```

- **8 小时 / hours**：曲线半衰参数，不是本帖流量每 8 小时减半的实测结论。
- **0.5 小时 / hours = 30 分钟 / minutes**：公式年龄下限，避免年龄接近零时分母过小；**不是 0.5 分钟**，也不是早期未爆就失败的截止线。
- **24 小时 / hours**：此池选择的帖子年龄窗口；负年龄或超过窗口的帖子被排除。[选择逻辑][popular-selection]
- 每作者默认保留 **5** 个，整个池默认 **500** 个；这是候选池预算，不是每日发帖上限。[选择逻辑][popular-selection]

The eight-hour parameter shapes the normalization curve. The half-hour floor limits the correction for very young posts. The 24-hour window bounds this pool's selection. The per-author and pool caps are candidate budgets, not posting quotas.

后台任务只在显式启动 `popular_posts_job` 或一次运行选项时执行，CLI 默认间隔 **300 秒 = 5 分钟**；读取名单缓存刷新间隔 **60 秒**。[任务参数][popular-job-cli]；[启动分支][popular-job-start]；[刷新常量][popular-refresh-constant]；[缓存刷新][popular-refresh] 候选源默认开关为 true，但只在无已有缓存、非纯内圈请求时取用名单。[源开关][popular-source-default]；[请求条件][popular-source] 任务从预选热门作者名单读取原创帖子并查询当前浏览；`Q` 用于选池，取用候选时并未把它直接作为最终个性化排名分数传递。[任务取数][popular-job]；[候选映射][popular-source]

The background job must be explicitly started. Its default interval is five minutes, while the serving cache refresh interval is one minute. The source's default feature switch is true, but request conditions still apply. The job reads original posts from a preselected author list. `Q` selects this pool; it is not directly supplied as the final personalized ranking score.

可以复现 `Q` 作为 **官方热门池启发式参考分**；不能把它称为未来 24 小时真实浏览、爆款概率、粉丝预测或算法给定曝光配额。若 RISE 另行拟合热度预测，应明确标为运营模型，使用真实历史留出观察验证误差；模型预测与实际新数据分别保存。

RISE may reproduce `Q` as a **reference to the official popular-pool heuristic**. It must not present it as actual future 24-hour views, virality probability, follower forecasts, or allocated impressions. Any separately fitted RISE forecast is an operator model and needs error evaluation on held-out historical observations.

## 探索与观看目标 / Exploration and viewing targets

训练中另有 `post_unexplored` 标签：窗口 **24 小时**、曲线参数 **8 小时**、目标比例 **0.03**。[标签公式][exploration-label] 它依据作者粉丝数 `F` 和浏览 `V`，判断是否低于：

```text
T(t) = 0.03 * F * (1 - 2^(-clip(t, 0, 24)/8)) / (1 - 2^(-3))
```

代码的 `is_original` 在此函数实际定义为 `in_reply_to_post_ids == 0`；还检查有效时间戳和年龄窗口。只有配置 `compute_post_unexplored_label=True` 才重算标签。[调用条件][exploration-enabled] **这是训练目标，不是线上保证补足到 `T(t)` 的展示配额。** Home 的预测标签权重默认 **0.015**，VM 默认 **0.02**，外圈默认不启用。[Home 权重][exploration-home]；[VM 权重][exploration-vm]；[评分条件][exploration-score]

The exploration curve defines a training label, conditional on configuration and timestamps. Here `is_original` specifically means no reply-parent ID. The label is not a guaranteed exposure quota. Home and VM have different default weights, applied to a prediction; the default out-of-network contribution is disabled.

| 项 / Item | 数值与语义 / Value and meaning |
| --- | --- |
| VQV 素材资格 / Media eligibility | 默认素材长度 **严格 >10,000 毫秒 / milliseconds**，不是用户观看十秒。Home 路径中已知观看者粉丝数 **≥10,000** 时不合资格，缺失粉丝数不触发该排除；引用视频时长检查默认关闭。[参数][video-default]；[资格][video-eligibility] VQV 权重默认为 0，[权重][vqv-weight] 因此不能从此阈值推出十秒以上视频必获加权。A media-duration eligibility condition, not watch-time reward; the Home path also excludes a viewer whose known follower count is at least 10,000. |
| 点击停留目标 / Click dwell target | 指定配置将 `CLICK_DWELL_TIME` 设为 **binary**，标签为停留 **严格 >10 秒 / seconds**；训练 loss 权重 fallback 为 0，须配置启用。[配置][click-dwell]；[标签][click-label] binary 输出 **0..1 概率**，推理时不乘归一化尺度还原为秒。[输出与还原规则][head-units] |
| 普通 dwell / Non-gallery dwell | 此配置的 MAE 头以 **30 秒 / seconds** 截断并归一化目标；推理按该尺度还原原单位。[配置][dwell-heads]；[目标处理][dwell-clamp] 这是具体头的处理，不能给所有停留预测统一单位。Head-specific target processing, not an optimal content length. |
| Gallery dwell | Gallery 专用 Tweedie 头的 norm 为 **300 秒 / seconds**，输出 cap 为 **300**，并有页面条件。[配置][dwell-heads] Not a universal cap for all pages or all videos. |
| 排名中的停留槽 / Ranking dwell slots | `ContDwellTimeWeight=.004`、`ContClickDwellTimeWeight=.4` 乘对应预测槽。[默认][dwell-weights]；[评分][dwell-scoring] 槽名字包含 `cont` 不保证其数值总是秒；按上述 click 配置可以是阈值概率。**不能写成“每秒点击停留加 .4”。** |

实际部署模型和配置未知。不同预测头的概率、连续时间、条件乘积必须依据对应导出配置解释，不能用名字推断单位。

The deployed model and configuration are unknown. Interpret probability heads, duration heads, and conditional products using the matching export configuration; a slot name alone does not establish its units.

## 历史请求、去重、缓存与超时 / History, deduplication, caches and deadlines

| 项 / Item | 值 / Value | 用途与限制 / Purpose and limitation |
| --- | --- | --- |
| 用户行为聚合请求 / User-action aggregation request | `window_time_ms=300,000` 毫秒，最大排序/召回序列各 **1,024** 项。[时间常量][uas-window]；[排序请求][scoring-history]；[召回请求][retrieval-history]；[长度][history-length] | 只能确认请求字段。服务端窗口解释未公开，不能说全部兴趣历史只有五分钟。Request fields, not a proven five-minute limit on all interest history. |
| 最近送达去重 / Recently served deduplication | **10 分钟 / minutes**，筛选后最多 **100** 个帖子/原帖 ID。[默认][served-default]；[执行][served-query] | 观看者近期重复送达过滤。A viewer deduplication window, not an author's cooldown or a guaranteed redistribution interval. |
| 已看帖子 / Previously seen | 请求 `seen_ids` 与 Bloom。[过滤][seen-filter] | 可见源码未给它们统一保留时间。Retention duration is unknown here; do not reuse the served window as a seen-history TTL. |
| 候选 Redis 缓存 / Candidate cache | **180 秒 / seconds = 3 分钟 / minutes**。[缓存写入][candidate-cache] | 生产且无已有候选缓存时写入。Storage lifetime, not a post's growth window. |
| Phoenix 请求记录缓存 / Request-record cache | 默认 **10,800 秒 / seconds = 3 小时 / hours**。[默认][request-cache-default]；[写入][request-cache] | 生产环境、开关开启、有候选及 prediction request ID 才写。Inference request storage, not a three-hour distribution promise. |
| 互动计数 hydration 缓存 / Engagement-count cache | **60 秒 / seconds**。[实现][count-cache] | 相关 hydration 开关开启或 shadow traffic 时读。读取数据缓存寿命不能承诺界面计数精确每分钟同步。Enabled by its hydration flag or shadow traffic; a read cache TTL, not a guaranteed UI refresh cadence. |
| VM 排名请求 / VM request | **400 毫秒 / milliseconds**；xDS send 等待 **1,700 毫秒**、transport safety net **3,000 毫秒**。[定义][vm-deadline] | 服务等待预算。Request deadlines, with no meaning as post-popularity windows. |
| NightOwl 请求 / request | **700 毫秒 / milliseconds**；collector **300 毫秒**。[客户端][nightowl-deadline]；[collector][following-age] | 搜索请求与收集器预算。Search deadlines, not early engagement thresholds. |

**运营回测的 60 分钟、24 小时、72 小时是 RISE 的观察设计，不是从缓存 TTL 或权重自动推得的官方黄金时间。** 对齐帖子年龄并保留实际采集时刻，才能比较不同内容的同龄表现；未来热度仍需真实样本验证。

**RISE's 60-minute, 24-hour, and 72-hour reviews are observation-design choices, not official golden windows derived from TTLs or ranking weights.** Preserve publication and collection times and compare matching post ages. Forecast accuracy still needs actual observations.

## 审计范围 / Audit coverage

本文所有官方链接固定到同一 SHA 与具体行。核对本文时，`references/upstream.json` 的文件 SHA-256 绑定集有 **30 个文件**；**本文没有扩展该清单，也不声称以下新增阅读文件已纳入该 hash 审计**。固定提交链接提供源码定位，不能替代更新审计清单。绑定集以后扩展时，以当前 manifest 为准。

All official links below pin the commit and lines. At this review, `references/upstream.json` contained 30 SHA-256-bound files. This document does not expand that manifest or claim that the additional files below have been included in its hash audit. Commit-pinned citations and manifest coverage are distinct; consult the current manifest if it later changes.

本文引用、但当时不在 30 文件绑定集中的文件 / Referenced files outside that binding set:

- `home-mixer/main.rs`, `home-mixer/server.rs`
- `home-mixer/sources/tweet_mixer_source.rs`, `home-mixer/sources/following_night_owl_source.rs`, `home-mixer/sources/popular_posts_source.rs`
- `home-mixer/candidate_pipeline/reverse_chron_posts_pipeline.rs`, `home-mixer/scorers/author_cold_start.rs`
- `home-mixer/util/popular_posts.rs`, `home-mixer/popular_posts_job.rs`
- `home-mixer/query_hydrators/served_history_query_hydrator.rs`
- `home-mixer/side_effects/redis_post_candidate_cache_side_effect.rs`, `home-mixer/side_effects/phoenix_request_cache_side_effect.rs`
- `home-mixer/candidate_hydrators/engagement_counts_hydrator.rs`, `home-mixer/candidate_hydrators/tweet_type_metrics_hydrator.rs`
- `home-mixer/clients/vm_ranker_client.rs`, `home-mixer/clients/night_owl_client.rs`
- `thunder/args.rs`, `thunder/posts/post_store.rs`, `thunder/kafka/tweet_events_listener.rs`
- `phoenix/xrex/data/recsys/recsys_batch.py`, `phoenix/xrex/configs/xrecsys.py`, `phoenix/xrex/models/recsys_model.py`, `phoenix/xrex/models/loss_recsys.py`
- `phoenix/xrex/data/cold_pool_filter.py`, `phoenix/xrex/data/retrieval_dataset.py`, `phoenix/xrex/models/recsys_two_tower_model.py`, `phoenix/xrex/train/recsys_bundle_export.py`, `phoenix/xrex/inference/model_runner.py`

[fs]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/server.rs#L181-L198
[max-age]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/config.rs#L36
[pipeline-age]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs#L392-L396
[age-filter]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/filters/age_filter.rs#L16-L31
[thunder-args]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/thunder/args.rs#L48-L49
[thunder-store]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/thunder/posts/post_store.rs#L127-L135
[retweet-event]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/thunder/kafka/tweet_events_listener.rs#L226-L241
[thunder-map]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/sources/thunder_source.rs#L107-L113
[tweetmixer]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/sources/tweet_mixer_source.rs#L17-L28
[source-flags]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/param.rs#L47-L58
[sim-age]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/param.rs#L623-L626
[sim-seed-limit]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/sources/simclusters_source.rs#L34-L36
[sim-seeds]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/sources/simclusters_source.rs#L213-L234
[following-age]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/sources/following_night_owl_source.rs#L18-L95
[following-pipeline]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/candidate_pipeline/reverse_chron_posts_pipeline.rs#L156-L157
[cold-default]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/param.rs#L478-L525
[cold-rank]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/scorers/author_cold_start.rs#L296-L307
[cold-conditions]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/scorers/author_cold_start.rs#L188-L234
[cold-pool-config]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/phoenix/xrex/models/recsys_two_tower_model.py#L1722-L1723
[cold-pool-limit]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/phoenix/xrex/data/cold_pool_filter.py#L16
[cold-pool-load]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/phoenix/xrex/data/retrieval_dataset.py#L431-L452
[cold-pool-export]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/phoenix/xrex/train/recsys_bundle_export.py#L1010-L1014
[cold-pool-infer]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/phoenix/xrex/inference/model_runner.py#L4514-L4551
[age-buckets]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/phoenix/xrex/models/recsys_model.py#L127-L158
[age-metrics]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/candidate_hydrators/tweet_type_metrics_hydrator.rs#L11-L113
[popular-formula]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/util/popular_posts.rs#L36-L53
[popular-selection]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/util/popular_posts.rs#L61-L85
[popular-job-cli]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/main.rs#L48-L59
[popular-job-start]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/main.rs#L165-L181
[popular-refresh-constant]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/util/popular_posts.rs#L7
[popular-refresh]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/util/popular_posts.rs#L190-L213
[popular-source-default]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/param.rs#L943-L953
[popular-source]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/sources/popular_posts_source.rs#L25-L60
[popular-job]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/popular_posts_job.rs#L67-L148
[exploration-label]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/phoenix/xrex/data/recsys/recsys_batch.py#L60-L88
[exploration-enabled]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/phoenix/xrex/data/recsys/recsys_batch.py#L580-L605
[exploration-home]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/param.rs#L384-L387
[exploration-vm]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L91-L100
[exploration-score]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L85-L90
[video-default]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/param.rs#L577-L587
[video-eligibility]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/util/candidates_util.rs#L4-L44
[vqv-weight]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/param.rs#L349
[click-dwell]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/phoenix/xrex/configs/xrecsys.py#L699-L705
[click-label]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/phoenix/xrex/models/loss_recsys.py#L258-L267
[head-units]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/phoenix/xrex/models/recsys_model.py#L274-L318
[dwell-heads]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/phoenix/xrex/configs/xrecsys.py#L679-L697
[dwell-clamp]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/phoenix/xrex/models/loss_recsys.py#L80-L87
[dwell-weights]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/param.rs#L390-L399
[dwell-scoring]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L112-L123
[uas-window]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/config.rs#L34
[scoring-history]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/query_hydrators/scoring_sequence_query_hydrator.rs#L40-L51
[retrieval-history]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/query_hydrators/retrieval_sequence_query_hydrator.rs#L38-L49
[history-length]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/param.rs#L833-L842
[served-default]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/param.rs#L979-L988
[served-query]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/query_hydrators/served_history_query_hydrator.rs#L82-L97
[seen-filter]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/filters/previously_seen_posts_filter.rs#L16-L30
[candidate-cache]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/side_effects/redis_post_candidate_cache_side_effect.rs#L10-L88
[request-cache-default]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/param.rs#L912-L921
[request-cache]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/side_effects/phoenix_request_cache_side_effect.rs#L53-L122
[count-cache]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/candidate_hydrators/engagement_counts_hydrator.rs#L60-L75
[vm-deadline]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/clients/vm_ranker_client.rs#L21-L30
[nightowl-deadline]: https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/clients/night_owl_client.rs#L14-L16
