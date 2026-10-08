# 模型输入契约：正文、媒体、评论与平台

这是拟议的统一输入契约 `rise-input-draft-1`，**不是当前解析器已支持的完整格式**。它定义未来模型需要什么证据，不证明语义模型已训练或能涨粉。统计定义见 [增长统计](growth-statistics.md)，来源算法事实见 [算法行动指南](algorithm-field-guide.md)。

## 当前实现边界

[predict_heat.py](../scripts/predict_heat.py) 目前读取单帖发布时间、观察时间及公开 views / owner impressions，分别运行最后值、最近速度基线，并提供可选三参数曲线 `I(t)=b+A×(1−exp(−t/τ))` 的 PyTorch CPU 拟合。三参数是 b、A、τ；它不是三参数语言或多模态模型。拟合代码存在，不等于某条真实帖已完成可复核训练或预测通过验证。文本、图像、视频、字幕和评论语义尚未进入该预测实现，也没有已使用冻结编码器的可核验实现证据。

**文案来源是第二预测目标。当前训练没有这个目标，也没有来源分类、校准或它改善热度预测的实际性能结果。** [authorship.py](../scripts/authorship.py) 已实现独立标签校验、外部概率接入与辅助特征输出，不运行检测器；它核对声明的 ID、时钟及提供的素材/事件组 ID，但分组是否正确、编辑链、重复正文及评论关联仍未独立验证。完整语义与联合模型仍待实现、检验。

## 每条样本必须有身份与时间

| 字段 | 输入约定 |
| --- | --- |
| `platform` / `post_id` / `version` | 联合标识原生帖子及内容版本；平台身份不能跨平台拼接，编辑不算第二条独立原创。目标与训练记录都使用无空格的小写规范平台标签；X 固定为 `x`，拒绝 `X`、`twitter`、`x.com` 等别名，不静默转换。`post_id` 不带首尾空格，X ID 为无前导零的正 ASCII 十进制；其他平台保留精确原生 ID。另保留原帖及最新版本链接。 |
| `published_at` | 首次真实发布时间，带时区；未发布为 null。编辑时刻另列 `edited_at`，固定观察窗口不因编辑重启。 |
| `captured_at` / `prediction_at` | 样本实际采集时刻 / 预测截止时刻；不能以补录时间冒充历史可得时间。 |
| 每项 `available_at` | 该输入实际可用于当时预测的时刻；正文、计数、评论、媒体特征各自记录，不能只靠样本总时间。 |
| `count_sources` / `exposure_unit` | 每个计数的原生名称、来源界面、单位、采集及可得时间。views / impressions 为各自定义的展示事件口径，均不默认是去重人数；video plays 另立指标。 |
| `counts` / `aggregation` | 非负整数或 null；注明累计从发布起、平台所报报告期或明确区间。累计前后相减只限同指标、来源与版本。未知不能补零，修订下降先核对。 |
| `text` | 完整可得正文、语言、截断/清洗版本；字符和 token 长度区分，模型 token 数还需记录 tokenizer 版本。正文每次编辑保存版本，不拿终稿替代早期预测输入。 |
| `media` | 列表内逐项记录 image/video/audio/GIF 等类型、顺序、MIME、文件字节、图像/帧宽高、视频/音频时长、来源版本与可得时间；未知尺寸或时长为 null。 |
| `visual_embeddings` / `subtitles` | 向量/字幕的模型版本、权重指纹、抽取配置、实际样本时刻和可得时间；未编码/未转写为 null。自动字幕还须保留方法及误差未知状态。 |
| `preexisting_comments` | 截止前可见的本帖评论范围及完整性；外部评论数、`external_author_unique_count`、实质评论、问题、self 评论分别统计，不能用总回复数代替外部作者数。 |
| `missing_masks` / `privacy` | 每个缺失输入的原因及范围；原文、媒体原件、评论身份、截图和向量缓存留私有 runs。公开仅经复核的聚合数据与已授权公共链接，不公开身份名单。 |

评论的实质/提问标签可以重叠，不能把它们相加还原总评论。不同回复来自同一作者时，独立外部作者只计一次；身份无法稳定去重就给 observed 范围或 null，不能伪称真实唯一人数。评论正文是否有帮助是单独的内容评估，短“OK”不自动等于实质技术反馈。

## 发布前与发布后是两个任务

**Prepublish** 只用已存在的草稿正文、媒体和已知发布计划；本帖未来计数、未来评论与未来粉丝结果必须排除。若回复既有讨论，可以单列已存在父帖上下文，但不可装成尚未发布帖子的受众反馈。计划时段不是实际发布时间。

