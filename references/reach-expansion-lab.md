# 陌生人分发：代码边界与三项内容实验

2026-10-09（Asia/Taipei）。**第 1 方向已用模型失败案例试了一篇；表中的坐标示范及另两个方向尚未执行，没有天量流量保证。** 目标是让具体领域的新观看者看到、使用并自愿传播原创内容，再观察是否形成高质量蓝 V 关注；不以操作次数或工程进度帖代替内容价值。

实际案例：[模型失败原创](https://x.com/LIghtJUNction_x/status/2108240460431134796)，发布于 **2026-10-08 16:57:49 UTC**。它采用具体失败案例的切入方向，**不是表中的坐标教程，也没有对照实验**。17:06:59.517 UTC 的早期观察为 10 views、1 repost，其余当时已观察计数为 0；转贴作者独立性未知，不能记作一次独立认可。60m（17:57:49 UTC）与 24h（2026-10-09 16:57:49 UTC）观察均待完成，未设自动调度。[置顶进展回复](https://x.com/LIghtJUNction_x/status/2108241779099340888) 单独记录，自己的回复／操作不算外部反馈。

版本核验：2026-10-08 **16:29:05 UTC**，官方 `git ls-remote` 的 HEAD/main 均为 **`35650fb89f3b14dc6234312535f642779d891d88`**。该提交时间为 2026-10-08 05:09:20 UTC。仓库已有 [upstream.json](upstream.json) 仍绑定 `78460ca8b65c57ddd3a05f9217c8aaeba214b628`；本页只复核分发相关路径，**没有替换已审清单，也不是新提交全部源码审计**。[官方新提交](https://github.com/xai-org/x-algorithm/commit/35650fb89f3b14dc6234312535f642779d891d88)；[版本比较](https://github.com/xai-org/x-algorithm/compare/78460ca8b65c57ddd3a05f9217c8aaeba214b628...35650fb89f3b14dc6234312535f642779d891d88)。下列源码链接全部固定到新提交。公开默认和源码存在某路径，不证明线上为本账号、每位观看者开启它。

## 真正新增的分发条件

**可选视频模块增加了一条选择路径。** 旧版 TopK 按分数取候选；新版在模块启用时，从未选候选再按预测 `video_open_score` 补选视频，公开常量最多补 30 个。这些并不是额外 30 次曝光。[TopK L10–23](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/selectors/top_k_score_selector.rs#L10-L23)、[常量 L17–19](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/params/config.rs#L17-L19)。最终模块选预测打开值较高的**非回复视频**，要求有该预测值及已知宽高比 `<1`，候选不足 3 个则不生成模块，最多 5 个；3–5 是观看者候选池的模块规模，不是要求同一作者发三条视频。[选择 L13–54](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/util/video_carousel.rs#L13-L54)、[常量 L35–36](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/params/config.rs#L35-L36)。

启用还同时要求 For You、`EnableVideoCarousel` 和观看者模块资格；**公开开关默认 false**。资格可由近期模块投放历史计算，默认疲劳窗口 60 分钟；该历史 hydrate 本身还有迁移组件开关。这是观看者模块出现条件，不是作者发帖间隔或“视频必爆”的规则。[启用 L7–10](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/util/video_carousel.rs#L7-L10)、[默认 L1041–1057](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/params/param.rs#L1041-L1057)、[历史条件 L25–56](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/query_hydrators/served_history_query_hydrator.rs#L25-L56)。策略只是假说：一次有完整结果的竖屏演示值得试，不能把效果归因于自己看不见的模块。

**话题请求明确跳过作者冷启动加成。** 新增分支直接返回原分数；`is_topic_request` 是 `topic_ids` 非空，**不是正文含 hashtag**。[新增分支 L378–389](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/scorers/author_cold_start.rs#L378-L389)、[请求定义 L249–254](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/models/query.rs#L249-L254)。常规冷启动仍需作者资格、实验分组、候选位置、年龄、Home 展示数等条件；公开阈值为年龄最多 7200 秒、Home 展示少于 200、粉丝不超过 50000。[条件 L296–307](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/scorers/author_cold_start.rs#L296-L307)、[默认 L478–505](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/params/param.rs#L478-L505)。小账号、低展示或加入话题不自动取得探索资格，不能人为制造互动去“过门槛”。

## 旧路径的新盲点：相关性先于可见计数

已有 [行动指南](algorithm-field-guide.md)、[时间说明](algorithm-time.md)、[真实公式](recommendation-formulas.md) 已解释观看者上下文、会话去重和作者多样性。这次选读的 Phoenix/SimClusters、外圈回复、已看、会话、VM 加权与 DPP 文件相对旧绑定没有变化；下面不是新算法规则，而是需要落实的策略边界。

- **召回与资格不等于评分。** Phoenix 依赖观看者检索序列，且常规外圈、话题和缓存请求走不同条件；语言和关注话题属于观看者上下文，不能由自己的点赞量替代。[Phoenix L98–111](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/sources/phoenix_source.rs#L98-L111)、[上下文 L72–112](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/util/phoenix_request.rs#L72-L112)。另外，话题过滤启用时按候选的 topic IDs 判断；观看者排除话题时，没有所需 filtered topic 信息的候选也可能移除。这不是标签字符串匹配加分。[TopicIdsFilter L15–17](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/filters/topic_ids_filter.rs#L15-L17)、[排除 L82–99](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/filters/topic_ids_filter.rs#L82-L99)。需要检验的是“某种具体问题有没有相关人愿意使用”，不是多堆热门话题。
- **探索不是所有陌生人都能领取的加分。** 加权 `post_unexplored` 项默认不包含外圈；另有作者冷启动机制，但不能把两者混称普遍新帖扶持。[资格 L85–90](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/xai-value-model/scoring.rs#L85-L90)、[默认 L91–100](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/vm-ranker/params.rs#L91-L100)。
- **实质交流与独立原创承担不同工作。** 默认外圈回复/转贴过滤有 Phoenix 回复开关例外，缺祖先的回复也会过滤；已看检查关联 ID，同会话只保留最高分候选。回复适合解决一个人的问题，独立原创承担新的发现入口，不能在置顶会话堆重复推广当多次陌生人曝光。[外圈过滤 L15–22](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/filters/oon_retweet_reply_filter.rs#L15-L22)、[已看 L24–29](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/filters/previously_seen_posts_filter.rs#L24-L29)、[会话 L19–35](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/filters/dedup_conversation_filter.rs#L19-L35)。
- **“值得转给同事”是可试价值，不是隐藏分数。** 评分同时使用观看者的回复、分享、关注以及不感兴趣、屏蔽、静音、举报预测。没有“一赞抵几次举报”的事件兑换规则。作者多样性按同候选池排序统计，而非每日条数；DPP 的启动默认 false、请求开关默认 true 双门仍在，线上是否使用未知。[正负项 L92–135](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/xai-value-model/scoring.rs#L92-L135)、[作者计数 L182–202](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/xai-value-model/scoring.rs#L182-L202)、[DPP 启动 L15](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/vm-ranker/args.rs#L15)、[请求门 L35–37](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/vm-ranker/scoring/mod.rs#L35-L37)。

## 三项实验，按顺序做，不同时混改

以下是候选选题，**先完成真实演示或取得问题背景再发布**。若该主题已发过，换一个尚未展示的真实案例，不换标题重复发。每项最多先试两篇各有新价值的原创，先看相关真人反馈再决定扩展；小样本和不同案例只能作方向探索，不能推因果。发布时间、语言、长度、对外互动尽量接近，差异照实记录，不承诺从代码推出最佳发帖时刻。

| 实验／唯一主要变量 | 具体原创角度与受众 | 60m／24h 观察 | 继续或停止 |
| --- | --- | --- | --- |
| 1．第一句从方法名改成具体失败症状 | 面向 AI 图像工作流／标注开发者：“图片缩成一半，框为什么跑偏？”用明确标记的合成框，展示像素与归一化坐标的一次输入→输出；正文直接给转换条件，不先介绍 RISE。另一个新案例仍服务同圈层，保持表现形式接近。 | 下述共同指标；特别看非本人作者给出自己的尺寸／反例、独立转贴、详情与主页变化。 | 有真实输入或使用反馈才做下一例。两篇各到 24h 都无实质反馈、主页没有可见改善，就暂停这个切入点，去找对方正在遇到的问题。不能把两篇差异称作随机实验效果。 |
| 2．呈现形式改为一次完整竖屏演示 | 面向 agent／API 构建者：“超时重试，如何避免重复产出？”先做受控合成请求演示，20–30 秒展示同一输入、重试、最终唯一结果及限制；不宣称任何产品存在这个 bug。相比近期有相近复杂度的静态教程，主要改变形式。 | 下述共同指标；有原生视频指标才记录打开／观看，缺失为 null；看独立转贴和具体复现反馈。不能由计数认定进了视频模块。 | 信息必须在视频内读懂，代码或证据可在正文查到。两篇新演示 24h 都未产生相关反馈／主页改善时停，不为赌模块批量发竖屏视频；比较不是同题随机分流，保留内容与时间混杂。 |
| 3．从作者自述改成可交给同行的判断清单 | 面向开源工具／数据产品开发者：“下载成功≠可训练：三步检查 ID、观察窗口、未来筛选。”给小型合成坏例与正确判定，并以官方数据字段作出处；不转售老模型、不再发版本流水账。新案例必须有新的边界价值。 | 下述共同指标；特别看独立作者转贴给同领域人、给出反例或明确说采用了哪一步。收藏可记录，但不把收藏当官方加权头。 | 有反例就纠错，有真实采用才深挖该问题。两篇 24h 只有自己的互动或泛泛互赞时停推广，不能拿累计星数／下载替代帖子外部反馈。 |

**传播放大假说（未验证）：** 让同一个真实失败案例具有跨相关受众的复用价值：开发者能拿检查步骤处理自己的数据，评测者能用边界例复核结论。下一步检验是否出现这两个圈层不同作者的自发采用、反例或独立转贴，再看 60m→24h 的 views、可得的 detail／profile 和新增高质量蓝 V 是否一起变化；缺少作者或圈层证据就不认定跨圈扩散。代码事实只到某条召回路径以**观看者**的显式／隐式互动帖 ID 构建种子，且受启用条件约束：[SimClusters L215–234](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/sources/simclusters_source.rs#L215-L234)、[种子 L287–309](https://github.com/xai-org/x-algorithm/blob/35650fb89f3b14dc6234312535f642779d891d88/home-mixer/sources/simclusters_source.rs#L287-L309)。它不证明一条转贴必然触达其全部粉丝；总计数和时间上随后的变化也不能证明推荐增益或因果，只决定是否继续验证这类可复用内容。

**三项共同指标及 null 边界：** 保存原创发布时间和 60m、24h 实际观察时刻，记录可见 `public_views`；只有帖子级 owner 数据明确提供其统计口径时才另记 impressions、detail opens、profile visits，不能把 public views 自动称作 Home 曝光。认证 Home 若只有账号总计、没有逐帖值，该帖字段为 **null**。没有识别陌生人／已关注者的可靠数据，陌生人曝光量也为 **null**；总 views 增长只是一项代理观察。

独立转贴记录可核验的非本人作者事件；只有一个原生计数而看不到作者时，保留计数，独立作者数为 null。新增蓝 V 必须用同一窗口的完整可比粉丝身份快照确认；部分列表只能记“新增观察”，真实新增为 null。高质量按既有明确标准核查相关原创／实质讨论证据，未知保留未知；新增人数 N=0 时质量占比 null，有未知 U 时报告 H/N 到 (H+U)/N 的分类边界，不假装置信区间。detail、profile、views 非同一用户的嵌套漏斗，不能把公开比率直接相乘；计数也不是模型隐藏预测概率。

到 60m 先看可读性／事实错误，不因早期低量删除重发。到 24h 再评方向；若字段缺失，结论为未能测量，不按零止损。帖子删除后标记不可用与历史快照时间，不把删除变成零互动；旧链接失效不再用于当前有效性证明。所有行动排除刷互动、假热度、交换传播和重复推广。2011 SEISMIC 转发实验与本页现代内容分发观察分开，不宣称它能预测当前曝光或认证 Home。
