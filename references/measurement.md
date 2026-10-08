# 实验与测量

## 质量判定

仅依据公开职业/内容证据，不按语言、国籍、性别或政治/宗教信仰筛选。blue 是范围条件，不是质量得分。对新增者读简介与至少 3 条近期原创内容，再给三个布尔项：

1. `relevant`：公开内容与本账号事先确定的主题/目标受众相符。
2. `original`：能看到原创方法、作品、案例或独立观点，而不是仅有转贴/互关口号。
3. `substantive`：公开回复/讨论含实质信息，存在可以继续交流的话题。

三项均 true 且附公开证据 URL 才标 `high`。明确不满足任一项标 `not_high`，没读够、账号受保护或没看到证据标 `unknown`。这是严格的运营评分，不宣称鉴定真伪或专业能力。标准按账号定位调整一次并记录，跨轮保持不变；不为涨比例改变标准。

## 快照格式

`python3 scripts/measure.py before.json after.json`。示例在 `examples/`，全部是虚构数据。真实记录放忽略的 `runs/`。

```json
{
  "account": "example_owner",
  "observed_at": "2026-10-08T04:00:00+08:00",
  "scope": "all_followers",
  "complete": true,
  "evidence": "完整列表采集或获授权的数据导出路径",
  "total_followers": 1,
  "followers": [{
    "id": "123456789",
    "handle": "example_follower",
    "badge": "blue",
    "quality": {
      "status": "high",
      "relevant": true, "original": true, "substantive": true,
      "evidence": ["https://x.com/example_follower/status/123"]
    }
  }],
  "posts": {
    "https://x.com/example_owner/status/123": {
      "replies": 0, "likes": 0, "reposts": 0,
      "bookmarks": null, "views": 10
    }
  }
}
```

scope 可为 `all_followers` 或 `verified_followers`。complete=true 必须有完整性证据；只有全粉丝完整快照可以排除老粉新认证。全粉丝完整快照的 `total_followers` 必须等于名单长度；分页采集中总数波动应重采或标 partial。用户 ID 可获授权读取时优先记录；只有 handle 时有改名歧义，工具不把它算确认新增。

时区明确、账号一致、after 时间较晚。每个 id/handle 唯一，不能把同一账号多次加载计成多个粉丝。只看蓝 V 列表与全粉丝列表不可混比。

分页采集记录 `collection_started_at`（开始时间）和 `observed_at`（结束时间），均须带时区；开始不能晚于结束。如果后轮采集开始早于前轮结束，两轮窗口重叠，工具只报告观察变化，不输出确认新增。没有开始时间时沿用单时点快照约定，不代表工具已核实采集全过程。ID 须为无前导零的正整数 ASCII 字符串，避免 `123` 和 `0123` 被当成不同身份。

每个帖子的计数可单独附 `observed_at`，不能晚于快照结束时间；省略时按快照结束时间计算。采集复用旧计数必须保留其真实采集时间。X、Twitter 域名、用户名变更和查询参数不改变 status ID；工具按 status ID 对齐帖子。同一快照中重复放入同一帖子的不同链接会被拒绝，不能重复累加。

## 输出解释