**Postpublish** 可增加截止前实际获得的计数与已有评论；每一输入必须满足 `available_at <= prediction_at`，并保留真实 captured_at。事后补读的评论、最终曝光、后来的终稿/字幕及 24/72 小时结果不能回填早期特征。未来目标作为 `target` 标签单独存储，只在标签实际可得后评价，不进入训练时的预测输入。

## 第二目标：文案由人写、AI 生成，还是混写

`content_origin` 只描述指定版本的**正文文本来源**；图片、视频来源另记，不能由正文标签概括。后台是手动还是自动发布不属于本任务，有限正文输入也不能证明后台发布方式。

| 标签 | 按预先固定的 `label_policy` 判定 |
| --- | --- |
| `human_written` | 有证据支持正文实质内容由人撰写，未使用生成式 AI 撰写或改写；普通拼写检查与排版按固定规则处理。 |
| `ai_generated` | 有证据支持正文实质内容由生成式 AI 产生，人只作选择、排版等不改变实质内容的处理。 |
| `mixed` | 人与生成式 AI 均参与实质撰写或改写，包括人改 AI 稿、AI 改人稿；不是“恰好 50% AI”。 |
| `unknown` | 缺可靠来源证据、证据矛盾或正文范围不能确定；不是“人写”的负例，也不是可随意补造的第四个来源类别。 |

标签证据只接受与该帖版本对应的作者公开披露，或有权取得且能说明生成/编辑过程的记录；发帖日志仅显示点击方式时不能证明文案来源。保存 `scope`、`label_policy`、证据类型/范围、可靠程度及 `label_available_at`，把作者自述与可核对记录区分。引用、翻译、AI 润色和短文本的边界先定规则，证据不足保留 unknown；凭“像 AI”、另一检测器输出或蓝 V 标记不能造真值。未知样本仍可参与有标签的热度任务，但来源监督损失须屏蔽，也不计来源准确率分母。

