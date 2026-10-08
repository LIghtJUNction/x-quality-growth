# 本轮算法行动指南

依据：X 官方 `xai-org/x-algorithm`，固定审核提交 `78460ca8b65c57ddd3a05f9217c8aaeba214b628`。2026-10-08 实时核对官方 HEAD，仍为该提交。以下把代码事实、待试策略和实测分开；公开默认不代表每次线上请求的配置。已有权重和过滤说明见 [algorithm.md](algorithm.md)。

## 1. 先找到相关受众，再看互动数字

**代码事实：** Thunder 用观看者的关注列表召回帖子（[L29](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/sources/thunder_source.rs#L29)）。Phoenix 和 SimClusters 是其他召回路线，内圈请求或缓存请求不走这两路（[Phoenix L98](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/sources/phoenix_source.rs#L98)、[SimClusters L215](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/sources/simclusters_source.rs#L215)）。

**可试策略：** 关注值得长期交流的同领域创作者，核实对方是否自愿回关。单向关注改变的是自己的 Thunder 召回，不能当作自己的曝光收益；也不能据此声称关注动作在整个推荐系统中只有一种影响。

**观察：** 分开记录已持久保存的关注动作、对方回关、实际新增蓝 V 和质量分类。未回关不等于低质量，回关也不等于高质量。

## 2. 内容主线要和目标观看者匹配

**代码事实：** 检索和评分分别取观看者的行为序列（[检索 L45](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/query_hydrators/retrieval_sequence_query_hydrator.rs#L45)、[评分 L47](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/query_hydrators/scoring_sequence_query_hydrator.rs#L47)）。预测请求还传入语言、国家和关注话题等上下文（[request L72](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/util/phoenix_request.rs#L72)）。代码没有给出各字段的实际影响大小。

**可试策略：** 本轮以中文 AI 编程、独立开发、开源实测为主线。回复要针对对方讨论提供例子、纠错或实际经验；互关话题用于发现候选人，之后仍检查其内容是否相关。此选择是受众匹配假设，不能宣传标签固定加权。

**观察：** 按内容主题比较新增蓝 V、其中高质量人数和占比；保留未知分类，不把所有互动者算作目标粉丝。

## 3. 持续更新置顶，同时区分更新与新内容

**代码事实：** Home 已看过滤会检查回复父帖（[filter L24](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/filters/previously_seen_posts_filter.rs#L24)、[关联 ID L13](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/util/candidates_util.rs#L13)）。选择后同会话只保留最高分候选（[filter L19](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/filters/dedup_conversation_filter.rs#L19)）。它不是每日发帖处罚，也不是直接访问会话的可见性规则。

**可试策略：** 继续把真实数据、改动和证据追加到同一置顶会话。有独立价值的新发现再写少量原创，并链接该证据会话。不要重复发布相同推广来代替更新。

**观察：** 置顶原帖、每条更新回复和独立原创分别留永久链接、观察时间及可见计数；不能把它们的展示量相加当作去重触达人群。

## 4. 保持主题一致，让每篇确实增加信息

**代码事实：** 作者多样性按同一候选池评分次序衰减，已有默认公式见 [algorithm.md](algorithm.md)。另有 DPP，用内容向量相似度和评分挑选候选（[kernel L119](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/dpp.rs#L119)）。其 feature switch 默认 `true`（[params L229](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L229)），启动参数默认 `false`（[args L15](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/args.rs#L15)）；需要启动建立上下文且请求开关允许（[入口 L35](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/scoring/mod.rs#L35)）。线上是否开启未知。

**可试策略：** 分别发一个实测结果、一个可复用例子或一个具体问题的解决办法。实际信息应有差异，换标题或换表情不算。避免相似推广只是待验证假设，不能许诺规避某个固定惩罚或保证曝光。

**观察：** 比较不同内容的讨论质量与后续合格粉丝变化；候选池和隐藏向量不可见，不能声称自己测到了 DPP 分数。

## 5. 优化真实目标，不制造“算法得分”

**代码事实：** 默认评分路径先调整分数再应用作者乘数（[scoring L314](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L314)）。服务返回的分数更新候选，最终 TopK 读取 `candidate.score`（[VM L125](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/scorers/vm_ranker.rs#L125)、[selector L9](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/selectors/top_k_score_selector.rs#L9)）。公开权重无法还原某帖最终位置。

**可试策略：** 每轮只改变一个主要内容选择，观察新增蓝 V 和质量占比，再决定是否延续。操作量只作成本记录；自己的点赞、回复和关注不能按公开权重加成自己的推荐得分。

**观察：** 保留轮次起止快照、质量证据和并行操作说明。部分名单只能说“新增观察”，不能说确证新增；时间上随后发生的变化不能直接证明由该行动造成。尚无实测证据时，这五条策略都保持“待验证”。
