# 先复用真实数据，再训练小模型

[English](data-reuse.en.md) · [模型输入契约](model-inputs.md) · [统计方法](growth-statistics.md)

先复用已有计数、正文和公开研究资源，再补真正缺失的固定窗口观察。数据可读、样本已取得、全量下载、特征已编码、训练完成和效果验证是不同状态；以下不把它们合并。

## X：可见列表已读，完整导出未完成

已实际浏览 [X owner Content 列表](https://x.com/i/account_analytics/content)，可见 Date、Impressions、Likes、Replies、Reposts 与截断正文。**2026-10-08 03:48:02.373 → 03:51:37.900 UTC** 的 6 份真实快照提取出 **99 个不同帖子、146 条采集记录，0 解析失败**。重复刷新不是独立训练样本；99 也不是已具备完整标签的训练样本数。[X 指标说明](https://business.x.com/help/tweet-activity-dashboard)。

界面日历日期覆盖 **2026-07-17 → 2026-10-08**，时区未知，`published_at` 全为 null；文案来源标签全为 unknown，统计口径保留 `unknown_report_window`。采样覆盖仍是 partial，不称完整三个月数据集。每行保留原生字段、帖子链接、筛选范围与实际采集时间；私有记录在忽略的 `runs/`，不公开原文或身份清单。

CSV 下载事件曾超时，没有成功文件证据；浏览器策略禁止访问下载记录，因此改用可见列表，不绕过限制，也不声称完整三个月导出完成。

历史帖的当前可见计数，只能作为**本次观察时点、该界面口径的标签**；口径未核实不能自动叫终身累计展示。即使另行确认累计值，也不能由当前总数补造过去的 1 小时或 24 小时快照，相应目标仍留 null。列表日期不自动提供精确发布秒数；截断正文保留截断标记，不能冒充全文。正文、编辑版本、评论、媒体和计数各自记录真实 `captured_at` 与 `available_at`，晚采集内容不回填早期预测输入。

## TPIC2017：四份元数据只取了小样本

作者的 [TPIC2017 仓库](https://github.com/social-media-prediction/TPIC2017) 与 [项目页](https://social-media-prediction.github.io/TPIC2017/) 指向四个 ZIP。本轮匿名 HTTP Range 读取每个 ZIP 开头的 65,536 bytes，在内存中解压首个文本条目的前 100 行；四份均返回 HTTP 206，总共读取 264,192 bytes（包含此前四次 512-byte 探测）。**没有完整 ZIP 下载，也没有获取图片。** 复核结论记录为 **2026-10-08 03:49:35 UTC**；精确 HTTP 获取时刻未留存，不能把该时钟冒充下载时间。

| 文本条目 | 实际读到的表头 |
| --- | --- |
| `USER_META.txt` | `pid uid commentcount haspeople titlelen deslen tagcount avgview groupcount avgmembercount` |
| `LABELS.txt` | `pid uid logviews` |
| `TIMEFLAG.txt` | `pid uid year month day hour_index` |
| `PHOTOURL.txt` | `pid uid url` |

`haspeople` 是图片是否有人，不能作为人写、AI 生成或混写的文案标签；标题长度也不是标题全文，图片 URL 不证明已取图或已编码。热度标签是 [原论文](https://www.ijcai.org/proceedings/2017/0427.pdf) 的 `log2(总 views / 发布后天数) + 1`，只有静态单值；没有原始 views、分母天数、抓取时刻或重复的 1h/24h 观察，不能还原这些时长的增长曲线。

`TIMEFLAG` 只有年月日与四小时档，不能称精确发布时间。已读样本含 2001–2006 年日期，与仓库所述 36 个月覆盖不能直接对齐，完整时间覆盖仍未核验。它是 Flickr 研究数据，指标不能直接当作 X impressions。作者页面有引用要求，但未找到明确的数据或图片许可；匿名可下载不证明获准公开镜像，先保留来源与许可缺口。

## RAID：四条来源样本已读，未训练

[RAID 作者仓库](https://github.com/liamdugan/raid) 直接关联 [作者数据卡](https://huggingface.co/datasets/liamdugan/raid)。`train` / `extra` 以 `model == 'human'` 表示人类原文，其余命名模型表示生成来源；公开 `test` 标签隐藏。实际 11 字段为 `id, adv_source_id, source_id, model, decoding, repetition_penalty, attack, domain, title, prompt, generation`，没有另一个数值 label 列。

**2026-10-08 03:52:40.357756 → 03:52:42.606995 UTC** 的两次匿名 HTTP 200 请求读取 [2 条 human](https://datasets-server.huggingface.co/rows?dataset=liamdugan%2Fraid&config=raid&split=train&offset=0&length=2) 与 [2 条 mpt](https://datasets-server.huggingface.co/rows?dataset=liamdugan%2Fraid&config=raid&split=train&offset=100000&length=2)，该轮共 9,769 bytes。它们只是 partial 字段／样本核验，未全量下载、训练或跑基准；mpt 样本带 `perplexity_misspelling` 对抗，不能冒充干净平衡测试集。

数据语言为 en/cs/de，另有代码；没有中文声明。文章与 Reddit 数据不证明适用于 X 短帖，也不提供本契约审定的混写标签。来源任务输入只用 `generation` 正文，不能拿 `model`、prompt 缺失、attack、decoding 等泄漏答案的元信息当特征；用 `source_id` 连接原文与变体，辅助追溯 `adv_source_id`，同源变体不可跨训练／测试。

[代码 LICENSE](https://github.com/liamdugan/raid/blob/main/LICENSE) 为 MIT，[数据卡](https://huggingface.co/datasets/liamdugan/raid/blob/main/README.md) 独立声明 `license: mit`；这不等于逐项核清每段上游新闻、书籍等原文的权利链。

## HC3：中文 QA 小样本已读

[HC3 作者仓库](https://github.com/Hello-SimpleAI/chatgpt-comparison-detection) 直接关联 [HC3-Chinese](https://huggingface.co/datasets/Hello-SimpleAI/HC3-Chinese)。**2026-10-08 03:54:02.415128 → 03:54:04.533263 UTC** 匿名 Range 读取 [open_qa.jsonl](https://huggingface.co/datasets/Hello-SimpleAI/HC3-Chinese/resolve/main/open_qa.jsonl) 开头 8,192 bytes，HTTP 206，完整文件声明大小为 6,529,129 bytes。首个完整对象只有 `question`、`human_answers`、`chatgpt_answers`，分别提供人类与早期 ChatGPT 答案来源，可按规则派生正文标签；没有数值 label 或混写标签。

这仍是样本／格式核验，未大文件下载或训练。中文 QA 不等于 X 短帖，也不验证 2026 年新模型的检测效果。[作者数据卡](https://huggingface.co/datasets/Hello-SimpleAI/HC3-Chinese/blob/main/README.md) 声明 CC-BY-SA-4.0，并要求遵守更严格的原来源许可；`open_qa` 原来源为 MIT，不等于 HC3 发布输出为 MIT。

## SEISMIC：准备阶段记录，后续训练见下文

依据作者的 [SEISMIC 项目页](https://snap.stanford.edu/seismic/) 与 [论文](https://snap.stanford.edu/seismic/seismic.pdf)，本轮已完整取得两份源文件：**2026-10-08 09:53:23.757982 → 09:57:36.848653 UTC**，均为 HTTP 200，实际合计 **307,455,420 bytes**。截至 **10:12:21.530980 UTC** 的准备核验记录，派生表已完成，新训练尚未开始；下载可访问不等于获得公开数据镜像许可。原始 ID、CSV、原文与个体信息留在私有材料中，这里只发布聚合状态与官方来源。

最终身份审计只接受规范 ASCII 十进制源 ID，拒绝猜测还原低精度科学计数法 ID：**139 段非规范 ID** 加上 **4 个重复 ID 对应的全部 8 段**，共 **147 段隔离**。最终为 **165,929 个唯一、未重复的源帖级联、331,858 条派生行**；早期仅按原始字符串处理的候选已退役，不作为最终规模或训练表。核验覆盖全部规范源身份与同级联成对窗口，并将 **1,000 个级联**的派生结果与源事件交叉检查。

每个级联在 **15 分钟 / 60 分钟**各准备一行：只用截止秒数及截至该时点的转发数量、首末事件时间，目标为**截止之后至帖龄 24 小时的新增转发**（`cutoff < t <= 86400`）；未来事件和目标累计数不作输入。同一源帖的两行必须在同一划分，不能算两个独立帖子；不同源 ID 也不能证明作者或热点独立，作者、正文重复与热点分组仍未知。

| 严格时间划分 | 源帖级联数（每个有两档窗口） |
| --- | ---: |
| 训练候选 | 59,565 |
| 标签成熟重叠隔离 | 12,193 |
| 后续评估候选 | 94,171 |

划分沿用历史相对时间的前 7 日／后 8 日，并额外清除 24 小时标签到第 7 日之后才成熟的训练候选；不是按本次下载时间造历史可得时刻。这些是准备好的候选划分，还没有模型拟合、验证调参或效果比较。

源语料为 **2011 年英文、无 hashtag**，作者说明按未来至少 50 次转发筛选，存在成功样本选择偏差。排除原帖事件后，实测全源 **1,280 段各有 49 次转发**；原因未核验。发布文件的最大事件时间为 **604,799 秒，不足 7 天**，不能证明论文所述 14 天完整随访；这两项异常描述全源，不冒充最终表所有行的属性。最终表仍保留截止时零转发的 **1,743 个 15 分钟案例、720 个 60 分钟案例**（包括隔离划分），但它们在 24 小时内都有转发，不能验证一般零流量帖子；截止后新增转发为 0 的目标也未删除。没有 views、认证首页展示、正文或文案来源标签，也未核验迁移到当前中文账号的能力。

## 热度与来源分开监督

热度与文案来源是两个标签任务。热度保留平台、指标、帖龄与观察窗口；来源只描述指定版本的正文，使用作者披露或经授权的生成／修订记录，并保留 `label_policy`、证据及 `label_available_at`。人写、AI 生成、混写按预先固定规则判定，证据不足为 unknown，不把检测器猜测、账号徽章、发布方式或 TPIC 的 `haspeople` 变成真值。来源未知样本仍可有真实热度标签，但不参与来源监督损失。[来源标签规则](model-inputs.md#第二目标文案由人写ai-生成还是混写)。

## 复用与验证顺序

1. 整理实际取得的样本清单、字段口径、许可、版本与时间；不完整的覆盖范围明确标记，原文、媒体、身份和缓存留在私有 `runs/`。
2. 先做时间／计数基线。复用预训练编码器时固定权重和预处理，缓存绑定内容版本、权重指纹与实际可得时刻；只训练轻量头。编码器缓存和语义训练是后续步骤，不是目前已完成的功能。
3. 分别准备热度与有真实来源证据的人写／AI／混写标签。来源真值不作为预测输入；若来源预测辅助热度，只用时间外折预测，不能将未来分类器输出回填过去。
4. 按帖子、版本、重复文本／媒体、会话与作者分组，并向未来按时间留出；相关内容不跨训练与测试。两个任务沿用相同隔离：归一化参数只在训练集拟合，阈值、特征与超参数用验证集选择，测试集只用于最终评估。
5. 分别报告热度误差、来源分类／校准／拒判、覆盖缺口和跨语言迁移；比较简单基线与新增特征。虚构示例只验证格式，不冒充真实训练、真实预测或涨粉效果。

此前已发布的浏览原型是两帖分别拟合的 [单帖时间计数曲线](https://huggingface.co/LIghtJUNction/RISE-heat-baseline)。文案来源分类目标尚未训练；本页不声称新的语义或多任务模型已泛化，或能带来新增高质粉丝。[已测结果](../README.md#统计与预测用真实误差检验模型)。

## 后续训练状态：SEISMIC retweet-v2 已完成

**2026-10-08 10:29:36.524651 UTC** 的实验记录确认后续训练完成；上文 **10:12:21.530980 UTC** 的“尚未训练”仍是当时的准备状态。新实验与已发布的两帖 views 曲线分开；10:29 当时尚未发布新模型，随后 HF 发布与匿名验证见下节。GitHub 的结果数据仅保留[聚合评价](../public/retweet-benchmark.json)与[结果图表](../README.md#统计与预测用真实误差检验模型)，不公开原始源 ID、CSV 或逐行预测。

每档小型 MLP 实际有 **241 个参数，双档共 482 个**，使用 **1 个 CPU 线程**。实际五项输入为 `log1p_observed`、`first_fraction`、`last_fraction`、`cold_indicator`、`cutoff_fraction_24h`，仅使用截止前事件。目标仍是 **15 分钟／60 分钟截止后至帖龄 24 小时的新增转帖**；不是累计 views、未来一小时曝光、认证首页展示或文案来源。

实际采用上文的 **165,929 个规范未重复级联、331,858 成对行**与每档 **59,565 训练／12,193 隔离／94,171 测试**时间划分。外层训练内部再按时间划为 **23,779 拟合／11,964 标签成熟重叠隔离／23,822 验证**；只用验证选择 **15 分钟 14 轮、60 分钟 10 轮**，随后完整外层训练重拟合，外层测试仅评估 **一次**。同帖两档不能算独立样本；作者、重复正文与热点组仍未知，不声称已实现这些组的隔离。

五模型的 15 分钟／60 分钟测试 MAE 分别为：零新增 **109.18／76.34**，训练目标中位数常量 **77.85／59.33**，早期恒定速率 **7,000.12／2,402.23**，训练计数分桶中位数 **63.18／47.08**，小型 MLP **60.40／45.71**。相比分桶的 **4.41%／2.90%** 总体下降仅为描述结果，置信区间未知。**15 分钟零转帖子组 n=881 的 MLP MAE 61.98825 高于分桶 61.72304；60 分钟全样本 p90 绝对误差 105.18341 也高于分桶 105.00000。** 不能宣称全面胜出。

本次仍受 **2011 年英文无 hashtag、未来成功选择偏差、未知作者／重复正文／热点分组、未核清数据许可**限制，不发布原数据镜像。没有当前账号 views、高质量获粉、认证首页展示或来源分类的验证；跨语言迁移与统计优越性仍未知。

## 复现准备与训练

新转帖模型已经发布到 [Hugging Face](https://huggingface.co/LIghtJUNction/RISE-retweet-baseline)，固定版本 `1282fc5e88e64073bf680b0dda21663f19b73c69`，与旧 `RISE-heat-baseline` 分开。匿名下载的 7 份文件全部匹配 SHA，合成推理通过；[公开发布核验](../public/hf-retweet-release.json)。许可证仅覆盖本项目代码及数值参数，不重新许可来源数据。

在本仓库使用 Python 3.11+，并从官方发行渠道安装 PyTorch。真实训练环境为 Python 3.14.7、PyTorch 2.14.0、单 CPU 线程；不同版本和硬件不保证逐位相同。下面会从作者网站下载约 307 MB，并在本地的新目录准备数据；不上传数据。输出必须为新／空目录，训练 run 不能覆盖。

```sh
python3 scripts/prepare_retweets.py --output runs/seismic-local
python3 scripts/retweet_benchmark.py plan --input runs/seismic-local/retweet-features.csv --provenance runs/seismic-local/prepared-summary.json --output runs/retweet-local --expected-input-sha256 f17d46503f68474ef777d59e4398e6c9faba9eb5ee9ed67238b861ae3768763b
python3 scripts/retweet_benchmark.py train --plan runs/retweet-local/plan.json
```

`plan` 只做来源、输入、时间划分和配置核验，不训练。`train` 只消费冻结计划一次，训练与基线冻结后才评估最终测试集。本轮准备脚本还通过了一次实际无网复现，整表 SHA 与训练输入精确一致，保留原下载时间，逐帖成对核验及 1,000 个源级联标签交叉核验通过。没有为这个复现重新训练或重看测试选参数。