未来 `origin_prediction` 可以单独给出 `human_written` / `ai_generated` / `mixed` 三项概率、模型/校准版本、预测时刻、判定及拒判原因；概率有输出时三项合计为 1，未训练或无法计算时为 null。它们是特定训练与测试范围下的模型估计，不是后台真相；`p(ai_generated)` 也不是正文中 AI 字符占比。样本太短、超出训练语言/题材或低置信度时可输出 `decision=unknown`，不强行二选一。来源概率不等于内容质量，不进入高质量蓝 V 的既定判定。跨题材、未知生成模型与改写会影响检测表现，不能直接移植论文分数到 X 帖子；这些限制可参照 [RAID 基准](https://aclanthology.org/2024.acl-long.674/) 和 [检测稳健性研究](https://arxiv.org/abs/2303.11156)。

### 与热度一起训练，怎样避免偷看答案

可研究共享正文编码、分开输出热度和来源；来源标签只用于该任务的监督损失，不能作为任一预测输入。即使事后才取得来源标签，训练也只能使用训练截止前已取得的标签，不能修改当年的输入或预测。来源证据中的直接答案也不混入正文编码。

若把来源概率作为热度特征，热度训练样本必须使用**按时间产生的折外预测**：来源模型和校准器只用更早且当时标签已可得的训练数据，对未参与拟合的后续帖子产生概率。同帖、编辑版本、重复文案不得跨折，未来留出数据不参与阈值或校准选择；历史概率保留生成模型、训练截止、`available_at` 和原始预测，不用未来模型结果回填。发布前/发布后同样满足输入的时间边界；没有合格历史概率就用 null 与缺失标记。

严格跨帖验收调用 `auxiliary_features(record, strict_cross_post=True)`，或 CLI `--auxiliary --strict-cross-post`。目标 `post` 和每条 `provenance.training_groups` 提供 `content_group_id`：同原帖的版本链、重复正文/素材、同一具体事件或热点及其衍生内容共用组 ID；有任一连接就合并成同组，可跨平台。不能把“AI 工具”等宽泛题材当成一组，也不能用不同 native ID 冒充内容独立。先按**首次真实发布时间**切分，再从训练侧移除与留出组相交的成员，不把未来帖子移回训练。

上游须在训练和查看留出误差前冻结分组依据及清单。严格路径要求目标首次 `published_at` 和所有组 ID 已知，缺失/null/显式 unknown 即拒判；验收器不猜素材关系或准确发布时间。不同 native ID 同组会拒绝辅助特征，时间、输入/标签可得性规则仍同时适用。旧调用继续兼容，但缺组数据的 `strict_cross_post_eligible=false`，不算通过严格验收。输出只声明组交集检查，`*_lineage_verified` 仍为 false；没有实际跨帖训练、来源检测效果或认证 Home 模型结果，当前 n=1 前瞻记录也不因此升级。

### 分开评价来源识别与热度收益

- **判对什么：** 在有来源证据的留出帖子上报告三类混淆矩阵、每类数量/比例，以及逐类一对其余的 PR-AUC；注明曲线积分还是 average precision，不能混称，类别缺失时对应分数为 null。unknown 标签的数量和排除原因单列。
- **概率是否可信：** 报告 Brier 概率误差，并注明多类缩放方式；ECE 比较各概率分箱的置信度与实际命中率，同时给分箱规则、各箱样本数和可靠性图，小样本/换分箱不能伪装成稳定校准。两者不证明单帖来源。参见 [Brier 官方说明](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.brier_score_loss.html) 和 [概率校准研究](https://proceedings.mlr.press/v70/guo17a.html)。
- **拒判了多少：** 分别报告 `label_coverage=有可靠标签数/采集帖子数` 和 `decision_coverage=作出三类判定数/适用预测帖子数`。再给有标签子集的判定覆盖率及已判样本误差，拒判不是预测正确；阈值在验证集固定，测试集只评估。覆盖与误差的取舍见 [选择性分类研究](https://papers.nips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html)。
- **能否换场景：** 按语言、题材、长度、作者、已知生成模型和混写/改写程度分层，保留作者与相似文案分组的时间留出；小分层给样本数，不能把未知来源当 AI 或把混写强塞进二分类。公开披露样本可能不同于全部帖子，报告范围偏差。
- **是否帮助热度：** 同一时间留出、窗口、输入与预算比较“只预测热度”“热度＋来源辅助任务”“热度＋时间折外来源概率”。来源准确率和热度误差分别报告，任务损失权重只用训练/验证数据选；共享模型可能互相拖累，不保证热度或涨粉改善。当前没有这些多任务消融结果。

## 媒体怎么进入模型

原件在私有目录保留；平台上传版本与本地版本不一致时分别记来源。先锁定可复现的抽样策略，例如每段视频按固定等间隔取帧、固定最大帧数和缩放配置，记录请求时间与解码后实际时间。字幕/音频使用同一冻结配置；画面中的文字可另提 OCR，不能与正文混成未注明来源的一串文字。不得看完热度再挑“最能解释成功”的帧。

未来可以缓存已有预训练文本/视觉/音频编码器的输出，冻结权重，只训练约 **1 万–5 万个可训练参数**的融合层。这是设计预算，不是已经训练的模型规模或效果；冻结编码器本身可能远大于该预算，也未被当前实现使用。避免从零训练大编码器。缓存须绑定内容版本、权重、预处理与抽样指纹，缺媒体用 missing mask，不用全零向量冒充已编码。

验证时分别比较：时间计数基线、加正文、加媒体、加截止前评论、完整融合；保持相同预测窗口与样本。整条帖子及其版本/评论不跨训练与测试集，按帖子或日期留出并做向未来的时间验证；所有拟合、编码器选择及阈值在训练部分确定。重复刷新不扩充独立训练样本。模型尚无这些消融或跨帖验证结果。

## 轻量 schema 草案与虚构例子

下面仅约束外层结构，不能替代逐字段来源、平台映射及时间比较；这些仍需运行时校验。JSON Schema 的结构/format 约定见 [官方 2020-12 验证说明](https://json-schema.org/draft/2020-12/json-schema-validation)。该草案尚未接入脚本。

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

**全部虚构，不是账号实测或已存媒体。** `example.com`、时间、计数及路径仅示范契约；这里的媒体特征尚未抽取。

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

## 通用测量，不等于通用推荐模型

输入与时间规则可以共用；平台适配器须保留原生指标定义、单位、来源及版本，先确认实际可采集能力。当前已有 X 指标读取与统计路径，其他平台适配器尚未验证。不得把视频播放量当成展示量、把事件数当独立用户、或把不同观看门槛的播放计数合并训练。

badge、身份稳定性、high-quality rubric 和 follower/订阅含义按平台单独定义；X blue 不自动映射到其他平台认证或付费标记。推荐算法、源模型和校准也分别验证，本说明不声称掌握其他平台当前算法。

数据足够时，可研究 `platform_id` embedding 或平台单独微调；样本少时先按平台分别做简单基线与校准，不靠共享字段假装已跨平台泛化。展示/互动计数可能过度离散，模型须检查计数分布，并对齐 60 分钟/24 小时/72 小时等目标窗口。评论采样不完整、内容编辑、并行发布和流量来源是混杂因素；主页粉丝差集仍不提供单帖归因。任何平台的来源计数、模型预测与已证实增长都必须分别报告。
