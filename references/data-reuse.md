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

## 热度与来源分开监督

热度与文案来源是两个标签任务。热度保留平台、指标、帖龄与观察窗口；来源只描述指定版本的正文，使用作者披露或经授权的生成／修订记录，并保留 `label_policy`、证据及 `label_available_at`。人写、AI 生成、混写按预先固定规则判定，证据不足为 unknown，不把检测器猜测、账号徽章、发布方式或 TPIC 的 `haspeople` 变成真值。来源未知样本仍可有真实热度标签，但不参与来源监督损失。[来源标签规则](model-inputs.md#第二目标文案由人写ai-生成还是混写)。

## 复用与验证顺序

1. 整理实际取得的样本清单、字段口径、许可、版本与时间；不完整的覆盖范围明确标记，原文、媒体、身份和缓存留在私有 `runs/`。
2. 先做时间／计数基线。复用预训练编码器时固定权重和预处理，缓存绑定内容版本、权重指纹与实际可得时刻；只训练轻量头。编码器缓存和语义训练是后续步骤，不是目前已完成的功能。
3. 分别准备热度与有真实来源证据的人写／AI／混写标签。来源真值不作为预测输入；若来源预测辅助热度，只用时间外折预测，不能将未来分类器输出回填过去。
4. 按帖子、版本、重复文本／媒体、会话与作者分组，并向未来按时间留出；相关内容不跨训练与测试。两个任务沿用相同隔离：归一化参数只在训练集拟合，阈值、特征与超参数用验证集选择，测试集只用于最终评估。
5. 分别报告热度误差、来源分类／校准／拒判、覆盖缺口和跨语言迁移；比较简单基线与新增特征。虚构示例只验证格式，不冒充真实训练、真实预测或涨粉效果。

现有真实训练仍是已发布的 [单帖时间计数曲线](https://huggingface.co/LIghtJUNction/RISE-heat-baseline)。文案来源分类目标尚未训练；本页不声称新的语义或多任务模型已泛化，或能带来新增高质粉丝。[已测结果](../README.md#统计与预测用真实误差检验模型)。
