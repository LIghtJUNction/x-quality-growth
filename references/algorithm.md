# 算法事实与策略推断

分析日期：2026-10-08（Asia/Taipei）。官方仓库：[xai-org/x-algorithm](https://github.com/xai-org/x-algorithm)。审核提交：`78460ca8b65c57ddd3a05f9217c8aaeba214b628`。本技能明确基于 X 开源推荐算法；不是 X 官方产品。

## 已读代码

| 代码事实与定位 | 策略推断，需要账号实验验证 |
| --- | --- |
| [scoring.rs](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L26)：各权重作用于每位观看者的预测概率或连续预测量，不是互动计数；再进行偏移和乘数调整。 | 内容针对具体受众，引发自发回复、分享或关注；不可按计数兑换公式刷量。 |
| [VM 参数](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L3)：公开默认 favorite=0.5、reply=5、retweet=1、quote=5、follow_author=4、share_copy_link=20；不感兴趣/屏蔽/静音/举报是负项。 | 优先可讨论、可分享、值得持续关注的内容。不能说一次回复等于十次赞。正负权重不同不能换算计数或模拟最终排名。 |
| [inputs.rs](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/inputs.rs#L20)、[weights.rs](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/weights.rs#L82)：互关且既非回复也非转贴的候选，reply 权重加上默认 15；dwell 互关加成默认 0。 | 真正的同领域互关关系与原创帖值得维护；不能宣称随便关注、群体互赞或给别人回一句就获得 15 倍曝光。默认 reply 5 加 15 为 20，是权重变化，不是曝光倍数。 |
| [scoring.rs](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/xai-value-model/scoring.rs#L187)、[VM 参数](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L163)：作者多样性默认启用，decay=.5、floor=.25；同一候选池按排序分数降序统计同作者已有候选数量 k，乘数为 `(1-floor) × decay^k + floor`；默认 k=0/1/2 为 1/.625/.4375。 | 一轮输出少量不同价值的内容，不连续复制同一观点。不把候选池惩罚解释成“每天第 N 条必被限流”。 |
| [VM value_model.rs](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/scoring/value_model.rs#L117)、[参数](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L205)：常规外圈乘数 .75、话题请求 .5；部分内圈回复/转贴也可应用外圈乘数。另有新用户条件分支；公开年龄阈值默认 0 秒，不能把它宣传为所有新账号享有优惠。 | 面向新的同领域人群发布原创内容，同时维护已形成的关系。它不是“蓝 V 外圈加成”，也不是永久固定到每个账号的曝光折扣。 |
| [AgeFilter](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/filters/age_filter.rs#L31) 与 [config.rs](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/params/config.rs#L36)：在 [Phoenix 候选管道](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/candidate_pipeline/phoenix_candidate_pipeline.rs#L396) 明确装配 48 小时年龄过滤。 | 优先近期讨论，用 24/72 小时观察不同效果；不是“发帖超过 48 小时后全站消失”。 |
| [OONRetweetReplyFilter](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/filters/oon_retweet_reply_filter.rs#L15)：默认过滤外圈转贴/回复和缺祖先的回复；Phoenix 外圈回复有开关例外。 | 评论能在会话中建立关系，但不能保证作为独立内容广泛进入陌生人的 For You。原帖、回复、引用、普通转贴分开评估。 |
| [SimClusters source](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/sources/simclusters_source.rs#L287)：以显式/隐式互动信号构建候选种子；模型还使用观看者的行为上下文。 | 内容保持明确专业主线、参与相关真实讨论，检验同领域粉丝是否增加。不能证明某个标签直接触发固定“圈层权重”。 |
| [VM scorer](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/scorers/vm_ranker.rs#L109) 将候选送到 VM 服务，失败可退回本地加权分数。 | 不以孤立参数文件声称已完整复现线上推荐；策略保持可观测而非伪造排名分数。 |

## 调用链复核，避免只看参数猜线上行为

- [VM 参数 ComputeValueModel](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/params.rs#L223) 默认 `false`，但 [Home 的 VM 请求](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/home-mixer/scorers/vm_ranker_request.rs#L38) 明确设置 `compute_value_model: true`；[服务端入口](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/vm-ranker/scoring/mod.rs#L33) 用“请求标志或配置开关”决定计算。不能仅据默认 `false` 宣称 Home 加权模型关闭；同样，实际是否调用该服务还需看请求路径和开关。
- 作者多样性看的是同一候选池按分数排序后的同作者数量，不是发帖时间顺序。默认第二个同作者候选乘 .625，而不是 .5；这仍不等于曝光量减少 37.5%。
- 新用户外圈分支以**观看者**账号年龄和关注数量判断，不是创作者账号年龄。它不能支持“注册新号发帖获得某种额外曝光”的运营建议。

## 不能从代码推出的结论

- 这份代码主要解释 **For You 内容分发**，不完整说明搜索、评论排序或推荐关注模块；它不直接保证粉丝增长。
- 当前公开参数不等于所有请求的配置。Feature switches、实验和观看者配置会改变路径；模型输出不可见，一些 Grox 提示词和 botmaker 规则未公开。见 [官方说明](https://github.com/xai-org/x-algorithm/blob/78460ca8b65c57ddd3a05f9217c8aaeba214b628/README.md#experiments-and-configuration)。
- 已读加权头里没有独立 bookmark 项。收藏仍是可用反馈指标，不能虚构“收藏权重”。profile_click 公开默认 0，不宣传固定主页点击加分。
- “高质量粉丝”是本技能的运营评估标准，不是 X 模型标签。代码没有证明本技能能保证指数增长或高质量涨粉。
- 自己点赞、关注别人的动作与别人对自己内容的预测行为方向不同；自我操作数不是自己的推荐得分。
- 搜索直达后的互动可能建立人际关系，但不能按某权重计成 Home 排序收益；评分代码注释明确区分 Home 展示后的动作与直接导航互动。

## 版本刷新

把上游独立检出到临时目录，读取新提交、实际参数、执行路径和过滤条件。运行 `python3 scripts/audit_source.py --source /path/to/x-algorithm --output references/upstream.json`，审查差异后同步本文件与策略。不要只修改提交号而保留过期结论。脚本只提取证据，不自动确认文档推断仍成立。当前清单覆盖 17 个文件哈希、两处参数表和 `MAX_POST_AGE` 的秒数；参数删除、重复或不支持的默认值语法会停止审计，避免静默遗漏。

复核已有证据而不覆盖它：

```sh
python3 scripts/audit_source.py --source /path/to/x-algorithm --check references/upstream.json
python3 scripts/audit_source.py --source /path/to/x-algorithm --check references/upstream.json --check-latest
```

第二条会联网比较官方当前 HEAD，发现未审核的新提交时失败；失败后应阅读差异、重查条件、修改结论，再生成清单。第一条完全离线，只验证已绑定提交。证据读取 Git 提交对象，不使用可能隐藏本地修改的工作树字节。官方 origin 名称本身不是签名证明；联网 HEAD 检查也只证明检查当时的版本，不证明日后或线上服务版本。