- confirmed_new_blue：在两次完整全粉丝、全稳定 ID 快照中，新增身份且 after 为 blue 的人数。
- observed_blue_arrivals：新观察到的蓝 V 身份数。部分列表、认证列表或 handle 匹配时只用这项，不声称确认新增。
- existing_became_blue：同一已存在粉丝从非 blue 变 blue，单列而不算新增粉丝。
- badge=unknown 不是明确非蓝 V；unknown→blue 或 blue→unknown 记为 unresolved_existing_badge_transitions，不当作新认证或取消认证。只要任一快照有未知认证状态，blue_membership_net 为 null，避免把漏读徽章当作蓝 V 总量变化。
- observed_blue_departures：前轮 blue 后轮名单没出现；部分列表不证明实际取关。
- quality_share：新增/观察到的新 blue 中 high/N；unknown 留分母，另输出可能区间 high/N 至 (high+unknown)/N。N=0 为 null。未知者不能伪装成“已确认低质”。
- quality_share_status 为 lower_bound 表示仍有未知者，quality_share 只是已知高质占总数的下界；全部判定后为 complete，没有新增时为 undefined。quality_classification_complete 单独记录是否已判定完毕，不用一个 0% 隐藏待判定情况。
- quality_share_scope 固定为 captured_blue_arrival_events，quality_share_denominator_count 是实际捕获差集中的蓝 V 人数。quality_share_status=complete 只代表这些人的分类已完成，不代表名单覆盖完整；例如部分名单捕获到两个高质，样本比例可为 100%，全窗口比例仍未知。
- coverage_complete 描述两次所选 scope 名单完整且未发现采集重叠，不代替稳定身份核验。full_window_quality_share 只有完整全粉丝、全稳定 ID、两次采集起止时间齐备且不重叠、徽章全已知、新蓝 V 质量全判定并且人数大于 0 时才给出；否则为 null。它描述快照之间新增并仍在后快照中的蓝 V 身份差集，不包括窗口内关注后又离开的所有瞬时事件；完整 handle 或认证名单也不能取得确认新增比例。
- quality_share_wilson95：对已确认新增、且全部已完成质量判定的样本给 Wilson 区间，反映小样本不确定性；不是因果置信度。
- 同一帖子两次公开计数相减；计数不可见、之前没采集、计数下降或帖子缺失时增量为 null，保留原因。新帖从发布时确认的 0 计数开始测，不假造之前的基线。
- post_feedback 中的 observation_window 保留该帖子计数的实际起止时间。后次计数采集时间没有推进时，即使数值变大也不输出增量，需要先核对记录；各帖子窗口可能不同，不能直接说所有增量来自同一轮行动。
- 实验期存在其他人/自动任务运营时记录混杂因素。仅看粉丝先后变化不能给单帖因果归因。

实际日志包括时间、action type、target URL、策略版本、变量、attempted/confirmed/failed、证据与固定窗口。发布需记录 permalink；关注需重新打开检查；转贴/点赞需检查持久状态。初始界面按钮不等于保存。

## 优化与停止

每轮对比新增 blue 数 N、高质量 H、H/N 与行动预算、观察时间。报告两个指标同时变化，保留帕累托更好的方案（至少一个提高且另一个不下降）；冲突时优先保护受众匹配与原创交流，再试另一变量。不把 1 人、5 分钟的变化说成策略胜出。没有新增时比例未定义，应调整话题/内容价值/分发入口，不通过随便判低质或减分母制造提高。

可见负反馈、重复状态回退或平台提示限制时，停止对应动作，记录风险，不“优化”到规避限制。未设调度器不得把 24/72 小时窗口标完成。

## 编辑版本

本轮浏览器实测中，编辑技术帖后 X 展示了不同的最新版本永久链接。保留首次发布链接、原始发布时刻、最新版本链接、编辑核验时刻与各版本独立计数；同一帖子编辑不算第二条原创行动。固定观察窗口仍按最初发布时间记录，同时注明编辑这一干扰因素，不为提高数字重新起算。未测得精确编辑时间就保留页面时间显示及核验时间，不补造秒数。发布含代码或文件名的内容时，重新打开检查平台是否将本地文件名误识别成站外链接；必要时编辑说明并复核。

互动对象也可能在读取后编辑：旧页面明确出现 “There’s a new version of this post.” 和 “See the latest post” 时，保留旧链接，打开 UI 给出的最新版本永久链接并重读正文，再执行和核验互动。旧版点赞或回复点击没有保存、没有出现回复框时只记录 attempted，不记成功或仅据此判平台限制；没有版本提示也不臆测发生了编辑。旧/新版本仍是同一原帖，保留首次发布观察窗口及各版本独立计数，不把版本计数合并或将编辑算作新增原创。
