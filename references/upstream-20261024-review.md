# 2026-10-24 算法局部复核 / Scoped source review

复核日期：2026-10-26（Asia/Taipei）。新源码固定到官方提交 [`6258a1549ef808be88fba83d3b2d58364b587ee0`](https://github.com/xai-org/x-algorithm/commit/6258a1549ef808be88fba83d3b2d58364b587ee0)，提交时间为 2026-10-24 03:22:45 UTC。与主清单 `78460ca8b65c57ddd3a05f9217c8aaeba214b628` 相比前进 12 次提交；原来绑定的 30 个文件有 16 个哈希变化、0 个删除。该统计来自独立 Git 检出和已有 `review_upstream.py`，不是完整变更文件数，也不是线上部署证明。[版本差异](https://github.com/xai-org/x-algorithm/compare/78460ca8b65c57ddd3a05f9217c8aaeba214b628...6258a1549ef808be88fba83d3b2d58364b587ee0)。

这里只复核下列默认表、评分衔接及过滤条件。原主清单和历史实验不覆盖重写；内容审核、训练、全部召回依赖及线上参数仍未整体审核。来源提取器成功生成新清单，只能证明提取完成，不能代替语义复核。

## 同一版本有两套默认权重

| 预测项 | 旧版 Home 默认 | 新版 Home 默认 | 新版 VM 默认 | 新版代码 |
| --- | ---: | ---: | ---: | --- |
| 点赞 `FavoriteWeight` | 0.5 | 0.66 | 0.5 | [Home L345](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/params/param.rs#L345)、[VM L3](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/vm-ranker/params.rs#L3) |
| 打开视频 `VideoOpenWeight` | 0.07 | 0.02 | 0.07 | [Home L366](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/params/param.rs#L366-L371)、[VM L12](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/vm-ranker/params.rs#L12-L17) |
| 连续停留时长 `ContDwellTimeWeight` | 0.004 | 0.006 | 0.004 | [Home L426](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/params/param.rs#L426-L431)、[VM L54](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/vm-ranker/params.rs#L54-L59) |
| 不感兴趣 `NotInterestedWeight` | -47.52 | -52.272 | -47.52 | [Home L439](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/params/param.rs#L439-L444)、[VM L108](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/vm-ranker/params.rs#L108-L113) |

旧数值绑定[旧版 Home 参数](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/param.rs#L314-L396)。**这张表比较代码默认值，不比较线上效果。** 权重乘的是观看者的动作预测值；时长项乘连续预测量，不是作者已经收到的互动数量。[代码说明与计算](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/xai-value-model/scoring.rs#L31-L60)、[各预测项加总](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/xai-value-model/scoring.rs#L92-L139)。

调用链解释了为什么不能任选一列预测最终排名：

1. Home 从自己的查询参数构建权重。[Home weights_for L8-L50](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/scorers/value_model.rs#L8-L50)。
2. 排序请求附候选预测和本地分数，要求 `compute_value_model=true`，同时传入观看者及 topic 请求标记。[请求 L26-L68](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/scorers/vm_ranker_request.rs#L26-L68)。
3. VM 按服务配置解析参数，再从自己的参数类型取权重；计算可能回退。没有服务配置时也不能直接断言用了 VM 默认列。[参数解析 L101-L112](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/vm-ranker/scoring/mod.rs#L101-L112)、[计算与权重 L45-L110](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/vm-ranker/scoring/value_model.rs#L45-L110)。
4. Home 在 RPC 失败时保留本地分数；成功收到候选结果时用返回值更新分数。选择器读取 `candidate.score`，并另有条件视频候选路径。[VM 调用及回退 L80-L140](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/scorers/vm_ranker.rs#L80-L140)、[选择器 L10-L41](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/selectors/top_k_score_selector.rs#L10-L41)。

因此不能把 0.5 → 0.66 写成“全站点赞收益提高 32%”，不能把停留系数变化解释成曝光增长 50%，也不能从任一列推导每日点赞、评论或发帖配额。线上配置、调用成败及个人预测量不可见，最终效果保持未知。

## 零赞来源、来源配额与回复条件

**ZeroFav 是候选来源标记，不是每条零赞帖都进入推荐的承诺。** `PhoenixSource` 将返回的 `RetrievalDatasetType::ZeroFav` 映射到专门的 served type。[来源映射 L199-L205](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/sources/phoenix_source.rs#L199-L205)。新增过滤器只在观看者实验开关开启时运行，对“来源仅为 ZeroFav”的候选按作者分组保留 treatment；其他来源候选不走这一排除条件。[开关与过滤 L59-L82](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/filters/zero_fav_codivert_filter.rs#L59-L82)、[仅来源判断 L104-L110](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/filters/zero_fav_codivert_filter.rs#L104-L110)。观看者与两个作者分组开关公开默认均为 false。[参数 L236-L253](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/params/param.rs#L236-L253)。不能用它宣称所有零赞帖被过滤，也不能建议自赞“解锁推荐”。

**FairShareRankingFilter 限制的是评分前候选池，不是作者的最终曝光配额。** 它按 served type 分组，按各组数量的比例分配 `PhoenixScoresResultSize` 预算，并在组内保留前面的候选；余数按确定顺序分配。默认开关 true，但缓存、缺失评分序列或 ranker kill switch 会关闭该过滤器。[启用与预算 L10-L39](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/filters/fair_share_ranking_filter.rs#L10-L39)、[分组及分配 L44-L116](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/filters/fair_share_ranking_filter.rs#L44-L116)、[公开默认 L1214-L1225](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/params/param.rs#L1214-L1225)。管道把它装在 Phoenix/VM 评分之前。[装配 L449-L478](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs#L449-L478)。不能把名称翻译成“每个创作者公平获得流量”。

**圈外回复的例外又多一个根回复条件。** 只有允许 Phoenix 圈外回复、来源符合 Phoenix Home 检索，并满足可选的 `PhoenixOonRepliesRootOnly` 条件，才跳过相应圈外回复排除。root-only 开启时要求父帖 ID 等于已知 conversation ID；缺祖先的回复仍被过滤。两个相关公开开关默认 false。[过滤 L15-L27](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/filters/oon_retweet_reply_filter.rs#L15-L27)、[默认 L73-L84](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/params/param.rs#L73-L84)。这不是全部评论页或搜索的规则，也不证明本账号回复无法被别人看到。

## 观看者上下文和 DPP 仍需看开关

近期搜索 hydrator 读取的是 `query.user_id` 对应观看者，开关默认 false。它只保留请求时刻之前、向量长度符合要求的最近最多 16 条记录，并清空查询文字，然后放进 Phoenix 用户上下文。[读取与筛选 L10-L57](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/query_hydrators/recent_search_queries_query_hydrator.rs#L10-L57)、[传入上下文 L146](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/util/phoenix_request.rs#L146)、[默认 L727-L732](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/home-mixer/params/param.rs#L727-L732)。作者自己搜索关键词，不能当成目标观看者已经搜索它，也不能从字段接入推断某个措辞的曝光收益。

DPP 仍要求服务有 DPP context；参数解析存在时，topic 请求还要求新增的 `TopicDppEnabled`，公开默认 false。参数为 None 时 `is_none_or` 返回 true，不能将 topic 默认关闭说成所有路径无条件关闭。[调用与条件 L31-L86](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/vm-ranker/scoring/mod.rs#L31-L86)、[默认 L235-L247](https://github.com/xai-org/x-algorithm/blob/6258a1549ef808be88fba83d3b2d58364b587ee0/vm-ranker/params.rs#L235-L247)。这里的 topic 请求也不等于作者正文里带了话题标签。

## 下一轮如何使用这些证据

运营假说仍是围绕具体读者交付独立可用的内容，并回应真实使用问题。用同来源、同帖龄观察、可核验反馈、名单差集和既定质量标准检验；不把源码条件计成曝光或新增粉丝。若同时存在其他运营者，分别记录自己的动作，不给单帖作因果归因。真实账号数据与个人质量判断继续留在 `runs/`。

复核命令使用独立官方检出；输出写入私有运行目录后人工审查，不覆盖旧主清单：

```sh
git -C /path/to/x-algorithm diff 78460ca8b65c57ddd3a05f9217c8aaeba214b628 6258a1549ef808be88fba83d3b2d58364b587ee0 -- home-mixer xai-value-model vm-ranker
python3 scripts/review_upstream.py --source /path/to/x-algorithm --output runs/pending-upstream-review.md
python3 scripts/audit_source.py --source /path/to/x-algorithm --output runs/upstream-candidate.json
```

## English

This scoped review pins official commit `6258a1549ef808be88fba83d3b2d58364b587ee0`. It does not replace the older 30-file manifest or establish production settings. Home and VM public defaults differ in this same revision: favorite 0.66 / 0.5, video-open 0.02 / 0.07, continuous dwell 0.006 / 0.004, and not-interested -52.272 / -47.52. The linked call chain covers local weighting, service-side parameter resolution/recomputation, RPC fallback and returned-score selection. These are weights on predictions, not engagement counts or measured reach.

ZeroFav is a returned source classification with viewer/author experiment gates; fair-share allocation limits the pre-scoring pool by source, not creator exposure. Out-of-network replies have a conditional root-only gate. Recent-search context belongs to the viewer and is disabled by public default. Topic DPP requires its own flag when parameters resolve, while absent parameters follow a separate branch. Every fact above links to its pinned implementation; none establishes acquisition, ranking visibility or a universal growth recipe.
